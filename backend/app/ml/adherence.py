"""M13: adherence and dropout risk.

Logistic regression predicting disengagement within fourteen days, from
session cadence and recent history.

**The target does not exist in the cohort and is constructed here.** No column
records dropout, so the label is derived, and how it is derived matters more
than anything else in this module.

The obvious definition, no completed session within fourteen days, turns out
to be nearly useless on this population: sessions are prescribed every three
to four days, so a full fortnight of silence describes total dropout and
occurs in well under one percent of cases. A model trained on that learns to
always answer "no risk" and scores well doing it.

So the label is a *lapse relative to the prescribed cadence*: a moment is
labeled at risk when the patient goes more than twice their own typical
interval without completing a session, while sessions are still prescribed.
That captures the clinically actionable thing, someone slipping out of their
rhythm, at a rate worth modelling, and it adapts to a patient training twice a
week as readily as one training daily.

Even with that definition the signal is modest: cross validated AUC sits
around 0.6, meaningfully better than chance but far from a confident
prediction. That is reported honestly rather than dressed up, and it is why
the interval widens as discrimination falls. A nudge is worth showing on a
weak signal; a number presented as certain would not be.

The surfaced copy is encouraging and never shaming. Someone who has missed
sessions is usually already aware of it, and a scolding app is one that gets
deleted. A test asserts the module contains no shaming language.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from app.ml.explain import Explanation, Interval, coefficient_factors

TRAINING_NOTES = (
    "Logistic regression on session cadence. The disengagement label is "
    "constructed from prescribed and completed dates, not read from a column."
)

ADHERENCE_FEATURES: tuple[str, ...] = (
    "sessions_completed",
    "days_since_last",
    "completion_rate",
    "recent_trend",
    "weeks_elapsed",
)

# The horizon the model predicts over.
HORIZON_DAYS = 14


@dataclass(frozen=True)
class AdherenceResult:
    """Probability of disengaging in the next two weeks."""

    probability: Interval
    risk_band: str
    nudge: str
    explanation: Explanation

    def to_dict(self) -> dict[str, object]:
        return {
            "probability": self.probability.to_dict(),
            "risk_band": self.risk_band,
            "nudge": self.nudge,
            "explanation": self.explanation.to_dict(),
        }


def build_training_set(cohort: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    """Derive features and the constructed lapse label.

    Walks each patient's programme in order. At every completed session it
    describes the history up to that point, then looks forward: if the next
    completed session does not arrive within twice this patient's own typical
    interval, that moment is labeled at risk.

    The threshold is per patient rather than fixed, so the label means the
    same thing for someone training twice a week as for someone training
    daily. See the module docstring for why a fixed fourteen day window does
    not work here.
    """
    rows: list[list[float]] = []
    labels: list[int] = []

    for _, group in cohort.groupby("patient_id", sort=True):
        group = group.sort_values("session_index")
        dates = pd.to_datetime(group["session_date"])
        completed = group["completed"].to_numpy(dtype=bool)

        programme_end = dates.iloc[-1]
        completed_dates = dates[completed]

        if len(completed_dates) < 4:
            continue

        # This patient's own rhythm, and the lapse threshold derived from it.
        typical_gap = float(
            np.median(np.diff(completed_dates).astype("timedelta64[D]").astype(int))
        )
        lapse_days = max(2.0 * typical_gap, 7.0)

        for position in range(len(group)):
            if not completed[position]:
                continue

            now = dates.iloc[position]
            history = completed[: position + 1]

            # Not enough history to describe a pattern yet.
            if history.sum() < 3:
                continue

            past_dates = completed_dates[completed_dates <= now]
            days_since_last = (
                float((now - past_dates.iloc[-2]).days) if len(past_dates) >= 2 else 0.0
            )

            strengths = group["strength_kg"].to_numpy(dtype=float)[: position + 1]
            recent = strengths[completed[: position + 1]][-5:]
            recent_trend = (
                float(np.polyfit(np.arange(len(recent)), recent, 1)[0])
                if len(recent) >= 3
                else 0.0
            )

            rows.append(
                [
                    float(history.sum()),
                    days_since_last,
                    float(history.sum() / (position + 1)),
                    recent_trend,
                    float((now - dates.iloc[0]).days / 7.0),
                ]
            )

            # The constructed label. A patient at the very end of their
            # programme has not disengaged, they have finished, so the window
            # has to still fall inside the programme for the question to mean
            # anything.
            horizon_end = now + pd.Timedelta(days=lapse_days)
            future = completed_dates[
                (completed_dates > now) & (completed_dates <= horizon_end)
            ]
            still_running = programme_end > horizon_end

            labels.append(1 if (still_running and len(future) == 0) else 0)

    return np.array(rows, dtype=float), np.array(labels, dtype=int)


def train(
    cohort: pd.DataFrame,
    *,
    summary: pd.DataFrame | None = None,
    seed: int = 0,
) -> dict[str, object]:
    """Fit the risk model. Returns the artifact to persist."""
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import cross_val_score
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler

    X, y = build_training_set(cohort)

    pipeline = Pipeline(
        [
            ("scale", StandardScaler()),
            (
                "model",
                LogisticRegression(
                    max_iter=1000,
                    random_state=seed,
                    # The classes are imbalanced: most sessions are followed by
                    # another one. Without this the model would learn to always
                    # say "no risk" and score well doing it.
                    class_weight="balanced",
                ),
            ),
        ]
    )

    # Guard against a cohort that produced only one class.
    if len(np.unique(y)) < 2:
        auc = 0.5
    else:
        auc = float(
            cross_val_score(pipeline, X, y, cv=5, scoring="roc_auc").mean()
        )

    pipeline.fit(X, y)

    return {
        "pipeline": pipeline,
        "features": list(ADHERENCE_FEATURES),
        "cv_auc": auc,
        "n_rows": int(X.shape[0]),
        "positive_rate": float(y.mean()) if y.size else 0.0,
    }


def assess(
    features: dict[str, float],
    artifact: dict[str, object] | None = None,
) -> AdherenceResult:
    """Estimate the risk of disengaging over the next two weeks."""
    if artifact is None:
        return _heuristic_assess(features)

    names = list(artifact["features"])  # type: ignore[arg-type]
    pipeline = artifact["pipeline"]
    row = np.array([[features.get(name, 0.0) for name in names]], dtype=float)

    probability = float(pipeline.predict_proba(row)[0, 1])  # type: ignore[union-attr]

    # The interval widens as the model's cross validated discrimination falls,
    # so a weak model reports a wide band rather than a confident number.
    auc = float(artifact.get("cv_auc", 0.5))  # type: ignore[arg-type]
    spread = max(0.05, (1.0 - (auc - 0.5) * 2.0) * 0.25)

    interval = Interval(
        point=probability,
        lower=probability - spread,
        upper=probability + spread,
        level=0.8,
    ).clamped(0.0, 1.0)

    model = pipeline.named_steps["model"]  # type: ignore[union-attr]
    scaler = pipeline.named_steps["scale"]  # type: ignore[union-attr]
    factors = coefficient_factors(
        model.coef_,
        names,
        feature_values=scaler.transform(row)[0],
        top_n=3,
    )

    band = "higher" if probability >= 0.6 else "moderate" if probability >= 0.3 else "lower"

    return AdherenceResult(
        probability=interval,
        risk_band=band,
        nudge=_nudge(band, features),
        explanation=Explanation(
            summary=_summary(band),
            factors=factors,
            method="logistic regression over session cadence",
        ),
    )


def _summary(band: str) -> str:
    if band == "higher":
        return (
            "A gap looks likely in the next couple of weeks. A short session "
            "counts for more than a perfect one."
        )
    if band == "moderate":
        return "Your rhythm has loosened a little. A session this week would settle it."
    return "You are keeping a steady rhythm, and that is the part that compounds."


def _nudge(band: str, features: dict[str, float]) -> str:
    """Encouraging copy. Never shaming, per docs/ML.md."""
    days = features.get("days_since_last", 0.0)

    if band == "higher":
        if days >= 7:
            return (
                "It has been a little while. Ten minutes today is worth more "
                "than a full session you keep putting off."
            )
        return "Even a short session keeps your progress moving."
    if band == "moderate":
        return "One session this week keeps your streak of progress going."
    return "Nicely consistent. Keep going at whatever pace suits you."


def _heuristic_assess(features: dict[str, float]) -> AdherenceResult:
    """Transparent fallback before the model has been trained."""
    days = features.get("days_since_last", 0.0)
    completion = features.get("completion_rate", 1.0)

    risk = float(np.clip(days / 21.0 * 0.6 + (1.0 - completion) * 0.5, 0.0, 1.0))
    band = "higher" if risk >= 0.6 else "moderate" if risk >= 0.3 else "lower"

    return AdherenceResult(
        probability=Interval(
            point=risk,
            lower=max(0.0, risk - 0.2),
            upper=min(1.0, risk + 0.2),
            level=0.8,
        ),
        risk_band=band,
        nudge=_nudge(band, features),
        explanation=Explanation(
            summary=_summary(band),
            method="heuristic fallback, no trained model available",
        ),
    )


__all__ = [
    "ADHERENCE_FEATURES",
    "AdherenceResult",
    "assess",
    "build_training_set",
    "train",
]
