"""Tests for the ML primitives: intervals, explanations, and the registry.

The interval invariant is the important one. It is what makes the no bare
point estimates rule structural rather than a matter of remembering, so it is
checked at construction and cannot be bypassed.
"""

from __future__ import annotations

import numpy as np
import pytest

from app.ml.explain import (
    Explanation,
    Factor,
    Interval,
    bootstrap_interval,
    coefficient_factors,
    label_for,
    permutation_factors,
)
from app.ml.registry import ModelRegistry


class TestInterval:
    def test_holds_ordering(self) -> None:
        interval = Interval(point=5.0, lower=3.0, upper=8.0)
        assert interval.lower <= interval.point <= interval.upper
        assert interval.width == 5.0

    def test_rejects_inverted_bounds(self) -> None:
        """A model producing an inverted interval has a bug, and it should
        surface here rather than in a chart."""
        with pytest.raises(ValueError, match="lower <= point <= upper"):
            Interval(point=5.0, lower=8.0, upper=3.0)

    def test_rejects_point_outside_bounds(self) -> None:
        with pytest.raises(ValueError):
            Interval(point=99.0, lower=3.0, upper=8.0)

    def test_rejects_non_finite_values(self) -> None:
        with pytest.raises(ValueError, match="finite"):
            Interval(point=float("nan"), lower=0.0, upper=1.0)
        with pytest.raises(ValueError):
            Interval(point=1.0, lower=float("-inf"), upper=2.0)

    def test_rejects_impossible_level(self) -> None:
        with pytest.raises(ValueError, match="level"):
            Interval(point=1.0, lower=0.0, upper=2.0, level=1.5)

    def test_degenerate_interval_is_allowed(self) -> None:
        """A model can be certain. That is not an error."""
        assert Interval(point=5.0, lower=5.0, upper=5.0).width == 0.0

    def test_clamping_preserves_ordering(self) -> None:
        clamped = Interval(point=95.0, lower=80.0, upper=130.0).clamped(0.0, 100.0)
        assert clamped.lower <= clamped.point <= clamped.upper
        assert clamped.upper == 100.0

    def test_serialization_carries_the_bounds(self) -> None:
        payload = Interval(point=5.0, lower=3.0, upper=8.0, unit="kg").to_dict()
        assert payload["lower"] == 3.0
        assert payload["upper"] == 8.0
        assert payload["unit"] == "kg"


class TestBootstrapInterval:
    def test_brackets_the_draws(self) -> None:
        draws = np.random.default_rng(0).normal(10.0, 2.0, size=2000)
        interval = bootstrap_interval(draws, level=0.8)

        assert interval.lower < interval.point < interval.upper
        assert interval.point == pytest.approx(10.0, abs=0.3)

    def test_wider_level_gives_wider_interval(self) -> None:
        draws = np.random.default_rng(1).normal(0.0, 1.0, size=2000)
        assert (
            bootstrap_interval(draws, level=0.95).width
            > bootstrap_interval(draws, level=0.5).width
        )

    def test_widens_to_include_a_supplied_point(self) -> None:
        """A skewed posterior can put the model's answer outside the
        empirical percentiles. The interval widens rather than rejecting it."""
        draws = np.random.default_rng(2).normal(0.0, 1.0, size=500)
        interval = bootstrap_interval(draws, point=9.0)

        assert interval.point == 9.0
        assert interval.upper >= 9.0

    def test_ignores_non_finite_draws(self) -> None:
        draws = np.array([1.0, 2.0, np.nan, 3.0, np.inf])
        assert np.isfinite(bootstrap_interval(draws).point)

    def test_rejects_all_non_finite(self) -> None:
        with pytest.raises(ValueError, match="zero finite"):
            bootstrap_interval(np.array([np.nan, np.inf]))


class TestCoefficientFactors:
    def test_ranks_by_absolute_contribution(self) -> None:
        factors = coefficient_factors([0.1, -5.0, 2.0], ["a", "b", "c"], top_n=2)

        assert [f.name for f in factors] == ["b", "c"]
        assert factors[0].direction == "decreases"
        assert factors[1].direction == "increases"

    def test_uses_values_when_supplied(self) -> None:
        """A large coefficient on a feature that is near zero did not move
        this particular prediction."""
        factors = coefficient_factors(
            [10.0, 1.0], ["big_coef", "small_coef"], feature_values=[0.0, 50.0], top_n=1
        )
        assert factors[0].name == "small_coef"

    def test_rejects_length_mismatch(self) -> None:
        with pytest.raises(ValueError):
            coefficient_factors([1.0, 2.0], ["only_one"])

    def test_plain_text_is_human_readable(self) -> None:
        factors = coefficient_factors([3.0], ["hold_cv"], top_n=1)
        assert "hold steadiness" in factors[0].plain_text


class TestPermutationFactors:
    def test_identifies_the_informative_feature(self) -> None:
        from sklearn.ensemble import RandomForestRegressor

        rng = np.random.default_rng(0)
        X = rng.normal(size=(200, 3))
        # Only column 1 carries signal.
        y = X[:, 1] * 5.0 + rng.normal(scale=0.1, size=200)

        model = RandomForestRegressor(n_estimators=30, random_state=0).fit(X, y)
        factors = permutation_factors(model, X, y, ["noise_a", "signal", "noise_b"], top_n=1)

        assert factors[0].name == "signal"

    def test_rejects_shape_mismatch(self) -> None:
        from sklearn.linear_model import LinearRegression

        X = np.zeros((10, 3))
        model = LinearRegression().fit(X, np.zeros(10))
        with pytest.raises(ValueError):
            permutation_factors(model, X, np.zeros(10), ["too", "few"])


class TestExplanation:
    def test_top_factor_is_the_first(self) -> None:
        explanation = Explanation(
            summary="because of things",
            factors=[
                Factor("a", 5.0, "increases", "a mattered"),
                Factor("b", 1.0, "decreases", "b mattered less"),
            ],
            method="coefficients",
        )
        assert explanation.top_factor is not None
        assert explanation.top_factor.name == "a"

    def test_empty_explanation_has_no_top_factor(self) -> None:
        assert Explanation(summary="no drivers").top_factor is None

    def test_serializes_nested_factors(self) -> None:
        payload = Explanation(
            summary="s",
            factors=[Factor("a", 1.0, "increases", "text")],
            method="m",
        ).to_dict()

        assert payload["factors"][0]["name"] == "a"
        assert payload["method"] == "m"


class TestFeatureLabels:
    def test_known_features_get_human_names(self) -> None:
        assert label_for("hold_cv") == "hold steadiness"
        assert label_for("rfd") == "rate of force development"

    def test_unknown_features_fall_back_readably(self) -> None:
        """Feature names leak into the UI, so an unmapped key should still
        read as words rather than as an identifier."""
        assert label_for("some_new_feature") == "some new feature"


class TestModelRegistry:
    def test_save_and_load_round_trip(self, tmp_path) -> None:
        registry = ModelRegistry(tmp_path)
        registry.save(
            "M99",
            {"weights": [1, 2, 3]},
            metric_name="r2",
            metric_value=0.87,
            cohort_version="v1",
            n_training_rows=100,
        )

        assert registry.load("M99") == {"weights": [1, 2, 3]}

    def test_missing_artifact_explains_how_to_build_it(self, tmp_path) -> None:
        with pytest.raises(FileNotFoundError, match="train_all"):
            ModelRegistry(tmp_path).load("M99")

    def test_try_load_returns_none_when_missing(self, tmp_path) -> None:
        assert ModelRegistry(tmp_path).try_load("M99") is None

    def test_manifest_records_provenance(self, tmp_path) -> None:
        registry = ModelRegistry(tmp_path)
        registry.save(
            "M99",
            object(),
            metric_name="accuracy",
            metric_value=0.91,
            cohort_version="v1",
            n_training_rows=250,
        )

        record = registry.manifest().artifacts["M99"]
        assert record.metric_name == "accuracy"
        assert record.metric_value == 0.91
        assert record.n_training_rows == 250
        assert record.trained_at

    def test_manifest_survives_a_reload(self, tmp_path) -> None:
        first = ModelRegistry(tmp_path)
        first.save(
            "M99",
            object(),
            metric_name="r2",
            metric_value=0.5,
            cohort_version="v1",
            n_training_rows=10,
        )

        assert "M99" in ModelRegistry(tmp_path).manifest().artifacts

    def test_corrupt_manifest_does_not_break_loading(self, tmp_path) -> None:
        (tmp_path / "manifest.json").write_text("{not json", encoding="utf-8")
        assert ModelRegistry(tmp_path).manifest().artifacts == {}

    def test_staleness_detection(self, tmp_path) -> None:
        registry = ModelRegistry(tmp_path)
        assert registry.is_stale("M99")

        registry.save(
            "M99",
            object(),
            metric_name="r2",
            metric_value=0.5,
            cohort_version="v1",
            n_training_rows=10,
        )
        assert not registry.is_stale("M99")

    def test_records_are_sorted(self, tmp_path) -> None:
        registry = ModelRegistry(tmp_path)
        for model_id in ("M12", "M01", "M06"):
            registry.save(
                model_id,
                object(),
                metric_name="r2",
                metric_value=0.5,
                cohort_version="v1",
                n_training_rows=10,
            )

        assert [r.model_id for r in registry.records()] == ["M01", "M06", "M12"]
