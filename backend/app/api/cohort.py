"""Cohort routes.

Everything here describes the synthetic reference population, so every
response carries is_synthetic and the UI labels it.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.ml.percentile import EWGSOP2_THRESHOLDS
from app.ml.registry import registry
from app.sim.cohort_gen import ARCHETYPE_LABELS, COHORT_VERSION

router = APIRouter(prefix="/api/cohort", tags=["cohort"])


@router.get("/summary")
def get_summary() -> dict[str, object]:
    """What the reference population is made of."""
    artifact = registry.try_load("M12")

    counts: dict[str, int] = {}
    if artifact:
        for point in artifact["points"]:
            name = point["archetype"]
            counts[name] = counts.get(name, 0) + 1

    return {
        "version": COHORT_VERSION,
        "n_patients": sum(counts.values()),
        "archetypes": [
            {
                "id": key,
                "label": ARCHETYPE_LABELS[key],
                "count": counts.get(key, 0),
            }
            for key in ARCHETYPE_LABELS
        ],
        "is_synthetic": True,
        "note": (
            "This population was generated to demonstrate the app. It does not "
            "describe real people and is not a clinical reference."
        ),
    }


@router.get("/percentiles")
def get_percentiles(age_band: str, sex: str) -> dict[str, object]:
    """The reference distribution for one demographic group."""
    artifact = registry.try_load("M14")
    if artifact is None:
        raise HTTPException(
            status_code=503,
            detail=(
                "The reference population has not been built yet. Run "
                "python -m app.ml.train_all."
            ),
        )

    from app.ml.percentile import reference_sample

    sample, group, pooled = reference_sample(
        artifact["cells"], sex, age_band  # type: ignore[arg-type]
    )
    if not sample:
        raise HTTPException(
            status_code=404, detail=f"No reference data for {sex}, {age_band}."
        )

    import numpy as np

    values = np.asarray(sample, dtype=float)

    return {
        "reference_group": group,
        "n_reference": int(values.size),
        "pooled": pooled,
        "ewgsop2_threshold": EWGSOP2_THRESHOLDS.get(sex),
        "curve": [
            {
                "percentile": int(p),
                "strength_kg": round(float(np.percentile(values, p)), 2),
            }
            for p in (5, 10, 25, 50, 75, 90, 95)
        ],
        "histogram": [
            {"strength_kg": round(float(edge), 1), "count": int(count)}
            for count, edge in zip(*np.histogram(values, bins=12))
        ],
        "is_synthetic": True,
    }


__all__ = ["router"]
