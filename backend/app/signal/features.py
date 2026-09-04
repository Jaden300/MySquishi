"""Time domain and frequency domain feature extraction.

Two families:

- window_features runs on short windows of the live stream and feeds M1, the
  signal quality index.
- rep_features runs on a completed repetition and feeds M4 (rep quality) and
  M5 (spectral fatigue).

The key sets are frozen and asserted in tests. They are the contract the ML
layer consumes, so adding or renaming a key is a deliberate change that
breaks a test rather than a silent one that corrupts a model's inputs.

Clinical definitions for these terms are in docs/CLINICAL.md.
"""

from __future__ import annotations

import numpy as np
from scipy import signal as sps

from app.signal.filters import BAND_HIGH_HZ, BAND_LOW_HZ, MAINS_HZ

# The exact keys each extractor returns. Frozen on purpose.
WINDOW_FEATURE_KEYS: tuple[str, ...] = (
    "rms",
    "mav",
    "zero_crossings",
    "slope_sign_changes",
    "waveform_length",
    "saturation_ratio",
    "baseline_drift",
    "mains_ratio",
    "snr_estimate",
)

REP_FEATURE_KEYS: tuple[str, ...] = (
    "peak_mvc",
    "mean_mvc",
    "time_to_peak_s",
    "rfd",
    "duration_s",
    "relaxation_time_s",
    "hold_cv",
    "plateau_flatness",
    "impulse",
    "median_frequency",
    "mean_frequency",
    "dimitrov_index",
)

# Amplitude threshold below which zero crossing and slope sign counts are
# treated as noise rather than signal.
_NOISE_DEADZONE = 1e-6


def _as_1d(x: np.ndarray) -> np.ndarray:
    arr = np.asarray(x, dtype=float)
    if arr.ndim != 1:
        raise ValueError(f"expected a 1D array, got shape {arr.shape}")
    return arr


def _psd(x: np.ndarray, fs: int) -> tuple[np.ndarray, np.ndarray]:
    """Welch power spectral density restricted to the sEMG band."""
    if x.size < 8:
        return np.zeros(0), np.zeros(0)

    nperseg = min(256, max(32, x.size // 4))
    freqs, psd = sps.welch(x, fs=fs, nperseg=nperseg)
    band = (freqs >= BAND_LOW_HZ) & (freqs <= BAND_HIGH_HZ)
    return freqs[band], psd[band]


def median_frequency(x: np.ndarray, fs: int) -> float:
    """MDF: the frequency splitting spectral power into equal halves.

    Falls as a muscle fatigues. This is the quantity M5 regresses against
    repetition index, and the strongest technical claim in the project.
    """
    freqs, psd = _psd(_as_1d(x), fs)
    total = psd.sum()
    if freqs.size == 0 or total <= 0:
        return float("nan")

    cumulative = np.cumsum(psd)
    return float(freqs[np.searchsorted(cumulative, total / 2.0)])


def mean_frequency(x: np.ndarray, fs: int) -> float:
    """MNF: the power weighted average frequency."""
    freqs, psd = _psd(_as_1d(x), fs)
    total = psd.sum()
    if freqs.size == 0 or total <= 0:
        return float("nan")
    return float(np.sum(freqs * psd) / total)


def dimitrov_index(x: np.ndarray, fs: int) -> float:
    """Dimitrov spectral fatigue index.

    Ratio of a low order to a high order spectral moment. Weighted toward low
    frequency content, so it rises as fatigue shifts the spectrum down. A
    secondary readout alongside MDF.
    """
    freqs, psd = _psd(_as_1d(x), fs)
    if freqs.size == 0 or psd.sum() <= 0:
        return float("nan")

    positive = freqs > 0
    freqs, psd = freqs[positive], psd[positive]
    if freqs.size == 0:
        return float("nan")

    moment_minus_1 = float(np.sum(psd / freqs))
    moment_5 = float(np.sum(psd * freqs**5))
    if moment_5 <= 0:
        return float("nan")
    return moment_minus_1 / moment_5


def window_features(x: np.ndarray, fs: int) -> dict[str, float]:
    """Features for one short window of the live stream. Feeds M1.

    These describe signal integrity rather than effort: is this trace
    trustworthy, or is the electrode loose and the mains bleeding in.
    """
    arr = _as_1d(x)
    if arr.size == 0:
        return dict.fromkeys(WINDOW_FEATURE_KEYS, 0.0)

    rms = float(np.sqrt(np.mean(arr**2)))
    mav = float(np.mean(np.abs(arr)))

    # Count sign changes and slope reversals, ignoring near zero jitter.
    centered = arr - arr.mean()
    above = np.abs(centered) > _NOISE_DEADZONE
    signs = np.sign(centered)
    crossings = int(np.sum((signs[:-1] * signs[1:] < 0) & above[:-1] & above[1:]))

    diffs = np.diff(arr)
    slope_changes = int(np.sum(diffs[:-1] * diffs[1:] < 0))

    waveform_length = float(np.sum(np.abs(diffs)))

    # Saturation: samples pinned at the observed extremes, which is what
    # clipping against an ADC rail looks like.
    span = float(arr.max() - arr.min())
    if span > 0:
        near_rail = (arr >= arr.max() - span * 0.001) | (arr <= arr.min() + span * 0.001)
        saturation = float(np.sum(near_rail) / arr.size)
    else:
        # A perfectly flat window is a dead electrode: fully saturated.
        saturation = 1.0

    # Baseline drift: how far the window mean wanders from its own start,
    # normalized so it is comparable across amplitudes.
    if arr.size >= 4:
        halves = np.array_split(arr, 4)
        means = np.array([float(h.mean()) for h in halves])
        drift = float(means.max() - means.min())
        baseline_drift = drift / rms if rms > 1e-12 else 0.0
    else:
        baseline_drift = 0.0

    # Mains contamination as a fraction of total band power.
    freqs, psd = _psd(arr, fs)
    if freqs.size and psd.sum() > 0:
        near_mains = np.abs(freqs - MAINS_HZ) <= 2.5
        mains_ratio = float(psd[near_mains].sum() / psd.sum())

        # Crude SNR: power in the physiological band away from mains, against
        # the power sitting at mains and at the spectral edges.
        signal_band = (freqs >= 30.0) & (freqs <= 300.0) & ~near_mains
        noise = psd[near_mains].sum() + psd[freqs > 380.0].sum()
        snr = float(psd[signal_band].sum() / noise) if noise > 0 else 100.0
    else:
        mains_ratio = 0.0
        snr = 0.0

    return {
        "rms": rms,
        "mav": mav,
        "zero_crossings": float(crossings),
        "slope_sign_changes": float(slope_changes),
        "waveform_length": waveform_length,
        "saturation_ratio": saturation,
        "baseline_drift": baseline_drift,
        "mains_ratio": mains_ratio,
        "snr_estimate": float(np.clip(snr, 0.0, 100.0)),
    }


def rep_features(
    envelope: np.ndarray,
    filtered: np.ndarray,
    fs: int,
    *,
    start_idx: int,
    peak_idx: int,
    end_idx: int,
    mvc_reference: float,
) -> dict[str, float]:
    """Features for one completed repetition. Feeds M4 and M5.

    envelope is the RMS envelope, filtered is the bandpassed trace the
    spectral measures run on, and mvc_reference is the calibration RMS that
    turns raw amplitude into percent MVC.
    """
    env = _as_1d(envelope)
    filt = _as_1d(filtered)

    if not 0 <= start_idx < end_idx <= env.size:
        raise ValueError(f"rep bounds {start_idx}-{end_idx} outside array of {env.size}")
    if mvc_reference <= 0:
        raise ValueError(f"mvc_reference must be positive, got {mvc_reference}")

    segment = env[start_idx:end_idx]
    if segment.size == 0:
        return dict.fromkeys(REP_FEATURE_KEYS, 0.0)

    # Percent MVC is the normalization that makes sessions comparable.
    as_mvc = segment / mvc_reference * 100.0

    peak_mvc = float(as_mvc.max())
    mean_mvc = float(as_mvc.mean())

    peak_offset = max(0, peak_idx - start_idx)
    time_to_peak = peak_offset / fs
    duration = (end_idx - start_idx) / fs

    # Rate of force development: the steepest rise during the ramp. A real
    # rehabilitation metric, since strength and speed recover differently.
    if peak_offset > 1:
        rise = as_mvc[: peak_offset + 1]
        rfd = float(np.max(np.diff(rise)) * fs)
    else:
        rfd = 0.0

    # The hold is between the peak and the start of release, taken as the
    # point where effort falls back through half of peak.
    release_idx = peak_offset
    half_peak = peak_mvc * 0.5
    below = np.where(as_mvc[peak_offset:] < half_peak)[0]
    if below.size:
        release_idx = peak_offset + int(below[0])

    hold = as_mvc[peak_offset:release_idx]
    if hold.size > 1:
        hold_mean = float(hold.mean())
        # Coefficient of variation during the hold: steadiness, which is a
        # measure of neuromuscular control.
        hold_cv = float(hold.std() / hold_mean) if hold_mean > 1e-9 else 0.0
        # Flatness: how little the hold drifts, expressed 0 to 1.
        drift = float(np.abs(np.polyfit(np.arange(hold.size), hold, 1)[0]) * hold.size)
        plateau_flatness = float(1.0 / (1.0 + drift / max(hold_mean, 1e-9)))
    else:
        hold_cv = 0.0
        plateau_flatness = 0.0

    relaxation_time = max(0.0, (end_idx - start_idx - release_idx) / fs)

    # Force time integral, the total work done in the repetition.
    impulse = float(np.trapezoid(as_mvc, dx=1.0 / fs))

    # Spectral measures run on the filtered trace over the hold, where effort
    # is steady, so fatigue is not confounded with the ramp.
    spectral_lo = start_idx + peak_offset
    spectral_hi = start_idx + max(release_idx, peak_offset + 1)
    spectral_hi = min(spectral_hi, filt.size)
    spectral = filt[spectral_lo:spectral_hi] if spectral_hi > spectral_lo else filt[start_idx:end_idx]

    return {
        "peak_mvc": peak_mvc,
        "mean_mvc": mean_mvc,
        "time_to_peak_s": float(time_to_peak),
        "rfd": rfd,
        "duration_s": float(duration),
        "relaxation_time_s": float(relaxation_time),
        "hold_cv": hold_cv,
        "plateau_flatness": plateau_flatness,
        "impulse": impulse,
        "median_frequency": median_frequency(spectral, fs),
        "mean_frequency": mean_frequency(spectral, fs),
        "dimitrov_index": dimitrov_index(spectral, fs),
    }
