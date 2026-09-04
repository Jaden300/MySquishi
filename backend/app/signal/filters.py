"""Surface EMG filtering.

The standard preprocessing chain for sEMG: bandpass to the useful band,
notch out mains interference, rectify, then smooth to an RMS envelope. The
envelope is what every downstream model actually consumes.

References for the band choices are in docs/CLINICAL.md.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import signal as sps

# Surface EMG power lives roughly between 20 and 450 Hz. Below 20 Hz is
# movement artifact and baseline wander; above 450 Hz there is little signal
# and plenty of noise.
BAND_LOW_HZ = 20.0
BAND_HIGH_HZ = 450.0

# Mains frequency. 60 Hz in North America, where this is being built.
MAINS_HZ = 60.0
NOTCH_Q = 30.0

# 150 ms is a common RMS window for isometric work: long enough to smooth the
# stochastic interference pattern, short enough to preserve contraction onset.
RMS_WINDOW_MS = 150.0


@dataclass(frozen=True)
class Filtered:
    """The three views of a trace that the rest of the pipeline uses."""

    raw: np.ndarray
    filtered: np.ndarray
    envelope: np.ndarray
    sample_rate: int


def _validate(x: np.ndarray, fs: int) -> np.ndarray:
    if fs <= 0:
        raise ValueError(f"sample rate must be positive, got {fs}")
    arr = np.asarray(x, dtype=float)
    if arr.ndim != 1:
        raise ValueError(f"expected a 1D trace, got shape {arr.shape}")
    return arr


def bandpass(
    x: np.ndarray,
    fs: int,
    low: float = BAND_LOW_HZ,
    high: float = BAND_HIGH_HZ,
    order: int = 4,
) -> np.ndarray:
    """Zero phase Butterworth bandpass.

    Uses second order sections with filtfilt so there is no phase distortion:
    contraction onset must not be smeared in time, since M2 segments on it.
    """
    arr = _validate(x, fs)
    nyquist = fs / 2.0

    # Clamp the upper edge so a low sample rate does not produce an invalid
    # normalized frequency. At 1000 Hz this never triggers.
    high = min(high, nyquist * 0.99)
    if low >= high:
        raise ValueError(f"low ({low} Hz) must be below high ({high} Hz)")

    sos = sps.butter(order, [low / nyquist, high / nyquist], btype="bandpass", output="sos")

    # filtfilt needs a few times the filter order in samples to be stable.
    if arr.size <= order * 6:
        return arr.copy()
    return sps.sosfiltfilt(sos, arr)


def notch(x: np.ndarray, fs: int, freq: float = MAINS_HZ, q: float = NOTCH_Q) -> np.ndarray:
    """Zero phase IIR notch, removing mains hum and leaving the band intact."""
    arr = _validate(x, fs)
    nyquist = fs / 2.0
    if freq >= nyquist:
        return arr.copy()

    b, a = sps.iirnotch(freq / nyquist, q)
    if arr.size <= 12:
        return arr.copy()
    return sps.filtfilt(b, a, arr)


def rectify(x: np.ndarray) -> np.ndarray:
    """Full wave rectification. EMG is bipolar; effort is in the magnitude."""
    return np.abs(np.asarray(x, dtype=float))


def rms_envelope(x: np.ndarray, fs: int, window_ms: float = RMS_WINDOW_MS) -> np.ndarray:
    """Root mean square over a centered sliding window.

    Returns an array the same length as the input, so sample indices stay
    aligned with the raw trace and rep boundaries map straight back.
    """
    arr = _validate(x, fs)
    if arr.size == 0:
        return arr.copy()

    width = max(1, int(round(window_ms * fs / 1000.0)))
    width = min(width, arr.size)

    # Reflect at the edges so the envelope does not sag at the start and end,
    # which would otherwise look like a slow onset to the segmenter.
    pad = width // 2
    padded = np.pad(arr**2, pad, mode="reflect")

    kernel = np.ones(width, dtype=float) / float(width)
    smoothed = np.convolve(padded, kernel, mode="same")
    smoothed = smoothed[pad : pad + arr.size]

    # Convolution of a non-negative signal can still land marginally below
    # zero in floating point. Clip before the square root.
    return np.sqrt(np.clip(smoothed, 0.0, None))


def preprocess(
    raw: np.ndarray,
    fs: int,
    *,
    apply_notch: bool = True,
    window_ms: float = RMS_WINDOW_MS,
) -> Filtered:
    """Run the full chain: bandpass, optional notch, rectify, RMS envelope."""
    arr = _validate(raw, fs)
    filtered = bandpass(arr, fs)
    if apply_notch:
        filtered = notch(filtered, fs)
    envelope = rms_envelope(rectify(filtered), fs, window_ms=window_ms)
    return Filtered(raw=arr, filtered=filtered, envelope=envelope, sample_rate=fs)
