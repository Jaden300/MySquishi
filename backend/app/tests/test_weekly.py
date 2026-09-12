"""M15 weekly rollup.

The arithmetic is simple and the ways it goes quietly wrong are not, so most
of what is asserted here is the quiet ones: a naive timestamp landing in the
wrong week, an empty week disappearing, a missed session counted as a
completed one, and a kilogram figure averaged across muscles it does not
describe.
"""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.ml.explain import Explanation
from app.ml.weekly import (
    MIN_WEEKS,
    WeekBucket,
    assert_gate_safe,
    bucket_weeks,
    compose_narrative,
    roll_up,
)
from app.models import Session

# A Sunday, so "the week after" is unambiguous.
MONDAY = datetime(2026, 7, 6, 9, 0, tzinfo=timezone.utc)

# Far enough past the fixtures that no fixture week is ever the current one.
LATER = date(2026, 12, 1)


def _session(
    started_at: datetime,
    *,
    muscle: str = "forearm_grip",
    rep_count: int | None = 10,
    mean_mvc: float | None = 55.0,
    strength_kg: float | None = 20.0,
    mean_rep_quality: float | None = 0.8,
) -> Session:
    return Session(
        patient_id="weekly-test",
        started_at=started_at,
        muscle=muscle,
        rep_count=rep_count,
        mean_mvc=mean_mvc,
        strength_kg=strength_kg,
        mean_rep_quality=mean_rep_quality,
    )


def _weeks(count: int, *, per_week: int = 2, **kwargs) -> list[Session]:
    """`count` consecutive ISO weeks with `per_week` sessions in each."""
    return [
        _session(MONDAY + timedelta(days=7 * week + day), **kwargs)
        for week in range(count)
        for day in range(per_week)
    ]


class TestBucketing:
    def test_no_sessions_is_no_weeks(self) -> None:
        assert bucket_weeks([]) == []

    def test_sessions_in_one_week_group_together(self) -> None:
        buckets = bucket_weeks(_weeks(1, per_week=3), today=LATER)

        assert len(buckets) == 1
        assert buckets[0].session_count == 3
        assert buckets[0].total_reps == 30

    def test_consecutive_weeks_stay_separate(self) -> None:
        buckets = bucket_weeks(_weeks(3), today=LATER)

        assert len(buckets) == 3
        assert [b.iso_week for b in buckets] == [28, 29, 30]

    def test_a_week_with_no_sessions_is_still_emitted(self) -> None:
        """A silence is the most informative thing a rollup can show, so an
        empty week has to survive into the output rather than closing up."""
        first = _session(MONDAY)
        third = _session(MONDAY + timedelta(days=14))

        buckets = bucket_weeks([first, third], today=LATER)

        assert len(buckets) == 3
        assert buckets[1].session_count == 0
        assert buckets[1].prescribed_count == 0
        assert buckets[1].mean_mvc is None

    def test_the_monday_is_reported_for_a_date_axis(self) -> None:
        buckets = bucket_weeks([_session(MONDAY)], today=LATER)
        assert buckets[0].start_date == date(2026, 7, 6)
        assert buckets[0].start_date.weekday() == 0

    def test_a_naive_timestamp_lands_in_the_same_week_as_an_aware_one(self) -> None:
        """The failure this guards is silent rather than loud: a naive
        timestamp still has an isocalendar, so it buckets into a plausible
        looking week instead of raising."""
        aware = _session(MONDAY)
        naive = _session(MONDAY.replace(tzinfo=None))

        buckets = bucket_weeks([aware, naive], today=LATER)

        assert len(buckets) == 1
        assert buckets[0].session_count == 2

    def test_the_week_range_survives_a_year_boundary(self) -> None:
        """ISO years have 52 or 53 weeks, so walking the range by adding one
        to the week number gets this wrong once a year."""
        december = _session(datetime(2026, 12, 21, 9, 0, tzinfo=timezone.utc))
        january = _session(datetime(2027, 1, 11, 9, 0, tzinfo=timezone.utc))

        buckets = bucket_weeks([december, january], today=LATER)

        assert len(buckets) == 4
        assert buckets[0].iso_year == 2026
        assert buckets[-1].iso_year == 2027


class TestMissedSessions:
    def test_a_missed_session_counts_as_prescribed_but_not_completed(self) -> None:
        buckets = bucket_weeks(
            [_session(MONDAY), _session(MONDAY, rep_count=None)],
            today=LATER,
        )

        assert buckets[0].prescribed_count == 2
        assert buckets[0].session_count == 1
        assert buckets[0].completion_rate == 0.5

    def test_a_missed_session_contributes_to_no_measure(self) -> None:
        """Its summary columns are null, so including it would either raise or
        quietly drag a mean toward whatever default stood in for it."""
        buckets = bucket_weeks(
            [
                _session(MONDAY, mean_mvc=60.0),
                _session(MONDAY, rep_count=None, mean_mvc=None),
            ],
            today=LATER,
        )

        assert buckets[0].mean_mvc is not None
        assert buckets[0].mean_mvc.point == 60.0

    def test_a_week_of_only_missed_sessions_reports_no_measures(self) -> None:
        buckets = bucket_weeks(
            [_session(MONDAY, rep_count=None, mean_mvc=None)], today=LATER
        )

        assert buckets[0].session_count == 0
        assert buckets[0].prescribed_count == 1
        assert buckets[0].completion_rate == 0.0
        assert buckets[0].mean_mvc is None


class TestPartialWeek:
    def test_the_current_week_is_flagged_partial(self) -> None:
        buckets = bucket_weeks([_session(MONDAY)], today=date(2026, 7, 8))
        assert buckets[0].is_partial is True

    def test_a_past_week_is_not_partial(self) -> None:
        buckets = bucket_weeks([_session(MONDAY)], today=LATER)
        assert buckets[0].is_partial is False

    def test_a_partial_week_is_excluded_from_the_trend(self) -> None:
        """Comparing a two day week against whole ones manufactures a
        decline, so the partial week is context rather than evidence."""
        sessions = _weeks(3)
        last_week = sessions[-1].started_at.isocalendar()[:2]

        rollup = roll_up(sessions, today=date(2026, 7, 21))

        assert rollup.weeks[-1].is_partial is True
        assert rollup.weeks[-1].iso_week == last_week[1]
        # Three weeks of history, but the trend saw only the two complete ones.
        assert "2 complete weeks" in rollup.explanation.summary


class TestClinicalGate:
    """kg is forearm grip only. See app/clinical_gate.py."""

    def test_a_non_grip_week_reports_no_kilogram_figure(self) -> None:
        buckets = bucket_weeks(
            [_session(MONDAY, muscle="biceps", strength_kg=99.0)], today=LATER
        )

        assert buckets[0].strength_kg is None
        assert buckets[0].mean_mvc is not None

    def test_a_mixed_week_averages_kilograms_over_grip_sessions_alone(self) -> None:
        """The hazard app/export/report.py already names: a kilogram mean
        across a mixed history describes nothing."""
        buckets = bucket_weeks(
            [
                _session(MONDAY, muscle="forearm_grip", strength_kg=20.0),
                _session(MONDAY, muscle="biceps", strength_kg=99.0),
            ],
            today=LATER,
        )

        assert buckets[0].strength_kg is not None
        assert buckets[0].strength_kg.point == 20.0
        # Effort generalizes to any muscle, so it counts both.
        assert buckets[0].session_count == 2

    def test_the_kilogram_key_is_omitted_rather_than_nulled(self) -> None:
        """A null still occupies the field, and a UI rendering a stale value
        into it would make a claim the measurement does not support."""
        payload = bucket_weeks(
            [_session(MONDAY, muscle="calf", strength_kg=None)], today=LATER
        )[0].to_dict()

        assert "strength_kg" not in payload
        assert "mean_mvc" in payload

    def test_a_non_grip_history_has_no_strength_change(self) -> None:
        rollup = roll_up(_weeks(4, muscle="biceps", strength_kg=None), today=LATER)

        assert rollup.strength_change is None
        assert rollup.effort_change is not None
        assert "strength_change" not in rollup.to_dict()


class TestRollup:
    def test_too_few_weeks_says_so_rather_than_guessing(self) -> None:
        rollup = roll_up(_weeks(1), today=LATER)

        assert rollup.insufficient_data is True
        assert rollup.adherence_rate is None
        assert str(MIN_WEEKS) in rollup.explanation.summary

    def test_enough_weeks_produces_a_rollup(self) -> None:
        rollup = roll_up(_weeks(4), today=LATER)

        assert rollup.insufficient_data is False
        assert len(rollup.weeks) == 4
        assert rollup.explanation.method.startswith("ISO week aggregation")

    def test_adherence_rate_stays_a_proportion(self) -> None:
        rollup = roll_up(_weeks(4), today=LATER)

        assert rollup.adherence_rate is not None
        assert 0.0 <= rollup.adherence_rate.lower
        assert rollup.adherence_rate.upper <= 1.0

    def test_rising_effort_reads_as_a_rise(self) -> None:
        sessions: list[Session] = []
        for week in range(6):
            for day in range(2):
                sessions.append(
                    _session(
                        MONDAY + timedelta(days=7 * week + day),
                        mean_mvc=40.0 + 4.0 * week,
                    )
                )

        rollup = roll_up(sessions, today=LATER)

        assert rollup.effort_change is not None
        assert rollup.effort_change.point > 0

    def test_a_quiet_week_is_named_in_the_explanation(self) -> None:
        first = _session(MONDAY)
        second = _session(MONDAY + timedelta(days=1))
        fourth = _session(MONDAY + timedelta(days=21))

        rollup = roll_up([first, second, fourth], today=LATER)

        assert "no session" in rollup.explanation.summary
        assert any(f.name == "quiet weeks" for f in rollup.explanation.factors)

    def test_every_interval_is_ordered(self) -> None:
        """The discipline docs/ML.md requires, on this model's own output."""
        rollup = roll_up(_weeks(6), today=LATER)

        candidates = [
            rollup.adherence_rate,
            rollup.effort_change,
            rollup.strength_change,
        ]
        for week in rollup.weeks:
            candidates.extend([week.mean_mvc, week.strength_kg, week.mean_rep_quality])

        for interval in [c for c in candidates if c is not None]:
            assert interval.lower <= interval.point <= interval.upper

    def test_a_single_session_week_collapses_to_a_zero_width_interval(self) -> None:
        """Honest rather than degenerate: there was one value and this is it."""
        buckets = bucket_weeks(_weeks(1, per_week=1), today=LATER)

        interval = buckets[0].mean_mvc
        assert interval is not None
        assert interval.lower == interval.point == interval.upper

    def test_to_dict_is_serializable(self) -> None:
        import json

        payload = roll_up(_weeks(4), today=LATER).to_dict()
        assert json.loads(json.dumps(payload))["weeks"][0]["iso_week"] == 28


class TestGateSafety:
    """The narrative is assembled from prose other models wrote, and M14's
    summary embeds both a kilogram figure and EWGSOP2 wording. Composition is
    where that leaks."""

    def test_grip_history_keeps_its_kilogram_prose(self) -> None:
        text = "Your 25.5 kg sits around the 27th percentile."
        assert assert_gate_safe(text, {"forearm_grip"}) == text

    @pytest.mark.parametrize(
        "poisoned",
        [
            "Your 25.5 kg sits around the 27th percentile.",
            "That is below the EWGSOP2 screening threshold.",
            "Measured against a hand dynamometer reference.",
            "You gained three kilograms this month.",
        ],
    )
    def test_a_grip_only_claim_is_dropped_for_another_muscle(
        self, poisoned: str
    ) -> None:
        assert assert_gate_safe(poisoned, {"biceps"}) == ""

    def test_ungated_prose_survives_on_any_muscle(self) -> None:
        """The gate has to withhold the claim without silencing the rest, or
        a non grip patient gets no narrative at all."""
        text = "You trained three times a week and your effort held steady."
        assert assert_gate_safe(text, {"calf"}) == text

    def test_a_mixed_history_is_treated_as_non_grip(self) -> None:
        """One biceps session in the history is enough to make a kilogram
        average across the whole of it meaningless."""
        text = "Your 25.5 kg sits around the 27th percentile."
        assert assert_gate_safe(text, {"forearm_grip", "biceps"}) == ""


class TestNarrative:
    def test_it_leads_with_the_rollup_and_closes_on_the_prescription(self) -> None:
        rollup = roll_up(_weeks(4), today=LATER)
        text, source = compose_narrative(
            rollup,
            [Explanation(summary="No plateau detected.", method="cusum")],
            prescription=["Carrying on with what has been working."],
        )

        assert source == "template"
        assert text.startswith("Across 4 complete weeks")
        assert "No plateau detected." in text
        assert text.endswith("Carrying on with what has been working.")

    def test_an_upstream_card_with_nothing_to_say_is_skipped(self) -> None:
        rollup = roll_up(_weeks(4), today=LATER)
        text, _ = compose_narrative(
            rollup,
            [Explanation(summary="", method="none"), Explanation(summary="Kept up.")],
        )

        assert "Kept up." in text
        assert "  " not in text

    def test_a_gated_claim_empties_the_narrative_for_another_muscle(self) -> None:
        """Empty rather than partial, so the caller falls back to something it
        knows is safe rather than shipping a half scrubbed sentence."""
        rollup = roll_up(_weeks(4, muscle="biceps", strength_kg=None), today=LATER)
        text, _ = compose_narrative(
            rollup,
            [Explanation(summary="Your 25.5 kg is around the 27th percentile.")],
            muscles={"biceps"},
        )

        assert text == ""


class TestGenerationStaysOutOfTheApp:
    """The narrative is written offline into a committed fixture.

    An SDK in the running app would be a network call on the demo path and,
    because app/api/__init__.py swallows ImportError when registering routers,
    an import failure in a module that touched it would silently delete the ML
    routes with nothing in the logs. Same shape as the pyserial guards in
    test_api.py.
    """

    APP_DIR = Path(__file__).resolve().parent.parent

    def test_no_model_sdk_is_imported_under_app(self) -> None:
        pattern = re.compile(r"^\s*(import\s+anthropic|from\s+anthropic\b)", re.M)

        offenders = [
            str(path.relative_to(self.APP_DIR))
            for path in self.APP_DIR.rglob("*.py")
            if pattern.search(path.read_text(encoding="utf-8"))
        ]

        assert not offenders, (
            "generation is offline and the app reads a committed fixture, so "
            f"nothing under app/ should import a model SDK: {offenders}"
        )

    def test_the_sdk_is_not_a_dependency_of_the_app(self) -> None:
        requirements = (
            self.APP_DIR.parent / "requirements.txt"
        ).read_text(encoding="utf-8")

        assert "anthropic" not in requirements.lower()

    def test_the_generation_tool_declares_its_own_dependency(self) -> None:
        """Kept beside requirements-probe.txt, installed only by the person
        running the tool."""
        declared = (
            self.APP_DIR.parent / "tools" / "requirements-narratives.txt"
        ).read_text(encoding="utf-8")

        assert "anthropic" in declared.lower()


class TestWeekBucketShape:
    def test_no_prescribed_sessions_reads_as_complete(self) -> None:
        """A week nothing was asked of is not a week the patient failed."""
        bucket = WeekBucket(
            iso_year=2026,
            iso_week=28,
            start_date=date(2026, 7, 6),
            session_count=0,
            prescribed_count=0,
            total_reps=0,
            is_partial=False,
        )
        assert bucket.completion_rate == 1.0
