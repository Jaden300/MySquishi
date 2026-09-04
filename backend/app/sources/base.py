"""The hardware boundary.

`SignalSource` is the interface every signal producer satisfies. It is a
structural Protocol, so a new implementation needs no base class and no edits
to any consumer: it only has to have the right shape and be registered in the
factory below.

Three implementations are planned:

- SimulatedSource, the synthetic generator. Phase 1. Always available.
- SerialSource, the real MyoWare over USB. Phase 3, and only to the fidelity
  the Phase 2 hardware bring up justifies.
- ReplaySource, a recorded session from CSV. Phase 3, as demo insurance.

**Phase 1 writes no serial port code.** A test asserts that `serial` appears
nowhere under app/, so the hard stop before hardware bring up is enforced
rather than merely remembered. See docs/ARCHITECTURE.md.
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
        available=False,
        note="Requires hardware bring up. Arrives in Phase 3.",
    ),
    SourceInfo(
        id="replay",
        label="Replay",
        is_live=False,
        available=False,
        note="Plays back a recorded session. Arrives in Phase 3.",
    ),
)


def list_sources() -> list[SourceInfo]:
    return list(SOURCE_CATALOGUE)


def get_source(source_id: str, **kwargs: object) -> SignalSource:
    """Construct a source by id.

    The single construction point for the whole application. Phase 3 adds its
    implementations here and nothing else changes.
    """
    if source_id == "simulated":
        # Imported here so the module graph stays acyclic: simulated.py
        # imports the Protocol from this module.
        from app.sources.simulated import SimulatedSource

        return SimulatedSource(**kwargs)  # type: ignore[arg-type]

    known = {info.id for info in SOURCE_CATALOGUE}
    if source_id in known:
        raise NotImplementedError(
            f"source '{source_id}' is not available yet. "
            "Live and replay sources arrive in Phase 3, after hardware bring up."
        )

    raise ValueError(f"unknown source '{source_id}'. Known sources: {sorted(known)}")
