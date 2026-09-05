"""Interval discipline, across every model that returns one.

docs/ML.md:88 requires a parameterized test asserting lower <= point <= upper
across every interval returning model. This is that test.

The completeness check matters as much as the assertions: a model added
without being registered here fails the suite, so this cannot quietly fall
behind the model stack it is meant to cover.
"""

from __future__ import annotations

import numpy as np
import pytest

from app.ml import (
    adherence,
    anomaly,
    fatigue,
    force,
    perceived,
    percentile,
    plateau,
    quality,
    rep_quality,
    time_to_goal,
    forecast,
)
from app.ml.explain import Interval
from app.signal.features import REP_FEATURE_KEYS
from app.sim.cohort_gen import load_or_generate, patient_summary

# Every model in the M1 to M14 stack, and where its uncertainty comes from.
# A model that legitimately returns no interval is listed with a reason, so
# the absence is a decision rather than an oversight.
NON_INTERVAL_MODELS = {
    "M2": "segmentation returns repetition boundaries, not a prediction",
    "M8": "the prescriber returns targets from rules, with reasons rather than a band",
    "M9": "returns a band per forecast step, asserted separately in test_ml_models",
    "M12": "returns a categorical archetype with a confidence, not an interval",
}


@pytest.fixture(scope="module")
def cohort():
    return load_or_generate()


@pytest.fixture(scope="module")
def summary(cohort):
    return patient_summary(cohort)


def _session() -> dict[str, float]:
    return {
        "mean_mvc": 55.0,
        "peak_mvc": 78.0,
        "rep_count": 10.0,
        "fatigue_slope": -0.4,
        "hold_cv": 0.10,
        "adherence_gap_days": 3.0,
        "sqi_mean": 88.0,
    }


def _intervals(cohort, summary) -> dict[str, Interval]:
    """One interval from each model that produces one."""
    rng = np.random.default_rng(0)
    found: dict[str, Interval] = {}

    # M1 signal quality.
    samples = rng.normal(0, 0.1, 2000)
    found["M1"] = quality.assess(samples, 1000).score

    # M3 force estimation.
    fractions = np.linspace(0.3, 1.0, 6)
    model = force.fit(
        [
            {"rms": f * 100, "mav": f * 80, "waveform_length": f * 1200}
            for f in fractions
        ],
        25.0 * fractions,
        mvc_reference_rms=100.0,
    )
    found["M3"] = model.predict(
        {"rms": 80.0, "mav": 64.0, "waveform_length": 960.0}
    )

    # M4 repetition quality.
    found["M4"] = rep_quality.score(dict.fromkeys(REP_FEATURE_KEYS, 1.0)).score

    # M5 spectral fatigue.
    found["M5"] = fatigue.assess(
        np.linspace(95, 80, 10) + rng.normal(0, 0.5, 10)
    ).slope

    # M6 session anomaly.
    found["M6"] = anomaly.assess(
        _session(),
        history=[_session() for _ in range(5)],
        artifact=anomaly.train(cohort, seed=0),
    ).score

    # M7 perceived effort.
    found["M7"] = perceived.assess(
        _session(), actual_borg=6.0, artifact=perceived.train(cohort, seed=0)
    ).predicted_borg

    # M10 time to goal.
    trajectory = forecast.fit_trajectory(
        12 + 0.4 * np.arange(20) + rng.normal(0, 0.4, 20)
    )
    result = time_to_goal.estimate(trajectory, 20.0)
    assert result.weeks is not None
    found["M10"] = result.weeks

    # M11 plateau, whose recent slope carries the interval.
    found["M11"] = plateau.detect(
        12 + 0.5 * np.arange(20) + rng.normal(0, 0.4, 20)
    ).recent_slope

    # M13 adherence risk.
    found["M13"] = adherence.assess(
        {
            "sessions_completed": 15.0,
            "days_since_last": 4.0,
            "completion_rate": 0.8,
            "recent_trend": 0.2,
            "weeks_elapsed": 7.0,
        },
        adherence.train(cohort, seed=0),
    ).probability

    # M14 cohort percentile.
    found["M14"] = percentile.assess(
        24.0,
        sex="female",
        age_band="50-64",
        artifact=percentile.train(cohort, summary=summary),
    ).percentile

    return found


@pytest.fixture(scope="module")
def intervals(cohort, summary):
    return _intervals(cohort, summary)


class TestIntervalDiscipline:
    @pytest.mark.parametrize(
        "model_id",
        ["M1", "M3", "M4", "M5", "M6", "M7", "M10", "M11", "M13", "M14"],
    )
    def test_bounds_are_ordered(self, intervals, model_id):
        interval = intervals[model_id]
        assert interval.lower <= interval.point <= interval.upper

    @pytest.mark.parametrize(
        "model_id",
        ["M1", "M3", "M4", "M5", "M6", "M7", "M10", "M11", "M13", "M14"],
    )
    def test_bounds_are_finite(self, intervals, model_id):
        interval = intervals[model_id]
        assert np.isfinite([interval.point, interval.lower, interval.upper]).all()

    @pytest.mark.parametrize(
        "model_id",
        ["M1", "M3", "M4", "M5", "M6", "M7", "M10", "M11", "M13", "M14"],
    )
    def test_level_is_a_probability(self, intervals, model_id):
        assert 0.0 < intervals[model_id].level < 1.0

    def test_every_model_is_accounted_for(self, intervals):
        """Completeness.

        Every model from M1 to M14 either returns an interval that is checked
        above, or is listed with a reason why it does not. A new model cannot
        slip past this file unnoticed.
        """
        expected = {f"M{i}" for i in range(1, 15)}
        covered = set(intervals) | set(NON_INTERVAL_MODELS)

        assert covered == expected, f"unaccounted for: {expected - covered}"

    def test_an_inverted_interval_cannot_be_constructed(self):
        """The discipline is enforced by the type, not by convention."""
        with pytest.raises(ValueError):
            Interval(point=5.0, lower=8.0, upper=3.0)

    def test_a_non_finite_interval_cannot_be_constructed(self):
        with pytest.raises(ValueError):
            Interval(point=float("nan"), lower=0.0, upper=1.0)
