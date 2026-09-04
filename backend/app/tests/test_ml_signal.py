"""Tests for the signal layer models: M1, M3, M4, M5.

These are property based rather than exact value assertions. What matters is
that each model orders the world correctly and reports its uncertainty
honestly, not that it produces one particular number.
"""

from __future__ import annotations

import numpy as np
import pytest

from app.ml import fatigue, force, quality
from app.ml import rep_quality as rq
from app.ml.explain import Interval
from app.signal.features import rep_features
from app.signal.filters import preprocess
from app.signal.segmentation import segment_reps
from app.sim.signal_gen import SyntheticEmgGenerator, make_protocol

FS = 1000


def _rest_window_starts(session, window: int = 200) -> list[int]:
    occupied = np.zeros(session.samples.size, dtype=bool)
    for rep in session.reps:
        occupied[int(rep.start_s * FS) : int(rep.end_s * FS)] = True
    return [
        start
        for start in range(0, session.samples.size - window, window)
        if not occupied[start : start + window].any()
    ]


@pytest.fixture(scope="module")
def sqi_artifact():
    return quality.train(seed=0)


@pytest.fixture(scope="module")
def rep_artifact():
    return rq.train(seed=0)


class TestM1SignalQuality:
    def test_clean_signal_scores_well(self, sqi_artifact) -> None:
        session = SyntheticEmgGenerator(FS, seed=1, junkiness=0.0).build_session(
            make_protocol(reps=3)
        )
        starts = _rest_window_starts(session)
        scores = [
            quality.assess(session.samples[s : s + 200], FS, sqi_artifact).score.point
            for s in starts[:10]
        ]
        assert np.mean(scores) > 70.0, f"clean signal scored {np.mean(scores):.0f}"

    def test_junky_signal_scores_poorly(self, sqi_artifact) -> None:
        session = SyntheticEmgGenerator(FS, seed=1, junkiness=1.0).build_session(
            make_protocol(reps=3)
        )
        starts = _rest_window_starts(session)
        scores = [
            quality.assess(session.samples[s : s + 200], FS, sqi_artifact).score.point
            for s in starts[:10]
        ]
        assert np.mean(scores) < 40.0, f"junky signal scored {np.mean(scores):.0f}"

    def test_quality_ordering_is_monotonic_enough(self, sqi_artifact) -> None:
        """Cleaner signal should not score worse than dirtier signal."""
        means = []
        for junkiness in (0.0, 0.5, 1.0):
            session = SyntheticEmgGenerator(
                FS, seed=2, junkiness=junkiness
            ).build_session(make_protocol(reps=3))
            starts = _rest_window_starts(session)
            means.append(
                np.mean(
                    [
                        quality.assess(
                            session.samples[s : s + 200], FS, sqi_artifact
                        ).score.point
                        for s in starts[:10]
                    ]
                )
            )

        assert means[0] > means[1] >= means[2] - 5.0

    def test_training_separates_the_classes(self, sqi_artifact) -> None:
        assert sqi_artifact["cv_accuracy"] > 0.75

    def test_score_is_bounded(self, sqi_artifact) -> None:
        session = SyntheticEmgGenerator(FS, seed=3, junkiness=0.4).build_session(
            make_protocol(reps=2)
        )
        assessment = quality.assess(session.samples[:200], FS, sqi_artifact)

        assert 0.0 <= assessment.score.lower <= assessment.score.point <= 100.0
        assert assessment.score.upper <= 100.0

    def test_bands_cover_the_range(self) -> None:
        assert quality.band_for(95.0)[0] == "A"
        assert quality.band_for(70.0)[0] == "B"
        assert quality.band_for(45.0)[0] == "C"
        assert quality.band_for(5.0)[0] == "D"

    def test_heuristic_fallback_still_scores(self) -> None:
        """The badge is permanently visible, so a missing model must not
        leave it blank or imply the signal is fine."""
        session = SyntheticEmgGenerator(FS, seed=4, junkiness=0.9).build_session(
            make_protocol(reps=2)
        )
        assessment = quality.assess(session.samples[:200], FS, artifact=None)

        assert 0.0 <= assessment.score.point <= 100.0
        assert "heuristic" in assessment.explanation.method

    def test_explanation_names_a_driver(self, sqi_artifact) -> None:
        session = SyntheticEmgGenerator(FS, seed=5, junkiness=0.8).build_session(
            make_protocol(reps=2)
        )
        assessment = quality.assess(session.samples[:200], FS, sqi_artifact)

        assert assessment.explanation.top_factor is not None
        assert assessment.explanation.summary


class TestM3Force:
    def _calibration(self, noise: float = 0.0, seed: int = 0):
        rng = np.random.default_rng(seed)
        kilograms = np.array([5.0, 12.0, 20.0, 28.0, 35.0])
        rows = [
            {
                "rms": k * 0.02 + rng.normal(0, noise),
                "mav": k * 0.016 + rng.normal(0, noise),
                "waveform_length": k * 2.1 + rng.normal(0, noise * 50),
            }
            for k in kilograms
        ]
        return rows, kilograms

    def test_recovers_a_known_linear_mapping(self) -> None:
        rows, kilograms = self._calibration()
        model = force.fit(rows, kilograms, mvc_reference_rms=0.7)

        for row, truth in zip(rows, kilograms):
            estimate = model.predict(row)
            assert abs(estimate.point - truth) / truth < 0.10

    def test_intervals_cover_the_truth(self) -> None:
        rows, kilograms = self._calibration(noise=0.002, seed=1)
        model = force.fit(rows, kilograms, mvc_reference_rms=0.7)

        covered = sum(
            model.predict(row).lower <= truth <= model.predict(row).upper
            for row, truth in zip(rows, kilograms)
        )
        assert covered >= len(kilograms) - 1

    def test_noisier_calibration_widens_the_interval(self) -> None:
        """A loose calibration should look loose, not falsely precise."""
        tight_rows, kilograms = self._calibration(noise=0.0005, seed=2)
        loose_rows, _ = self._calibration(noise=0.02, seed=2)

        tight = force.fit(tight_rows, kilograms, mvc_reference_rms=0.7)
        loose = force.fit(loose_rows, kilograms, mvc_reference_rms=0.7)

        assert loose.residual_sigma > tight.residual_sigma

    def test_interval_never_collapses_to_zero(self) -> None:
        """A perfect fit through five points is not proof of certainty."""
        rows, kilograms = self._calibration()
        model = force.fit(rows, kilograms, mvc_reference_rms=0.7)

        assert model.predict(rows[0]).width > 0.0

    def test_rejects_too_few_points(self) -> None:
        with pytest.raises(ValueError, match="at least"):
            force.fit(
                [{"rms": 0.1, "mav": 0.08, "waveform_length": 2.0}],
                [10.0],
                mvc_reference_rms=0.7,
            )

    def test_rejects_mismatched_inputs(self) -> None:
        rows, kilograms = self._calibration()
        with pytest.raises(ValueError):
            force.fit(rows, kilograms[:3], mvc_reference_rms=0.7)

    def test_rejects_bad_mvc_reference(self) -> None:
        rows, kilograms = self._calibration()
        with pytest.raises(ValueError):
            force.fit(rows, kilograms, mvc_reference_rms=0.0)

    def test_serializes_onto_a_calibration_row(self) -> None:
        rows, kilograms = self._calibration()
        model = force.fit(rows, kilograms, mvc_reference_rms=0.7)
        restored = force.ForceModel.from_json(model.to_json())

        assert restored.coefficients == model.coefficients
        assert restored.residual_sigma == model.residual_sigma
        assert restored.predict(rows[0]).point == pytest.approx(
            model.predict(rows[0]).point
        )

    def test_force_is_never_negative(self) -> None:
        rows, kilograms = self._calibration()
        model = force.fit(rows, kilograms, mvc_reference_rms=0.7)

        estimate = model.predict({"rms": 0.0, "mav": 0.0, "waveform_length": 0.0})
        assert estimate.point >= 0.0
        assert estimate.lower >= 0.0

    def test_explanation_states_it_is_an_estimate(self) -> None:
        rows, kilograms = self._calibration()
        model = force.fit(rows, kilograms, mvc_reference_rms=0.7)

        assert "estimate" in model.explain().summary.lower()

    def test_percent_mvc_normalization(self) -> None:
        assert force.percent_mvc(0.35, 0.7) == pytest.approx(50.0)
        assert force.percent_mvc(0.0, 0.7) == 0.0

    def test_percent_mvc_rejects_bad_reference(self) -> None:
        with pytest.raises(ValueError):
            force.percent_mvc(0.5, 0.0)


class TestM4RepQuality:
    GOOD = {
        "time_to_peak_s": 0.6,
        "rfd": 150.0,
        "duration_s": 5.4,
        "relaxation_time_s": 1.1,
        "hold_cv": 0.04,
        "plateau_flatness": 0.93,
    }
    POOR = {
        "time_to_peak_s": 2.1,
        "rfd": 30.0,
        "duration_s": 3.1,
        "relaxation_time_s": 0.2,
        "hold_cv": 0.29,
        "plateau_flatness": 0.38,
    }

    def test_ranks_a_good_rep_above_a_poor_one(self, rep_artifact) -> None:
        good = rq.score(self.GOOD, rep_artifact)
        poor = rq.score(self.POOR, rep_artifact)
        assert good.score.point > poor.score.point

    def test_separation_is_substantial(self, rep_artifact) -> None:
        good = rq.score(self.GOOD, rep_artifact)
        poor = rq.score(self.POOR, rep_artifact)
        assert good.score.point - poor.score.point > 30.0

    def test_model_fits_its_training_signal(self, rep_artifact) -> None:
        assert rep_artifact["cv_r2"] > 0.85

    def test_score_is_bounded(self, rep_artifact) -> None:
        for row in (self.GOOD, self.POOR):
            result = rq.score(row, rep_artifact)
            assert 0.0 <= result.score.lower <= result.score.point <= 100.0
            assert result.score.upper <= 100.0

    def test_feedback_is_a_sentence(self, rep_artifact) -> None:
        """This text is read by a patient mid session, so it has to be
        plain language rather than a feature name."""
        feedback = rq.score(self.GOOD, rep_artifact).feedback

        assert feedback[0].isupper()
        assert feedback.endswith(".")
        assert "_" not in feedback

    def test_heuristic_fallback_preserves_ordering(self) -> None:
        good = rq.score(self.GOOD, artifact=None)
        poor = rq.score(self.POOR, artifact=None)

        assert good.score.point > poor.score.point
        assert "heuristic" in good.explanation.method

    def test_explanation_names_factors(self, rep_artifact) -> None:
        explanation = rq.score(self.GOOD, rep_artifact).explanation
        assert explanation.factors
        assert explanation.top_factor is not None


class TestM5Fatigue:
    def _session_mdfs(self, shift: float, seed: int = 77) -> list[float]:
        generator = SyntheticEmgGenerator(
            FS, seed=seed, junkiness=0.1, fatigue_shift_hz_per_rep=shift
        )
        session = generator.build_session(make_protocol(reps=10))
        processed = preprocess(session.samples, FS)
        reps = segment_reps(processed.envelope, FS).reps
        rest = processed.envelope[: 2 * FS].mean()

        return [
            rep_features(
                processed.envelope,
                processed.filtered,
                FS,
                start_idx=rep.start_idx,
                peak_idx=rep.peak_idx,
                end_idx=rep.end_idx,
                mvc_reference=max(rest * 10, 1e-6),
            )["median_frequency"]
            for rep in reps
        ]

    def test_detects_fatigue_end_to_end(self) -> None:
        """The demo's central technical claim, through the whole pipeline."""
        assessment = fatigue.assess(self._session_mdfs(shift=2.2))

        assert assessment.slope is not None
        assert assessment.slope.point < 0
        assert assessment.significant
        assert assessment.fatigued
        assert assessment.p_value < 0.05

    def test_does_not_claim_fatigue_when_absent(self) -> None:
        """The negative control. A model that always finds fatigue is
        worthless."""
        assessment = fatigue.assess(self._session_mdfs(shift=0.0))

        assert not assessment.fatigued

    def test_slope_interval_brackets_the_estimate(self) -> None:
        assessment = fatigue.assess(self._session_mdfs(shift=2.2))
        assert assessment.slope is not None
        assert assessment.slope.lower <= assessment.slope.point <= assessment.slope.upper

    def test_reports_fit_quality(self) -> None:
        assessment = fatigue.assess(self._session_mdfs(shift=2.2))
        assert assessment.r_squared > 0.5

    def test_declines_to_fit_too_few_reps(self) -> None:
        assessment = fatigue.assess([100.0, 98.0])

        assert assessment.slope is None
        assert not assessment.fatigued
        assert "at least" in assessment.explanation.summary.lower()

    def test_handles_non_finite_values(self) -> None:
        """A repetition too short to give a spectrum yields nan, and that
        must not poison the regression."""
        assessment = fatigue.assess([120.0, np.nan, 110.0, 105.0, 100.0, 95.0])
        assert assessment.slope is not None

    def test_thorstensson_index(self) -> None:
        assert fatigue.thorstensson_index([100.0, 95.0, 80.0]) == pytest.approx(20.0)
        assert fatigue.thorstensson_index([50.0]) == 0.0

    def test_explanation_mentions_the_direction(self) -> None:
        assessment = fatigue.assess(self._session_mdfs(shift=2.2))
        assert "fell" in assessment.explanation.summary.lower()


class TestIntervalDiscipline:
    """Every model that predicts must return a bounded interval."""

    def test_all_signal_models_return_intervals(
        self, sqi_artifact, rep_artifact
    ) -> None:
        session = SyntheticEmgGenerator(FS, seed=9, junkiness=0.2).build_session(
            make_protocol(reps=6)
        )

        outputs = [
            quality.assess(session.samples[:200], FS, sqi_artifact).score,
            rq.score(TestM4RepQuality.GOOD, rep_artifact).score,
        ]

        rows = [
            {"rms": k * 0.02, "mav": k * 0.016, "waveform_length": k * 2.1}
            for k in (5.0, 12.0, 20.0, 28.0)
        ]
        model = force.fit(rows, [5.0, 12.0, 20.0, 28.0], mvc_reference_rms=0.7)
        outputs.append(model.predict(rows[0]))

        for interval in outputs:
            assert isinstance(interval, Interval)
            assert interval.lower <= interval.point <= interval.upper
