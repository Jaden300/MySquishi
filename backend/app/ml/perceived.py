"""M7: perceived versus actual effort.

Ridge predicting Borg CR10 from what the session actually measured. The
prediction itself is not the interesting output: the residual is.

A patient who feels wrecked after a session that measured easy, or who reports
a walk in the park after producing far more than usual, is telling you
something the sensor cannot. Large residuals in either direction are
clinically interesting, and that is what gets surfaced as an insight card.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np
import pandas as pd

from app.ml.explain import Explanation, Interval, coefficient_factors

TRAINING_NOTES = (
    "Ridge predicting Borg CR10 from session measures. The residual, not the "
    "prediction, is what gets surfaced."
)

PERCEIVED_FEATURES: tuple[str, ...] = (
    "mean_mvc",
    "peak_mvc",
    "rep_count",
    "fatigue_slope",
    "hold_cv",
)

# How many residual standard deviations count as a gap worth mentioning.
FLAG_SIGMA = 1.5

Flag = Literal["harder_than_expected", "easier_than_expected", "as_expected"]


@dataclass(frozen=True)
class PerceivedResult:
    """What the session should have felt like, against what it did."""

    predicted_borg: Interval
    actual_borg: float | None
    residual: float | None
    flag: Flag
    explanation: Explanation

    def to_dict(self) -> dict[str, object]:
        return {
            "predicted_borg": self.predicted_borg.to_dict(),
            "actual_borg": self.actual_borg,
            "residual": round(self.residual, 3) if self.residual is not None else None,
            "flag": self.flag,
            "explanation": self.explanation.to_dict(),
        }


def train(
    cohort: pd.DataFrame,
    *,
    summary: pd.DataFrame | None = None,
    seed: int = 0,
) -> dict[str, object]:
    """Fit the effort model on completed cohort sessions."""
    from sklearn.linear_model import Ridge
    from sklearn.model_selection import cross_val_score
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler

    completed = cohort[cohort["completed"]]
    features = list(PERCEIVED_FEATURES)

    X = completed[features].to_numpy(dtype=float)
    y = completed["borg"].to_numpy(dtype=float)

    pipeline = Pipeline(
        [("scale", StandardScaler()), ("model", Ridge(alpha=1.0, random_state=seed))]
    )

    scores = cross_val_score(pipeline, X, y, cv=5, scoring="r2")
    pipeline.fit(X, y)

    residuals = y - pipeline.predict(X)

    return {
        "pipeline": pipeline,
        "features": features,
        "cv_r2": float(scores.mean()),
        "residual_sigma": float(np.std(residuals)),
        "n_rows": int(X.shape[0]),
    }


def assess(
    session: dict[str, float],
    *,
    actual_borg: float | None = None,
    artifact: dict[str, object] | None = None,
) -> PerceivedResult:
    """Predict how hard a session should have felt, and compare."""
    if artifact is None:
        return _heuristic_assess(session, actual_borg)

    features = list(artifact["features"])  # type: ignore[arg-type]
    pipeline = artifact["pipeline"]
    sigma = float(artifact.get("residual_sigma", 1.0))  # type: ignore[arg-type]

    row = np.array([[session.get(name, 0.0) for name in features]], dtype=float)
    predicted = float(pipeline.predict(row)[0])  # type: ignore[union-attr]

    interval = Interval(
        point=predicted,
        # 80 percent of a normal sits within 1.28 standard deviations.
        lower=predicted - 1.28 * sigma,
        upper=predicted + 1.28 * sigma,
        level=0.8,
        unit="Borg CR10",
    ).clamped(0.0, 10.0)

    residual = None if actual_borg is None else float(actual_borg - predicted)
    flag: Flag = "as_expected"
    if residual is not None and abs(residual) > FLAG_SIGMA * sigma:
        flag = "harder_than_expected" if residual > 0 else "easier_than_expected"

    model = pipeline.named_steps["model"]  # type: ignore[union-attr]
    scaler = pipeline.named_steps["scale"]  # type: ignore[union-attr]
    factors = coefficient_factors(
        model.coef_, features, feature_values=scaler.transform(row)[0], top_n=3
    )

    return PerceivedResult(
        predicted_borg=interval,
        actual_borg=actual_borg,
        residual=residual,
        flag=flag,
        explanation=Explanation(
            summary=_summary(flag, predicted, actual_borg),
            factors=factors,
            method="ridge regression over session measures",
        ),
    )


def _summary(flag: Flag, predicted: float, actual: float | None) -> str:
    if actual is None:
        return (
            f"Based on what this session measured, it would typically feel "
            f"around {predicted:.0f} out of 10."
        )

    if flag == "harder_than_expected":
        return (
            f"You rated this {actual:.0f} out of 10, harder than the "
            f"{predicted:.0f} the measurements suggest. Worth noticing if it "
            "keeps happening: fatigue, sleep and stress all show up here "
            "before they show up in the signal."
        )
    if flag == "easier_than_expected":
        return (
            f"You rated this {actual:.0f} out of 10, easier than the "
            f"{predicted:.0f} the measurements suggest. That often means the "
            "work is becoming routine, which is a good sign."
        )
    return (
        f"You rated this {actual:.0f} out of 10, about what the measurements "
        "suggest it should have felt like."
    )


def _heuristic_assess(
    session: dict[str, float],
    actual_borg: float | None,
) -> PerceivedResult:
    """Transparent fallback: effort scaled onto the Borg range."""
    predicted = float(np.clip(session.get("mean_mvc", 40.0) / 10.0, 0.0, 10.0))

    residual = None if actual_borg is None else float(actual_borg - predicted)
    flag: Flag = "as_expected"
    if residual is not None and abs(residual) > 2.0:
        flag = "harder_than_expected" if residual > 0 else "easier_than_expected"

    return PerceivedResult(
        predicted_borg=Interval(
            point=predicted,
            lower=max(0.0, predicted - 2.0),
            upper=min(10.0, predicted + 2.0),
            level=0.8,
            unit="Borg CR10",
        ),
        actual_borg=actual_borg,
        residual=residual,
        flag=flag,
        explanation=Explanation(
            summary=_summary(flag, predicted, actual_borg),
            method="heuristic fallback, no trained model available",
        ),
    )


__all__ = [
    "PERCEIVED_FEATURES",
    "PerceivedResult",
    "assess",
    "train",
]
