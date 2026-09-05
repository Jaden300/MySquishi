"""M8: adaptive session prescriber.

A rule engine, not an estimator. It sets the next session's target percent
MVC, repetition count, hold duration and rest interval from recent
performance, fatigue, anomalies and adherence.

Every rule that fires appends its own reason in plain language, so the numbers
are never bare. A prescription a patient cannot interrogate is one they have
to take on trust, and the whole point of this app is not asking for that.

Rules are ordered and deterministic. Safety rules run last so they cannot be
overridden by an optimistic progression rule earlier in the list.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.ml.explain import Explanation

# The starting point for someone with no history.
DEFAULT_TARGET_MVC = 50.0
DEFAULT_REPS = 10
DEFAULT_HOLD_S = 5.0
DEFAULT_REST_S = 5.0

# Bounds. The prescriber never leaves this range whatever the rules say.
MIN_TARGET_MVC = 25.0
MAX_TARGET_MVC = 80.0
MIN_REPS = 5
MAX_REPS = 15


@dataclass
class Prescription:
    """What to do next, and why."""

    target_mvc_pct: float = DEFAULT_TARGET_MVC
    rep_count: int = DEFAULT_REPS
    hold_s: float = DEFAULT_HOLD_S
    rest_s: float = DEFAULT_REST_S
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "target_mvc_pct": round(self.target_mvc_pct, 1),
            "rep_count": self.rep_count,
            "hold_s": round(self.hold_s, 1),
            "rest_s": round(self.rest_s, 1),
            "reasons": list(self.reasons),
        }


def prescribe(
    *,
    recent_quality: list[float] | None = None,
    fatigue_slope: float | None = None,
    last_target_mvc: float | None = None,
    anomaly_direction: str | None = None,
    adherence_risk: float | None = None,
    last_sqi: float | None = None,
) -> tuple[Prescription, Explanation]:
    """Build the next session's prescription.

    Every argument is optional: a new patient has none of this history, and
    the defaults are a sensible starting session.
    """
    plan = Prescription(target_mvc_pct=last_target_mvc or DEFAULT_TARGET_MVC)
    quality = recent_quality or []

    # 1. Progression. Three good sessions earns a step up.
    if len(quality) >= 3 and all(score >= 80 for score in quality[-3:]):
        plan.target_mvc_pct += 5.0
        plan.reasons.append(
            "Your last three sessions were all well executed, so the target "
            "goes up slightly."
        )
    elif len(quality) >= 2 and all(score < 50 for score in quality[-2:]):
        # Struggling. Back off rather than pushing through.
        plan.target_mvc_pct -= 5.0
        plan.reasons.append(
            "The last couple of sessions were a struggle, so the target comes "
            "down a little. Consistency matters more than intensity."
        )

    # 2. Fatigue. A meaningfully negative median frequency slope means the
    # muscle was tiring within the session.
    if fatigue_slope is not None and fatigue_slope < -0.5:
        plan.target_mvc_pct -= 10.0
        plan.rest_s += 3.0
        plan.reasons.append(
            "You fatigued noticeably during your last session, so this one "
            "eases off and rests longer between repetitions."
        )

    # 3. Anomalies. A negative one is a reason to hold steady, not to push.
    if anomaly_direction == "negative":
        plan.reasons.append(
            "Your last session did not fit your usual pattern, so the targets "
            "stay where they are while things settle."
        )
        plan.target_mvc_pct = last_target_mvc or DEFAULT_TARGET_MVC
    elif anomaly_direction == "positive":
        plan.reasons.append(
            "Your last session was a standout. This one keeps the same shape "
            "so it is not a one off."
        )

    # 4. Adherence. Lower the barrier rather than the ambition: a shorter
    # session that happens beats a longer one that does not.
    if adherence_risk is not None and adherence_risk >= 0.6:
        plan.rep_count = max(MIN_REPS, plan.rep_count - 3)
        plan.reasons.append(
            "This is a shorter session. Getting started is the hard part, and "
            "a short session done is worth more than a long one skipped."
        )

    # 5. Signal quality, last so it cannot be overridden. When the last
    # reading could not be trusted, changing the targets would mean acting on
    # a measurement that was not real.
    if last_sqi is not None and last_sqi < 60:
        plan.target_mvc_pct = last_target_mvc or DEFAULT_TARGET_MVC
        plan.reasons.append(
            "The signal quality was poor last time, so the targets are "
            "unchanged. Check the electrode placement before this session."
        )

    if not plan.reasons:
        plan.reasons.append(
            "Carrying on with what has been working. Nothing suggests a change."
        )

    plan.target_mvc_pct = float(
        min(MAX_TARGET_MVC, max(MIN_TARGET_MVC, plan.target_mvc_pct))
    )
    plan.rep_count = int(min(MAX_REPS, max(MIN_REPS, plan.rep_count)))

    explanation = Explanation(
        summary=(
            f"Next session: {plan.rep_count} repetitions at about "
            f"{plan.target_mvc_pct:.0f} percent of your maximum, holding for "
            f"{plan.hold_s:.0f} seconds with {plan.rest_s:.0f} seconds rest."
        ),
        method="rule engine, reporting the rules it fired",
    )

    return plan, explanation


__all__ = [
    "DEFAULT_TARGET_MVC",
    "Prescription",
    "prescribe",
]
