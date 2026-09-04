"""Tests for the synthetic EMG generator.

The generator gates every ML slice, so these tests are the foundation the
rest of the stack stands on. The most important one is the fatigue test:
the demo claims the power spectrum shifts downward as the muscle tires, and
M5 can only detect that if the generator genuinely puts it there.
"""

from __future__ import annotations

import numpy as np
import pytest

from app.signal.filters import preprocess, rms_envelope
from app.sim.signal_gen import (
    SessionProtocol,
    SyntheticEmgGenerator,
    make_protocol,
)

FS = 1000


def median_frequency(x: np.ndarray, fs: int) -> float:
    """Frequency dividing the power spectrum into two equal halves."""
    freqs, psd = _welch(x, fs)
    if psd.sum() <= 0:
        return float("nan")
    cumulative = np.cumsum(psd)
    half = cumulative[-1] / 2.0
    return float(freqs[np.searchsorted(cumulative, half)])


def _welch(x: np.ndarray, fs: int):
    from scipy import signal as sps

    nperseg = min(512, max(64, x.size // 4))
    freqs, psd = sps.welch(x, fs=fs, nperseg=nperseg)
    band = (freqs >= 20.0) & (freqs <= 450.0)
    return freqs[band], psd[band]


def power_at(x: np.ndarray, fs: int, freq: float, half_width: float = 2.0) -> float:
    spectrum = np.abs(np.fft.rfft(x)) ** 2
    freqs = np.fft.rfftfreq(x.size, 1.0 / fs)
    band = (freqs >= freq - half_width) & (freqs <= freq + half_width)
    return float(spectrum[band].sum())


class TestDeterminism:
    def test_same_seed_reproduces_exactly(self) -> None:
        a = SyntheticEmgGenerator(FS, seed=7).generate_session(make_protocol(reps=3))
        b = SyntheticEmgGenerator(FS, seed=7).generate_session(make_protocol(reps=3))
        assert np.array_equal(a, b)

    def test_different_seeds_differ(self) -> None:
        a = SyntheticEmgGenerator(FS, seed=1).generate_session(make_protocol(reps=3))
        b = SyntheticEmgGenerator(FS, seed=2).generate_session(make_protocol(reps=3))
        assert not np.array_equal(a, b)

    def test_reset_restores_start_state(self) -> None:
        gen = SyntheticEmgGenerator(FS, seed=11)
        first = gen.generate_session(make_protocol(reps=2))
        gen.reset()
        second = gen.generate_session(make_protocol(reps=2))
        assert np.array_equal(first, second)


class TestStructure:
    def test_contraction_rises_well_above_rest(self) -> None:
        """The plateau envelope must be clearly above resting, or the
        segmenter has nothing to threshold on."""
        gen = SyntheticEmgGenerator(FS, seed=3, junkiness=0.0)
        session = gen.build_session(make_protocol(reps=4))

        env = rms_envelope(np.abs(session.samples), FS)
        rep = session.reps[0]

        # Sample the middle of the hold, away from ramp and release.
        hold_start = int((rep.peak_s + 0.3) * FS)
        hold_end = int((rep.end_s - 0.5) * FS)
        plateau = env[hold_start:hold_end].mean()

        rest = env[: int(3.0 * FS)].mean()

        assert plateau / rest > 4.0, f"contrast was only {plateau / rest:.1f}x"

    def test_ground_truth_matches_requested_rep_count(self) -> None:
        session = SyntheticEmgGenerator(FS, seed=4).build_session(make_protocol(reps=7))
        assert len(session.reps) == 7

    def test_ground_truth_reps_are_ordered_and_disjoint(self) -> None:
        session = SyntheticEmgGenerator(FS, seed=5).build_session(make_protocol(reps=5))
        for earlier, later in zip(session.reps, session.reps[1:]):
            assert earlier.start_s < earlier.peak_s < earlier.end_s
            assert earlier.end_s < later.start_s

    def test_duration_matches_protocol(self) -> None:
        proto = make_protocol(reps=3, hold_s=4.0, rest_s=5.0)
        session = SyntheticEmgGenerator(FS, seed=6).build_session(proto)

        spec = proto.rep
        expected = proto.lead_in_s + proto.reps * (
            spec.ramp_s + spec.hold_s + spec.release_s + spec.rest_s
        )
        assert session.duration_s == pytest.approx(expected, abs=0.05)


class TestFatigue:
    """The load bearing behaviour: the spectrum must slide down across reps."""

    def test_median_frequency_declines_across_reps(self) -> None:
        gen = SyntheticEmgGenerator(FS, seed=21, junkiness=0.0)
        session = gen.build_session(make_protocol(reps=10))

        mdfs = []
        for rep in session.reps:
            hold = session.samples[
                int((rep.peak_s + 0.2) * FS) : int((rep.end_s - 0.4) * FS)
            ]
            mdfs.append(median_frequency(hold, FS))

        assert mdfs[7] < mdfs[0], f"rep 8 MDF {mdfs[7]:.1f} not below rep 1 {mdfs[0]:.1f}"
        assert mdfs[0] - mdfs[7] > 5.0, "the decline is too small for M5 to detect"

    def test_decline_is_statistically_significant_at_ten_reps(self) -> None:
        """M5 regresses MDF on rep index and reports a p value. If the shift
        is not significant here, the demo's fatigue claim does not hold."""
        from scipy import stats

        gen = SyntheticEmgGenerator(FS, seed=22, junkiness=0.0)
        session = gen.build_session(make_protocol(reps=10))

        mdfs = [
            median_frequency(
                session.samples[int((r.peak_s + 0.2) * FS) : int((r.end_s - 0.4) * FS)],
                FS,
            )
            for r in session.reps
        ]

        result = stats.linregress(np.arange(len(mdfs)), mdfs)
        assert result.slope < 0, "slope should be negative"
        assert result.pvalue < 0.05, f"p was {result.pvalue:.3f}, not significant"

    def test_fatigue_can_be_disabled(self) -> None:
        """A non fatiguing session is needed as the negative control."""
        from scipy import stats

        gen = SyntheticEmgGenerator(
            FS, seed=23, junkiness=0.0, fatigue_shift_hz_per_rep=0.0
        )
        session = gen.build_session(make_protocol(reps=10))

        mdfs = [
            median_frequency(
                session.samples[int((r.peak_s + 0.2) * FS) : int((r.end_s - 0.4) * FS)],
                FS,
            )
            for r in session.reps
        ]

        result = stats.linregress(np.arange(len(mdfs)), mdfs)
        assert result.pvalue > 0.05, "flat session should show no fatigue trend"


class TestArtifacts:
    def test_junkiness_raises_mains_power_by_orders_of_magnitude(self) -> None:
        proto = make_protocol(reps=3)
        clean = SyntheticEmgGenerator(FS, seed=31, junkiness=0.0).generate_session(proto)
        dirty = SyntheticEmgGenerator(FS, seed=31, junkiness=1.0).generate_session(proto)

        ratio = power_at(dirty, FS, 60.0) / max(power_at(clean, FS, 60.0), 1e-12)
        assert ratio > 10.0, f"60 Hz only rose {ratio:.1f}x"

    def test_junkiness_adds_baseline_drift(self) -> None:
        proto = make_protocol(reps=3)
        clean = SyntheticEmgGenerator(FS, seed=32, junkiness=0.0).generate_session(proto)
        dirty = SyntheticEmgGenerator(FS, seed=32, junkiness=1.0).generate_session(proto)

        assert power_at(dirty, FS, 0.35, 0.3) > power_at(clean, FS, 0.35, 0.3) * 10.0

    def test_clean_signal_survives_preprocessing(self) -> None:
        """Artifacts at junkiness 0 should be absent, so the filter chain has
        little to remove and the envelope stays interpretable."""
        session = SyntheticEmgGenerator(FS, seed=33, junkiness=0.0).build_session(
            make_protocol(reps=3)
        )
        result = preprocess(session.samples, FS)
        assert np.all(np.isfinite(result.envelope))
        assert result.envelope.max() > 0

    def test_rejects_out_of_range_junkiness(self) -> None:
        with pytest.raises(ValueError):
            SyntheticEmgGenerator(FS, junkiness=1.5)

    def test_rejects_bad_sample_rate(self) -> None:
        with pytest.raises(ValueError):
            SyntheticEmgGenerator(0)


class TestStreaming:
    def test_yields_fixed_size_windows(self) -> None:
        gen = SyntheticEmgGenerator(FS, seed=41)
        stream = gen.stream(200, make_protocol(reps=2))

        windows = [next(stream) for _ in range(20)]
        assert all(w.size == 200 for w in windows)

    def test_loops_indefinitely(self) -> None:
        """A demo may run longer than the protocol, and must not stop."""
        gen = SyntheticEmgGenerator(FS, seed=42)
        proto = SessionProtocol(reps=1, lead_in_s=0.5)
        stream = gen.stream(200, proto, loop=True)

        # Far more windows than the protocol itself contains.
        windows = [next(stream) for _ in range(300)]
        assert len(windows) == 300
        assert all(np.all(np.isfinite(w)) for w in windows)

    def test_non_looping_stream_terminates(self) -> None:
        gen = SyntheticEmgGenerator(FS, seed=43)
        proto = SessionProtocol(reps=1, lead_in_s=0.5)
        windows = list(gen.stream(200, proto, loop=False))

        assert len(windows) > 0
        assert all(w.size > 0 for w in windows)

    def test_rejects_bad_window_size(self) -> None:
        gen = SyntheticEmgGenerator(FS, seed=44)
        with pytest.raises(ValueError):
            next(gen.stream(0))
