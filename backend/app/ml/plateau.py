"""M11: plateau and changepoint detection.

A two sided CUSUM over the detrended strength series, returning candidate
changepoints with the mean slope either side, and a plateau verdict when the
slope after the changepoint has a confidence interval containing zero.

Detrending first is what makes this a plateau detector rather than a progress
detector. A patient improving steadily has a large positive drift, and a raw
CUSUM would flag that immediately; against the trend, only a genuine change in
the rate of change registers.

The verdict is deliberately conservative. Telling someone they have plateaued
when they have had two flat weeks is discouraging and wrong, so a plateau is
declared only when the post changepoint slope is statistically
indistinguishable from zero.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from app.ml.explain import Explanation, Interval

# CUSUM slack and threshold, in standard deviations of the detrended series.
SLACK_SD = 0.5
THRESHOLD_SD = 5.0

# A segment shorter than this cannot support a slope estimate worth reporting.
MIN_SEGMENT = 4


@dataclass(frozen=True)
class Changepoint:
    """Where the trend changed, and what it changed from and to."""

    index: int
    slope_before: float
    slope_after: float
    drift_magnitude: float

    def to_dict(self) -> dict[str, object]:
        return {
            "index": self.index,
            "slope_before": round(self.slope_before, 4),
            "slope_after": round(self.slope_after, 4),
            "drift_magnitude": round(self.drift_magnitude, 4),
        }


@dataclass(frozen=True)
class PlateauResult:
    """Whether progress has levelled off."""

    changepoints: list[Changepoint]
    is_plateau: bool
    recent_slope: Interval
    explanation: Explanation

    def to_dict(self) -> dict[str, object]:
        return {
            "changepoints": [c.to_dict() for c in self.changepoints],
            "is_plateau": self.is_plateau,
            "recent_slope": self.recent_slope.to_dict(),
            "explanation": self.explanation.to_dict(),
        }


def _slope_interval(y: np.ndarray, level: float = 0.8) -> Interval:
    """A slope with its confidence interval, from the regression standard error."""
    from scipy import stats

    if y.size < 3:
        return Interval(point=0.0, lower=-1.0, upper=1.0, level=level, unit="kg per session")

    x = np.arange(y.size, dtype=float)
    result = stats.linregress(x, y)

    # 1.28 standard errors is the 80 percent interval.
    margin = 1.28 * float(result.stderr)
    slope = float(result.slope)

    return Interval(
        point=slope,
        lower=slope - margin,
        upper=slope + margin,
        level=level,
        unit="kg per session",
    )


def detect(strengths: list[float] | np.ndarray) -> PlateauResult:
    """Find changepoints and decide whether progress has levelled off."""
    y = np.asarray(strengths, dtype=float)
    y = y[np.isfinite(y)]

    if y.size < MIN_SEGMENT * 2:
        return PlateauResult(
            changepoints=[],
            is_plateau=False,
            recent_slope=_slope_interval(y),
            explanation=Explanation(
                summary=(
                    "Not enough sessions yet to say whether your progress has "
                    "levelled off."
                ),
                method="not enough data for changepoint detection",
            ),
        )

    # Detrend: CUSUM then responds to a change in the rate, not to progress.
    x = np.arange(y.size, dtype=float)
    trend = np.polyval(np.polyfit(x, y, 1), x)
    residual = y - trend

    sd = float(np.std(residual))
    if sd < 1e-9:
        sd = 1e-9

    slack = SLACK_SD * sd
    threshold = THRESHOLD_SD * sd

    # Two sided CUSUM. Accumulates deviation in each direction, resetting at
    # zero, and fires when either accumulator crosses the threshold.
    high = low = 0.0
    candidates: list[int] = []

    for i, value in enumerate(residual):
        high = max(0.0, high + value - slack)
        low = min(0.0, low + value + slack)

        if high > threshold or low < -threshold:
            # Keep changepoints separated so one shift is reported once.
            if not candidates or i - candidates[-1] >= MIN_SEGMENT:
                candidates.append(i)
            high = low = 0.0

    changepoints = []
    for index in candidates:
        if index < MIN_SEGMENT or index > y.size - MIN_SEGMENT:
            continue

        before = _slope_interval(y[:index]).point
        after = _slope_interval(y[index:]).point
        changepoints.append(
            Changepoint(
                index=index,
                slope_before=before,
                slope_after=after,
                drift_magnitude=abs(after - before),
            )
        )

    # The verdict rests on the most recent segment: what is happening now.
    tail_start = changepoints[-1].index if changepoints else max(0, y.size - 8)
    recent_slope = _slope_interval(y[tail_start:])

    # A plateau means the recent slope cannot be distinguished from zero.
    is_plateau = (
        y.size - tail_start >= MIN_SEGMENT
        and recent_slope.lower <= 0.0 <= recent_slope.upper
    )

    return PlateauResult(
        changepoints=changepoints,
        is_plateau=is_plateau,
        recent_slope=recent_slope,
        explanation=Explanation(
            summary=_summary(is_plateau, recent_slope, changepoints),
            method=(
                f"two sided CUSUM over the detrended series, slack {SLACK_SD} "
                f"and threshold {THRESHOLD_SD} standard deviations"
            ),
        ),
    )


def _summary(
    is_plateau: bool,
    slope: Interval,
    changepoints: list[Changepoint],
) -> str:
    if is_plateau:
        base = (
            "Your recent sessions have levelled off: the trend over them is "
            "not distinguishable from flat."
        )
        if changepoints:
            base += (
                f" The change appears around session {changepoints[-1].index + 1}."
            )
        return (
            base
            + " A plateau usually means the programme needs to change rather "
            "than that you need to try harder. Worth raising with your "
            "clinician."
        )

    direction = "upward" if slope.point > 0 else "downward"
    return (
        f"Your recent sessions are still trending {direction}, at around "
        f"{slope.point:.2f} kg per session. No plateau detected."
    )


__all__ = ["Changepoint", "PlateauResult", "detect"]
