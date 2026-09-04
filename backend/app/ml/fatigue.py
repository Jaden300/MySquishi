"""M5: spectral fatigue estimator.

As a muscle fatigues, its motor units fire more slowly and conduction
velocity falls, which shifts the EMG power spectrum downward. Regressing
median frequency against repetition index turns that into a number: a
negative slope is objective evidence of fatigue rather than a subjective
impression.

This is a real, textbook technique, and it is the strongest technical claim
in the project. It is reported with its confidence interval, its R squared,
and its p value, so a weak or noisy trend is visible as weak rather than
presented as fact.

Two established indices are reported alongside:

- Thorstensson: the decline from peak to final repetition, as a percentage.
- Dimitrov: a spectral moment ratio weighted toward low frequency content.

No artifact is stored. The regression is fitted per session at request time.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import stats

from app.ml.explain import Explanation, Factor, Interval

# A slope steeper than this is treated as meaningful fatigue rather than
# measurement noise, provided it is also statistically significant.
FATIGUE_SLOPE_THRESHOLD = -1.0

# Below this many repetitions a trend line is not worth fitting.
MIN_REPS_FOR_TREND = 4

SIGNIFICANCE_LEVEL = 0.05


@dataclass(frozen=True)
class FatigueAssessment:
    """The fatigue picture for one session."""

    slope: Interval | None
    r_squared: float
    p_value: float
    thorstensson_index: float
    dimitrov_mean: float
    median_frequencies: list[float]
    fatigued: bool
    significant: bool
    explanation: Explanation

    def to_dict(self) -> dict[str, object]:
        return {
            "slope": self.slope.to_dict() if self.slope else None,
            "r_squared": round(self.r_squared, 4),
            "p_value": round(self.p_value, 5),
            "thorstensson_index": round(self.thorstensson_index, 2),
            "dimitrov_mean": round(self.dimitrov_mean, 6),
            "median_frequencies": [round(f, 2) for f in self.median_frequencies],
            "fatigued": self.fatigued,
            "significant": self.significant,
            "explanation": self.explanation.to_dict(),
        }


def thorstensson_index(peaks: list[float] | np.ndarray) -> float:
    """Percentage decline from the best repetition to the last one.

    A complementary view to the spectral measure: this one is about force
    output falling away, not about the spectrum shifting.
    """
    values = np.asarray(peaks, dtype=float)
    values = values[np.isfinite(values)]
    if values.size < 2:
        return 0.0

    best = float(values.max())
    if best <= 0:
        return 0.0
    return float((best - values[-1]) / best * 100.0)


def assess(
    median_frequencies: list[float] | np.ndarray,
    *,
    peak_amplitudes: list[float] | np.ndarray | None = None,
    dimitrov_indices: list[float] | np.ndarray | None = None,
) -> FatigueAssessment:
    """Fit the fatigue trend for one session.

    median_frequencies is one value per repetition, in order.
    """
    mdfs = np.asarray(median_frequencies, dtype=float)
    finite = np.isfinite(mdfs)
    usable = mdfs[finite]

    thorstensson = (
        thorstensson_index(peak_amplitudes) if peak_amplitudes is not None else 0.0
    )
    dimitrov_mean = (
        float(np.nanmean(dimitrov_indices))
        if dimitrov_indices is not None and len(dimitrov_indices)
        else 0.0
    )

    if usable.size < MIN_REPS_FOR_TREND:
        return FatigueAssessment(
            slope=None,
            r_squared=0.0,
            p_value=1.0,
            thorstensson_index=thorstensson,
            dimitrov_mean=dimitrov_mean,
            median_frequencies=[float(v) for v in mdfs],
            fatigued=False,
            significant=False,
            explanation=Explanation(
                summary=(
                    f"Not enough repetitions to assess fatigue. "
                    f"At least {MIN_REPS_FOR_TREND} are needed, and this "
                    f"session has {usable.size}."
                ),
                method="linear regression of median frequency on repetition index",
            ),
        )

    indices = np.arange(mdfs.size, dtype=float)[finite]
    result = stats.linregress(indices, usable)

    slope = float(result.slope)
    r_squared = float(result.rvalue**2)
    p_value = float(result.pvalue)

    # The standard error gives a proper interval on the slope, so a noisy
    # trend reports as uncertain rather than as a confident number.
    critical = stats.t.ppf(0.9, df=max(usable.size - 2, 1))
    margin = critical * float(result.stderr)

    slope_interval = Interval(
        point=slope,
        lower=slope - margin,
        upper=slope + margin,
        level=0.8,
        unit="Hz per rep",
    )

    significant = p_value < SIGNIFICANCE_LEVEL
    fatigued = significant and slope <= FATIGUE_SLOPE_THRESHOLD

    return FatigueAssessment(
        slope=slope_interval,
        r_squared=r_squared,
        p_value=p_value,
        thorstensson_index=thorstensson,
        dimitrov_mean=dimitrov_mean,
        median_frequencies=[float(v) for v in mdfs],
        fatigued=fatigued,
        significant=significant,
        explanation=_explain(slope, r_squared, p_value, usable.size, fatigued, significant),
    )


def _explain(
    slope: float,
    r_squared: float,
    p_value: float,
    n_reps: int,
    fatigued: bool,
    significant: bool,
) -> Explanation:
    if fatigued:
        summary = (
            f"Median frequency fell by {abs(slope):.1f} Hz per repetition across "
            f"{n_reps} repetitions. That downward shift is objective evidence of "
            "muscle fatigue."
        )
    elif significant and slope > 0:
        summary = (
            f"Median frequency rose by {slope:.1f} Hz per repetition. There is no "
            "sign of fatigue in this session."
        )
    elif significant:
        summary = (
            f"Median frequency fell slightly, by {abs(slope):.1f} Hz per repetition. "
            "The trend is real but too small to call fatigue."
        )
    else:
        summary = (
            f"No reliable fatigue trend across {n_reps} repetitions. The spectrum "
            "moved, but not consistently enough to separate from noise."
        )

    direction = "decreases" if slope < 0 else "increases"
    factors = [
        Factor(
            name="median_frequency_slope",
            contribution=slope,
            direction=direction,
            plain_text=f"the spectrum shifted {abs(slope):.1f} Hz per repetition",
        ),
        Factor(
            name="fit_quality",
            contribution=r_squared,
            direction="increases" if r_squared > 0.5 else "neutral",
            plain_text=(
                f"the trend explains {r_squared * 100:.0f} percent of the variation"
            ),
        ),
        Factor(
            name="significance",
            contribution=1.0 - p_value,
            direction="increases" if significant else "neutral",
            plain_text=(
                "the trend is statistically significant"
                if significant
                else "the trend is not statistically significant"
            ),
        ),
    ]

    return Explanation(
        summary=summary,
        factors=factors,
        method="linear regression of median frequency on repetition index",
    )


__all__ = [
    "FATIGUE_SLOPE_THRESHOLD",
    "MIN_REPS_FOR_TREND",
    "FatigueAssessment",
    "assess",
    "thorstensson_index",
]
