"""M3: EMG to force calibration.

Ridge regression mapping sEMG amplitude features to estimated grip force in
kilograms, fitted per user during a short calibration routine.

The honest framing matters here and is carried through to the UI. This is an
estimate calibrated against a self reported reference, not a dynamometer
reading. A Jamar dynamometer measures force directly; this infers it from
muscle activity, and the two are related but not interchangeable. Every
kilogram figure the app displays says so, and every prediction carries the
residual based interval that says how much the fit itself is unsure.

The fitted model is small enough to serialize onto the patient's calibration
row, so it travels with the calibration rather than living in the shared
artifact store.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

import numpy as np

from app.ml.explain import Explanation, Interval, coefficient_factors

# Amplitude features the force model reads. Deliberately few: a calibration
# trial yields a handful of points, so a wide model would overfit instantly.
FORCE_FEATURES: tuple[str, ...] = ("rms", "mav", "waveform_length")

# Below this many reference points the fit is not trustworthy.
MIN_CALIBRATION_POINTS = 3

# Ridge penalty. Small, since the features are correlated by construction and
# the point is to stabilize rather than to select.
RIDGE_ALPHA = 1.0


@dataclass(frozen=True)
class ForceModel:
    """A fitted per user force model, serializable onto a calibration row."""

    coefficients: list[float]
    intercept: float
    residual_sigma: float
    feature_names: list[str]
    r_squared: float
    n_points: int
    mvc_reference_rms: float

    def to_json(self) -> str:
        return json.dumps(
            {
                "coefficients": self.coefficients,
                "intercept": self.intercept,
                "residual_sigma": self.residual_sigma,
                "feature_names": self.feature_names,
                "r_squared": self.r_squared,
                "n_points": self.n_points,
                "mvc_reference_rms": self.mvc_reference_rms,
            }
        )

    @classmethod
    def from_json(cls, payload: str) -> ForceModel:
        data = json.loads(payload)
        return cls(
            coefficients=list(data["coefficients"]),
            intercept=float(data["intercept"]),
            residual_sigma=float(data["residual_sigma"]),
            feature_names=list(data["feature_names"]),
            r_squared=float(data["r_squared"]),
            n_points=int(data["n_points"]),
            mvc_reference_rms=float(data["mvc_reference_rms"]),
        )

    def predict(self, features: dict[str, float]) -> Interval:
        """Estimate grip force in kilograms, with its uncertainty.

        The interval comes from the residual spread of the calibration fit,
        so a loose calibration produces a visibly wider estimate rather than
        a falsely precise one.
        """
        vector = np.array([features[name] for name in self.feature_names], dtype=float)
        point = float(np.dot(vector, self.coefficients) + self.intercept)

        # 80 percent interval, so roughly 1.28 standard deviations.
        margin = 1.2816 * self.residual_sigma

        # Force cannot be negative, and the lower bound must not cross the
        # point estimate when the point itself is near zero.
        point = max(point, 0.0)
        return Interval(
            point=point,
            lower=max(0.0, point - margin),
            upper=point + margin,
            level=0.8,
            unit="kg",
        )

    def explain(self, features: dict[str, float] | None = None) -> Explanation:
        values = (
            [features[name] for name in self.feature_names] if features else None
        )
        factors = coefficient_factors(
            self.coefficients, self.feature_names, feature_values=values, top_n=2
        )

        quality = (
            "closely" if self.r_squared > 0.9
            else "reasonably" if self.r_squared > 0.7
            else "loosely"
        )

        return Explanation(
            summary=(
                f"Estimated from muscle activity using {self.n_points} calibration "
                f"points, which the model fits {quality} "
                f"(R squared {self.r_squared:.2f}). This is an estimate, not a "
                "dynamometer measurement."
            ),
            factors=factors,
            method="ridge regression coefficients",
        )


def fit(
    feature_rows: list[dict[str, float]],
    reference_kg: list[float] | np.ndarray,
    *,
    mvc_reference_rms: float,
    alpha: float = RIDGE_ALPHA,
) -> ForceModel:
    """Fit the per user force model from a calibration trial.

    feature_rows are amplitude features from each calibration hold, and
    reference_kg the self reported force for each.
    """
    from sklearn.linear_model import Ridge

    if len(feature_rows) != len(reference_kg):
        raise ValueError(
            f"{len(feature_rows)} feature rows for {len(reference_kg)} references"
        )
    if len(feature_rows) < MIN_CALIBRATION_POINTS:
        raise ValueError(
            f"need at least {MIN_CALIBRATION_POINTS} calibration points, "
            f"got {len(feature_rows)}"
        )
    if mvc_reference_rms <= 0:
        raise ValueError(f"mvc_reference_rms must be positive, got {mvc_reference_rms}")

    names = list(FORCE_FEATURES)
    X = np.array([[row[name] for name in names] for row in feature_rows], dtype=float)
    y = np.asarray(reference_kg, dtype=float)

    model = Ridge(alpha=alpha).fit(X, y)
    predictions = model.predict(X)
    residuals = y - predictions

    # With few points the naive residual standard deviation understates the
    # true spread, so correct for the degrees of freedom the fit consumed.
    dof = max(len(y) - len(names) - 1, 1)
    sigma = float(np.sqrt(np.sum(residuals**2) / dof))

    # A perfect fit through few points is not evidence of certainty. Keep a
    # floor so the interval never collapses to nothing.
    sigma = max(sigma, float(np.std(y)) * 0.05, 0.5)

    ss_res = float(np.sum(residuals**2))
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    r_squared = 1.0 - ss_res / ss_tot if ss_tot > 1e-12 else 0.0

    return ForceModel(
        coefficients=[float(c) for c in model.coef_],
        intercept=float(model.intercept_),
        residual_sigma=sigma,
        feature_names=names,
        r_squared=float(np.clip(r_squared, 0.0, 1.0)),
        n_points=len(y),
        mvc_reference_rms=float(mvc_reference_rms),
    )


def percent_mvc(rms: float, mvc_reference_rms: float) -> float:
    """Express an amplitude as a percentage of the patient's own maximum.

    The single most important normalization in the app: it is what makes
    readings comparable across sessions, across electrode placements, and
    between people. Computed server side so there is exactly one definition
    of percent MVC in the system.
    """
    if mvc_reference_rms <= 0:
        raise ValueError(f"mvc_reference_rms must be positive, got {mvc_reference_rms}")
    return float(np.clip(rms / mvc_reference_rms * 100.0, 0.0, 150.0))


__all__ = [
    "FORCE_FEATURES",
    "MIN_CALIBRATION_POINTS",
    "ForceModel",
    "fit",
    "percent_mvc",
]
