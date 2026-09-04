"""Tests for M2, rep segmentation.

This is the critical path. M4, M5, M6, M8 and every rep level chart consume
this output, and a segmenter that is subtly wrong fails silently downstream.
So the central test is exact: generate a session with a known number of
repetitions at known times, and assert the segmenter recovers both.
"""

from __future__ import annotations

import numpy as np
import pytest

from app.signal.filters import preprocess
from app.signal.segmentation import (
    Rep,
    describe,
    estimate_baseline,
    segment_reps,
)
from app.sim.signal_gen import SyntheticEmgGenerator, make_protocol

FS = 1000

# How far a detected peak may sit from the truth. The generator places its
# peak at the start of the plateau, while the segmenter reports the envelope
# maximum, which can land anywhere in a flat hold. A wide hold plus RMS
# smoothing means an exact match is not the right expectation; what matters
# is that the peak lands inside the correct repetition.
PEAK_TOLERANCE_S = 0.15


def envelope_for(session) -> np.ndarray:
    return preprocess(session.samples, FS).envelope


class TestBaseline:
    def test_estimates_from_the_lead_in(self) -> None:
        rng = np.random.default_rng(0)
        env = np.abs(rng.normal(loc=0.1, scale=0.02, size=10 * FS))

        mean, sd = estimate_baseline(env, FS, baseline_s=2.0)
        assert mean == pytest.approx(0.1, abs=0.02)
        assert sd > 0

    def test_falls_back_when_lead_in_is_too_short(self) -> None:
        """A stream that starts mid contraction still needs a baseline."""
        rng = np.random.default_rng(1)
        env = np.abs(rng.normal(loc=0.1, scale=0.02, size=100))

        mean, sd = estimate_baseline(env, FS, baseline_s=5.0)
        assert np.isfinite(mean) and np.isfinite(sd)
        assert sd > 0

    def test_flat_signal_gets_a_nonzero_spread(self) -> None:
        """Zero spread would make every threshold equal the mean and detect
        nothing at all."""
        _, sd = estimate_baseline(np.ones(5 * FS), FS)
        assert sd > 0

    def test_empty_input(self) -> None:
        assert estimate_baseline(np.zeros(0), FS) == (0.0, 0.0)


class TestExactRecovery:
    """The gate. Nothing downstream is built until these pass."""

    @pytest.mark.parametrize("junkiness", [0.0, 0.3])
    @pytest.mark.parametrize("reps", [5, 10])
    def test_recovers_exact_rep_count(self, junkiness: float, reps: int) -> None:
        gen = SyntheticEmgGenerator(FS, seed=100 + reps, junkiness=junkiness)
        session = gen.build_session(make_protocol(reps=reps))

        result = segment_reps(envelope_for(session), FS)

        assert result.count == reps, (
            f"expected {reps} reps at junkiness {junkiness}, got {result.count}"
        )

    @pytest.mark.parametrize("junkiness", [0.0, 0.3])
    def test_peaks_land_within_tolerance(self, junkiness: float) -> None:
        gen = SyntheticEmgGenerator(FS, seed=200, junkiness=junkiness)
        session = gen.build_session(make_protocol(reps=8))

        result = segment_reps(envelope_for(session), FS)
        assert result.count == len(session.reps)

        for detected, truth in zip(result.reps, session.reps):
            # The detected peak must fall inside the true repetition, and
            # near the plateau the generator built.
            assert truth.start_s <= detected.peak_s <= truth.end_s, (
                f"rep {detected.index} peak at {detected.peak_s:.2f}s outside "
                f"true bounds {truth.start_s:.2f}-{truth.end_s:.2f}s"
            )
            assert detected.peak_s >= truth.peak_s - PEAK_TOLERANCE_S

    @pytest.mark.parametrize("junkiness", [0.0, 0.3])
    def test_boundaries_align_with_ground_truth(self, junkiness: float) -> None:
        gen = SyntheticEmgGenerator(FS, seed=300, junkiness=junkiness)
        session = gen.build_session(make_protocol(reps=6))

        result = segment_reps(envelope_for(session), FS)
        assert result.count == len(session.reps)

        for detected, truth in zip(result.reps, session.reps):
            # Onset is detected once the envelope clears the threshold, which
            # is necessarily a little after the contraction truly begins.
            assert abs(detected.start_s - truth.start_s) < 0.6
            assert abs(detected.end_s - truth.end_s) < 0.9

    def test_reps_are_ordered_and_disjoint(self) -> None:
        gen = SyntheticEmgGenerator(FS, seed=400, junkiness=0.2)
        session = gen.build_session(make_protocol(reps=7))

        result = segment_reps(envelope_for(session), FS)

        for earlier, later in zip(result.reps, result.reps[1:]):
            assert earlier.start_idx < earlier.end_idx <= later.start_idx
        assert [r.index for r in result.reps] == list(range(result.count))


class TestChatterSuppression:
    def test_short_burst_produces_no_reps(self) -> None:
        """A motion spike is tens of milliseconds. It must not become a rep."""
        rng = np.random.default_rng(2)
        env = np.abs(rng.normal(loc=0.05, scale=0.005, size=10 * FS))

        # A 50 ms burst, well under the 200 ms dwell requirement.
        env[5 * FS : 5 * FS + FS // 20] += 2.0

        assert segment_reps(env, FS).count == 0

    def test_hysteresis_keeps_a_wobbling_hold_as_one_rep(self) -> None:
        """Without hysteresis, an envelope hovering near threshold splits a
        single repetition into several."""
        rng = np.random.default_rng(3)
        env = np.abs(rng.normal(loc=0.05, scale=0.005, size=12 * FS))

        # A 4 second hold that dips repeatedly toward the threshold.
        hold = slice(4 * FS, 8 * FS)
        t = np.arange(4 * FS) / FS
        env[hold] += 0.5 + 0.18 * np.sin(2 * np.pi * 3.0 * t)

        assert segment_reps(env, FS).count == 1

    def test_sub_minimum_duration_rep_is_discarded(self) -> None:
        rng = np.random.default_rng(4)
        env = np.abs(rng.normal(loc=0.05, scale=0.005, size=10 * FS))

        # 300 ms: clears the onset dwell but under the 600 ms minimum.
        env[5 * FS : 5 * FS + int(0.3 * FS)] += 1.0

        assert segment_reps(env, FS).count == 0

    def test_quiet_trace_produces_no_reps(self) -> None:
        rng = np.random.default_rng(5)
        env = np.abs(rng.normal(loc=0.05, scale=0.005, size=10 * FS))
        assert segment_reps(env, FS).count == 0


class TestParameters:
    def test_rejects_inverted_hysteresis(self) -> None:
        """k_off must sit below k_on or there is no hysteresis at all."""
        with pytest.raises(ValueError):
            segment_reps(np.ones(1000), FS, k_on=1.0, k_off=3.0)

    def test_rejects_bad_sample_rate(self) -> None:
        with pytest.raises(ValueError):
            segment_reps(np.ones(1000), 0)

    def test_empty_envelope(self) -> None:
        assert segment_reps(np.zeros(0), FS).count == 0

    def test_explicit_baseline_is_honoured(self) -> None:
        """Live segmentation passes a fixed baseline so the thresholds do not
        drift with whatever is in the current buffer."""
        rng = np.random.default_rng(6)
        env = np.abs(rng.normal(loc=0.05, scale=0.005, size=10 * FS))
        env[3 * FS : 7 * FS] += 0.5

        result = segment_reps(env, FS, baseline=(0.05, 0.005))
        assert result.baseline_mean == 0.05
        assert result.baseline_sd == 0.005
        assert result.count == 1

    def test_thresholds_are_reported(self) -> None:
        """M2 has no learned parameters, so the thresholds are its
        explanation and must be surfaced."""
        gen = SyntheticEmgGenerator(FS, seed=500, junkiness=0.0)
        session = gen.build_session(make_protocol(reps=3))

        result = segment_reps(envelope_for(session), FS)
        assert result.threshold_off < result.threshold_on
        assert result.baseline_sd > 0
        assert "3 repetitions" in describe(result)


class TestRepGeometry:
    def test_time_properties_match_indices(self) -> None:
        rep = Rep(
            index=0,
            start_idx=1000,
            peak_idx=1500,
            end_idx=4000,
            sample_rate=FS,
            peak_amplitude=1.0,
        )
        assert rep.start_s == 1.0
        assert rep.peak_s == 1.5
        assert rep.end_s == 4.0
        assert rep.duration_s == 3.0

    def test_peak_amplitude_is_the_envelope_maximum(self) -> None:
        gen = SyntheticEmgGenerator(FS, seed=600, junkiness=0.0)
        session = gen.build_session(make_protocol(reps=3))
        env = envelope_for(session)

        for rep in segment_reps(env, FS).reps:
            assert rep.peak_amplitude == pytest.approx(
                env[rep.start_idx : rep.end_idx].max()
            )
