"""Application settings.

Paths are resolved relative to the backend directory so the app behaves the
same whether it is started from the repository root or from backend/.
"""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings

BACKEND_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BACKEND_DIR / "data"


class Settings(BaseSettings):
    """Runtime configuration, overridable by MYSQUISHI_ prefixed env vars."""

    app_name: str = "MySquishi"

    # Storage. Tests override db_path to a temporary file.
    db_path: Path = DATA_DIR / "mysquishi.db"
    models_dir: Path = DATA_DIR / "models"
    cohort_dir: Path = DATA_DIR / "cohort"

    # Signal acquisition. 1000 Hz is well above the useful sEMG band and keeps
    # the 20-450 Hz bandpass comfortably inside Nyquist.
    sample_rate: int = 1000

    # Analysis window: 200 samples at 1000 Hz is 200 ms, so the live socket
    # carries 5 frames per second.
    window_samples: int = 200

    # Raw traces are decimated to this many points before going over the wire.
    # The oscilloscope is a few hundred pixels wide, so more would be wasted.
    frame_raw_points: int = 100

    # Synthetic data generation.
    cohort_seed: int = 42
    cohort_size: int = 300

    model_config = {"env_prefix": "MYSQUISHI_"}

    @property
    def db_url(self) -> str:
        return f"sqlite:///{self.db_path}"

    def ensure_dirs(self) -> None:
        """Create the data directories if they are not already present."""
        for path in (self.db_path.parent, self.models_dir, self.cohort_dir):
            path.mkdir(parents=True, exist_ok=True)


settings = Settings()
