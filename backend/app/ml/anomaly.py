"""M6: session anomaly detection.

An Isolation Forest over a session feature vector, flagging sessions that do
not fit the pattern.

**Direction is the whole point.** An outlier is not automatically a problem: a
session where someone produced far more than usual is unusual in exactly the
same statistical sense as one where they collapsed. Reporting a breakthrough
as an anomaly to be worried about would be both wrong and discouraging, so
every flagged session is classified against the patient's own recent average
and a positive anomaly is surfaced as a standout rather than a warning.

Explanation comes from leaving one feature out at a time: replace a feature
with the patient's own median and see how much the score moves. Whatever moves
it most is what made the session unusual.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np
import pandas as pd

from app.ml.explain import Explanation, Factor, Interval, label_for

TRAINING_NOTES = (
    "Isolation Forest over session features. Direction is assigned against "
    "the patient's own trailing mean, so a standout session is not reported "
    "as a problem."
)

ANOMALY_FEATURES: tuple[str, ...] = (
    "mean_mvc",
    "rep_count",
    "fatigue_slope",
    "hold_cv",
    "adherence_gap_days",
    "sqi_mean",
)

# How many previous sessions define "usual" for this patient.
TRAILING_WINDOW = 5

Direction = Literal["positive", "negative"]


@dataclass(frozen=True)
class AnomalyResult:
    """Whether one session fits the patient's pattern."""

    score: Interval
    is_anomaly: bool
    direction: Direction
    explanation: Explanation

    def to_dict(self) -> dict[str, object]:
        return {
            "score": self.score.to_dict(),
            "is_anomaly": self.is_anomaly,
            "direction": self.direction,
            "explanation": self.explanation.to_dict(),
        }


def train(
    cohort: pd.DataFrame,
    *,
    summary: pd.DataFrame | None = None,
    seed: int = 0,
) -> dict[str, object]:
    """Fit the detector on completed cohort sessions."""
    from sklearn.ensemble import IsolationForest
    from sklearn.preprocessing import StandardScaler

    completed = cohort[cohort["completed"]]
    features = list(ANOMALY_FEATURES)
    X = completed[features].to_numpy(dtype=float)

    scaler = StandardScaler().fit(X)
    model = IsolationForest(
        n_estimators=200,
        contamination=0.06,
        random_state=seed,
    ).fit(scaler.transform(X))

    return {
        "model": model,
        "scaler": scaler,
        "features": features,
        "medians": {name: float(completed[name].median()) for name in features},
        "contamination": 0.06,
        "n_rows": int(X.shape[0]),
    }


def assess(
    session: dict[str, float],
    *,
    history: list[dict[str, float]] | None = None,
    artifact: dict[str, object] | None = None,
) -> AnomalyResult:
    """Judge one session against the cohort, and direction against the patient.

    history is the patient's own recent sessions, most recent last. Without it
    the session can still be scored, but direction falls back to comparing
    against the cohort median, which is a weaker statement.
    """
    if artifact is None:
        return _heuristic_assess(session, history)

    features = list(artifact["features"])  # type: ignore[arg-type]
    model = artifact["model"]
    scaler = artifact["scaler"]
    medians: dict[str, float] = artifact["medians"]  # type: ignore[assignment]

    row = np.array([[session.get(name, medians[name]) for name in features]], dtype=float)
    scaled = scaler.transform(row)  # type: ignore[union-attr]

    # Isolation Forest scores are negative for outliers. Map to 0 to 100 where
    # higher means more unusual, which is the direction a reader expects.
    raw = float(model.decision_function(scaled)[0])  # type: ignore[union-attr]
    score = float(np.clip(50.0 - raw * 100.0, 0.0, 100.0))
    is_anomaly = bool(model.predict(scaled)[0] == -1)  # type: ignore[union-attr]

    # How isolated the point is, in tree depth terms, drives the width. A
    # point the ensemble isolates decisively gets a tighter interval than one
    # sitting near the boundary, where a slightly different forest would have
    # scored it differently.
    #
    # Individual estimators do not expose decision_function, so the width
    # comes from distance to the decision boundary rather than from polling
    # the trees.
    boundary_distance = abs(raw - model.offset_)  # type: ignore[union-attr]
    spread = float(np.clip(18.0 - boundary_distance * 120.0, 4.0, 18.0))

    interval = Interval(
        point=score,
        lower=score - spread,
        upper=score + spread,
        level=0.8,
    ).clamped(0.0, 100.0)

    direction = _direction(session, history, medians)
    factors = _leave_one_out(session, features, medians, model, scaler, raw)

    return AnomalyResult(
        score=interval,
        is_anomaly=is_anomaly,
        direction=direction,
        explanation=Explanation(
            summary=_summary(is_anomaly, direction, factors),
            factors=factors,
            method="isolation forest, explained by leaving one feature out",
        ),
    )


def _direction(
    session: dict[str, float],
    history: list[dict[str, float]] | None,
    medians: dict[str, float],
) -> Direction:
    """Was this session unusual upward or downward?

    Compared against the patient's own recent average rather than the cohort,
    because "unusual for you" is the question a patient is actually asking.
    """
    current = session.get("mean_mvc", medians["mean_mvc"])

    if history:
        recent = [h.get("mean_mvc") for h in history[-TRAILING_WINDOW:]]
        values = [v for v in recent if v is not None]
        if values:
            return "positive" if current >= float(np.mean(values)) else "negative"

    return "positive" if current >= medians["mean_mvc"] else "negative"


def _leave_one_out(
    session: dict[str, float],
    features: list[str],
    medians: dict[str, float],
    model,
    scaler,
    baseline: float,
) -> list[Factor]:
    """Which feature made this session unusual.

    Each feature is replaced by the patient's typical value in turn. Whichever
    substitution moves the score most is what was driving it.
    """
    deltas: list[tuple[str, float]] = []

    for i, name in enumerate(features):
        probe = np.array(
            [[session.get(other, medians[other]) for other in features]], dtype=float
        )
        probe[0, i] = medians[name]
        moved = float(model.decision_function(scaler.transform(probe))[0])
        deltas.append((name, moved - baseline))

    deltas.sort(key=lambda pair: abs(pair[1]), reverse=True)

    return [
        Factor(
            name=name,
            contribution=delta,
            # A positive delta means the session looked more normal once this
            # feature was replaced, so this feature is what made it unusual.
            direction="increases" if delta > 0 else "decreases",
            plain_text=f"{label_for(name)} was the main difference",
        )
        for name, delta in deltas[:3]
    ]


def _summary(is_anomaly: bool, direction: Direction, factors: list[Factor]) -> str:
    if not is_anomaly:
        return "This session fits your usual pattern."

    driver = factors[0].plain_text if factors else "several measures differed"

    if direction == "positive":
        return f"This session stood out, in a good way. {driver.capitalize()}."
    return (
        f"This session did not fit your usual pattern. {driver.capitalize()}. "
        "One session on its own is rarely worth acting on."
    )


def _heuristic_assess(
    session: dict[str, float],
    history: list[dict[str, float]] | None,
) -> AnomalyResult:
    """Transparent fallback: how far from the patient's own recent average."""
    current = session.get("mean_mvc", 0.0)

    values = [
        h["mean_mvc"] for h in (history or [])[-TRAILING_WINDOW:] if "mean_mvc" in h
    ]
    if len(values) >= 2:
        mean, sd = float(np.mean(values)), float(np.std(values))
        z = abs(current - mean) / sd if sd > 1e-6 else 0.0
        direction: Direction = "positive" if current >= mean else "negative"
    else:
        z, direction = 0.0, "positive"

    score = float(np.clip(z * 25.0, 0.0, 100.0))
    is_anomaly = z > 2.0

    return AnomalyResult(
        score=Interval(
            point=score,
            lower=max(0.0, score - 15.0),
            upper=min(100.0, score + 15.0),
            level=0.8,
        ),
        is_anomaly=is_anomaly,
        direction=direction,
        explanation=Explanation(
            summary=(
                "This session fits your usual pattern."
                if not is_anomaly
                else (
                    "This session stood out, in a good way."
                    if direction == "positive"
                    else "This session did not fit your usual pattern."
                )
            ),
            method="heuristic fallback, no trained model available",
        ),
    )


__all__ = [
    "ANOMALY_FEATURES",
    "AnomalyResult",
    "assess",
    "train",
]
