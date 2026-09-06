"""The hardware boundary.

`SignalSource` is the interface every signal producer satisfies. It is a
structural Protocol, so a new implementation needs no base class and no edits
to any consumer: it only has to have the right shape and be registered in the
factory below.

Three implementations exist:

- SimulatedSource, the synthetic generator. Always available, and a permanent
  first class feature rather than a fallback.
- SerialSource, the real MyoWare over USB at 500 Hz, scoped to the fidelity the
  Phase 2 bring up justifies. See docs/HARDWARE_FINDINGS.md.
- ReplaySource, a recorded session from CSV, as demo insurance.

`app/sources/serial_source.py` is the only module in the application permitted
to import pyserial. Guard tests scan the rest of `app/` and still fail on a
serial import anywhere else, so hardware code cannot leak in unnoticed. See
docs/ARCHITECTURE.md.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

import numpy as np


@runtime_checkable
class SignalSource(Protocol):
    """A source of raw sEMG samples.

    Implementations are hot swappable from the settings dropdown. Consumers
    depend on this shape alone and never on a concrete class.
    """

    def connect(self) -> bool:
        """Open the source. Returns True when it is ready to read."""
        ...

    def read_window(self) -> np.ndarray:
        """Return the next window of raw samples."""
        ...

    @property
    def sample_rate(self) -> int:
        """Samples per second."""
        ...

    @property
    def is_live(self) -> bool:
        """True when samples come from real hardware.

        This is what drives the honesty chip in the UI. The label derives
        from the source itself, never from page copy, so a simulated session
        cannot be presented as a live one.
        """
        ...

    def disconnect(self) -> None:
        """Release the source. Safe to call when not connected."""
        ...


@dataclass(frozen=True)
class SourceInfo:
    """What the settings page needs in order to describe a source."""

    id: str
    label: str
    is_live: bool
    available: bool
    note: str


# The catalogue the UI renders. Sources that do not exist yet are listed but
# marked unavailable, so the roadmap is visible rather than hidden.
SOURCE_CATALOGUE: tuple[SourceInfo, ...] = (
    SourceInfo(
        id="simulated",
        label="Simulated",
        is_live=False,
        available=True,
        note="Synthetic signal generator. No hardware required.",
    ),
    SourceInfo(
        id="serial",
        label="Live sensor",
        is_live=True,
        available=True,
        note="MyoWare over USB at 500 Hz. Needs the sensor connected.",
    ),
    SourceInfo(
        id="replay",
        label="Replay",
        is_live=False,
        available=True,
        note="Plays back a recorded session. No hardware required.",
    ),
)


def list_sources() -> list[SourceInfo]:
    return list(SOURCE_CATALOGUE)


def get_source(source_id: str, **kwargs: object) -> SignalSource:
    """Construct a source by id.

    The single construction point for the whole application. Phase 3 adds its
    implementations here and nothing else changes.
    """
    # Every import here is deferred so the module graph stays acyclic: each
    # implementation imports the Protocol from this module. Deferring the
    # serial import additionally keeps pyserial off the application's startup
    # path, so a missing driver is an error when a live session is requested
    # rather than at boot.
    if source_id == "simulated":
        from app.sources.simulated import SimulatedSource

        return SimulatedSource(**kwargs)  # type: ignore[arg-type]

    if source_id == "serial":
        from app.sources.serial_source import SerialSource

        return SerialSource(**kwargs)  # type: ignore[arg-type]

    if source_id == "replay":
        from app.sources.replay_source import ReplaySource

        return ReplaySource(**kwargs)  # type: ignore[arg-type]

    known = {info.id for info in SOURCE_CATALOGUE}
    raise ValueError(f"unknown source '{source_id}'. Known sources: {sorted(known)}")
