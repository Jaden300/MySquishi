"""The live session loop.

Drives one websocket session from start to summary. The socket carries
frames, not queries: everything else in the app is REST. See the streaming
contract in docs/ARCHITECTURE.md.

Three details here are easy to get wrong and expensive to debug:

**The source blocks.** SimulatedSource paces its reads against the wall clock
so the client sees a realistic frame rate. Calling read_window on the event
loop would stall every other request in the process, so it goes through a
thread executor.

**Filtering is not per frame.** filters.preprocess uses filtfilt, which is
non causal and needs padding either side. Filtering each 200 sample frame in
isolation puts an edge transient at every frame boundary, five times a
second. So a rolling buffer is filtered and only its tail is emitted.

**The segmentation baseline is frozen.** M2's thresholds come from resting
statistics. Re-estimating them from the current buffer mid session would let
the thresholds drift upward as the patient works, and repetitions would
quietly stop being detected. The baseline is measured once from the opening
rest window and passed explicitly from then on.
"""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone

import numpy as np

from app.clinical_gate import DEFAULT_MUSCLE
from app.config import settings
from app.ml import fatigue, force, quality, rep_quality
from app.ml.registry import registry
from app.signal.features import rep_features, window_features
from app.signal.filters import preprocess
from app.signal.segmentation import segment_reps

# How much history the rolling buffer holds. Ten seconds is comfortably longer
# than any single repetition, so a repetition is always wholly inside the
# buffer when it closes, and short enough that refiltering it stays cheap.
BUFFER_SECONDS = 10.0

# Resting window used to fix the segmentation baseline, in seconds.
BASELINE_SECONDS = 2.0

# Envelope points per frame. One per 10 ms at a 200 ms window.
ENVELOPE_POINTS = 20

# Used when a session runs before calibration. The frame carries
# calibrated=False so the UI can say the kilogram figures are uncalibrated
# rather than presenting them as if they were measured.
DEFAULT_MVC_REFERENCE_RMS = 0.15

# The keys every frame carries. Exposed so the frontend can assert the
# contract rather than discovering a missing field as undefined in a chart.
FRAME_KEYS: tuple[str, ...] = (
    "type",
    "t",
    "seq",
    "fs",
    "raw",
    "envelope",
    "mvc_pct",
    "sqi",
    "is_live",
    "source_id",
    "muscle",
    "calibrated",
    "rep_event",
    "coach",
)


def _decimate(x: np.ndarray, points: int) -> list[float]:
    """Reduce a trace to a fixed number of points for transport.

    Picks evenly spaced samples rather than averaging: the oscilloscope is
    showing a shape, and averaging would flatten exactly the peaks that make
    a contraction legible.
    """
    arr = np.asarray(x, dtype=float)
    if arr.size == 0:
        return []
    if arr.size <= points:
        return [round(float(v), 5) for v in arr]

    idx = np.linspace(0, arr.size - 1, points).astype(int)
    return [round(float(v), 5) for v in arr[idx]]


@dataclass
class CoachState:
    """The on screen prompt.

    A small state machine so the patient is told what to do next in plain
    language, in the voice docs/DESIGN.md sets: "Squeeze and hold", not
    "initiate isometric contraction protocol".
    """

    target_mvc_pct: float = 50.0
    hold_s: float = 5.0
    rest_s: float = 5.0
    ramp_s: float = 1.5

    phase: str = "ready"
    phase_started_s: float = 0.0
    reps_done: int = 0

    def update(self, t: float, mvc_pct: float) -> dict[str, object]:
        elapsed = t - self.phase_started_s

        if self.phase == "ready":
            # Waiting for the patient to start pulling.
            if mvc_pct > 8.0:
                self._to("ramp", t)
            prompt = "When you are ready, squeeze."
            remaining = 0.0

        elif self.phase == "ramp":
            if elapsed >= self.ramp_s or mvc_pct >= self.target_mvc_pct * 0.8:
                self._to("hold", t)
            prompt = f"Build up to {self.target_mvc_pct:.0f} percent."
            remaining = max(0.0, self.ramp_s - elapsed)

        elif self.phase == "hold":
            if elapsed >= self.hold_s:
                self._to("release", t)
            prompt = "Hold it steady."
            remaining = max(0.0, self.hold_s - elapsed)

        elif self.phase == "release":
            if mvc_pct < 8.0:
                self.reps_done += 1
                self._to("rest", t)
            prompt = "Ease off slowly."
            remaining = 0.0

        else:  # rest
            if elapsed >= self.rest_s:
                self._to("ready", t)
            prompt = "Rest."
            remaining = max(0.0, self.rest_s - elapsed)

        return {
            "phase": self.phase,
            "seconds_remaining": round(remaining, 1),
            "prompt": prompt,
            "target_mvc_pct": self.target_mvc_pct,
            "reps_done": self.reps_done,
        }

    def _to(self, phase: str, t: float) -> None:
        self.phase = phase
        self.phase_started_s = t


@dataclass
class LiveSessionRunner:
    """One live session.

    Holds the rolling buffer, the frozen baseline, and the repetitions
    detected so far. Persistence happens once, when the session closes.
    """

    source_id: str = "simulated"
    patient_id: str = "demo"
    muscle: str = DEFAULT_MUSCLE
    mvc_reference_rms: float = DEFAULT_MVC_REFERENCE_RMS
    calibrated: bool = False
    junkiness: float = 0.0

    source: object | None = None
    seq: int = 0
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    _t0: float = 0.0

    # Rolling raw buffer, and how many samples have been discarded off the
    # front of it, so buffer indices can be mapped back to session time.
    buffer: np.ndarray = field(default_factory=lambda: np.array([], dtype=float))
    samples_dropped: int = 0

    baseline: tuple[float, float] | None = None
    last_rep_end_abs: int = -1

    reps: list[dict[str, object]] = field(default_factory=list)
    sqi_values: list[float] = field(default_factory=list)
    mvc_values: list[float] = field(default_factory=list)
    coach: CoachState = field(default_factory=CoachState)

    # Amplitude features from the hardest window of the session, which is what
    # M3 turns into kilograms when the session closes. Held here because the
    # force model wants rms, mav and waveform_length, and only window_features
    # produces those: the per rep feature set describes effort shape instead.
    peak_window_features: dict[str, float] | None = None
    _peak_window_rms: float = -1.0

    def __post_init__(self) -> None:
        self._m1 = registry.try_load("M1")
        self._m4 = registry.try_load("M4")

    # -- lifecycle ---------------------------------------------------------

    def connect(self) -> None:
        """Open the source. Everything goes through the factory."""
        from app.sources.base import get_source

        kwargs: dict[str, object] = {}
        if self.source_id == "simulated":
            kwargs["junkiness"] = self.junkiness

        self.source = get_source(self.source_id, **kwargs)
        self.source.connect()  # type: ignore[union-attr]
        self._t0 = time.monotonic()

    def disconnect(self) -> None:
        if self.source is not None:
            self.source.disconnect()  # type: ignore[union-attr]
            self.source = None

    @property
    def sample_rate(self) -> int:
        return int(self.source.sample_rate) if self.source else settings.sample_rate

    @property
    def window_samples(self) -> int:
        """The source's own window size, not the global default.

        Sources do not agree on this: the simulator runs 200 samples at
        1000 Hz while the sensor runs 100 at 500 Hz. Both are 200 ms, and
        reading it from the source is what keeps session duration correct
        whichever one is selected.
        """
        if self.source is not None:
            declared = getattr(self.source, "window_samples", None)
            if isinstance(declared, int) and declared > 0:
                return declared
        return settings.window_samples

    @property
    def is_live(self) -> bool:
        return bool(self.source.is_live) if self.source else False

    async def read_window(self) -> np.ndarray:
        """Read one window without blocking the event loop.

        The source sleeps to pace itself against the wall clock, so this has
        to happen on a worker thread.
        """
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self.source.read_window)  # type: ignore[union-attr]

    # -- per frame ---------------------------------------------------------

    def process(self, window: np.ndarray) -> dict[str, object]:
        """Turn one raw window into a frame."""
        fs = self.sample_rate
        self.seq += 1
        t = self.seq * len(window) / fs

        self._append(window, fs)

        # Filter the buffer, not the isolated window, so filtfilt's edge
        # transients land inside history rather than at the frame boundary.
        result = preprocess(self.buffer, fs)
        envelope = result.envelope

        window_env = envelope[-len(window):] if envelope.size >= len(window) else envelope
        window_rms = float(np.sqrt(np.mean(np.square(window)))) if window.size else 0.0

        # Percent MVC is computed here and only here. The frontend never
        # divides, so there is exactly one definition of it in the system.
        mvc_pct = force.percent_mvc(window_rms, self.mvc_reference_rms)
        self.mvc_values.append(mvc_pct)

        sqi_assessment = quality.assess(window, fs, self._m1)
        sqi_value = float(sqi_assessment.score.point)
        self.sqi_values.append(sqi_value)

        # Keep the amplitude features of the hardest window seen. M3 reads
        # these on close to estimate force in kilograms, for grip only.
        self._track_peak_window(window, fs, window_rms)

        self._freeze_baseline(envelope, fs)
        rep_event = self._detect_rep(result, envelope, fs)

        return {
            "type": "frame",
            "t": round(t, 3),
            "seq": self.seq,
            "fs": fs,
            "raw": _decimate(window, settings.frame_raw_points),
            "envelope": _decimate(window_env, ENVELOPE_POINTS),
            "mvc_pct": round(mvc_pct, 2),
            "sqi": round(sqi_value, 1),
            "is_live": self.is_live,
            "source_id": self.source_id,
            "muscle": self.muscle,
            "calibrated": self.calibrated,
            "rep_event": rep_event,
            "coach": self.coach.update(t, mvc_pct),
        }

    def _append(self, window: np.ndarray, fs: int) -> None:
        """Add a window to the rolling buffer, trimming the front."""
        self.buffer = np.concatenate([self.buffer, np.asarray(window, dtype=float)])

        limit = int(BUFFER_SECONDS * fs)
        if self.buffer.size > limit:
            excess = self.buffer.size - limit
            self.buffer = self.buffer[excess:]
            self.samples_dropped += excess

    def _freeze_baseline(self, envelope: np.ndarray, fs: int) -> None:
        """Fix the resting statistics once, from the opening rest window."""
        if self.baseline is not None:
            return
        if envelope.size < int(BASELINE_SECONDS * fs):
            return

        from app.signal.segmentation import estimate_baseline

        self.baseline = estimate_baseline(envelope, fs, BASELINE_SECONDS)

    def _detect_rep(
        self,
        result,
        envelope: np.ndarray,
        fs: int,
    ) -> dict[str, object] | None:
        """Emit a repetition once, when it closes.

        The buffer slides, so a buffer index means a different moment on every
        frame. Indices are converted to absolute sample positions before being
        compared against what has already been emitted.

        Two properties of segment_reps on a live buffer shape the rest of
        this. It closes a trailing repetition at the end of the array whether
        or not the envelope has come back down, which is right on a finished
        recording but means an in progress repetition looks closed on every
        frame. And once the buffer has trimmed past a repetition's onset, that
        repetition appears to start at the buffer's left edge, so its start
        position creeps forward frame by frame.

        So identity is keyed on the **end** position, which stops moving once
        a repetition genuinely closes, and a repetition is only emitted once
        its end sits clear of the buffer edge, which is what distinguishes a
        real relaxation from simply running out of samples.

        The end position is compared with a tolerance rather than exactly.
        Refiltering a sliding buffer moves a boundary by a few samples between
        frames, so an exact comparison would let the same repetition through
        twice on a drift of one sample. Nothing genuinely new can close within
        M2's minimum repetition length of the previous one, so that is the
        separation required.
        """
        if self.baseline is None:
            return None

        segmentation = segment_reps(envelope, fs, baseline=self.baseline)

        # A repetition must have closed at least this far from the edge to be
        # believed: the minimum off duration M2 requires, plus a window.
        edge_guard = int(0.4 * fs)
        closed_before = envelope.size - edge_guard

        # Two repetitions cannot legitimately close closer together than the
        # minimum repetition duration.
        min_separation = int(0.6 * fs)

        # A repetition whose onset has already been trimmed off the front of
        # the buffer is only partly observed. Its features would describe a
        # fragment rather than a contraction, so it is left alone: better to
        # miss a repetition than to score a piece of one.
        onset_guard = 2 if self.samples_dropped > 0 else 0

        newest = None
        for rep in segmentation.reps:
            end_abs = rep.end_idx + self.samples_dropped
            if (
                end_abs > self.last_rep_end_abs + min_separation
                and rep.end_idx <= closed_before
                and rep.start_idx >= onset_guard
            ):
                newest = (rep, end_abs)

        if newest is None:
            return None

        rep, end_abs = newest
        self.last_rep_end_abs = end_abs

        try:
            features = rep_features(
                envelope,
                result.filtered,
                fs,
                start_idx=rep.start_idx,
                peak_idx=rep.peak_idx,
                end_idx=rep.end_idx,
                mvc_reference=self.mvc_reference_rms,
            )
        except ValueError:
            # The repetition started before the buffer window. Nothing useful
            # to score, so it is skipped rather than scored from a fragment.
            return None

        scored = rep_quality.score(features, self._m4)
        index = len(self.reps)

        record = {
            "index": index,
            "start_s": round((rep.start_idx + self.samples_dropped) / fs, 3),
            "peak_s": round((rep.peak_idx + self.samples_dropped) / fs, 3),
            "end_s": round(end_abs / fs, 3),
            "features": features,
            "quality": scored.score.to_dict(),
            "top_factor": scored.top_factor,
            "feedback": scored.feedback,
        }
        self.reps.append(record)

        return {
            "index": index,
            "peak_mvc": round(features["peak_mvc"], 1),
            "quality": scored.score.to_dict(),
            "factor": scored.top_factor,
            "feedback": scored.feedback,
        }

    def _track_peak_window(
        self, window: np.ndarray, fs: int, window_rms: float
    ) -> None:
        """Remember the amplitude features of the hardest window so far.

        The peak is the right anchor for a force estimate: calibration asks the
        patient for a maximal effort and records what it was worth, so the
        session's own maximum is the comparable quantity.
        """
        if window.size == 0 or window_rms <= self._peak_window_rms:
            return

        self._peak_window_rms = window_rms
        self.peak_window_features = window_features(window, fs)

    # -- close -------------------------------------------------------------

    def summary(self) -> dict[str, object]:
        """The one summary frame sent on stop.

        M5 runs here rather than per frame: a fatigue slope over two
        repetitions would be noise, and the whole point of the measure is the
        trend across the session.
        """
        mdfs = [float(r["features"]["median_frequency"]) for r in self.reps]  # type: ignore[index]
        peaks = [float(r["features"]["peak_mvc"]) for r in self.reps]  # type: ignore[index]
        dimitrovs = [float(r["features"]["dimitrov_index"]) for r in self.reps]  # type: ignore[index]

        fatigue_payload: dict[str, object] | None = None
        if len(mdfs) >= 3:
            assessment = fatigue.assess(
                np.array(mdfs),
                peak_amplitudes=np.array(peaks),
                dimitrov_indices=np.array(dimitrovs),
            )
            fatigue_payload = assessment.to_dict()

        qualities = [float(r["quality"]["point"]) for r in self.reps]  # type: ignore[index]

        return {
            "type": "summary",
            "seq": self.seq,
            "rep_count": len(self.reps),
            "mean_mvc": round(float(np.mean(self.mvc_values)), 2) if self.mvc_values else 0.0,
            "peak_mvc": round(float(np.max(self.mvc_values)), 2) if self.mvc_values else 0.0,
            "mean_rep_quality": round(float(np.mean(qualities)), 1) if qualities else None,
            "sqi_mean": round(float(np.mean(self.sqi_values)), 1) if self.sqi_values else None,
            "duration_s": round(self.seq * self.window_samples / self.sample_rate, 1),
            "total_impulse": round(
                sum(float(r["features"]["impulse"]) for r in self.reps), 2  # type: ignore[index]
            ),
            "fatigue": fatigue_payload,
            "is_live": self.is_live,
            "source_id": self.source_id,
            "muscle": self.muscle,
            "calibrated": self.calibrated,
            "reps": [
                {
                    "index": r["index"],
                    "peak_mvc": round(float(r["features"]["peak_mvc"]), 1),  # type: ignore[index]
                    "quality": r["quality"],
                    "feedback": r["feedback"],
                }
                for r in self.reps
            ],
        }


def frame_json(payload: dict[str, object]) -> str:
    """Serialize a frame. Kept in one place so the wire format has one owner."""
    return json.dumps(payload)


__all__ = [
    "BUFFER_SECONDS",
    "CoachState",
    "FRAME_KEYS",
    "LiveSessionRunner",
    "frame_json",
]
