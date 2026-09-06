"""Which claims are honest for which muscle.

Phase 2 measured that this rig resolves how hard a muscle is working and not
which motion produced it. Effort grading and fatigue are properties of motor
unit recruitment, so they generalize to any skeletal muscle. That is what turns
a grip device into a general strength and fatigue trainer.

Kilograms and population percentiles do not generalize, and this module is why.

`app/ml/percentile.py` carries the EWGSOP2 low grip strength thresholds
(27.0 kg male, 16.0 kg female). Those are sarcopenia screening references
validated on **hand dynamometry**, and they are meaningless on a biceps or a
calf. `app/ml/force.py` maps sEMG amplitude to kilograms through a fit that
belongs to one muscle on one person. Reporting either against a non grip muscle
would be a false clinical claim, which CLAUDE.md forbids outright.

So the rule, from docs/HARDWARE_FINDINGS.md:

| Claim                       | forearm_grip | Any other muscle |
|-----------------------------|--------------|------------------|
| Force in kilograms          | yes          | **no**           |
| EWGSOP2 status              | yes          | **no**           |
| Population percentile       | yes          | **no**           |
| Percent MVC                 | yes          | yes              |
| Fatigue, median frequency   | yes          | yes              |
| Rep counts and timing       | yes          | yes              |
| Effort consistency          | yes          | yes              |

The gate lives in the API layer so a frontend bug cannot bypass it, and the
gated fields are **omitted** from responses rather than sent as null, so a UI
mistake cannot render a stale value from a previous grip session.
"""

from __future__ import annotations

from fastapi import HTTPException

# The muscle every session defaults to, and the only one kilograms are valid
# for. A session recorded before the muscle selector existed was a grip
# session, so this default is also correct for old rows.
GRIP = "forearm_grip"
DEFAULT_MUSCLE = GRIP

# What the selector offers. "other" is deliberately included: someone training
# a muscle not on this list still gets percent MVC, fatigue and rep counts,
# which is everything that is honest for an uncharacterised site.
MUSCLES: tuple[str, ...] = (GRIP, "biceps", "calf", "other")

MUSCLE_LABELS: dict[str, str] = {
    GRIP: "Forearm, grip",
    "biceps": "Biceps",
    "calf": "Calf",
    "other": "Other muscle",
}

# Shown wherever a kilogram claim has been withheld, so the absence reads as a
# deliberate clinical decision rather than as missing data.
NON_GRIP_NOTE = (
    "Force in kilograms and population percentiles are validated on hand "
    "dynamometry, so they are only reported for forearm grip. Percent of your "
    "own maximum, fatigue and repetition counts are valid for every muscle."
)


def normalize(muscle: str | None) -> str:
    """Coerce a muscle to a known value, defaulting to grip.

    An unrecognised muscle becomes "other" rather than an error: the honest
    response to an unknown site is to withhold the grip only claims, which is
    exactly what "other" does.
    """
    if muscle is None:
        return DEFAULT_MUSCLE
    candidate = muscle.strip().lower()
    if candidate in MUSCLES:
        return candidate
    return "other" if candidate else DEFAULT_MUSCLE


def is_grip(muscle: str | None) -> bool:
    """True when kilogram based claims are valid for this muscle."""
    return normalize(muscle) == GRIP


def allows_kilograms(muscle: str | None) -> bool:
    """Force in kg, EWGSOP2 status and population percentile, together.

    They stand or fall as one: each depends on the same hand dynamometry
    validation, so there is no muscle where one is honest and another is not.
    """
    return is_grip(muscle)


def require_grip(muscle: str | None, claim: str) -> None:
    """Refuse a kilogram based claim on a non grip muscle.

    Raises HTTPException rather than returning a flag so a caller cannot
    forget to check. In `app/api/ml.py` the insights assembler already
    swallows HTTPException per card, so a gated claim is simply not shown
    there, which is the correct behaviour and needs no extra handling.
    """
    if allows_kilograms(muscle):
        return

    label = MUSCLE_LABELS.get(normalize(muscle), normalize(muscle))
    raise HTTPException(
        status_code=409,
        detail=(
            f"{claim} is not reported for {label}. {NON_GRIP_NOTE}"
        ),
    )


__all__ = [
    "DEFAULT_MUSCLE",
    "GRIP",
    "MUSCLES",
    "MUSCLE_LABELS",
    "NON_GRIP_NOTE",
    "allows_kilograms",
    "is_grip",
    "normalize",
    "require_grip",
]
