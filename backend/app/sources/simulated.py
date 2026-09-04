"""SimulatedSource: the synthetic generator behind the hardware boundary.

This is a permanent, first class feature rather than a fallback. It is what
the demo runs on, and it is what makes the app fully usable with nothing
plugged in.
"""

from __future__ import annotations

import time

import numpy as np

from app.config import settings
from app.sim.signal_gen import SessionProtocol, SyntheticEmgGenerator


class SimulatedSource:
    """Serves windows from the synthetic EMG generator.

    Satisfies the SignalSource Protocol structurally. Reads are paced against
    the wall clock so the frontend sees a realistic frame rate rather than a
    firehose, which also keeps the oscilloscope scrolling at a lifelike speed.
    """

    def __init__(
        self,
        sample_rate: int | None = None,
        window_samples: int | None = None,
        seed: int | None = None,
        junkiness: float = 0.0,
        protocol: SessionProtocol | None = None,
        *,
        paced: bool = True,
    ) -> None:
        self._sample_rate = sample_rate or settings.sample_rate
        self._window_samples = window_samples or settings.window_samples
        self._junkiness = junkiness
        self._protocol = protocol
        self._paced = paced

        self._generator = SyntheticEmgGenerator(
            sample_rate=self._sample_rate,
            seed=seed,
            junkiness=junkiness,
        )
        self._stream = None
        self._connected = False
        self._next_due: float | None = None

    # -- SignalSource ------------------------------------------------------

    def connect(self) -> bool:
        self._generator.reset()
        self._stream = self._generator.stream(
            self._window_samples,
            self._protocol,
            loop=True,
        )
        self._connected = True
        self._next_due = None
        return True

    def read_window(self) -> np.ndarray:
        if not self._connected or self._stream is None:
            raise RuntimeError("read_window called before connect")

        if self._paced:
            self._wait_for_next_window()

        return next(self._stream)

    @property
    def sample_rate(self) -> int:
        return self._sample_rate

    @property
    def is_live(self) -> bool:
        """Always False. These samples are synthetic and the UI says so."""
        return False

    def disconnect(self) -> None:
        self._stream = None
        self._connected = False
        self._next_due = None

    # -- extras beyond the Protocol ---------------------------------------

    @property
    def window_samples(self) -> int:
        return self._window_samples

    @property
    def junkiness(self) -> float:
        return self._junkiness

    def set_junkiness(self, value: float) -> None:
        """Adjust signal quality mid session, so the SQI badge can be shown
        reacting to a deteriorating electrode during a demo."""
        if not 0.0 <= value <= 1.0:
            raise ValueError(f"junkiness must be within 0 to 1, got {value}")

        self._junkiness = value
        self._generator.junkiness = value

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
