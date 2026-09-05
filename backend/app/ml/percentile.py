"""M14: cohort percentile normalization.

Places an absolute grip strength in context: empirical percentile curves by
age band and sex, with the EWGSOP2 screening thresholds as reference lines.

Two honesty requirements sit on this model, and both are structural rather
than left to the caller.

**The reference population is synthetic.** is_synthetic is hardcoded True on
every result, because there is no circumstance in which this reference is real
data, and the UI must label it.

**Some demographic cells are small.** The cohort has as few as twelve patients
in its smallest age band and sex combination, and a percentile computed from
twelve points is noise wearing a number's clothes. Cells below a minimum are
pooled across adjacent age bands, the result says that it pooled, and the
reference count is always reported.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from app.ml.explain import Explanation, Interval, bootstrap_interval

TRAINING_NOTES = (
    "Empirical percentile curves by age band and sex. Small cells are pooled "
    "across adjacent age bands and the result reports that it pooled."
)

# Below this many patients a cell is pooled with its neighbours.
MIN_CELL = 30

# EWGSOP2 low grip strength thresholds, in kilograms. A screening reference,
# not a diagnosis. See docs/CLINICAL.md.
EWGSOP2_THRESHOLDS = {"male": 27.0, "female": 16.0}

AGE_BAND_ORDER = ("18-34", "35-49", "50-64", "65-79", "80+")


@dataclass(frozen=True)
class PercentileResult:
    """Where a grip strength sits against the reference population."""

    percentile: Interval
    reference_group: str
    n_reference: int
    pooled: bool
    ewgsop2_threshold: float | None
    below_threshold: bool
    curve: list[dict[str, float]]
    explanation: Explanation
    # The reference is synthetic in every case, so this is not a parameter.
    is_synthetic: bool = True

    def to_dict(self) -> dict[str, object]:
        return {
            "percentile": self.percentile.to_dict(),
            "reference_group": self.reference_group,
            "n_reference": self.n_reference,
            "pooled": self.pooled,
            "ewgsop2_threshold": self.ewgsop2_threshold,
            "below_threshold": self.below_threshold,
            "curve": self.curve,
            "is_synthetic": self.is_synthetic,
            "explanation": self.explanation.to_dict(),
        }


def _ordinal(value: float) -> str:
    """1st, 22nd, 43rd, 11th. Written out because "22th" reads as a bug."""
    n = int(round(value))
    if 10 <= n % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def _neighbours(age_band: str) -> list[str]:
    """Adjacent age bands, nearest first, for pooling a small cell."""
    if age_band not in AGE_BAND_ORDER:
        return list(AGE_BAND_ORDER)

    index = AGE_BAND_ORDER.index(age_band)
    ordered = sorted(
        (b for b in AGE_BAND_ORDER if b != age_band),
        key=lambda b: abs(AGE_BAND_ORDER.index(b) - index),
    )
    return ordered


def train(
    cohort: pd.DataFrame,
    *,
    summary: pd.DataFrame | None = None,
    seed: int = 0,
) -> dict[str, object]:
    """Build the reference distributions. Returns the artifact to persist."""
    if summary is None:
        from app.sim.cohort_gen import patient_summary

        summary = patient_summary(cohort)

    # Reference values are each patient's final strength: where they got to,
    # which is what a percentile against a population should compare.
    cells: dict[str, list[float]] = {}
    for (sex, band), group in summary.groupby(["sex", "age_band"]):
        cells[f"{sex}|{band}"] = group["final_kg"].astype(float).tolist()

    return {
        "cells": cells,
        "features": ["strength_kg", "age_band", "sex"],
        "n_reference": int(len(summary)),
        "n_rows": int(len(summary)),
        # The metric train_all records: the size of the smallest cell, which
        # is the thing most worth knowing about this artifact.
        "min_cell": int(min((len(v) for v in cells.values()), default=0)),
    }


def reference_sample(
    cells: dict[str, list[float]],
    sex: str,
    age_band: str,
) -> tuple[list[float], str, bool]:
    """The comparison sample, pooling adjacent age bands when it is small."""
    key = f"{sex}|{age_band}"
    sample = list(cells.get(key, []))
    pooled = False

    if len(sample) < MIN_CELL:
        for neighbour in _neighbours(age_band):
            if len(sample) >= MIN_CELL:
                break
            extra = cells.get(f"{sex}|{neighbour}", [])
            if extra:
                sample.extend(extra)
                pooled = True

    group = f"{sex}, {age_band}" + (" and nearby age bands" if pooled else "")
    return sample, group, pooled


def assess(
    strength_kg: float,
    *,
    sex: str,
    age_band: str,
    artifact: dict[str, object] | None = None,
) -> PercentileResult:
    """Place a grip strength against the reference population."""
    if artifact is None:
        return _heuristic_assess(strength_kg, sex=sex, age_band=age_band)

    cells: dict[str, list[float]] = artifact["cells"]  # type: ignore[assignment]
    sample, group, pooled = reference_sample(cells, sex, age_band)

    if not sample:
        return _heuristic_assess(strength_kg, sex=sex, age_band=age_band)

    values = np.asarray(sample, dtype=float)
    percentile = float((values < strength_kg).mean() * 100.0)

    # The interval comes from resampling the reference itself: with a small
    # reference the percentile genuinely is uncertain, and this is where that
    # shows up rather than being asserted away.
    rng = np.random.default_rng(0)
    draws = [
        float((rng.choice(values, size=values.size, replace=True) < strength_kg).mean() * 100.0)
        for _ in range(200)
    ]
    interval = bootstrap_interval(
        draws, level=0.8, unit="percentile", point=percentile
    ).clamped(0.0, 100.0)

    threshold = EWGSOP2_THRESHOLDS.get(sex)
    below = threshold is not None and strength_kg < threshold

    curve = [
        {"percentile": float(p), "strength_kg": round(float(np.percentile(values, p)), 2)}
        for p in (5, 10, 25, 50, 75, 90, 95)
    ]

    return PercentileResult(
        percentile=interval,
        reference_group=group,
        n_reference=int(values.size),
        pooled=pooled,
        ewgsop2_threshold=threshold,
        below_threshold=bool(below),
        curve=curve,
        explanation=Explanation(
            summary=(
                f"Your {strength_kg:.1f} kg sits around the {_ordinal(percentile)} "
                f"percentile of {group}, from a synthetic reference of "
                f"{values.size} people."
                + (
                    " That is below the EWGSOP2 screening threshold, which is "
                    "a prompt to talk to a clinician rather than a diagnosis."
                    if below
                    else ""
                )
            ),
            method=(
                "empirical percentiles over a synthetic reference population"
                + (", pooled across adjacent age bands" if pooled else "")
            ),
        ),
    )


def _heuristic_assess(
    strength_kg: float,
    *,
    sex: str,
    age_band: str,
) -> PercentileResult:
    """Fallback that reports only what it can defend: the threshold check."""
    threshold = EWGSOP2_THRESHOLDS.get(sex)
    below = threshold is not None and strength_kg < threshold

    return PercentileResult(
        percentile=Interval(point=50.0, lower=0.0, upper=100.0, level=0.8, unit="percentile"),
        reference_group=f"{sex}, {age_band}",
        n_reference=0,
        pooled=False,
        ewgsop2_threshold=threshold,
        below_threshold=bool(below),
        curve=[],
        explanation=Explanation(
            summary=(
                "No reference population is available, so no percentile can be "
                "given. "
                + (
                    f"Your {strength_kg:.1f} kg is below the EWGSOP2 screening "
                    "threshold, which is worth raising with a clinician."
                    if below
                    else f"Your {strength_kg:.1f} kg is above the EWGSOP2 screening threshold."
                )
            ),
            method="heuristic fallback, no reference population available",
        ),
    )


__all__ = [
    "EWGSOP2_THRESHOLDS",
    "reference_sample",
    "MIN_CELL",
    "PercentileResult",
    "assess",
    "train",
]
