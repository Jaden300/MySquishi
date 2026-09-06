"""ReplaySource: a recorded session, played back through the same interface.

This is demo insurance. Hardware fails during demos, electrodes peel, cables
get kicked, and a recorded Tier A session played back at wall clock speed looks
exactly like the live path to everything downstream.

`is_live` is False, so the honesty chip correctly reports this is not a live
session. That is the whole point of deriving the label from the source object
rather than from page copy.
"""

from __future__ import annotations

import time
from pathlib import Path

import numpy as np

from app.sources.serial_source import ADC_MIDPOINT, COUNTS_PER_UNIT, SAMPLE_HZ

# Where the recorded traces live. tools/probe.py writes here, and its save()
# docstring names these files as the seed corpus for exactly this class.
CALIBRATION_DIR = Path(__file__).resolve().parents[2] / "calibration"

# Same 200 ms cadence the other sources produce, so the frontend sees a
# consistent frame rate whichever source is selected.
WINDOW_SAMPLES = 100


class ReplayUnavailable(RuntimeError):
    """No trace to replay, and the message says which directory was searched."""


def list_traces() -> list[str]:
    """Recorded traces available for replay, newest first.

    Filenames carry a timestamp, so a reverse sort is chronological.
    """
    if not CALIBRATION_DIR.is_dir():
        return []
    return sorted((p.name for p in CALIBRATION_DIR.glob("*.csv")), reverse=True)


def _parse_trace(path: Path) -> tuple[np.ndarray, int, list[str]]:
    """Read counts and the declared sample rate out of a probe CSV.

    The parsing follows tools/probe.py:load, minus its _fail path: that calls
    SystemExit, which would take down the server rather than the request.

    The sample rate comes from the `# sample_hz=` header rather than being
    assumed, so a trace recorded at a different rate still replays at its own
    speed. load() collects these header lines but never reads this key.
    """
    counts: list[float] = []
    header: list[str] = []
    sample_rate = SAMPLE_HZ

    with path.open() as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue

            if line.startswith("#"):
                body = line.lstrip("# ").strip()
                header.append(body)
                if body.startswith("sample_hz="):
                    try:
                        sample_rate = int(body.partition("=")[2])
                    except ValueError:
                        pass
                continue

            parts = line.split(",")
            # The second condition skips the "millis,adc_counts" column row.
            if len(parts) != 2 or not parts[0].lstrip("-").isdigit():
                continue
            try:
                counts.append(float(parts[1]))
            except ValueError:
                continue

    if not counts:
        raise ReplayUnavailable(f"No samples found in {path.name}.")

    return np.asarray(counts, dtype=float), sample_rate, header


class ReplaySource:
    """Serves windows from a recorded trace, paced to real time.

    Satisfies the SignalSource Protocol structurally. Scaling matches
    SerialSource exactly, since both are reading the same integer ADC counts
    off the same converter, so a replayed session and a live one are
    interpreted identically by everything downstream.
    """

    def __init__(
        self,
        trace: str | None = None,
        window_samples: int = WINDOW_SAMPLES,
        *,
        paced: bool = True,
        loop: bool = True,
    ) -> None:
        self._trace = trace
        self._window_samples = window_samples
        self._paced = paced
        self._loop = loop

        self._samples: np.ndarray | None = None
        self._sample_rate = SAMPLE_HZ
        self._header: list[str] = []
        self._cursor = 0
        self._connected = False
        self._next_due: float | None = None

    # -- SignalSource ------------------------------------------------------

    def connect(self) -> bool:
        name = self._trace
        if name is None:
            available = list_traces()
            if not available:
                raise ReplayUnavailable(
                    f"No recorded traces in {CALIBRATION_DIR}. Record one with "
                    "the probe first: .venv/bin/python -m tools.probe"
                )
            name = available[0]

        path = CALIBRATION_DIR / Path(name).name
        if not path.is_file():
            raise ReplayUnavailable(f"No such trace: {name}")

        counts, sample_rate, header = _parse_trace(path)

        # Centre and scale exactly as SerialSource does, so a replayed trace
        # and a live one are indistinguishable to the pipeline.
        self._samples = (counts - ADC_MIDPOINT) / COUNTS_PER_UNIT
        self._sample_rate = sample_rate
        self._header = header
        self._trace = path.name
        self._cursor = 0
        self._connected = True
        self._next_due = None
        return True

    def read_window(self) -> np.ndarray:
        if not self._connected or self._samples is None:
            raise RuntimeError("read_window called before connect")

        if self._paced:
            self._wait_for_next_window()

        total = self._samples.size
        start = self._cursor
        end = start + self._window_samples

        if end <= total:
            self._cursor = end
            return self._samples[start:end].copy()

        # Ran off the end of the trace.
        tail = self._samples[start:total]
        if not self._loop:
            self._cursor = total
            window = np.zeros(self._window_samples, dtype=float)
            window[: tail.size] = tail
            return window

        # Wrap, so a demo that outlasts the recording keeps running rather
        # than going silent at the worst possible moment.
        wrap = self._window_samples - tail.size
        self._cursor = wrap
        return np.concatenate([tail, self._samples[:wrap]])

    @property
    def sample_rate(self) -> int:
        return self._sample_rate

    @property
    def is_live(self) -> bool:
        """Always False. This is a recording, and the UI says so."""
        return False

    def disconnect(self) -> None:
        self._samples = None
        self._connected = False
        self._cursor = 0
        self._next_due = None

    # -- extras beyond the Protocol ---------------------------------------

    @property
    def window_samples(self) -> int:
        return self._window_samples

    @property
    def trace(self) -> str | None:
        return self._trace

    @property
    def header(self) -> list[str]:
        return list(self._header)

    @property
    def exhausted(self) -> bool:
        """True when a non looping replay has played out."""
        if self._samples is None:
            return False
        return not self._loop and self._cursor >= self._samples.size

    def _wait_for_next_window(self) -> None:
        """Pace reads to real time, without drifting.

        The deadline advances by exactly one window each call rather than
        being measured from the moment the last read finished, so processing
        time does not accumulate into a slow drift.
        """
        window_s = self._window_samples / self._sample_rate
        now = time.monotonic()

        if self._next_due is None:
            self._next_due = now + window_s
            return

        delay = self._next_due - now
        if delay > 0:
            time.sleep(delay)
            self._next_due += window_s
        else:
            # Fell behind. Resynchronize rather than trying to catch up, which
            # would burst frames at the client.
            self._next_due = now + window_s


__all__ = [
    "CALIBRATION_DIR",
    "ReplaySource",
    "ReplayUnavailable",
    "list_traces",
]
