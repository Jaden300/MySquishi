"""M12: recovery archetype clustering.

KMeans over per patient trajectory shape features, reduced to two dimensions
by PCA so the cohort scatter has stable coordinates.

The features are deliberately scale free: initial slope, final to initial
ratio, time to eighty percent of the gain, plateau index and variability.
Clustering keys on the shape of a recovery rather than on how strong the
patient happens to be, so a strong plateaued patient and a weak plateaued
patient land together.

**KMeans label order is not stable across refits.** Cluster 0 is not reliably
the fast responder next time, so archetype names are derived from centroid
geometry at fit time and that map is persisted inside the artifact. Nothing
downstream may key on a cluster index. See docs/ML.md.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from app.ml.explain import Explanation, Factor, label_for

TRAINING_NOTES = (
    "KMeans over scale free trajectory shape features. Archetype names are "
    "mapped from centroid geometry at fit time, never from cluster index."
)

SHAPE_FEATURES: tuple[str, ...] = (
    "initial_slope",
    "final_ratio",
    "time_to_80pct",
    "plateau_index",
    "variability",
)

ARCHETYPE_LABELS = {
    "fast_responder": "Fast responder",
    "steady_climber": "Steady climber",
    "late_bloomer": "Late bloomer",
    "plateaued": "Plateaued",
}

ARCHETYPE_DESCRIPTIONS = {
    "fast_responder": (
        "Quick early gains that settle at a good level. Most of your progress "
        "came early."
    ),
    "steady_climber": (
        "Steady improvement throughout, without a dramatic early jump or a "
        "stall."
    ),
    "late_bloomer": (
        "A slow start that picked up later. The early weeks understated where "
        "this was going."
    ),
    "plateaued": (
        "Early gains that have levelled off short of the goal. This is the "
        "signal for a change of protocol, not a reason to push harder."
    ),
}


@dataclass(frozen=True)
class ArchetypeResult:
    """Which recovery shape a patient's trajectory resembles."""

    archetype: str
    label: str
    description: str
    coordinates: tuple[float, float]
    confidence: float
    explanation: Explanation

    def to_dict(self) -> dict[str, object]:
        return {
            "archetype": self.archetype,
            "label": self.label,
            "description": self.description,
            "coordinates": list(self.coordinates),
            "confidence": round(self.confidence, 3),
            "explanation": self.explanation.to_dict(),
        }


def _name_clusters(centroids: np.ndarray, feature_names: list[str]) -> dict[int, str]:
    """Map cluster indices to archetype names from centroid geometry.

    Assigned greedily in order of how distinctive each archetype is, so every
    name is used exactly once:

    - plateaued: the highest plateau index, which is what plateauing means
    - fast_responder: reaches eighty percent of its gain earliest
    - late_bloomer: reaches it latest
    - steady_climber: whatever remains

    This is what makes the mapping survive a refit. The centroids move a
    little between fits, but their ordering on these axes does not.
    """
    columns = {name: i for i, name in enumerate(feature_names)}
    remaining = set(range(centroids.shape[0]))
    mapping: dict[int, str] = {}

    def take(name: str, column: str, *, largest: bool) -> None:
        if not remaining:
            return
        values = {i: centroids[i, columns[column]] for i in remaining}
        chosen = (max if largest else min)(values, key=values.get)  # type: ignore[arg-type]
        mapping[chosen] = name
        remaining.discard(chosen)

    take("plateaued", "plateau_index", largest=True)
    take("fast_responder", "time_to_80pct", largest=False)
    take("late_bloomer", "time_to_80pct", largest=True)

    for index in sorted(remaining):
        mapping[index] = "steady_climber"

    return mapping


def train(
    cohort: pd.DataFrame,
    *,
    summary: pd.DataFrame | None = None,
    seed: int = 0,
) -> dict[str, object]:
    """Fit the clustering. Returns the artifact to persist."""
    from sklearn.cluster import KMeans
    from sklearn.decomposition import PCA
    from sklearn.metrics import silhouette_score
    from sklearn.preprocessing import StandardScaler

    if summary is None:
        from app.sim.cohort_gen import patient_summary

        summary = patient_summary(cohort)

    features = list(SHAPE_FEATURES)
    X = summary[features].to_numpy(dtype=float)

    scaler = StandardScaler().fit(X)
    scaled = scaler.transform(X)

    kmeans = KMeans(n_clusters=4, n_init=10, random_state=seed).fit(scaled)
    labels = kmeans.labels_

    pca = PCA(n_components=2, random_state=seed).fit(scaled)
    coordinates = pca.transform(scaled)

    label_map = _name_clusters(kmeans.cluster_centers_, features)

    # The cohort scatter is served from here rather than refitted per request.
    points = [
        {
            "patient_id": str(pid),
            "x": round(float(coordinates[i, 0]), 4),
            "y": round(float(coordinates[i, 1]), 4),
            "archetype": label_map[int(labels[i])],
        }
        for i, pid in enumerate(summary["patient_id"].tolist())
    ]

    return {
        "scaler": scaler,
        "kmeans": kmeans,
        "pca": pca,
        "label_map": label_map,
        "features": features,
        "points": points,
        "silhouette": float(silhouette_score(scaled, labels)),
        "n_rows": int(X.shape[0]),
    }


def assign(
    shape_features: dict[str, float],
    artifact: dict[str, object] | None = None,
) -> ArchetypeResult:
    """Place one patient's trajectory into an archetype."""
    if artifact is None:
        return _heuristic_assign(shape_features)

    features = list(artifact["features"])  # type: ignore[arg-type]
    scaler = artifact["scaler"]
    kmeans = artifact["kmeans"]
    pca = artifact["pca"]
    label_map: dict[int, str] = artifact["label_map"]  # type: ignore[assignment]

    row = np.array([[shape_features.get(name, 0.0) for name in features]], dtype=float)
    scaled = scaler.transform(row)  # type: ignore[union-attr]

    cluster = int(kmeans.predict(scaled)[0])  # type: ignore[union-attr]
    archetype = label_map[cluster]
    coords = pca.transform(scaled)[0]  # type: ignore[union-attr]

    # Distance to the nearest centroid against the next nearest, so a patient
    # sitting between two shapes is reported as a weaker match rather than
    # being presented as a confident assignment.
    distances = np.linalg.norm(kmeans.cluster_centers_ - scaled, axis=1)  # type: ignore[union-attr]
    order = np.argsort(distances)
    nearest, second = distances[order[0]], distances[order[1]]
    confidence = float(np.clip(1.0 - nearest / (second + 1e-9), 0.0, 1.0))

    # The two features that most separate this patient from the centroid are
    # what make their trajectory this shape rather than another.
    centroid = kmeans.cluster_centers_[cluster]  # type: ignore[union-attr]
    deviations = scaled[0] - centroid
    top = np.argsort(np.abs(deviations))[::-1][:2]

    factors = [
        Factor(
            name=features[i],
            contribution=float(deviations[i]),
            direction="increases" if deviations[i] > 0 else "decreases",
            plain_text=(
                f"your {label_for(features[i])} is "
                f"{'above' if deviations[i] > 0 else 'below'} typical for this group"
            ),
        )
        for i in top
    ]

    return ArchetypeResult(
        archetype=archetype,
        label=ARCHETYPE_LABELS[archetype],
        description=ARCHETYPE_DESCRIPTIONS[archetype],
        coordinates=(float(coords[0]), float(coords[1])),
        confidence=confidence,
        explanation=Explanation(
            summary=(
                f"Your recovery most resembles the {ARCHETYPE_LABELS[archetype].lower()} "
                f"pattern. {ARCHETYPE_DESCRIPTIONS[archetype]}"
            ),
            factors=factors,
            method="k means clustering over trajectory shape, named by centroid geometry",
        ),
    )


def _heuristic_assign(shape: dict[str, float]) -> ArchetypeResult:
    """Transparent fallback before the model has been trained."""
    plateau = shape.get("plateau_index", 0.0)
    time_to_80 = shape.get("time_to_80pct", 0.5)

    if plateau > 0.12:
        archetype = "plateaued"
    elif time_to_80 < 0.35:
        archetype = "fast_responder"
    elif time_to_80 > 0.75:
        archetype = "late_bloomer"
    else:
        archetype = "steady_climber"

    return ArchetypeResult(
        archetype=archetype,
        label=ARCHETYPE_LABELS[archetype],
        description=ARCHETYPE_DESCRIPTIONS[archetype],
        coordinates=(0.0, 0.0),
        confidence=0.0,
        explanation=Explanation(
            summary=(
                f"Your recovery most resembles the {ARCHETYPE_LABELS[archetype].lower()} "
                f"pattern. {ARCHETYPE_DESCRIPTIONS[archetype]}"
            ),
            method="heuristic fallback, no trained model available",
        ),
    )


__all__ = [
    "ARCHETYPE_LABELS",
    "SHAPE_FEATURES",
    "ArchetypeResult",
    "assign",
    "train",
]
