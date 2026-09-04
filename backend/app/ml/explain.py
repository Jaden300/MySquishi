"""Explanation and uncertainty primitives.

Two ideas the whole ML layer is built on:

`Interval` is how every prediction leaves a model. There is no path that
returns a bare float, because a point estimate with the uncertainty stripped
off is the dishonest way to report a model. See docs/ML.md.

`Explanation` is the single shape every model uses to say what drove its
output. Tree models explain through permutation importance, linear models
through their coefficients, and rule systems by reporting the rules they
fired. The UI renders all three identically.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

import numpy as np

Direction = Literal["increases", "decreases", "neutral"]


@dataclass(frozen=True)
class Interval:
    """A prediction with its uncertainty.

    `level` is the nominal coverage, so 0.8 means an 80 percent interval.
    Bounds are validated on construction: a model that produces an inverted
    interval has a bug, and it should surface here rather than in a chart.
    """

    point: float
    lower: float
    upper: float
    level: float = 0.8
    unit: str = ""

    def __post_init__(self) -> None:
        if not np.isfinite([self.point, self.lower, self.upper]).all():
            raise ValueError(
                f"interval must be finite, got point={self.point} "
                f"lower={self.lower} upper={self.upper}"
            )
        if not self.lower <= self.point <= self.upper:
            raise ValueError(
                f"interval must satisfy lower <= point <= upper, got "
                f"{self.lower} <= {self.point} <= {self.upper}"
            )
        if not 0.0 < self.level < 1.0:
            raise ValueError(f"level must be within 0 to 1, got {self.level}")

    @property
    def width(self) -> float:
        return self.upper - self.lower

    def clamped(self, low: float, high: float) -> Interval:
        """Restrict to a valid range, keeping the ordering intact.

        Used where a model's arithmetic can wander outside the meaningful
        range of the quantity, such as a percentage below zero.
        """
        return Interval(
            point=float(np.clip(self.point, low, high)),
            lower=float(np.clip(self.lower, low, high)),
            upper=float(np.clip(self.upper, low, high)),
            level=self.level,
            unit=self.unit,
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "point": round(self.point, 4),
            "lower": round(self.lower, 4),
            "upper": round(self.upper, 4),
            "level": self.level,
            "unit": self.unit,
        }


@dataclass(frozen=True)
class Factor:
    """One contributor to a model's output."""

    name: str
    contribution: float
    direction: Direction
    plain_text: str

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "contribution": round(self.contribution, 4),
            "direction": self.direction,
            "plain_text": self.plain_text,
        }


@dataclass(frozen=True)
class Explanation:
    """Why a model said what it said.

    Every model output surfaced to a user carries one of these. The method
    field is named so the About page can state honestly how each explanation
    was produced.
    """

    summary: str
    factors: list[Factor] = field(default_factory=list)
    method: str = ""

    @property
    def top_factor(self) -> Factor | None:
        return self.factors[0] if self.factors else None

    def to_dict(self) -> dict[str, object]:
        return {
            "summary": self.summary,
            "factors": [f.to_dict() for f in self.factors],
            "method": self.method,
        }


# Human readable names for the feature keys the models consume. Feature names
# leak into the UI through explanations, and "hold_cv" means nothing to a
# patient.
FEATURE_LABELS: dict[str, str] = {
    "rms": "signal amplitude",
    "mav": "average signal level",
    "zero_crossings": "signal crossings",
    "slope_sign_changes": "signal direction changes",
    "waveform_length": "signal complexity",
    "saturation_ratio": "clipping",
    "baseline_drift": "baseline drift",
    "mains_ratio": "mains interference",
    "snr_estimate": "signal to noise ratio",
    "peak_mvc": "peak effort",
    "mean_mvc": "average effort",
    "time_to_peak_s": "time to peak",
    "rfd": "rate of force development",
    "duration_s": "contraction length",
    "relaxation_time_s": "relaxation time",
    "hold_cv": "hold steadiness",
    "plateau_flatness": "hold flatness",
    "impulse": "total work",
    "median_frequency": "median frequency",
    "mean_frequency": "mean frequency",
    "dimitrov_index": "spectral fatigue index",
    "fatigue_slope": "fatigue trend",
    "rep_count": "repetitions completed",
    "sqi_mean": "signal quality",
    "adherence_gap_days": "days since last session",
    "adherence_rate": "adherence",
    "completion_rate": "session completion",
    "sessions_completed": "sessions completed",
    "days_since_last": "days since last session",
    "recent_trend": "recent trend",
    "weeks_elapsed": "weeks in programme",
    "initial_slope": "early progress",
    "final_ratio": "overall gain",
    "time_to_80pct": "time to most of the gain",
    "plateau_index": "plateau",
    "variability": "session to session variability",
}


def label_for(feature: str) -> str:
    """Human readable name for a feature key."""
    return FEATURE_LABELS.get(feature, feature.replace("_", " "))


def _direction(value: float, tolerance: float = 1e-9) -> Direction:
    if value > tolerance:
        return "increases"
    if value < -tolerance:
        return "decreases"
    return "neutral"


def coefficient_factors(
    coefficients: np.ndarray | list[float],
    feature_names: list[str],
    *,
    feature_values: np.ndarray | list[float] | None = None,
    top_n: int = 3,
) -> list[Factor]:
    """Explain a linear model from its coefficients.

    When feature_values are supplied the contribution is coefficient times
    value, which is what actually moved this particular prediction. Without
    them the coefficient alone describes the model's general behaviour.
    """
    coefs = np.asarray(coefficients, dtype=float).ravel()
    if coefs.size != len(feature_names):
        raise ValueError(
            f"{coefs.size} coefficients for {len(feature_names)} feature names"
        )

    if feature_values is not None:
        values = np.asarray(feature_values, dtype=float).ravel()
        if values.size != coefs.size:
            raise ValueError(f"{values.size} values for {coefs.size} coefficients")
        contributions = coefs * values
    else:
        contributions = coefs

    order = np.argsort(np.abs(contributions))[::-1][:top_n]

    factors = []
    for i in order:
        contribution = float(contributions[i])
        direction = _direction(contribution)
        name = feature_names[i]
        label = label_for(name)

        if direction == "increases":
            text = f"higher {label} pushed this up"
        elif direction == "decreases":
            text = f"higher {label} pulled this down"
        else:
            text = f"{label} had little effect"

        factors.append(
            Factor(
                name=name,
                contribution=contribution,
                direction=direction,
                plain_text=text,
            )
        )

    return factors


def permutation_factors(
    model,
    X: np.ndarray,
    y: np.ndarray,
    feature_names: list[str],
    *,
    top_n: int = 3,
    n_repeats: int = 5,
    random_state: int = 0,
) -> list[Factor]:
    """Explain a tree model by permutation importance.

    Shuffling one feature and measuring the drop in score says how much the
    model relied on it. Preferred over SHAP here: it is model agnostic, it
    ships with scikit-learn, and it is fast enough to run on request.
    """
    from sklearn.inspection import permutation_importance

    if X.shape[1] != len(feature_names):
        raise ValueError(
            f"{X.shape[1]} columns for {len(feature_names)} feature names"
        )

    result = permutation_importance(
        model,
        X,
        y,
        n_repeats=n_repeats,
        random_state=random_state,
        scoring=None,
    )

    importances = np.asarray(result.importances_mean, dtype=float)
    order = np.argsort(importances)[::-1][:top_n]

    factors = []
    for i in order:
        importance = float(importances[i])
        label = label_for(feature_names[i])
        factors.append(
            Factor(
                name=feature_names[i],
                contribution=importance,
                # Permutation importance is unsigned: it measures reliance,
                # not the direction of the effect.
                direction="increases" if importance > 1e-9 else "neutral",
                plain_text=(
                    f"{label} mattered most" if importance > 1e-9
                    else f"{label} had little effect"
                ),
            )
        )

    return factors


def bootstrap_interval(
    samples: np.ndarray | list[float],
    *,
    level: float = 0.8,
    unit: str = "",
    point: float | None = None,
) -> Interval:
    """An interval from a set of draws, using empirical percentiles.

    The general purpose path for models whose uncertainty comes from
    resampling rather than from a closed form.
    """
    draws = np.asarray(samples, dtype=float).ravel()
    draws = draws[np.isfinite(draws)]
    if draws.size == 0:
        raise ValueError("cannot build an interval from zero finite samples")

    tail = (1.0 - level) / 2.0
    lower = float(np.percentile(draws, tail * 100))
    upper = float(np.percentile(draws, (1.0 - tail) * 100))
    centre = float(np.median(draws)) if point is None else float(point)

    # A supplied point estimate can sit outside the empirical percentiles
    # when the draws are skewed. Widen rather than reject: the point is the
    # model's answer and the interval is the uncertainty around it.
    lower = min(lower, centre)
    upper = max(upper, centre)

    return Interval(point=centre, lower=lower, upper=upper, level=level, unit=unit)
