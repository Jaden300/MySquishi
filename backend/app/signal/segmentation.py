"""M2: contraction segmentation, the onset and offset detector.

Adaptive dual threshold in the Bonato tradition. A resting window sets the
baseline statistics, and two thresholds derived from it bracket the
contraction:

    t_on  = mu + k_on  * sigma
    t_off = mu + k_off * sigma      with k_off < k_on

The gap between them is hysteresis. A single threshold chatters when the
envelope hovers near it, splitting one repetition into several; requiring a
higher level to open and a lower one to close removes that.

Two dwell times finish the job: the envelope must stay above t_on for
min_on_ms before a repetition is declared, and below t_off for min_off_ms
before it closes. Short noise bursts therefore produce nothing at all.

Everything downstream depends on this being right. A segmenter that is
subtly wrong is worse than one that is broken, because the error propagates
silently into rep quality, fatigue, anomalies, and the prescriber.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

# Threshold multipliers in units of resting standard deviation.
DEFAULT_K_ON = 3.0
DEFAULT_K_OFF = 1.5

# Dwell times. Deliberately long enough to reject motion spikes, which are
# tens of milliseconds, while staying well inside a real contraction.
DEFAULT_MIN_ON_MS = 200.0
DEFAULT_MIN_OFF_MS = 200.0

# Repetitions shorter than this are treated as artifacts, not effort.
DEFAULT_MIN_REP_MS = 600.0

# How much of the trace start is assumed to be rest when no explicit baseline
# window is supplied.
DEFAULT_BASELINE_S = 2.0

# Fraction of the offset window that must sit below t_off for a repetition to
# close. Below 1.0 because a settling envelope crosses the threshold several
# times as baseline noise straddles it.
_OFF_MAJORITY = 0.85


@dataclass(frozen=True)
class Rep:
    """One detected repetition."""

    index: int
    start_idx: int
    peak_idx: int
    end_idx: int
    sample_rate: int
    peak_amplitude: float

    @property
    def start_s(self) -> float:
        return self.start_idx / self.sample_rate

    @property
    def peak_s(self) -> float:
        return self.peak_idx / self.sample_rate

    @property
    def end_s(self) -> float:
        return self.end_idx / self.sample_rate

    @property
    def duration_s(self) -> float:
        return (self.end_idx - self.start_idx) / self.sample_rate


@dataclass(frozen=True)
class SegmentationResult:
    """Detected repetitions plus the thresholds that produced them.

    The thresholds are carried so the UI can report them verbatim: M2 has no
    learned parameters, so its explanation is simply what it used.
    """

    reps: list[Rep]
    baseline_mean: float
    baseline_sd: float
    threshold_on: float
    threshold_off: float

    @property
    def count(self) -> int:
        return len(self.reps)


def _rolling_fraction(mask: np.ndarray, width: int) -> np.ndarray:
    """Fraction of the next `width` samples that are True, per position.

    Positions closer to the end than `width` are measured over whatever
    remains, so a repetition still closes when the trace runs out.
    """
    if mask.size == 0:
        return np.zeros(0)

    counts = np.cumsum(np.concatenate([[0.0], mask.astype(float)]))
    ends = np.minimum(np.arange(mask.size) + width, mask.size)
    windows = ends - np.arange(mask.size)
    return (counts[ends] - counts[: mask.size]) / np.maximum(windows, 1)


def estimate_baseline(
    envelope: np.ndarray,
    fs: int,
    baseline_s: float = DEFAULT_BASELINE_S,
) -> tuple[float, float]:
    """Resting mean and standard deviation from the head of the trace.

    Falls back to a robust low percentile band when the lead in is too short
    to sample, which is what happens on a stream that starts mid contraction.
    """
    arr = np.asarray(envelope, dtype=float)
    if arr.size == 0:
        return 0.0, 0.0

    n = int(baseline_s * fs)
    if n >= 8 and n <= arr.size:
        window = arr[:n]
    else:
        # No usable lead in: assume the quietest quartile is rest.
        cutoff = np.percentile(arr, 25)
        window = arr[arr <= cutoff]
        if window.size < 8:
            window = arr

    mean = float(window.mean())
    sd = float(window.std())

    # A perfectly quiet baseline would make every threshold equal to the mean
    # and detect nothing. Floor the spread at a small fraction of the signal.
    if sd <= 1e-12:
        sd = max(float(arr.std()) * 0.01, 1e-9)

    return mean, sd


def segment_reps(
    envelope: np.ndarray,
    fs: int,
    *,
    k_on: float = DEFAULT_K_ON,
    k_off: float = DEFAULT_K_OFF,
    min_on_ms: float = DEFAULT_MIN_ON_MS,
    min_off_ms: float = DEFAULT_MIN_OFF_MS,
    min_rep_ms: float = DEFAULT_MIN_REP_MS,
    baseline_s: float = DEFAULT_BASELINE_S,
    baseline: tuple[float, float] | None = None,
) -> SegmentationResult:
    """Detect repetitions in an RMS envelope.

    Pass baseline explicitly when segmenting a live stream incrementally, so
    the resting statistics stay fixed for the whole session rather than being
    re-estimated from whatever happens to be in the current buffer.
    """
    arr = np.asarray(envelope, dtype=float)
    if fs <= 0:
        raise ValueError(f"sample rate must be positive, got {fs}")
    if k_off >= k_on:
        raise ValueError(f"k_off ({k_off}) must be below k_on ({k_on}) for hysteresis")

    mean, sd = baseline if baseline is not None else estimate_baseline(arr, fs, baseline_s)
    t_on = mean + k_on * sd
    t_off = mean + k_off * sd

    empty = SegmentationResult([], mean, sd, t_on, t_off)
    if arr.size == 0:
        return empty

    min_on = max(1, int(min_on_ms * fs / 1000.0))
    min_off = max(1, int(min_off_ms * fs / 1000.0))
    min_rep = max(1, int(min_rep_ms * fs / 1000.0))

    reps: list[Rep] = []
    above_on = arr > t_on
    below_off = arr < t_off

    i = 0
    n = arr.size

    while i < n:
        # Find a candidate onset: the envelope must clear t_on and stay there.
        if not above_on[i]:
            i += 1
            continue

        run_end = i
        while run_end < n and above_on[run_end]:
            run_end += 1

        if run_end - i < min_on:
            # Too brief to be effort. This is the chatter suppression.
            i = run_end
            continue

        start = i

        # Walk forward for a sustained return below t_off.
        #
        # The criterion is a rolling majority rather than an unbroken run: a
        # real envelope settling back to rest crosses t_off repeatedly as
        # baseline noise straddles it, so requiring min_off consecutive
        # samples would hold the repetition open to the end of the trace.
        # Asking instead that most of the next min_off samples sit below the
        # threshold closes the rep where a reader would say it ended.
        end = n
        if run_end < n:
            quiet_fraction = _rolling_fraction(below_off, min_off)
            candidates = np.where(quiet_fraction[run_end:] >= _OFF_MAJORITY)[0]
            if candidates.size:
                end = run_end + int(candidates[0])

        if end - start >= min_rep:
            segment = arr[start:end]
            peak_offset = int(np.argmax(segment))
            reps.append(
                Rep(
                    index=len(reps),
                    start_idx=start,
                    peak_idx=start + peak_offset,
                    end_idx=end,
                    sample_rate=fs,
                    peak_amplitude=float(segment[peak_offset]),
                )
            )

        i = max(end + min_off, start + 1)

    return SegmentationResult(reps, mean, sd, t_on, t_off)


def describe(result: SegmentationResult) -> str:
    """Plain text explanation. M2 has no learned parameters, so its reasoning
    is simply the thresholds it applied."""
    return (
        f"Detected {result.count} repetitions. Resting baseline was "
        f"{result.baseline_mean:.4f} with a spread of {result.baseline_sd:.4f}. "
        f"A repetition opened above {result.threshold_on:.4f} and closed below "
        f"{result.threshold_off:.4f}."
    )
