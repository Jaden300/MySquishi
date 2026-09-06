"""Tests for the hardware boundary.

Two jobs: confirm SimulatedSource satisfies the Protocol structurally, and
enforce the Phase 1 rule that no serial port code exists anywhere in the
application. The second one is a guard rail around the Phase 2 hard stop.
"""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pytest

from app.sources.base import (
    SOURCE_CATALOGUE,
    SignalSource,
    SourceInfo,
    get_source,
    list_sources,
)
from app.sources.simulated import SimulatedSource

APP_DIR = Path(__file__).resolve().parent.parent


class TestProtocolConformance:
    def test_simulated_source_satisfies_the_protocol(self) -> None:
        assert isinstance(SimulatedSource(paced=False), SignalSource)

    def test_factory_returns_a_signal_source(self) -> None:
        assert isinstance(get_source("simulated", paced=False), SignalSource)

    def test_unknown_source_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="unknown source"):
            get_source("telepathy")

    def test_every_catalogue_source_can_be_constructed(self) -> None:
        """Construction must not touch hardware. A source only opens its port
        on connect(), so building one is always safe."""
        for info in list_sources():
            assert isinstance(get_source(info.id), SignalSource)

    def test_catalogue_marks_all_three_available(self) -> None:
        available = {info.id for info in list_sources() if info.available}
        assert available == {"simulated", "serial", "replay"}

    def test_catalogue_entries_are_fully_described(self) -> None:
        for info in SOURCE_CATALOGUE:
            assert isinstance(info, SourceInfo)
            assert info.id and info.label and info.note


class TestSimulatedSource:
    def test_reports_not_live(self) -> None:
        """The honesty chip in the UI is driven by this, so a simulated
        session can never present itself as a real one."""
        assert SimulatedSource(paced=False).is_live is False

    def test_window_shape_and_rate(self) -> None:
        source = SimulatedSource(sample_rate=1000, window_samples=200, paced=False)
        source.connect()

        window = source.read_window()
        assert isinstance(window, np.ndarray)
        assert window.shape == (200,)
        assert source.sample_rate == 1000

    def test_read_before_connect_is_an_error(self) -> None:
        with pytest.raises(RuntimeError, match="before connect"):
            SimulatedSource(paced=False).read_window()

    def test_disconnect_then_read_is_an_error(self) -> None:
        source = SimulatedSource(paced=False)
        source.connect()
        source.read_window()
        source.disconnect()

        with pytest.raises(RuntimeError):
            source.read_window()

    def test_disconnect_is_safe_when_never_connected(self) -> None:
        SimulatedSource(paced=False).disconnect()

    def test_streams_indefinitely(self) -> None:
        """A demo may run longer than the protocol and must not run dry."""
        source = SimulatedSource(window_samples=200, paced=False)
        source.connect()

        windows = [source.read_window() for _ in range(400)]
        assert all(w.size == 200 for w in windows)
        assert all(np.all(np.isfinite(w)) for w in windows)

    def test_seeded_sources_reproduce(self) -> None:
        def first_windows(seed: int) -> np.ndarray:
            source = SimulatedSource(seed=seed, paced=False)
            source.connect()
            return np.concatenate([source.read_window() for _ in range(5)])

        assert np.array_equal(first_windows(42), first_windows(42))
        assert not np.array_equal(first_windows(1), first_windows(2))

    def test_reconnect_restarts_the_same_sequence(self) -> None:
        source = SimulatedSource(seed=9, paced=False)

        source.connect()
        first = source.read_window().copy()
        source.connect()
        second = source.read_window().copy()

        assert np.array_equal(first, second)

    def test_junkiness_can_be_adjusted_mid_session(self) -> None:
        """So a demo can show the quality badge reacting to a failing
        electrode."""
        source = SimulatedSource(junkiness=0.0, paced=False)
        source.connect()
        source.set_junkiness(0.8)
        assert source.junkiness == 0.8

    def test_junkiness_is_range_checked(self) -> None:
        source = SimulatedSource(paced=False)
        with pytest.raises(ValueError):
            source.set_junkiness(1.5)

    def test_pacing_approximates_real_time(self) -> None:
        """Windows should arrive at roughly the wall clock rate so the
        oscilloscope scrolls at a lifelike speed."""
        import time

        source = SimulatedSource(sample_rate=1000, window_samples=200, paced=True)
        source.connect()

        start = time.monotonic()
        for _ in range(5):
            source.read_window()
        elapsed = time.monotonic() - start

        # Five 200 ms windows is 1.0 s, with the first read returning at once.
        assert 0.5 < elapsed < 1.5, f"took {elapsed:.2f}s"


class TestSerialStaysContained:
    """Phase 3 opens exactly one door to the serial port, not a general
    permission. These guards narrowed rather than disappeared: hardware code
    must not spread beyond the one module that owns it."""

    # The single module permitted to import pyserial.
    SERIAL_MODULE = ("sources", "serial_source.py")

    def test_only_serial_source_imports_serial(self) -> None:
        pattern = re.compile(r"^\s*(import\s+serial|from\s+serial\b)", re.MULTILINE)
        offenders = []

        for path in APP_DIR.rglob("*.py"):
            if "tests" in path.parts:
                continue
            if path.parts[-2:] == self.SERIAL_MODULE:
                continue
            if pattern.search(path.read_text(encoding="utf-8")):
                offenders.append(str(path.relative_to(APP_DIR)))

        assert not offenders, (
            f"serial imports found in {offenders}. Only "
            "app/sources/serial_source.py may talk to a serial port, so the "
            "hardware boundary stays a boundary."
        )

    def test_serial_source_imports_pyserial_lazily(self) -> None:
        """A missing driver must surface when a live session is requested, not
        at application import, or the zero hardware demo path breaks."""
        source = APP_DIR / "sources" / "serial_source.py"
        text = source.read_text(encoding="utf-8")

        module_level = re.compile(r"^(import\s+serial|from\s+serial\b)", re.MULTILINE)
        assert not module_level.search(text), (
            "pyserial is imported at module level in serial_source.py. It must "
            "be imported inside a function so app import never needs it."
        )
        assert "import serial" in text, "expected a deferred pyserial import"

    def test_pyserial_is_a_deliberate_dependency(self) -> None:
        """Phase 3 promotes pyserial from a probe only extra to a real
        dependency. Pinned here on purpose, so it cannot arrive by accident."""
        requirements = (APP_DIR.parent / "requirements.txt").read_text(encoding="utf-8")
        assert "pyserial" in requirements.lower()
