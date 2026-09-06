"""Phase 2 hardware bring up probe.

Records a guided 60 second session from the Arduino, grades the rig, and
prints a tier verdict. Run it once with the sensor on your forearm and the
answer scopes what Phase 3 is allowed to build.

    backend/.venv/bin/pip install -r tools/requirements-probe.txt
    backend/.venv/bin/python -m tools.probe

This module is the only place in the repository that opens a serial port.
Everything it learns is handed to `probe_analysis`, which holds all of the
judgement and is tested with no hardware attached. Keeping acquisition thin
is what makes the verdict trustworthy: there is nothing to get wrong here
except reading bytes.

Re grade a recording you already have, with nothing plugged in:

    backend/.venv/bin/python -m tools.probe --replay calibration/probe_x.csv
"""

from __future__ import annotations

import argparse
import csv
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import numpy as np

from tools.probe_analysis import analyze, format_report

# Must match firmware/mysquishi_probe.ino. A mismatch here produces a stream
# of plausible looking garbage rather than an error, so the two are documented
# together and checked against the header the sketch prints on boot.
BAUD = 230400
SAMPLE_HZ = 500

# The MyoWare envelope filter and the AC coupling both need a moment to settle
# after the sensor powers up. Those first samples are not resting baseline,
# they are a capacitor charging, and letting them into the rest window would
# inflate the baseline and crush the contrast ratio.
WARMUP_S = 0.5

# The scripted protocol. Each entry is a prompt, a duration, and the phase
# label the analysis uses. Rest appears three times but only the first span is
# labelled: one clean rest window is what the contrast needs, and the later
# ones exist to let the muscle recover so the hard squeeze is really hard.
PROTOCOL: tuple[tuple[str, float, str | None], ...] = (
    ("Relax completely. Let your arm rest.", 10.0, "rest"),
    ("Squeeze LIGHTLY, about a quarter of your strength.", 5.0, "light"),
    ("Relax again.", 10.0, None),
    ("Squeeze HARD, as hard as you comfortably can.", 5.0, "hard"),
    ("Relax again.", 10.0, None),
    ("Three short HARD pulses: squeeze, release, repeat.", 15.0, None),
)

# Serial ports that are never an Arduino. macOS lists these permanently and
# offering them in the menu just invites a wrong answer.
PORT_DENYLIST = ("Bluetooth-Incoming-Port", "debug-console")

# Substrings that identify a USB serial adapter across the common boards:
# genuine Uno, FTDI and CP210x adapters, and the CH340 on Nano clones.
PORT_HINTS = ("usbmodem", "usbserial", "wchusb", "SLAB", "ttyACM", "ttyUSB")


@dataclass(frozen=True)
class Recording:
    """What the acquisition produced, before any judgement."""

    timestamps_ms: np.ndarray
    counts: np.ndarray
    phases: dict[str, tuple[float, float]]
    header: list[str]

    @property
    def duration_s(self) -> float:
        if self.timestamps_ms.size < 2:
            return 0.0
        return float(self.timestamps_ms[-1] - self.timestamps_ms[0]) / 1000.0


def _fail(message: str) -> None:
    """Print an operator facing error and stop.

    Bring up happens with electrodes taped to an arm, so an error here has to
    say what to do next, not just what went wrong.
    """
    print(f"\n  {message}\n", file=sys.stderr)
    raise SystemExit(1)


def _require_serial():  # type: ignore[no-untyped-def]
    """Import pyserial, or explain how to get it.

    pyserial is deliberately absent from backend/requirements.txt: two guard
    tests assert it is not there, which is what keeps the application serial
    free until Phase 3 adds a SerialSource on purpose. The probe declares it
    separately.
    """
    try:
        import serial  # noqa: PLC0415
        from serial.tools import list_ports  # noqa: PLC0415
    except ImportError:
        _fail(
            "pyserial is not installed. From the backend directory run:\n\n"
            "      .venv/bin/pip install -r tools/requirements-probe.txt"
        )
    return serial, list_ports


def discover_port(explicit: str | None = None) -> str:
    """Find the Arduino, asking only when the answer is genuinely ambiguous."""
    _, list_ports = _require_serial()

    if explicit:
        return explicit

    ports = [
        p
        for p in list_ports.comports()
        if not any(deny in p.device for deny in PORT_DENYLIST)
    ]
    likely = [p for p in ports if any(hint in p.device for hint in PORT_HINTS)]

    if len(likely) == 1:
        print(f"  Found {likely[0].device}  ({likely[0].description})")
        return str(likely[0].device)

    candidates = likely or ports
    if not candidates:
        _fail(
            "No serial ports found. Check that the Arduino is plugged in with a\n"
            "  data cable rather than a charge only one, and that the Serial\n"
            "  Monitor is closed. Nano clones may need the CH340 driver."
        )

    print("\n  Multiple ports found:\n")
    for i, port in enumerate(candidates, 1):
        print(f"    {i}. {port.device}  ({port.description})")

    while True:
        choice = input("\n  Which one is the Arduino? ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(candidates):
            return str(candidates[int(choice) - 1].device)
        print("  Enter one of the numbers above.")


def _countdown(prompt: str, seconds: float) -> None:
    """Show a live countdown so the builder knows when to change effort."""
    end = time.monotonic() + seconds
    while True:
        remaining = end - time.monotonic()
        if remaining <= 0:
            break
        print(f"\r  {prompt}  [{remaining:4.1f}s]", end="", flush=True)
        time.sleep(0.1)
    print(f"\r  {prompt}  [ done ]" + " " * 10)


def record(
    port: str,
    *,
    guided: bool = True,
    seconds: float = 60.0,
    protocol: tuple[tuple[str, float, str | None], ...] | None = None,
    lead_in: "Callable[[str, str | None], None] | None" = None,
) -> Recording:
    """Run the protocol and collect the trace.

    Returns whatever was captured even if the builder interrupts partway, on
    the principle that a short recording still grades and a lost one does not.

    `protocol` overrides the module level PROTOCOL, and `lead_in` is called
    before each span's window opens. Both exist for tools/gestures.py, which
    needs a different phase table and a countdown ahead of every pose. They
    have to be handled inside this loop rather than by calling record() once
    per span: reopening the port between spans resets the link, which drops
    samples and pushes the recorded phase offsets out of step with the data.
    """
    serial, _ = _require_serial()

    try:
        link = serial.Serial(port, BAUD, timeout=1.0)
    except serial.SerialException as exc:
        _fail(
            f"Could not open {port}: {exc}\n\n"
            "  The Serial Monitor holds the port exclusively. Close it and\n"
            "  try again."
        )

    timestamps: list[float] = []
    counts: list[float] = []
    header: list[str] = []
    phases: dict[str, tuple[float, float]] = {}

    with link:
        # Discard whatever was mid transmission when the port opened, so the
        # first line parsed is a whole one.
        link.reset_input_buffer()
        time.sleep(0.2)

        started = time.monotonic()
        if protocol is not None:
            plan = protocol
        else:
            plan = PROTOCOL if guided else (("Recording.", seconds, None),)

        if guided and lead_in is None:
            print("\n  Starting in 3 seconds. Get comfortable.\n")
            time.sleep(3.0)

        try:
            for prompt, duration, label in plan:
                if lead_in is not None:
                    # The countdown runs before the window opens, so the
                    # seconds spent reading the prompt are not measured as
                    # part of the pose.
                    lead_in(prompt, label)

                phase_start = time.monotonic() - started
                deadline = time.monotonic() + duration

                while time.monotonic() < deadline:
                    raw = link.readline()
                    if not raw:
                        continue
                    line = raw.decode("ascii", errors="replace").strip()
                    if not line:
                        continue
                    if line.startswith("#"):
                        header.append(line.lstrip("# ").strip())
                        continue
                    parts = line.split(",")
                    if len(parts) != 2:
                        continue
                    try:
                        timestamps.append(float(parts[0]))
                        counts.append(float(parts[1]))
                    except ValueError:
                        # A partial line from the moment the port opened.
                        continue

                    remaining = deadline - time.monotonic()
                    print(f"\r  {prompt}  [{remaining:4.1f}s]", end="", flush=True)

                print(f"\r  {prompt}  [ done ]" + " " * 12)

                if label is not None:
                    phases[label] = (phase_start, time.monotonic() - started)

        except KeyboardInterrupt:
            print("\n\n  Interrupted. Grading what was captured so far.")
            phases = {}

    if not counts:
        _fail(
            "No data received. Check the baud rate matches the sketch (230400),\n"
            "  and that the Arduino is running mysquishi_probe.ino."
        )

    return Recording(
        timestamps_ms=np.asarray(timestamps, dtype=float),
        counts=np.asarray(counts, dtype=float),
        phases=phases,
        header=header,
    )


def trim_warmup(recording: Recording) -> Recording:
    """Drop the settling period at the start of the recording."""
    if recording.timestamps_ms.size == 0:
        return recording

    origin = recording.timestamps_ms[0]
    keep = (recording.timestamps_ms - origin) >= WARMUP_S * 1000.0
    if not keep.any():
        return recording

    # Phase spans are measured from the start of acquisition, so they shift by
    # exactly the amount trimmed.
    shifted = {
        label: (max(0.0, start - WARMUP_S), max(0.0, end - WARMUP_S))
        for label, (start, end) in recording.phases.items()
    }
    return Recording(
        timestamps_ms=recording.timestamps_ms[keep],
        counts=recording.counts[keep],
        phases=shifted,
        header=recording.header,
    )


def save(recording: Recording, verdict_tier: str) -> Path:
    """Write the trace to calibration/, raw counts preserved.

    Integer ADC counts are stored rather than anything scaled, because a
    recording is only re analyzable if it still says what the converter
    actually saw. These files are also the seed corpus for the Phase 3
    ReplaySource, which is the demo insurance if the hardware dies later.
    """
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = Path(__file__).resolve().parents[1] / "calibration"
    out_dir.mkdir(exist_ok=True)
    path = out_dir / f"probe_{stamp}.csv"

    with path.open("w", newline="") as handle:
        writer = csv.writer(handle)
        for line in recording.header:
            handle.write(f"# {line}\n")
        handle.write(f"# recorded={stamp}\n")
        handle.write(f"# tier={verdict_tier}\n")
        for label, (start, end) in sorted(recording.phases.items()):
            handle.write(f"# phase_{label}={start:.2f},{end:.2f}\n")
        writer.writerow(["millis", "adc_counts"])
        writer.writerows(
            zip(recording.timestamps_ms.astype(int), recording.counts.astype(int))
        )

    return path


def load(path: Path) -> Recording:
    """Read a recording back for re grading, with its phase spans."""
    timestamps: list[float] = []
    counts: list[float] = []
    phases: dict[str, tuple[float, float]] = {}
    header: list[str] = []

    with path.open() as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            if line.startswith("#"):
                body = line.lstrip("# ").strip()
                header.append(body)
                if body.startswith("phase_") and "=" in body:
                    name, _, span = body.partition("=")
                    start, _, end = span.partition(",")
                    try:
                        phases[name[len("phase_") :]] = (float(start), float(end))
                    except ValueError:
                        continue
                continue
            parts = line.split(",")
            if len(parts) != 2 or not parts[0].lstrip("-").isdigit():
                continue
            timestamps.append(float(parts[0]))
            counts.append(float(parts[1]))

    if not counts:
        _fail(f"No samples found in {path}.")

    return Recording(
        timestamps_ms=np.asarray(timestamps, dtype=float),
        counts=np.asarray(counts, dtype=float),
        phases=phases,
        header=header,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="probe",
        description="Grade the MyoWare rig and report a tier, A through D.",
    )
    parser.add_argument("--port", help="serial port, otherwise auto detected")
    parser.add_argument(
        "--replay", type=Path, help="re grade a saved CSV, no hardware needed"
    )
    parser.add_argument(
        "--no-protocol",
        action="store_true",
        help="free run instead of the guided protocol, no separability score",
    )
    parser.add_argument(
        "--seconds", type=float, default=60.0, help="free run duration"
    )
    args = parser.parse_args(argv)

    if args.replay:
        recording = load(args.replay)
        print(f"\n  Re grading {args.replay}")
    else:
        print("\n" + "=" * 62)
        print("  MySquishi hardware probe")
        print("=" * 62)
        print("\n  Before starting, confirm:")
        print("    - the MyoWare output selector is on RAW, not ENV")
        print("    - electrodes are fresh and firmly attached")
        print("    - the laptop charger is unplugged")
        print("    - the Arduino Serial Monitor is closed\n")

        port = discover_port(args.port)
        recording = trim_warmup(
            record(port, guided=not args.no_protocol, seconds=args.seconds)
        )

    verdict = analyze(
        recording.counts,
        SAMPLE_HZ,
        phases=recording.phases or None,
        timestamps_ms=recording.timestamps_ms,
        counts=recording.counts,
    )

    print(format_report(verdict))

    if not args.replay:
        path = save(recording, verdict.tier)
        print(f"  Trace saved to {path}\n")

    print(f"  Report this tier: {verdict.tier}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
