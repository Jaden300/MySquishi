"""Model artifact storage.

Cohort trained models are fitted once by app.ml.train_all and cached to disk
as joblib artifacts. This module loads them lazily, keeps them in process,
and records provenance in a manifest so the About page can state honestly
when each model was trained and how it scored.

Models that fit per request (segmentation, fatigue, the forecast) do not
appear here: they have no artifact to store.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import joblib

from app.config import settings

MANIFEST_NAME = "manifest.json"

# Bumped when a model's inputs or structure change in a way that makes an
# existing artifact wrong rather than merely stale.
ARTIFACT_VERSION = "1"


@dataclass
class ArtifactRecord:
    """Provenance for one trained model."""

    model_id: str
    version: str
    trained_at: str
    metric_name: str
    metric_value: float
    cohort_version: str
    n_training_rows: int
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Manifest:
    """Everything the registry knows about what is on disk."""

    artifacts: dict[str, ArtifactRecord] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_version": ARTIFACT_VERSION,
            "artifacts": {k: v.to_dict() for k, v in self.artifacts.items()},
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> Manifest:
        records = {
            model_id: ArtifactRecord(**record)
            for model_id, record in payload.get("artifacts", {}).items()
        }
        return cls(artifacts=records)


class ModelRegistry:
    """Lazy loading store for trained artifacts.

    Loading is deferred until first use and cached in process, so importing
    a model module never pays for disk reads and a busy endpoint never pays
    twice.
    """

    def __init__(self, models_dir: Path | None = None) -> None:
        self._dir = models_dir or settings.models_dir
        self._cache: dict[str, Any] = {}
        self._manifest: Manifest | None = None

    @property
    def directory(self) -> Path:
        return self._dir

    def path_for(self, model_id: str) -> Path:
        return self._dir / f"{model_id.lower()}.joblib"

    def has(self, model_id: str) -> bool:
        return self.path_for(model_id).exists()

    def save(
        self,
        model_id: str,
        artifact: Any,
        *,
        metric_name: str,
        metric_value: float,
        cohort_version: str,
        n_training_rows: int,
        notes: str = "",
    ) -> None:
        """Persist a fitted model and record how it was produced."""
        self._dir.mkdir(parents=True, exist_ok=True)
        joblib.dump(artifact, self.path_for(model_id))
        self._cache[model_id] = artifact

        manifest = self.manifest()
        manifest.artifacts[model_id] = ArtifactRecord(
            model_id=model_id,
            version=ARTIFACT_VERSION,
            trained_at=datetime.now(UTC).isoformat(timespec="seconds"),
            metric_name=metric_name,
            metric_value=round(float(metric_value), 4),
            cohort_version=cohort_version,
            n_training_rows=int(n_training_rows),
            notes=notes,
        )
        self._write_manifest(manifest)

    def load(self, model_id: str) -> Any:
        """Load an artifact, raising a useful error when it is missing."""
        if model_id in self._cache:
            return self._cache[model_id]

        path = self.path_for(model_id)
        if not path.exists():
            raise FileNotFoundError(
                f"no trained artifact for {model_id}. Run "
                "backend/.venv/bin/python -m app.ml.train_all to build the "
                "cohort trained models."
            )

        artifact = joblib.load(path)
        self._cache[model_id] = artifact
        return artifact

    def try_load(self, model_id: str) -> Any | None:
        """Load if present, otherwise None. For endpoints that degrade
        gracefully rather than failing when a model is unavailable."""
        try:
            return self.load(model_id)
        except FileNotFoundError:
            return None

    def manifest(self) -> Manifest:
        if self._manifest is not None:
            return self._manifest

        path = self._dir / MANIFEST_NAME
        if path.exists():
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                self._manifest = Manifest.from_dict(payload)
            except (json.JSONDecodeError, TypeError, KeyError):
                # A corrupt manifest should not prevent training from
                # rewriting it.
                self._manifest = Manifest()
        else:
            self._manifest = Manifest()

        return self._manifest

    def records(self) -> list[ArtifactRecord]:
        """Every artifact record, for the About page."""
        return sorted(self.manifest().artifacts.values(), key=lambda r: r.model_id)

    def is_stale(self, model_id: str) -> bool:
        """True when an artifact is missing or was built by an older version."""
        record = self.manifest().artifacts.get(model_id)
        if record is None or not self.has(model_id):
            return True
        return record.version != ARTIFACT_VERSION

    def clear_cache(self) -> None:
        """Drop in process caches. Used after retraining."""
        self._cache.clear()
        self._manifest = None

    def _write_manifest(self, manifest: Manifest) -> None:
        self._dir.mkdir(parents=True, exist_ok=True)
        (self._dir / MANIFEST_NAME).write_text(
            json.dumps(manifest.to_dict(), indent=2), encoding="utf-8"
        )
        self._manifest = manifest


# The application wide registry.
registry = ModelRegistry()
