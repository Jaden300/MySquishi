"""Tests for the sEMG filter chain.

These protect the assumptions every downstream model rests on: the mains
notch actually removes 60 Hz, the bandpass actually removes baseline wander,
real signal survives, and the envelope stays index aligned with the raw trace.
"""

from __future__ import annotations

import numpy as np
import pytest

from app.signal.filters import (
    bandpass,
    notch,
    preprocess,
    rectify,
    rms_envelope,
)

FS = 1000
DURATION_S = 4.0


@pytest.fixture
def t() -> np.ndarray:
    return np.arange(0, DURATION_S, 1.0 / FS)


def power_at(x: np.ndarray, fs: int, freq: float, half_width: float = 2.0) -> float:
    """Total spectral power within a narrow band around freq."""
    spectrum = np.abs(np.fft.rfft(x)) ** 2
    freqs = np.fft.rfftfreq(x.size, 1.0 / fs)
    band = (freqs >= freq - half_width) & (freqs <= freq + half_width)
    return float(spectrum[band].sum())


class TestNotch:
    def test_attenuates_mains_by_over_20_db(self, t: np.ndarray) -> None:
        hum = np.sin(2 * np.pi * 60.0 * t)
        cleaned = notch(hum, FS, freq=60.0)

        before = power_at(hum, FS, 60.0)
        after = power_at(cleaned, FS, 60.0)
        attenuation_db = 10 * np.log10(before / max(after, 1e-20))

        assert attenuation_db > 20.0, f"only {attenuation_db:.1f} dB of rejection"

    def test_leaves_nearby_signal_intact(self, t: np.ndarray) -> None:
        """A notch wide enough to eat 100 Hz would gut the EMG band."""
        tone = np.sin(2 * np.pi * 100.0 * t)
        cleaned = notch(tone, FS, freq=60.0)

        retained = power_at(cleaned, FS, 100.0) / power_at(tone, FS, 100.0)
        assert retained > 0.9


class TestBandpass:
    def test_attenuates_baseline_drift(self, t: np.ndarray) -> None:
        drift = np.sin(2 * np.pi * 5.0 * t)
        filtered = bandpass(drift, FS)

        retained = power_at(filtered, FS, 5.0) / power_at(drift, FS, 5.0)
        assert retained < 0.01, "5 Hz drift survived the bandpass"

    def test_passes_in_band_signal(self, t: np.ndarray) -> None:
        tone = np.sin(2 * np.pi * 100.0 * t)
        filtered = bandpass(tone, FS)

        gain = np.sqrt(power_at(filtered, FS, 100.0) / power_at(tone, FS, 100.0))
        assert gain > 0.7, f"100 Hz gain was only {gain:.2f}"

    def test_rejects_inverted_band(self) -> None:
        with pytest.raises(ValueError):
            bandpass(np.zeros(1000), FS, low=400.0, high=100.0)

    def test_short_input_is_returned_unchanged(self) -> None:
        tiny = np.array([1.0, 2.0, 3.0])
        assert np.array_equal(bandpass(tiny, FS), tiny)


class TestRectify:
    def test_output_is_non_negative(self) -> None:
        x = np.array([-3.0, -1.0, 0.0, 2.0])
        assert np.all(rectify(x) >= 0)
        assert np.array_equal(rectify(x), np.array([3.0, 1.0, 0.0, 2.0]))


class TestRmsEnvelope:
    def test_preserves_length(self, t: np.ndarray) -> None:
        x = np.random.default_rng(0).normal(size=t.size)
        assert rms_envelope(x, FS).size == x.size

    def test_is_non_negative(self, t: np.ndarray) -> None:
        x = np.random.default_rng(1).normal(size=t.size)
        assert np.all(rms_envelope(x, FS) >= 0)

    def test_is_flat_for_constant_amplitude(self, t: np.ndarray) -> None:
        """A steady burst should give a steady envelope, which is what makes a
        hold plateau readable to the segmenter."""
        burst = np.sin(2 * np.pi * 100.0 * t)
        env = rms_envelope(np.abs(burst), FS)

        interior = env[FS // 2 : -FS // 2]
        assert interior.std() / interior.mean() < 0.05

    def test_tracks_amplitude_changes(self, t: np.ndarray) -> None:
        carrier = np.sin(2 * np.pi * 100.0 * t)
        gain = np.where(t < DURATION_S / 2, 1.0, 4.0)
        env = rms_envelope(np.abs(carrier * gain), FS)

        quiet = env[FS // 4 : FS // 2].mean()
        loud = env[-FS // 2 : -FS // 4].mean()
        assert loud / quiet > 3.0

    def test_empty_input(self) -> None:
        assert rms_envelope(np.array([]), FS).size == 0


class TestPreprocess:
    def test_returns_aligned_views(self, t: np.ndarray) -> None:
        raw = np.random.default_rng(2).normal(size=t.size)
        result = preprocess(raw, FS)

        assert result.raw.size == raw.size
        assert result.filtered.size == raw.size
        assert result.envelope.size == raw.size
        assert result.sample_rate == FS

    def test_removes_hum_and_drift_together(self, t: np.ndarray) -> None:
        """The realistic case: real signal buried under mains and wander."""
        rng = np.random.default_rng(3)
        signal_band = rng.normal(size=t.size) * 0.5
        signal_band = bandpass(signal_band, FS)
        contaminated = signal_band + 3.0 * np.sin(2 * np.pi * 60.0 * t) + 2.0 * np.sin(
            2 * np.pi * 3.0 * t
        )

        result = preprocess(contaminated, FS)

        assert power_at(result.filtered, FS, 60.0) < power_at(contaminated, FS, 60.0) * 0.01
        assert power_at(result.filtered, FS, 3.0) < power_at(contaminated, FS, 3.0) * 0.01

    def test_rejects_2d_input(self) -> None:
        with pytest.raises(ValueError):
            preprocess(np.zeros((2, 100)), FS)

    def test_rejects_bad_sample_rate(self) -> None:
        with pytest.raises(ValueError):
            preprocess(np.zeros(100), 0)
