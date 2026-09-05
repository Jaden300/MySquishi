"""Tests for the Phase 2 probe's judgement, with no hardware attached.

The probe splits acquisition from judgement precisely so this file can exist.
On bring up day the builder gets one shot at a working rig with electrodes on
their arm, and a bug in the tier logic is the worst possible thing to discover
then. So every verdict path is exercised here against synthetic signals whose
tier is known in advance.

The fixtures are built to look like what the MyoWare 2.0 actually puts out:
10 bit ADC counts riding on a mid scale DC offset, not the zero centered
floats the simulator produces.
"""

from __future__ import annotations

import numpy as np
import pytest

from tools.probe_analysis import (
    ADC_MAX,
    CONTRAST_MARGINAL,
    SEPARABILITY_USABLE,
    ProbeMetrics,
    adc_saturation,
    analyze,
    detect_output_mode,
    format_report,
    grade,
    measure,
    measure_link,
    measure_phases,
)

FS = 500
DURATION_S = 20.0
DC_OFFSET = 512.0


def _rng() -> np.random.Generator:
    return np.random.default_rng(42)


def _raw_trace(
    contrast: float = 8.0,
    *,
    fs: int = FS,
    duration_s: float = DURATION_S,
    rest_amp: float = 4.0,
    mains_amp: float = 0.0,
    drift_amp: float = 0.0,
) -> np.ndarray:
    """A raw sEMG-like trace: broadband noise bursts on a DC offset.

    Raw sEMG is an interference pattern, so broadband noise whose amplitude
    tracks contraction is the honest cheap stand in. Amplitude modulation is
    what the probe measures, and it is reproduced faithfully here.
    """
    rng = _rng()
    t = np.arange(0, duration_s, 1.0 / fs)
    active = np.sin(2 * np.pi * 0.25 * t) > 0

    trace = rng.normal(0.0, rest_amp, t.size)
    trace[active] = rng.normal(0.0, rest_amp * contrast, int(active.sum()))

    if mains_amp:
        trace += mains_amp * np.sin(2 * np.pi * 60.0 * t)
    if drift_amp:
        trace += drift_amp * np.linspace(0.0, 1.0, t.size)

    return trace + DC_OFFSET


def _env_trace(fs: int = FS, duration_s: float = DURATION_S) -> np.ndarray:
    """What the MyoWare 2.0 puts out when the selector is left on ENV.

    Already rectified and smoothed, so essentially all of its energy is below
    the 20 Hz bandpass corner. The small noise term matters: it is what
    survives the filter and produces the plausible looking contrast that makes
    this failure mode quiet rather than loud.
    """
    rng = _rng()
    t = np.arange(0, duration_s, 1.0 / fs)
    envelope = 150.0 + 120.0 * np.clip(np.sin(2 * np.pi * 0.25 * t), 0.0, None)
    return envelope + rng.normal(0.0, 2.0, t.size)


def _phased_trace(
    light_contrast: float,
    hard_contrast: float,
    *,
    fs: int = FS,
) -> tuple[np.ndarray, dict[str, tuple[float, float]]]:
    """A trace following the scripted protocol, with its phase spans."""
    rng = _rng()
    rest_amp = 4.0
    segments = [
        ("rest", 10.0, 1.0),
        ("light", 5.0, light_contrast),
        ("hard", 5.0, hard_contrast),
    ]

    chunks: list[np.ndarray] = []
    phases: dict[str, tuple[float, float]] = {}
    cursor = 0.0
    for label, seconds, scale in segments:
        n = int(seconds * fs)
        chunks.append(rng.normal(0.0, rest_amp * scale, n))
        phases[label] = (cursor, cursor + seconds)
        cursor += seconds

    return np.concatenate(chunks) + DC_OFFSET, phases


class TestOutputModeDetection:
    """The central design risk: ENV output graded as if it were RAW."""

    def test_raw_trace_is_detected_as_raw(self) -> None:
        mode, ratio = detect_output_mode(_raw_trace(), FS)
        assert mode == "raw"
        assert ratio > 0.35

    def test_envelope_is_detected_as_env(self) -> None:
        mode, ratio = detect_output_mode(_env_trace(), FS)
        assert mode == "env"
        assert ratio < 0.10

    def test_dc_offset_does_not_swamp_the_ratio(self) -> None:
        """A large offset must not make a raw trace look like an envelope."""
        trace = _raw_trace()
        shifted = trace + 10_000.0
        assert detect_output_mode(shifted, FS)[0] == detect_output_mode(trace, FS)[0]

    def test_env_input_is_capped_at_tier_c(self) -> None:
        """The whole point: an envelope cannot earn A or B, however clean.

        Without this cap the surviving noise floor produces a plausible
        contrast and the probe reports a confident, wrong tier.
        """
        verdict = analyze(_env_trace(), FS)
        assert verdict.tier in ("C", "D")
        assert any("ENV" in r or "RAW" in r for r in verdict.reasons)

    def test_env_verdict_withholds_spectral_numbers(self) -> None:
        """Mains ratio on an envelope is an artifact, so it is not printed."""
        report = format_report(analyze(_env_trace(), FS))
        assert "Mains" not in report
        assert "WARNING" in report

    def test_too_short_to_judge_is_unknown_not_a_guess(self) -> None:
        assert detect_output_mode(np.zeros(4), FS)[0] == "unknown"


class TestTierGrading:
    def test_clean_raw_trace_earns_tier_a(self) -> None:
        verdict = analyze(_raw_trace(contrast=10.0), FS)
        assert verdict.tier == "A"
        assert verdict.is_usable
        assert "spectral fatigue" in verdict.capabilities

    def test_mains_contamination_pulls_the_tier_down(self) -> None:
        clean = analyze(_raw_trace(contrast=10.0), FS)
        noisy = analyze(_raw_trace(contrast=10.0, mains_amp=30.0), FS)
        assert noisy.tier > clean.tier
        assert any("mains" in r.lower() for r in noisy.reasons)

    def test_low_contrast_is_marginal(self) -> None:
        verdict = analyze(_raw_trace(contrast=2.2), FS)
        assert verdict.tier == "C"
        assert verdict.capabilities == ("live contraction indicator only",)

    def test_no_detectable_contraction_is_tier_d(self) -> None:
        verdict = analyze(_raw_trace(contrast=1.0), FS)
        assert verdict.tier == "D"
        assert not verdict.is_usable
        assert verdict.capabilities == ()

    def test_flat_dead_trace_is_tier_d(self) -> None:
        verdict = analyze(np.full(FS * 10, DC_OFFSET), FS)
        assert verdict.tier == "D"

    def test_problems_accumulate_and_never_cancel(self) -> None:
        """A strong contraction does not buy back a corrupted recording."""
        verdict = analyze(
            _raw_trace(contrast=10.0, mains_amp=60.0, drift_amp=200.0), FS
        )
        assert verdict.tier in ("B", "C")
        assert len(verdict.reasons) >= 2


class TestAdcSaturation:
    """Rail clipping is judged against the converter, not the trace."""

    def test_counts_pinned_at_a_rail_are_saturated(self) -> None:
        counts = np.full(1000, 500.0)
        counts[:100] = ADC_MAX
        assert adc_saturation(counts) == pytest.approx(0.1)

    def test_a_comfortable_mid_range_signal_is_not_saturated(self) -> None:
        """The distinction window_features cannot make.

        An ENV output sitting between 300 and 700 counts never approaches a
        rail, but the scale relative check still flags its observed extremes.
        """
        assert adc_saturation(_env_trace()) == 0.0

    def test_rail_pinning_disqualifies_to_tier_d(self) -> None:
        trace = _raw_trace(contrast=10.0)
        counts = np.clip(trace, 0, ADC_MAX)
        counts[: counts.size // 10] = ADC_MAX
        verdict = analyze(trace, FS, counts=counts)
        assert verdict.tier == "D"
        assert any("rail" in r for r in verdict.reasons)

    def test_empty_counts_do_not_crash(self) -> None:
        assert adc_saturation(np.asarray([])) == 0.0


class TestLinkIntegrity:
    def test_clean_link_reports_the_configured_rate(self) -> None:
        ts = np.arange(0, 10_000, 2.0)  # 500 Hz, 2 ms period
        rate, dropout = measure_link(ts)
        assert rate == pytest.approx(500.0)
        assert dropout == 0.0

    def test_gaps_are_counted_as_the_samples_they_swallowed(self) -> None:
        ts = np.concatenate([np.arange(0, 1000, 2.0), np.arange(1100, 2000, 2.0)])
        rate, dropout = measure_link(ts)
        assert rate == pytest.approx(500.0)
        assert dropout > 0.05

    def test_a_degraded_rate_is_measured_not_assumed(self) -> None:
        ts = np.arange(0, 10_000, 4.0)  # 250 Hz against a 500 Hz intent
        assert measure_link(ts)[0] == pytest.approx(250.0)

    def test_too_few_timestamps_is_not_an_error(self) -> None:
        rate, dropout = measure_link(np.asarray([5.0]))
        assert np.isnan(rate)
        assert dropout == 0.0

    def test_heavy_dropout_caps_the_tier(self) -> None:
        trace = _raw_trace(contrast=10.0)
        ts = np.arange(trace.size, dtype=float) * 2.0
        ts[trace.size // 2 :] += 4000.0  # a long stall mid recording
        verdict = analyze(trace, FS, timestamps_ms=ts)
        assert verdict.tier >= "C"
        assert any("dropped" in r for r in verdict.reasons)

    def test_rate_far_below_configured_caps_the_tier(self) -> None:
        trace = _raw_trace(contrast=10.0)
        ts = np.arange(trace.size, dtype=float) * 5.0  # 200 Hz against 500
        verdict = analyze(trace, FS, timestamps_ms=ts)
        assert verdict.tier >= "B"
        assert any("truncated" in r for r in verdict.reasons)


class TestSeparability:
    def test_three_distinct_levels_are_ordered(self) -> None:
        trace, phases = _phased_trace(light_contrast=4.0, hard_contrast=9.0)
        metrics = measure_phases(trace, FS, phases)
        assert metrics.rest_rms < metrics.light_rms < metrics.hard_rms
        assert metrics.separability is not None

    def test_well_separated_levels_support_force_regression(self) -> None:
        trace, phases = _phased_trace(light_contrast=5.0, hard_contrast=14.0)
        verdict = analyze(trace, FS, phases=phases)
        assert verdict.metrics.separability > SEPARABILITY_USABLE
        assert "force regression in kg" in verdict.capabilities

    def test_overlapping_effort_levels_block_force_regression(self) -> None:
        """A rig that cannot grade effort must not promise kilograms."""
        trace, phases = _phased_trace(light_contrast=7.8, hard_contrast=8.0)
        verdict = analyze(trace, FS, phases=phases)
        assert verdict.tier == "C"
        assert "force regression in kg" not in verdict.capabilities
        assert any("cannot grade" in r for r in verdict.reasons)

    def test_missing_phases_fall_back_to_the_quintile_split(self) -> None:
        """A fumbled protocol still produces a verdict."""
        trace, phases = _phased_trace(light_contrast=4.0, hard_contrast=9.0)
        del phases["light"]
        metrics = measure_phases(trace, FS, phases)
        assert metrics.separability is None
        assert metrics.contrast > 0

    def test_phase_spans_too_short_fall_back(self) -> None:
        trace, _ = _phased_trace(light_contrast=4.0, hard_contrast=9.0)
        tiny = {k: (0.0, 0.01) for k in ("rest", "light", "hard")}
        assert measure_phases(trace, FS, tiny).separability is None


class TestBackwardCompatibility:
    """The array only path predates the probe shell and must keep working."""

    def test_measure_without_extras_still_grades(self) -> None:
        metrics = measure(_raw_trace(contrast=10.0), FS)
        assert metrics.measured_sample_rate is None
        assert metrics.adc_saturation_ratio is None
        assert metrics.separability is None
        assert grade(metrics).tier in ("A", "B", "C", "D")

    def test_unmeasured_fields_never_fire_their_checks(self) -> None:
        """An unmeasured field must not be graded as though it were zero."""
        metrics = measure(_raw_trace(contrast=10.0), FS)
        assert not any("rail" in r for r in grade(metrics).reasons)

    def test_to_dict_omits_what_was_not_measured(self) -> None:
        payload = measure(_raw_trace(), FS).to_dict()
        assert "adc_saturation_ratio" not in payload
        assert "separability" not in payload
        assert payload["output_mode"] == "raw"

    def test_to_dict_includes_what_was_measured(self) -> None:
        trace = _raw_trace(contrast=10.0)
        ts = np.arange(trace.size, dtype=float) * 2.0
        payload = analyze(trace, FS, timestamps_ms=ts).metrics.to_dict()
        assert payload["measured_sample_rate"] == pytest.approx(500.0)

    def test_empty_input_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="no samples"):
            measure(np.asarray([]), FS)

    def test_too_short_a_recording_says_so(self) -> None:
        with pytest.raises(ValueError, match="Record for longer"):
            measure(np.zeros(50), FS)


class TestReport:
    def test_report_names_the_tier_and_its_reasons(self) -> None:
        verdict = analyze(_raw_trace(contrast=10.0), FS)
        report = format_report(verdict)
        assert f"TIER {verdict.tier}" in report
        assert "What this means" in report

    def test_tier_d_report_points_at_simulation(self) -> None:
        report = format_report(analyze(_raw_trace(contrast=1.0), FS))
        assert "Simulated" in report
        assert "not a failure" in report

    def test_report_shows_measured_rate_when_known(self) -> None:
        trace = _raw_trace(contrast=10.0)
        ts = np.arange(trace.size, dtype=float) * 2.0
        report = format_report(analyze(trace, FS, timestamps_ms=ts))
        assert "Measured rate" in report

    def test_no_dashes_anywhere_in_operator_output(self) -> None:
        """Repo wide rule, enforced where the builder actually reads text."""
        for contrast in (10.0, 2.2, 1.0):
            report = format_report(analyze(_raw_trace(contrast=contrast), FS))
            assert "—" not in report
            assert "–" not in report


class TestMetricsContract:
    def test_defaults_keep_direct_construction_working(self) -> None:
        """Callers predating the optional fields must not have to change."""
        metrics = ProbeMetrics(
            n_samples=1000,
            duration_s=2.0,
            sample_rate=FS,
            rest_rms=1.0,
            active_rms=10.0,
            contrast=10.0,
            mains_ratio=0.01,
            saturation_ratio=0.0,
            baseline_drift=0.1,
            snr_estimate=20.0,
        )
        assert metrics.output_mode == "unknown"
        assert metrics.dropout_ratio == 0.0
        assert grade(metrics).tier == "A"

    def test_contrast_floor_is_the_documented_constant(self) -> None:
        below = ProbeMetrics(
            n_samples=1000,
            duration_s=2.0,
            sample_rate=FS,
            rest_rms=1.0,
            active_rms=CONTRAST_MARGINAL - 0.1,
            contrast=CONTRAST_MARGINAL - 0.1,
            mains_ratio=0.01,
            saturation_ratio=0.0,
            baseline_drift=0.1,
            snr_estimate=20.0,
        )
        assert grade(below).tier == "D"
