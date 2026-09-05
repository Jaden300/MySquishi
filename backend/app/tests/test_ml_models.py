"""M6 to M14.

The emphasis here is on the specific failure modes docs/ML.md names: KMeans
label instability, shuffled cross validation flattering the linear model,
silently dropping the draws that never reach a goal, and reporting an
exceptional session as a problem. Those are the mistakes worth a test.
"""

from __future__ import annotations

import numpy as np
import pytest

from app.ml import (
    adherence,
    anomaly,
    archetype,
    forecast,
    perceived,
    percentile,
    plateau,
    prescriber,
    time_to_goal,
)
from app.sim.cohort_gen import load_or_generate, patient_summary


@pytest.fixture(scope="module")
def cohort():
    return load_or_generate()


@pytest.fixture(scope="module")
def summary(cohort):
    return patient_summary(cohort)


# -- M12 archetype ---------------------------------------------------------


class TestArchetype:
    @pytest.fixture(scope="class")
    def artifact(self, cohort, summary):
        return archetype.train(cohort, summary=summary, seed=0)

    def test_names_are_stable_across_refits(self, cohort, summary):
        """The pitfall docs/ML.md:74 warns about.

        KMeans cluster indices are not stable between fits. If archetype names
        were keyed on the index, a patient would be a fast responder today and
        plateaued tomorrow with no change in their data.
        """
        rows = summary.iloc[:20][list(archetype.SHAPE_FEATURES)].to_dict("records")

        assignments = []
        for seed in (0, 1, 7, 42):
            artifact = archetype.train(cohort, summary=summary, seed=seed)
            assignments.append(
                [archetype.assign(row, artifact).archetype for row in rows]
            )

        for other in assignments[1:]:
            assert other == assignments[0]

    def test_uses_all_four_archetypes(self, artifact):
        found = {point["archetype"] for point in artifact["points"]}
        assert found == set(archetype.ARCHETYPE_LABELS)

    def test_persists_the_label_map_rather_than_hardcoding(self, artifact):
        assert set(artifact["label_map"].values()) == set(archetype.ARCHETYPE_LABELS)

    def test_falls_back_transparently(self):
        result = archetype.assign({"plateau_index": 0.3, "time_to_80pct": 0.2})
        assert "heuristic" in result.explanation.method


# -- M13 adherence ---------------------------------------------------------


class TestAdherence:
    @pytest.fixture(scope="class")
    def artifact(self, cohort):
        return adherence.train(cohort, seed=0)

    def test_constructed_label_has_usable_positives(self, cohort):
        """A fixed fourteen day window produces under one percent positives on
        this cohort, which is not enough to learn from. The per patient lapse
        definition has to do better."""
        _, y = adherence.build_training_set(cohort)
        assert 0.01 < y.mean() < 0.30

    def test_discriminates_better_than_chance(self, artifact):
        assert artifact["cv_auc"] > 0.55

    def test_a_long_gap_raises_risk(self, artifact):
        steady = adherence.assess(
            {
                "sessions_completed": 20,
                "days_since_last": 2,
                "completion_rate": 0.95,
                "recent_trend": 0.4,
                "weeks_elapsed": 8,
            },
            artifact,
        )
        slipping = adherence.assess(
            {
                "sessions_completed": 8,
                "days_since_last": 18,
                "completion_rate": 0.45,
                "recent_trend": -0.2,
                "weeks_elapsed": 9,
            },
            artifact,
        )
        assert slipping.probability.point > steady.probability.point

    def test_copy_is_never_shaming(self):
        """docs/ML.md:76 requires the surfaced copy to be encouraging.

        Someone who has missed sessions already knows. An app that scolds is
        one that gets deleted.
        """
        from pathlib import Path

        source = Path(adherence.__file__).read_text(encoding="utf-8").lower()
        for word in (
            "failed",
            "you should have",
            "lazy",
            "excuse",
            "disappointing",
            "poor effort",
        ):
            assert word not in source, f"shaming language found: {word}"


# -- M14 percentile --------------------------------------------------------


class TestPercentile:
    @pytest.fixture(scope="class")
    def artifact(self, cohort, summary):
        return percentile.train(cohort, summary=summary)

    def test_small_cells_are_pooled_and_say_so(self, artifact):
        """The smallest demographic cell holds twelve patients. A percentile
        from twelve points needs to admit what it is."""
        result = percentile.assess(
            20.0, sex="male", age_band="80+", artifact=artifact
        )
        assert result.pooled is True
        assert result.n_reference >= percentile.MIN_CELL

    def test_always_reports_the_reference_size(self, artifact):
        result = percentile.assess(
            25.0, sex="female", age_band="50-64", artifact=artifact
        )
        assert result.n_reference > 0

    def test_is_always_labeled_synthetic(self, artifact):
        # There is no circumstance where this reference is real data.
        result = percentile.assess(
            25.0, sex="female", age_band="50-64", artifact=artifact
        )
        assert result.is_synthetic is True

    def test_applies_ewgsop2_thresholds_correctly(self, artifact):
        # Under 27 kg for men and under 16 kg for women, per docs/CLINICAL.md.
        assert percentile.assess(
            26.0, sex="male", age_band="50-64", artifact=artifact
        ).below_threshold
        assert not percentile.assess(
            28.0, sex="male", age_band="50-64", artifact=artifact
        ).below_threshold
        assert percentile.assess(
            15.0, sex="female", age_band="50-64", artifact=artifact
        ).below_threshold

    def test_stronger_grip_ranks_higher(self, artifact):
        weak = percentile.assess(15.0, sex="female", age_band="50-64", artifact=artifact)
        strong = percentile.assess(30.0, sex="female", age_band="50-64", artifact=artifact)
        assert strong.percentile.point > weak.percentile.point

    def test_writes_ordinals_correctly(self):
        from app.ml.percentile import _ordinal

        assert _ordinal(1) == "1st"
        assert _ordinal(22) == "22nd"
        assert _ordinal(43) == "43rd"
        assert _ordinal(11) == "11th"
        assert _ordinal(50) == "50th"


# -- M6 anomaly ------------------------------------------------------------


class TestAnomaly:
    @pytest.fixture(scope="class")
    def artifact(self, cohort):
        return anomaly.train(cohort, seed=0)

    @staticmethod
    def _session(**overrides) -> dict[str, float]:
        base = {
            "mean_mvc": 55.0,
            "rep_count": 10.0,
            "fatigue_slope": -0.4,
            "hold_cv": 0.10,
            "adherence_gap_days": 3.0,
            "sqi_mean": 88.0,
        }
        return {**base, **overrides}

    def test_an_exceptional_session_is_not_reported_as_a_problem(self, artifact):
        """docs/ML.md:52. Direction is the point of this model.

        A breakthrough session is statistically as unusual as a collapse.
        Telling someone their best session was an anomaly to worry about would
        be both wrong and discouraging.
        """
        history = [self._session() for _ in range(5)]
        result = anomaly.assess(
            self._session(mean_mvc=95.0, rep_count=16.0),
            history=history,
            artifact=artifact,
        )

        assert result.direction == "positive"
        assert "good" in result.explanation.summary.lower()

    def test_a_collapse_is_reported_as_negative(self, artifact):
        history = [self._session() for _ in range(5)]
        result = anomaly.assess(
            self._session(mean_mvc=15.0, rep_count=3.0, hold_cv=0.45),
            history=history,
            artifact=artifact,
        )
        assert result.direction == "negative"

    def test_direction_is_relative_to_the_patient_not_the_cohort(self, artifact):
        """A weak session for a strong patient is still a down session."""
        strong_history = [self._session(mean_mvc=85.0) for _ in range(5)]
        result = anomaly.assess(
            self._session(mean_mvc=60.0), history=strong_history, artifact=artifact
        )
        assert result.direction == "negative"

    def test_a_typical_session_is_not_flagged(self, artifact):
        history = [self._session() for _ in range(5)]
        result = anomaly.assess(self._session(), history=history, artifact=artifact)
        assert result.is_anomaly is False

    def test_explains_which_measure_differed(self, artifact):
        history = [self._session() for _ in range(5)]
        result = anomaly.assess(
            self._session(hold_cv=0.55), history=history, artifact=artifact
        )
        assert result.explanation.factors


# -- M7 perceived ----------------------------------------------------------


class TestPerceived:
    @pytest.fixture(scope="class")
    def artifact(self, cohort):
        return perceived.train(cohort, seed=0)

    @staticmethod
    def _session() -> dict[str, float]:
        return {
            "mean_mvc": 55.0,
            "peak_mvc": 78.0,
            "rep_count": 10.0,
            "fatigue_slope": -0.4,
            "hold_cv": 0.10,
        }

    def test_flags_a_session_that_felt_much_harder(self, artifact):
        result = perceived.assess(
            self._session(), actual_borg=10.0, artifact=artifact
        )
        assert result.flag == "harder_than_expected"

    def test_flags_a_session_that_felt_much_easier(self, artifact):
        result = perceived.assess(self._session(), actual_borg=1.0, artifact=artifact)
        assert result.flag == "easier_than_expected"

    def test_says_nothing_when_the_rating_matches(self, artifact):
        predicted = perceived.assess(self._session(), artifact=artifact)
        result = perceived.assess(
            self._session(),
            actual_borg=round(predicted.predicted_borg.point),
            artifact=artifact,
        )
        assert result.flag == "as_expected"

    def test_prediction_stays_on_the_borg_scale(self, artifact):
        result = perceived.assess(self._session(), artifact=artifact)
        assert 0.0 <= result.predicted_borg.point <= 10.0


# -- M9 forecast -----------------------------------------------------------


class TestForecast:
    def test_plateau_curve_wins_on_saturating_history(self):
        """The physiologically realistic shape should win when the data has
        that shape. If linear wins here, the selection is broken."""
        rng = np.random.default_rng(0)
        t = np.arange(24) / 2.5
        y = 12 + (26 - 12) * (1 - np.exp(-0.35 * t)) + rng.normal(0, 0.5, 24)

        result = forecast.fit_trajectory(y)
        assert result.winner == "exponential_plateau"

    def test_uses_expanding_window_not_shuffled_cross_validation(self):
        """docs/ML.md:66. Shuffling leaks the future into the past.

        Asserted against the source, because the failure is silent: shuffled
        folds still produce plausible numbers, they are just the wrong ones.
        """
        from pathlib import Path

        source = Path(forecast.__file__).read_text(encoding="utf-8")
        assert "TimeSeriesSplit" in source
        assert "KFold" not in source
        assert "shuffle=True" not in source

    def test_refuses_to_fit_through_too_few_points(self):
        result = forecast.fit_trajectory([10.0, 11.0, 12.0])
        assert result.insufficient_data is True
        assert result.forecast == []

    def test_band_contains_the_projection_at_every_step(self):
        rng = np.random.default_rng(1)
        y = 12 + 0.5 * np.arange(20) + rng.normal(0, 0.5, 20)

        for point in forecast.fit_trajectory(y).forecast:
            assert point.lower <= point.point <= point.upper

    def test_reports_the_full_comparison_not_just_the_winner(self):
        rng = np.random.default_rng(2)
        y = 12 + 0.5 * np.arange(20) + rng.normal(0, 0.5, 20)

        result = forecast.fit_trajectory(y)
        assert set(result.cv_table) == set(forecast.CANDIDATES)


# -- M10 time to goal ------------------------------------------------------


class TestTimeToGoal:
    @staticmethod
    def _rising():
        rng = np.random.default_rng(0)
        return forecast.fit_trajectory(
            12 + 0.4 * np.arange(20) + rng.normal(0, 0.4, 20)
        )

    def test_reports_weeks_for_a_reachable_goal(self):
        result = time_to_goal.estimate(self._rising(), 22.0)
        assert result.reachable is True
        assert result.weeks is not None
        assert result.weeks.lower <= result.weeks.point <= result.weeks.upper

    def test_never_crossing_draws_are_reported_not_dropped(self):
        """docs/ML.md:68. The easy mistake is to take the median of the draws
        that did cross and print a confident number that describes only the
        optimistic minority."""
        result = time_to_goal.estimate(self._rising(), 200.0)

        assert result.never_crosses_share > 0.5
        assert result.weeks is None, "no median may be reported for an unlikely goal"
        assert "unlikely" in result.explanation.summary.lower()

    def test_says_so_when_the_goal_is_already_met(self):
        result = time_to_goal.estimate(self._rising(), 5.0)
        assert result.weeks is not None
        assert result.weeks.point == 0.0

    def test_handles_a_history_too_short_to_fit(self):
        short = forecast.fit_trajectory([10.0, 11.0])
        result = time_to_goal.estimate(short, 20.0)
        assert result.reachable is False
        assert result.weeks is None


# -- M11 plateau -----------------------------------------------------------


class TestPlateau:
    def test_finds_a_planted_changepoint(self):
        rng = np.random.default_rng(0)
        rising = 12 + 0.7 * np.arange(14)
        flat = np.full(12, rising[-1]) + rng.normal(0, 0.35, 12)
        series = np.concatenate([rising, flat]) + rng.normal(0, 0.2, 26)

        result = plateau.detect(series)
        assert result.is_plateau is True
        assert result.changepoints

    def test_does_not_flag_steady_progress(self):
        """Calling a still improving patient plateaued would be discouraging
        and wrong."""
        rng = np.random.default_rng(1)
        series = 12 + 0.6 * np.arange(26) + rng.normal(0, 0.4, 26)

        assert plateau.detect(series).is_plateau is False

    def test_verdict_requires_a_slope_indistinguishable_from_zero(self):
        rng = np.random.default_rng(2)
        series = np.concatenate(
            [12 + 0.7 * np.arange(14), np.full(12, 21.8) + rng.normal(0, 0.3, 12)]
        )
        result = plateau.detect(series)

        assert result.recent_slope.lower <= 0.0 <= result.recent_slope.upper

    def test_declines_to_judge_a_short_history(self):
        assert plateau.detect([10.0, 11.0, 12.0]).is_plateau is False


# -- M8 prescriber ---------------------------------------------------------


class TestPrescriber:
    def test_every_number_comes_with_a_reason(self):
        """A prescription a patient cannot interrogate is one they have to
        take on trust."""
        plan, _ = prescriber.prescribe()
        assert plan.reasons

    def test_progresses_after_three_strong_sessions(self):
        plan, _ = prescriber.prescribe(
            recent_quality=[85.0, 88.0, 90.0], last_target_mvc=50.0
        )
        assert plan.target_mvc_pct > 50.0

    def test_eases_off_after_fatigue(self):
        plan, _ = prescriber.prescribe(fatigue_slope=-1.2, last_target_mvc=60.0)
        assert plan.target_mvc_pct < 60.0
        assert plan.rest_s > prescriber.DEFAULT_REST_S

    def test_poor_signal_quality_holds_targets_steady(self):
        """Changing a target on the basis of a reading that could not be
        trusted would be acting on a measurement that was not real."""
        plan, _ = prescriber.prescribe(
            recent_quality=[90.0, 92.0, 95.0], last_target_mvc=50.0, last_sqi=35.0
        )
        assert plan.target_mvc_pct == 50.0
        assert any("electrode" in reason for reason in plan.reasons)

    def test_lowers_the_barrier_when_adherence_is_at_risk(self):
        plan, _ = prescriber.prescribe(adherence_risk=0.8)
        assert plan.rep_count < prescriber.DEFAULT_REPS

    def test_stays_within_safe_bounds(self):
        plan, _ = prescriber.prescribe(
            recent_quality=[100.0] * 3, last_target_mvc=79.0
        )
        assert plan.target_mvc_pct <= prescriber.MAX_TARGET_MVC
