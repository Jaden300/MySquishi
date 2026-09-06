"""SerialSource: the real MyoWare sensor over USB.

The one place in the application that talks to a serial port. Two guard tests
still scan the rest of `app/` for serial imports, so this file is the single
door Phase 3 opens on purpose rather than a general permission.

Scope comes from the Phase 2 bring up, recorded in docs/HARDWARE_FINDINGS.md.
The rig graded Tier A and resolves how hard a muscle is working across three
effort levels. It does not resolve which motion produced the effort, so nothing
here attempts per finger or per gesture decoding.

Two behaviours matter beyond simply reading the port:

- A background thread drains the port into a ring buffer, so `read_window()`
  returns promptly instead of blocking while serial dribbles in at 500 Hz.
- Unplugging the sensor degrades the signal visibly through the SQI badge
  rather than crashing the session. A demo survives a yanked cable.
"""

from __future__ import annotations

import threading
import time
from collections import deque

import numpy as np

# Must match firmware/mysquishi_probe.ino. A mismatch produces a stream of
# plausible looking garbage rather than an error, so the two are documented
# together and checked against the header the sketch prints on boot.
BAUD = 230400
SAMPLE_HZ = 500

# The window the live pipeline reads at a time. 100 samples at 500 Hz is 200 ms,
# matching the frame cadence the simulated source produces at 1000 Hz, so the
# frontend sees the same 5 frames per second either way.
WINDOW_SAMPLES = 100

# A 10 bit ADC idles near mid rail. Phase 2 measured 510.7 counts resting.
# Centring on the observed mean rather than a nominal 511.5 keeps a small DC
# offset out of the filters.
ADC_MIDPOINT = 511.5

# Scale counts to roughly the amplitude range the synthetic generator produces,
# so the shared pipeline thresholds and the MVC reference behave comparably
# across sources. This is a display and feature scaling, not a calibration:
# kilograms come only from the per patient force model.
COUNTS_PER_UNIT = 100.0

# Serial ports that are never an Arduino. macOS lists these permanently.
PORT_DENYLIST = ("Bluetooth-Incoming-Port", "debug-console")

# Substrings identifying a USB serial adapter across the common boards:
# genuine Uno, FTDI and CP210x adapters, and the CH340 on Nano clones.
PORT_HINTS = ("usbmodem", "usbserial", "wchusb", "SLAB", "ttyACM", "ttyUSB")

# How long a read waits for the buffer to fill before giving up and returning
# what it has. Generous enough to cover a stalled window, short enough that the
# UI keeps updating while the sensor is unplugged.
READ_TIMEOUT_S = 1.0

# How much history the ring holds. Two seconds is ample for the pipeline, and
# capping it means a paused client cannot grow the buffer without bound.
RING_SECONDS = 2.0


class SerialUnavailable(RuntimeError):
    """The port could not be opened, and the message says what to do."""


def _require_serial():  # type: ignore[no-untyped-def]
    """Import pyserial, or explain how to get it.

    Deferred rather than module level so a missing dependency surfaces as a
    clear error at connect time instead of breaking application import.
    """
    try:
        import serial  # noqa: PLC0415
        from serial.tools import list_ports  # noqa: PLC0415
    except ImportError as exc:  # pragma: no cover - dependency is declared
        raise SerialUnavailable(
            "pyserial is not installed. From the backend directory run: "
            ".venv/bin/pip install -r requirements.txt"
        ) from exc
    return serial, list_ports


def list_candidate_ports() -> list[dict[str, str]]:
    """Serial ports that might be the sensor, most likely first.

    The probe's equivalent prompts on stdin when the answer is ambiguous, which
    cannot happen inside a websocket handler. This returns the candidates
    instead and lets the UI ask.
    """
    try:
        _, list_ports = _require_serial()
    except SerialUnavailable:
        return []

    ports = [
        port
        for port in list_ports.comports()
        if not any(deny in port.device for deny in PORT_DENYLIST)
    ]
    likely = [p for p in ports if any(hint in p.device for hint in PORT_HINTS)]
    rest = [p for p in ports if p not in likely]

    return [
        {"device": str(p.device), "description": str(p.description or "")}
        for p in (*likely, *rest)
    ]


def discover_port() -> str | None:
    """The single most likely sensor port, or None when there is no answer."""
    candidates = list_candidate_ports()
    return candidates[0]["device"] if candidates else None


class SerialSource:
    """Streams real sEMG samples from the Arduino.

    Satisfies the SignalSource Protocol structurally. A background thread owns
    the port and fills a ring buffer; `read_window()` only ever touches the
    ring, so a slow or absent sensor never blocks the event loop for longer
    than READ_TIMEOUT_S.
    """

    def __init__(
        self,
        port: str | None = None,
        baud: int = BAUD,
        window_samples: int = WINDOW_SAMPLES,
        *,
        sample_rate: int = SAMPLE_HZ,
    ) -> None:
        self._port = port
        self._baud = baud
        self._window_samples = window_samples
        self._sample_rate = sample_rate

        self._link: object | None = None
        self._connected = False

        # The ring, and the lock that guards it. The reader thread appends and
        # read_window drains, so every touch is under the lock.
        self._ring: deque[float] = deque(maxlen=int(sample_rate * RING_SECONDS))
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

        # Boot header lines the sketch prints, collected for diagnostics.
        self._header: list[str] = []

        # Set when the reader thread loses the port. Read by `is_streaming` so
        # the UI can show the sensor has gone away.
        self._error: str | None = None
        self._last_sample_at: float = 0.0

    # -- SignalSource ------------------------------------------------------

    def connect(self) -> bool:
        """Open the port and start the reader thread.

        Raises SerialUnavailable with an operator facing message when the port
        cannot be opened, since that is the common case with a charge only
        cable or the Arduino Serial Monitor still holding the port.
        """
        serial, _ = _require_serial()

        port = self._port or discover_port()
        if port is None:
            raise SerialUnavailable(
                "No serial port found. Check that the Arduino is plugged in "
                "with a data cable rather than a charge only one, and that the "
                "Arduino Serial Monitor is closed. Nano clones may need the "
                "CH340 driver."
            )

        try:
            link = serial.Serial(port, self._baud, timeout=1.0)
        except serial.SerialException as exc:
            raise SerialUnavailable(
                f"Could not open {port}: {exc}. The Arduino Serial Monitor "
                "holds the port exclusively, so close it and try again."
            ) from exc

        # Discard whatever was mid transmission when the port opened, so the
        # first line parsed is a whole one.
        link.reset_input_buffer()
        time.sleep(0.2)

        self._port = port
        self._link = link
        self._error = None
        self._last_sample_at = time.monotonic()
        self._stop.clear()
        with self._lock:
            self._ring.clear()

        self._thread = threading.Thread(
            target=self._reader,
            name="serial-source-reader",
            daemon=True,
        )
        self._thread.start()

        self._connected = True
        return True

    def read_window(self) -> np.ndarray:
        """Return the next window, waiting only as long as READ_TIMEOUT_S.

        A short window is padded with the resting midpoint rather than raising.
        A sensor that has been unplugged mid session produces a flat trace and
        a collapsing SQI, which is what the badge is for: the session degrades
        visibly instead of ending in a stack trace.
        """
        if not self._connected:
            raise RuntimeError("read_window called before connect")

        deadline = time.monotonic() + READ_TIMEOUT_S
        while time.monotonic() < deadline:
            with self._lock:
                if len(self._ring) >= self._window_samples:
                    window = [self._ring.popleft() for _ in range(self._window_samples)]
                    return np.asarray(window, dtype=float)
            time.sleep(0.002)

        # Timed out. Return whatever arrived, padded to a full window so the
        # frame contract holds and the pipeline sees a real length.
        with self._lock:
            partial = [self._ring.popleft() for _ in range(len(self._ring))]

        window = np.zeros(self._window_samples, dtype=float)
        if partial:
            window[: len(partial)] = partial[: self._window_samples]
        return window

    @property
    def sample_rate(self) -> int:
        return self._sample_rate

    @property
    def is_live(self) -> bool:
        """Always True. These samples come from real hardware and the UI says so."""
        return True

    def disconnect(self) -> None:
        self._stop.set()

        thread, self._thread = self._thread, None
        if thread is not None:
            thread.join(timeout=2.0)

        link, self._link = self._link, None
        if link is not None:
            try:
                link.close()
            except Exception:  # noqa: BLE001 - closing must never raise
                pass

        self._connected = False
        with self._lock:
            self._ring.clear()

    # -- extras beyond the Protocol ---------------------------------------

    @property
    def window_samples(self) -> int:
        return self._window_samples

    @property
    def port(self) -> str | None:
        return self._port

    @property
    def header(self) -> list[str]:
        """Boot header lines the sketch printed, for diagnostics."""
        return list(self._header)

    @property
    def error(self) -> str | None:
        """Why the reader stopped, when it has."""
        return self._error

    @property
    def is_streaming(self) -> bool:
        """True while samples are still arriving.

        Goes False about a second after the cable is pulled, which is what
        lets the UI distinguish a resting muscle from a dead sensor.
        """
        if not self._connected or self._error is not None:
            return False
        return (time.monotonic() - self._last_sample_at) < READ_TIMEOUT_S

    # -- the reader thread -------------------------------------------------

    def _reader(self) -> None:
        """Drain the port into the ring until told to stop.

        Line handling matches tools/probe.py: skip blanks, collect the `#` boot
        header, require exactly two comma separated fields, and treat an
        unparseable number as the partial line it almost always is.
        """
        link = self._link
        if link is None:  # pragma: no cover - connect sets this first
            return

        while not self._stop.is_set():
            try:
                raw = link.readline()
            except Exception as exc:  # noqa: BLE001 - unplugging raises broadly
                self._error = (
                    f"Lost the sensor: {exc}. Check the USB cable is still seated."
                )
                return

            if not raw:
                # Timed out with nothing to read. Not an error on its own: the
                # sketch may simply be between samples.
                continue

            line = raw.decode("ascii", errors="replace").strip()
            if not line:
                continue

            if line.startswith("#"):
                self._header.append(line.lstrip("# ").strip())
                continue

            parts = line.split(",")
            if len(parts) != 2:
                continue

            try:
                counts = float(parts[1])
            except ValueError:
                # A partial line from the moment the port opened.
                continue

            with self._lock:
                self._ring.append((counts - ADC_MIDPOINT) / COUNTS_PER_UNIT)
            self._last_sample_at = time.monotonic()


__all__ = [
    "BAUD",
    "SAMPLE_HZ",
    "SerialSource",
    "SerialUnavailable",
    "discover_port",
    "list_candidate_ports",
]
