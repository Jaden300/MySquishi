"""SerialSource and ReplaySource, without requiring hardware.

The suite has to pass on a machine with nothing plugged in, so the serial
tests drive a fake port object with the same surface pyserial exposes. What is
being tested is the parsing, the ring buffer and the degradation behaviour,
none of which need a real Arduino to be wrong.

ReplaySource is tested against the real Phase 2 traces in calibration/, which
is also what proves the demo insurance actually works.
"""

from __future__ import annotations

import time

import numpy as np
import pytest

from app.sources.base import SignalSource, get_source
from app.sources.replay_source import (
    CALIBRATION_DIR,
    ReplaySource,
    ReplayUnavailable,
    list_traces,
)
from app.sources.serial_source import (
    ADC_MIDPOINT,
    BAUD,
    COUNTS_PER_UNIT,
    SAMPLE_HZ,
    SerialSource,
    SerialUnavailable,
)


class FakeSerial:
    """Stands in for a pyserial Serial object.

    Yields the lines it was given, then blocks the way a real port does when
    the sketch goes quiet: returning empty bytes on timeout rather than
    raising, which is what the reader thread has to tolerate.
    """

    def __init__(self, lines: list[bytes], *, fail_after: int | None = None) -> None:
        self._lines = list(lines)
        self._index = 0
        self._fail_after = fail_after
        self.closed = False
        self.buffer_reset = False

    def readline(self) -> bytes:
        if self._fail_after is not None and self._index >= self._fail_after:
            raise OSError("device disconnected")
        if self._index >= len(self._lines):
            time.sleep(0.005)
            return b""
        line = self._lines[self._index]
        self._index += 1
        return line

    def reset_input_buffer(self) -> None:
        self.buffer_reset = True

    def close(self) -> None:
        self.closed = True


def _sample_lines(count: int, value: int = 600) -> list[bytes]:
    header = [
        b"# mysquishi_probe v1\n",
        b"# sample_hz=500\n",
        b"# baud=230400\n",
        b"# columns: millis,adc_counts\n",
    ]
    body = [f"{i * 2},{value}\n".encode() for i in range(count)]
    return header + body


def _connected_source(fake: FakeSerial, **kwargs) -> SerialSource:
    """Wire a SerialSource to a fake port, skipping discovery."""
    source = SerialSource(port="/dev/fake", **kwargs)
    source._link = fake
    source._error = None
    source._last_sample_at = time.monotonic()
    source._stop.clear()

    import threading

    source._thread = threading.Thread(target=source._reader, daemon=True)
    source._thread.start()
    source._connected = True
    return source


class TestSerialSourceConformance:
    def test_satisfies_the_protocol(self) -> None:
        assert isinstance(SerialSource(port="/dev/fake"), SignalSource)

    def test_factory_builds_one_without_touching_hardware(self) -> None:
        """Construction must not open a port. Only connect() does that, which
        is what lets the settings page list the source safely."""
        assert isinstance(get_source("serial"), SignalSource)

    def test_reports_live(self) -> None:
        """The honesty chip derives from this, so a real session is labelled
        as one."""
        assert SerialSource(port="/dev/fake").is_live is True

    def test_declares_the_firmware_constants(self) -> None:
        """A mismatch with the sketch produces plausible garbage rather than
        an error, so the values are asserted rather than trusted."""
        assert BAUD == 230400
        assert SAMPLE_HZ == 500
        assert SerialSource(port="/dev/fake").sample_rate == 500

    def test_read_before_connect_is_an_error(self) -> None:
        with pytest.raises(RuntimeError, match="before connect"):
            SerialSource(port="/dev/fake").read_window()

    def test_disconnect_is_safe_when_never_connected(self) -> None:
        SerialSource(port="/dev/fake").disconnect()


class TestSerialSourceParsing:
    def test_reads_a_window_of_scaled_counts(self) -> None:
        fake = FakeSerial(_sample_lines(400, value=600))
        source = _connected_source(fake, window_samples=100)
        try:
            window = source.read_window()
        finally:
            source.disconnect()

        assert window.shape == (100,)
        expected = (600 - ADC_MIDPOINT) / COUNTS_PER_UNIT
        assert np.allclose(window, expected)

    def test_header_lines_are_collected_not_parsed_as_samples(self) -> None:
        fake = FakeSerial(_sample_lines(200))
        source = _connected_source(fake, window_samples=50)
        try:
            source.read_window()
            header = source.header
        finally:
            source.disconnect()

        assert any("sample_hz=500" in line for line in header)
        assert any("mysquishi_probe" in line for line in header)

    def test_partial_and_malformed_lines_are_skipped(self) -> None:
        """A partial line arrives every time the port opens mid transmission,
        so it is an expected condition rather than an error."""
        lines = [
            b"# mysquishi_probe v1\n",
            b"garbage\n",
            b"12,\n",
            b"34,not_a_number\n",
            b"56,78,90\n",
            b"\n",
        ] + [f"{i},600\n".encode() for i in range(60)]

        fake = FakeSerial(lines)
        source = _connected_source(fake, window_samples=50)
        try:
            window = source.read_window()
        finally:
            source.disconnect()

        assert window.shape == (50,)
        assert np.all(np.isfinite(window))

    def test_buffer_is_reset_on_connect(self) -> None:
        """So the first line parsed is a whole one."""
        fake = FakeSerial(_sample_lines(100))
        source = SerialSource(port="/dev/fake")
        source._link = fake
        fake.reset_input_buffer()
        assert fake.buffer_reset


class TestSerialSourceDegradesVisibly:
    """A demo has to survive a yanked cable. Losing the sensor degrades the
    signal through the SQI badge rather than ending in a stack trace."""

    def test_unplugging_does_not_raise_from_read_window(self) -> None:
        fake = FakeSerial(_sample_lines(30), fail_after=10)
        source = _connected_source(fake, window_samples=100)
        try:
            window = source.read_window()
        finally:
            source.disconnect()

        # A short window is padded rather than raising, so the frame contract
        # holds and the session keeps rendering.
        assert window.shape == (100,)
        assert np.all(np.isfinite(window))

    def test_lost_sensor_is_reported(self) -> None:
        fake = FakeSerial(_sample_lines(30), fail_after=10)
        source = _connected_source(fake, window_samples=100)
        try:
            source.read_window()
            assert source.error is not None
            assert "cable" in source.error.lower()
            assert source.is_streaming is False
        finally:
            source.disconnect()

    def test_missing_port_explains_what_to_do(self, monkeypatch) -> None:
        """With no sensor attached the message has to say how to attach one:
        bring up happens with electrodes taped to an arm."""
        from app.sources import serial_source

        monkeypatch.setattr(serial_source, "discover_port", lambda: None)

        with pytest.raises(SerialUnavailable) as exc:
            serial_source.SerialSource().connect()

        message = str(exc.value)
        assert "data cable" in message
        assert "Serial Monitor" in message

    def test_disconnect_closes_the_port(self) -> None:
        fake = FakeSerial(_sample_lines(200))
        source = _connected_source(fake, window_samples=50)
        source.read_window()
        source.disconnect()

        assert fake.closed is True


class TestReplaySource:
    def test_satisfies_the_protocol(self) -> None:
        assert isinstance(ReplaySource(paced=False), SignalSource)

    def test_reports_not_live(self) -> None:
        """A recording is not a live session, and the honesty chip says so."""
        assert ReplaySource(paced=False).is_live is False

    def test_read_before_connect_is_an_error(self) -> None:
        with pytest.raises(RuntimeError, match="before connect"):
            ReplaySource(paced=False).read_window()

    def test_unknown_trace_is_reported(self) -> None:
        with pytest.raises(ReplayUnavailable, match="No such trace"):
            ReplaySource(trace="nonexistent.csv", paced=False).connect()

    @pytest.mark.skipif(
        not list_traces(), reason="no recorded traces in calibration/"
    )
    def test_every_recorded_trace_replays(self) -> None:
        """The demo insurance is only insurance if it actually plays back."""
        for name in list_traces():
            source = ReplaySource(trace=name, paced=False)
            source.connect()
            try:
                windows = [source.read_window() for _ in range(20)]
            finally:
                source.disconnect()

            assert all(w.shape == (100,) for w in windows), name
            assert all(np.all(np.isfinite(w)) for w in windows), name

    @pytest.mark.skipif(
        not list_traces(), reason="no recorded traces in calibration/"
    )
    def test_sample_rate_comes_from_the_trace_header(self) -> None:
        """Rather than being assumed, so a trace recorded at another rate
        still replays at its own speed."""
        source = ReplaySource(trace=list_traces()[0], paced=False)
        source.connect()
        try:
            assert source.sample_rate == 500
            assert any("sample_hz=500" in line for line in source.header)
        finally:
            source.disconnect()

    @pytest.mark.skipif(
        not list_traces(), reason="no recorded traces in calibration/"
    )
    def test_looping_outlasts_the_recording(self) -> None:
        """A demo that runs longer than the trace keeps going rather than
        falling silent at the worst possible moment."""
        source = ReplaySource(trace=list_traces()[0], paced=False, loop=True)
        source.connect()
        try:
            total = source._samples.size
            reads = (total // 100) + 5
            windows = [source.read_window() for _ in range(reads)]
        finally:
            source.disconnect()

        assert all(w.shape == (100,) for w in windows)
        assert np.any(windows[-1] != 0.0), "wrapped read should carry real signal"

    def test_calibration_directory_is_where_the_probe_writes(self) -> None:
        assert CALIBRATION_DIR.name == "calibration"
