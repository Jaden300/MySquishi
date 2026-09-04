"""Tests for feature extraction.

The frozen key assertions matter most: those key sets are what the ML layer
consumes, so a rename or an addition should break a test loudly rather than
silently corrupt a model's inputs.
"""

from __future__ import annotations

import numpy as np
import pytest

from app.signal.features import (
    REP_FEATURE_KEYS,
    WINDOW_FEATURE_KEYS,
    dimitrov_index,
    mean_frequency,
    median_frequency,
    rep_features,
    window_features,
)
from app.signal.filters import preprocess
from app.sim.signal_gen import SyntheticEmgGenerator, make_protocol

FS = 1000


@pytest.fixture
def t() -> np.ndarray:
    return np.arange(0, 2.0, 1.0 / FS)


class TestSpectralMeasures:
    def test_median_frequency_finds_dominant_tone(self, t: np.ndarray) -> None:
        """A 100 Hz dominated signal should report MDF near 100 Hz."""
        rng = np.random.default_rng(0)
        x = np.sin(2 * np.pi * 100.0 * t) + 0.05 * rng.normal(size=t.size)
        assert median_frequency(x, FS) == pytest.approx(100.0, abs=10.0)

    def test_mean_frequency_finds_dominant_tone(self, t: np.ndarray) -> None:
        rng = np.random.default_rng(1)
        x = np.sin(2 * np.pi * 120.0 * t) + 0.05 * rng.normal(size=t.size)
        assert mean_frequency(x, FS) == pytest.approx(120.0, abs=20.0)

    def test_median_frequency_tracks_a_downward_shift(self, t: np.ndarray) -> None:
        """The behaviour M5 depends on."""
        high = np.sin(2 * np.pi * 150.0 * t)
        low = np.sin(2 * np.pi * 70.0 * t)
        assert median_frequency(low, FS) < median_frequency(high, FS)

    def test_dimitrov_index_rises_as_spectrum_falls(self, t: np.ndarray) -> None:
        """The index is weighted toward low frequency content, so a fatigued
        (lower) spectrum should score higher."""
        high = np.sin(2 * np.pi * 150.0 * t)
        low = np.sin(2 * np.pi * 70.0 * t)
        assert dimitrov_index(low, FS) > dimitrov_index(high, FS)

    def test_empty_input_is_nan_not_a_crash(self) -> None:
        assert np.isnan(median_frequency(np.zeros(0), FS))
        assert np.isnan(mean_frequency(np.zeros(0), FS))


class TestWindowFeatures:
    def test_keys_are_frozen(self, t: np.ndarray) -> None:
        """This key set is the M1 contract."""
        feats = window_features(np.sin(2 * np.pi * 100 * t), FS)
        assert tuple(feats.keys()) == WINDOW_FEATURE_KEYS

    def test_all_values_are_finite(self, t: np.ndarray) -> None:
        rng = np.random.default_rng(2)
        feats = window_features(rng.normal(size=t.size), FS)
        assert all(np.isfinite(v) for v in feats.values())

    def test_empty_window_returns_full_key_set(self) -> None:
        feats = window_features(np.zeros(0), FS)
        assert tuple(feats.keys()) == WINDOW_FEATURE_KEYS

    def test_rms_scales_with_amplitude(self, t: np.ndarray) -> None:
        quiet = window_features(np.sin(2 * np.pi * 100 * t) * 0.1, FS)
        loud = window_features(np.sin(2 * np.pi * 100 * t) * 1.0, FS)
        assert loud["rms"] > quiet["rms"] * 5

    def test_mains_ratio_detects_hum(self, t: np.ndarray) -> None:
        rng = np.random.default_rng(3)
        clean = rng.normal(size=t.size)
        hummy = clean + 5.0 * np.sin(2 * np.pi * 60.0 * t)

        assert window_features(hummy, FS)["mains_ratio"] > (
            window_features(clean, FS)["mains_ratio"] * 5
        )

    def test_saturation_detects_clipping(self, t: np.ndarray) -> None:
        rng = np.random.default_rng(4)
        clean = rng.normal(size=t.size) * 0.3
        clipped = np.clip(rng.normal(size=t.size) * 3.0, -1.0, 1.0)

        assert (
            window_features(clipped, FS)["saturation_ratio"]
            > window_features(clean, FS)["saturation_ratio"]
        )

    def test_flat_window_reads_as_fully_saturated(self) -> None:
        """A dead electrode gives a constant trace, which should not look
        like a pristine signal."""
        assert window_features(np.ones(500), FS)["saturation_ratio"] == 1.0

    def test_baseline_drift_detects_wander(self, t: np.ndarray) -> None:
        rng = np.random.default_rng(5)
        steady = rng.normal(size=t.size)
        wandering = steady + 4.0 * np.sin(2 * np.pi * 0.4 * t)

        assert (
            window_features(wandering, FS)["baseline_drift"]
            > window_features(steady, FS)["baseline_drift"]
        )

    def test_snr_is_higher_for_clean_signal(self, t: np.ndarray) -> None:
        rng = np.random.default_rng(6)
        clean = np.sin(2 * np.pi * 100.0 * t) + 0.05 * rng.normal(size=t.size)
        noisy = clean + 3.0 * np.sin(2 * np.pi * 60.0 * t)

        assert window_features(clean, FS)["snr_estimate"] > window_features(noisy, FS)[
            "snr_estimate"
        ]


class TestRepFeatures:
    @pytest.fixture
    def session(self):
        gen = SyntheticEmgGenerator(FS, seed=10, junkiness=0.0)
        return gen.build_session(make_protocol(reps=4))

    def _extract(self, session, rep_index: int = 0) -> dict[str, float]:
        result = preprocess(session.samples, FS)
        rep = session.reps[rep_index]
        rest = result.envelope[: int(3.0 * FS)].mean()
        return rep_features(
            result.envelope,
            result.filtered,
            FS,
            start_idx=int(rep.start_s * FS),
            peak_idx=int(rep.peak_s * FS),
            end_idx=int(rep.end_s * FS),
            mvc_reference=max(rest * 10, 1e-6),
        )

    def test_keys_are_frozen(self, session) -> None:
        """This key set is the M4 and M5 contract."""
        assert tuple(self._extract(session).keys()) == REP_FEATURE_KEYS

    def test_all_values_are_finite(self, session) -> None:
        feats = self._extract(session)
        assert all(np.isfinite(v) for v in feats.values()), feats

    def test_peak_is_at_least_mean(self, session) -> None:
        feats = self._extract(session)
        assert feats["peak_mvc"] >= feats["mean_mvc"]

    def test_duration_matches_the_protocol(self, session) -> None:
        feats = self._extract(session)
        # ramp 0.7 + hold 4.0 + release 0.8
        assert feats["duration_s"] == pytest.approx(5.5, abs=0.3)

    def test_time_to_peak_matches_the_ramp(self, session) -> None:
        feats = self._extract(session)
        assert feats["time_to_peak_s"] == pytest.approx(0.7, abs=0.2)

    def test_impulse_is_positive(self, session) -> None:
        assert self._extract(session)["impulse"] > 0

    def test_flat_hold_gives_low_cv(self) -> None:
        """A perfectly steady hold is the reference case for steadiness."""
        fs = FS
        env = np.concatenate([np.zeros(fs), np.linspace(0, 1, fs // 2), np.ones(2 * fs)])
        filt = np.random.default_rng(0).normal(size=env.size) * 0.01

        feats = rep_features(
            env,
            filt,
            fs,
            start_idx=fs,
            peak_idx=fs + fs // 2,
            end_idx=env.size,
            mvc_reference=1.0,
        )
        assert feats["hold_cv"] < 0.05

    def test_noisy_hold_gives_higher_cv(self) -> None:
        fs = FS
        rng = np.random.default_rng(1)
        steady = np.ones(2 * fs)
        shaky = 1.0 + rng.normal(scale=0.25, size=2 * fs)

        def cv_for(hold: np.ndarray) -> float:
            env = np.concatenate([np.zeros(fs), np.linspace(0, 1, fs // 2), hold])
            filt = rng.normal(size=env.size) * 0.01
            return rep_features(
                env,
                filt,
                fs,
                start_idx=fs,
                peak_idx=fs + fs // 2,
                end_idx=env.size,
                mvc_reference=1.0,
            )["hold_cv"]

        assert cv_for(shaky) > cv_for(steady)

    def test_fast_ramp_gives_higher_rfd(self) -> None:
        """Rate of force development must actually distinguish ramp speeds."""
        fs = FS
        rng = np.random.default_rng(2)

        def rfd_for(ramp_samples: int) -> float:
            env = np.concatenate(
                [np.zeros(fs), np.linspace(0, 1, ramp_samples), np.ones(fs)]
            )
            filt = rng.normal(size=env.size) * 0.01
            return rep_features(
                env,
                filt,
                fs,
                start_idx=fs,
                peak_idx=fs + ramp_samples,
                end_idx=env.size,
                mvc_reference=1.0,
            )["rfd"]

        assert rfd_for(fs // 10) > rfd_for(fs)

    def test_rejects_bounds_outside_the_array(self) -> None:
        with pytest.raises(ValueError):
            rep_features(
                np.ones(100),
                np.ones(100),
                FS,
                start_idx=0,
                peak_idx=10,
                end_idx=500,
                mvc_reference=1.0,
            )

    def test_rejects_non_positive_mvc_reference(self) -> None:
        with pytest.raises(ValueError):
            rep_features(
                np.ones(100),
                np.ones(100),
                FS,
                start_idx=0,
                peak_idx=10,
                end_idx=50,
                mvc_reference=0.0,
            )
