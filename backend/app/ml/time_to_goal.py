"""M10: time to goal.

Samples M9's posterior and finds the first week each draw crosses the goal.

**The share of draws that never cross is reported, never dropped.** It is the
easy mistake here: take the draws that do cross, take their median, print a
confident "about nine weeks". If most draws never reach the goal at all, that
number describes only the optimistic minority and the honest answer is that
the goal is unlikely on the current trajectory. Silently conditioning on
success would turn a warning into an encouragement. See docs/ML.md.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from app.ml.explain import Explanation, Interval
from app.ml.forecast import TrajectoryForecast

# Beyond this the projection is not worth reporting on.
DEFAULT_HORIZON_WEEKS = 26

# Above this share of non crossing draws, no median is reported at all.
UNLIKELY_SHARE = 0.5


@dataclass(frozen=True)
class TimeToGoalResult:
    """How long until the goal, and how confident that is."""

    weeks: Interval | None
    never_crosses_share: float
    goal_kg: float
    reachable: bool
    explanation: Explanation

    def to_dict(self) -> dict[str, object]:
        return {
            "weeks": self.weeks.to_dict() if self.weeks else None,
            "never_crosses_share": round(self.never_crosses_share, 3),
            "goal_kg": self.goal_kg,
            "reachable": self.reachable,
            "explanation": self.explanation.to_dict(),
        }


def estimate(
    forecast: TrajectoryForecast,
    goal_kg: float,
    *,
    horizon_weeks: int = DEFAULT_HORIZON_WEEKS,
) -> TimeToGoalResult:
    """When the goal is likely to be reached, if it is."""
    if forecast.insufficient_data or forecast.draws is None:
        return TimeToGoalResult(
            weeks=None,
            never_crosses_share=1.0,
            goal_kg=goal_kg,
            reachable=False,
            explanation=Explanation(
                summary=(
                    "There is not enough history yet to estimate when you will "
                    "reach your goal."
                ),
                method="not fitted",
            ),
        )

    draws = np.asarray(forecast.draws, dtype=float)
    weeks_axis = np.array([p.week for p in forecast.forecast], dtype=float)

    # First crossing per draw. A draw that never crosses contributes to the
    # share rather than to the median.
    crossings: list[float] = []
    never = 0

    for draw in draws:
        above = np.where(draw >= goal_kg)[0]
        if above.size:
            crossings.append(float(weeks_axis[above[0]]))
        else:
            never += 1

    never_share = never / len(draws) if len(draws) else 1.0

    # Already there.
    if forecast.history and forecast.history[-1] >= goal_kg:
        return TimeToGoalResult(
            weeks=Interval(point=0.0, lower=0.0, upper=0.0, level=0.8, unit="weeks"),
            never_crosses_share=0.0,
            goal_kg=goal_kg,
            reachable=True,
            explanation=Explanation(
                summary="You have already reached your goal.",
                method="observed directly, no projection needed",
            ),
        )

    if never_share > UNLIKELY_SHARE or not crossings:
        # No median is reported. One computed from the minority that crossed
        # would be an encouraging number describing an unlikely outcome.
        return TimeToGoalResult(
            weeks=None,
            never_crosses_share=never_share,
            goal_kg=goal_kg,
            reachable=False,
            explanation=Explanation(
                summary=(
                    f"On your current trajectory, {goal_kg:.1f} kg is unlikely "
                    f"within the next {horizon_weeks} weeks: only "
                    f"{(1 - never_share) * 100:.0f} percent of projections "
                    "reach it. That is worth discussing with your clinician, "
                    "and it may mean the goal or the programme should change "
                    "rather than that you are doing something wrong."
                ),
                method="posterior sampling from the fitted trajectory",
            ),
        )

    values = np.array(crossings, dtype=float)
    median = float(np.median(values))
    interval = Interval(
        point=median,
        lower=float(np.percentile(values, 10)),
        upper=float(np.percentile(values, 90)),
        level=0.8,
        unit="weeks",
    )

    caveat = (
        ""
        if never_share < 0.05
        else (
            f" About {never_share * 100:.0f} percent of projections do not "
            "reach it within the horizon at all."
        )
    )

    return TimeToGoalResult(
        weeks=interval,
        never_crosses_share=never_share,
        goal_kg=goal_kg,
        reachable=True,
        explanation=Explanation(
            summary=(
                f"At your current rate you would reach {goal_kg:.1f} kg in "
                f"around {median:.0f} weeks, most likely between "
                f"{interval.lower:.0f} and {interval.upper:.0f}.{caveat}"
            ),
            method="posterior sampling from the fitted trajectory",
        ),
    )


__all__ = ["DEFAULT_HORIZON_WEEKS", "TimeToGoalResult", "estimate"]
