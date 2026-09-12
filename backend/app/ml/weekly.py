"""M15: the week by week rollup.

Every other model in this package answers a question about a session or about
a whole history. Nobody was answering "how was last week", which is the unit a
patient and a clinician actually talk in, so this bucket the sessions into ISO
weeks and describes the shape of them.

Two decisions worth stating, because both are easy to get wrong quietly.

**Weeks are ISO weeks off `started_at`, not a rolling seven days.** A rolling
window slices through a cadence of roughly four sessions a week and produces
buckets that jitter as the calendar moves underneath them, so the same history
reads differently on Tuesday than it did on Monday. ISO weeks are stable, and
they are what "last week" means to the person reading.

**A week with no sessions is emitted, not skipped.** A three week silence is
the single most informative thing a rollup can show, and dropping empty
buckets would render it as nothing at all. The same reasoning applies to a
prescribed session that was never completed: it is counted, then excluded from
every measure.

The uncertainty here is two different quantities and they are treated
differently. Within a week, the interval is the observed spread of the
sessions themselves, exactly as app/export/report.py:_spread does it, because
those sessions are not a sample drawn from a population. Across weeks, the
change genuinely is an estimate, so it gets a bootstrap interval.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import TYPE_CHECKING, Iterable

import numpy as np

from app.clinical_gate import GATED_METRICS, GRIP, allows_kilograms
from app.ml.explain import Explanation, Factor, Interval, bootstrap_interval

if TYPE_CHECKING:  # pragma: no cover
    from app.models import Session

# Below this many complete weeks there is nothing to compare against and no
# trend worth drawing. Two is the minimum that makes "change" mean anything.
MIN_WEEKS = 2

# How many resamples build the interval on a cross week change.
N_BOOTSTRAP = 200

# The measures summarized per week, as (attribute, unit). Kept as data so the
# gate reads from one list rather than from a chain of if statements.
WEEK_MEASURES: tuple[tuple[str, str], ...] = (
    ("mean_mvc", "%"),
    ("strength_kg", "kg"),
    ("mean_rep_quality", ""),
)


def _aware(moment: datetime) -> datetime:
    """Coerce a timestamp to UTC.

    Seeded rows are timezone aware and live rows are too, but rows written
    before that was true are not, and comparing the two raises. Worse, the
    failure mode for bucketing is silent: a naive timestamp still has an
    isocalendar, so it lands in a plausible looking week rather than raising.
    """
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)


def _completed(session: "Session") -> bool:
    """A prescribed session that was never done has a null rep count.

    The seeder writes these deliberately so a missed session is data rather
    than an absence of data. They count toward adherence and toward nothing
    else.
    """
    return session.rep_count is not None


def _spread(values: list[float], unit: str) -> Interval:
    """Mean with the observed range around it.

    Deliberately the range rather than a confidence interval, matching
    app/export/report.py. The sessions in a week are the population, not a
    sample from one, so what the reader wants is the spread actually recorded.
    A single session week collapses to a zero width interval, which is honest:
    there was one value and this was it.
    """
    point = sum(values) / len(values)

    # The bounds have to contain the point, and floating point arithmetic does
    # not guarantee it: the mean of three identical 0.8 values comes out at
    # 0.8000000000000002, just above the max. Widening rather than rejecting
    # matches what bootstrap_interval already does with a skewed resample.
    return Interval(
        point=point,
        lower=min(min(values), point),
        upper=max(max(values), point),
        unit=unit,
    )


@dataclass(frozen=True)
class WeekBucket:
    """One ISO week of a patient's history."""

    iso_year: int
    iso_week: int
    # The Monday, so a chart has a real date axis rather than a week label.
    start_date: date
    session_count: int
    prescribed_count: int
    total_reps: int
    is_partial: bool
    mean_mvc: Interval | None = None
    # Grip only. None on any week whose sessions were all another muscle.
    strength_kg: Interval | None = None
    mean_rep_quality: Interval | None = None

    @property
    def completion_rate(self) -> float:
        """Completed over prescribed. Zero prescribed reads as complete."""
        if self.prescribed_count == 0:
            return 1.0
        return self.session_count / self.prescribed_count

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "iso_year": self.iso_year,
            "iso_week": self.iso_week,
            "start_date": self.start_date.isoformat(),
            "session_count": self.session_count,
            "prescribed_count": self.prescribed_count,
            "total_reps": self.total_reps,
            "is_partial": self.is_partial,
            "completion_rate": round(self.completion_rate, 4),
        }

        # Omitted rather than nulled, matching the discipline in
        # app/schemas.py. A null still occupies the field, and a UI that
        # rendered a stale kilogram value into it would be making a clinical
        # claim the measurement does not support. See app/clinical_gate.py.
        for attribute, _unit in WEEK_MEASURES:
            interval = getattr(self, attribute)
            if interval is not None:
                payload[attribute] = interval.to_dict()

        return payload


@dataclass(frozen=True)
class WeeklyRollup:
    """A patient's history, week by week, with what changed across it."""

    weeks: list[WeekBucket] = field(default_factory=list)
    adherence_rate: Interval | None = None
    effort_change: Interval | None = None
    # Grip only, for the same reason as WeekBucket.strength_kg.
    strength_change: Interval | None = None
    insufficient_data: bool = False
    explanation: Explanation | None = None

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "weeks": [w.to_dict() for w in self.weeks],
            "insufficient_data": self.insufficient_data,
            "explanation": (
                self.explanation.to_dict() if self.explanation else None
            ),
        }

        for name in ("adherence_rate", "effort_change", "strength_change"):
            interval = getattr(self, name)
            if interval is not None:
                payload[name] = interval.to_dict()

        return payload


def _monday(iso_year: int, iso_week: int) -> date:
    return date.fromisocalendar(iso_year, iso_week, 1)


def _week_range(first: tuple[int, int], last: tuple[int, int]) -> list[tuple[int, int]]:
    """Every ISO week from first to last inclusive, gaps included.

    Walked by date rather than by arithmetic on the week number, because ISO
    years have 52 or 53 weeks and incrementing the integer gets that wrong
    once a year.
    """
    cursor = _monday(*first)
    end = _monday(*last)
    weeks: list[tuple[int, int]] = []

    while cursor <= end:
        weeks.append(cursor.isocalendar()[:2])
        cursor += timedelta(days=7)

    return weeks


def bucket_weeks(
    sessions: Iterable["Session"],
    *,
    today: date | None = None,
) -> list[WeekBucket]:
    """Group sessions into continuous ISO weeks.

    Pure: takes session shaped rows and returns buckets, touching no database
    and no explanation machinery, so the arithmetic can be tested on its own.
    """
    rows = list(sessions)
    if not rows:
        return []

    now = today or datetime.now(timezone.utc).date()
    current_week = now.isocalendar()[:2]

    grouped: dict[tuple[int, int], list["Session"]] = {}
    for session in rows:
        key = _aware(session.started_at).isocalendar()[:2]
        grouped.setdefault(key, []).append(session)

    ordered = sorted(grouped)
    buckets: list[WeekBucket] = []

    for key in _week_range(ordered[0], ordered[-1]):
        in_week = grouped.get(key, [])
        done = [s for s in in_week if _completed(s)]

        measures: dict[str, Interval | None] = {}
        for attribute, unit in WEEK_MEASURES:
            # The gate, applied per measure rather than per week. A week
            # mixing grip with biceps still reports its effort and quality;
            # only the kilogram figure narrows to the grip sessions in it.
            eligible = (
                [s for s in done if allows_kilograms(s.muscle)]
                if attribute in GATED_METRICS
                else done
            )
            values = [
                float(getattr(s, attribute))
                for s in eligible
                if getattr(s, attribute, None) is not None
            ]
            measures[attribute] = _spread(values, unit) if values else None

        buckets.append(
            WeekBucket(
                iso_year=key[0],
                iso_week=key[1],
                start_date=_monday(*key),
                session_count=len(done),
                prescribed_count=len(in_week),
                total_reps=sum(int(s.rep_count or 0) for s in done),
                # The current week is incomplete by definition on any day but
                # its last, so a trend that included it would compare a part
                # week against whole ones and manufacture a decline.
                is_partial=key == current_week,
                **measures,
            )
        )

    return buckets


def _change(values: list[float], unit: str) -> Interval | None:
    """Change from the first half of the history to the second.

    Bootstrapped rather than reported bare, because unlike a within week
    spread this genuinely is an estimate: the weeks are a sample of how the
    patient is doing and another week would move the number.
    """
    if len(values) < MIN_WEEKS:
        return None

    series = np.asarray(values, dtype=float)
    split = series.size // 2
    early, late = series[:split], series[split:]

    if early.size == 0 or late.size == 0:
        return None

    rng = np.random.default_rng(0)
    draws = [
        float(
            rng.choice(late, size=late.size, replace=True).mean()
            - rng.choice(early, size=early.size, replace=True).mean()
        )
        for _ in range(N_BOOTSTRAP)
    ]

    return bootstrap_interval(
        draws,
        unit=unit,
        point=float(late.mean() - early.mean()),
    )


def _explain(weeks: list[WeekBucket], complete: list[WeekBucket]) -> Explanation:
    """What the rollup is saying, and what drove it."""
    per_week = [w.session_count for w in complete]
    sessions_mean = sum(per_week) / len(per_week)
    missed = sum(w.prescribed_count - w.session_count for w in complete)
    quiet = sum(1 for w in complete if w.session_count == 0)

    factors = [
        Factor(
            name="sessions per week",
            contribution=sessions_mean,
            direction="increases" if sessions_mean >= 2.0 else "decreases",
            plain_text=(
                f"{sessions_mean:.1f} sessions a week across "
                f"{len(complete)} complete weeks"
            ),
        ),
        Factor(
            name="missed sessions",
            contribution=float(missed),
            direction="decreases" if missed else "neutral",
            plain_text=(
                f"{missed} prescribed sessions were not completed"
                if missed
                else "every prescribed session was completed"
            ),
        ),
        Factor(
            name="quiet weeks",
            contribution=float(quiet),
            direction="decreases" if quiet else "neutral",
            plain_text=(
                f"{quiet} weeks passed with no session at all"
                if quiet
                else "no week passed without a session"
            ),
        ),
    ]

    return Explanation(
        summary=(
            f"Across {len(complete)} complete weeks you trained "
            f"{sessions_mean:.1f} times a week. "
            + (
                f"{quiet} of those weeks had no session."
                if quiet
                else "You had a session in every one of them."
            )
        ),
        factors=factors,
        method="ISO week aggregation with bootstrap intervals over week means",
    )


def roll_up(
    sessions: Iterable["Session"],
    *,
    today: date | None = None,
) -> WeeklyRollup:
    """M15: bucket a history into weeks and describe how it changed."""
    weeks = bucket_weeks(sessions, today=today)
    complete = [w for w in weeks if not w.is_partial]

    if len(complete) < MIN_WEEKS:
        return WeeklyRollup(
            weeks=weeks,
            insufficient_data=True,
            explanation=Explanation(
                summary=(
                    f"A weekly view needs at least {MIN_WEEKS} complete weeks "
                    "of history. Keep going and this fills in on its own."
                ),
                method="not enough weeks to aggregate",
            ),
        )

    effort = [w.mean_mvc.point for w in complete if w.mean_mvc is not None]
    strength = [w.strength_kg.point for w in complete if w.strength_kg is not None]

    return WeeklyRollup(
        weeks=weeks,
        adherence_rate=bootstrap_interval(
            [w.completion_rate for w in complete],
            unit="",
        ).clamped(0.0, 1.0),
        effort_change=_change(effort, "%"),
        strength_change=_change(strength, "kg"),
        insufficient_data=False,
        explanation=_explain(weeks, complete),
    )


# Wording that is only honest about a forearm grip, checked against generated
# prose before it ships. The leading space on " kg" matches the assertion in
# app/tests/test_clinical_gate.py, so a figure like "25.5 kg" is caught while
# an innocent word containing the letters is not.
FORBIDDEN_OFF_GRIP = (
    "ewgsop2",
    " kg",
    "kilogram",
    "dynamomet",
    "percentile",
)


def assert_gate_safe(text: str, muscles: set[str]) -> str:
    """Drop a narrative that makes a grip only claim about another muscle.

    The narrative is assembled from prose other models wrote, and M14's
    summary embeds both a kilogram figure and EWGSOP2 wording. Composition is
    where that leaks, so this is the check between composing and shipping.

    Dropped whole rather than redacted. A sentence with a clinical claim cut
    out of the middle of it reads as though something is missing, and it is:
    the reader cannot tell what was removed or why. An empty string tells the
    caller to fall back to something it knows is safe.
    """
    if all(allows_kilograms(muscle) for muscle in muscles):
        return text

    lowered = text.lower()
    if any(token in lowered for token in FORBIDDEN_OFF_GRIP):
        return ""

    return text


def compose_narrative(
    rollup: WeeklyRollup,
    upstream: list[Explanation],
    *,
    muscles: set[str] | None = None,
    prescription: list[str] | None = None,
) -> tuple[str, str]:
    """Assemble the week in review, and say where the words came from.

    Composed rather than written: every clause is a sentence one of the models
    already produced, joined in an order that reads as a paragraph. Nothing
    here invents a clinical claim, which is what makes it safe to show without
    a person having read it first.

    Returns the text and its provenance, so the UI can say which it is.
    """
    sites = muscles or {GRIP}
    parts: list[str] = []

    if rollup.explanation is not None:
        parts.append(rollup.explanation.summary)

    parts.extend(e.summary for e in upstream if e.summary)

    # The close looks forward rather than back, so the paragraph ends on
    # something to do rather than on a verdict.
    if prescription:
        parts.append(prescription[0])

    return assert_gate_safe(" ".join(parts), sites), "template"


__all__ = [
    "FORBIDDEN_OFF_GRIP",
    "MIN_WEEKS",
    "WEEK_MEASURES",
    "WeekBucket",
    "WeeklyRollup",
    "assert_gate_safe",
    "bucket_weeks",
    "compose_narrative",
    "roll_up",
]
