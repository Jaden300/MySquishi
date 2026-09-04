"""Tests for the synthetic patient cohort.

The cohort gates M6, M7, M12, M13 and M14, so these tests check that the
population has the structure those models need: four distinguishable
archetypes, realistic adherence including dropouts, and a perceived versus
measured effort relationship that is real but not deterministic.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.sim.cohort_gen import (
    ARCHETYPES,
    _COHORT_COLUMNS,
    generate_cohort,
    patient_summary,
)

SEED = 42
N = 300


@pytest.fixture(scope="module")
def cohort() -> pd.DataFrame:
    return generate_cohort(N, SEED)


@pytest.fixture(scope="module")
def summary(cohort: pd.DataFrame) -> pd.DataFrame:
    return patient_summary(cohort)


class TestShape:
    def test_generates_the_requested_population(self, cohort: pd.DataFrame) -> None:
        assert cohort["patient_id"].nunique() == N

    def test_cohort_size_is_range_checked(self) -> None:
        """The plan calls for 200 to 400 patients."""
        with pytest.raises(ValueError):
            generate_cohort(50, SEED)
        with pytest.raises(ValueError):
            generate_cohort(900, SEED)

    def test_columns_are_frozen(self, cohort: pd.DataFrame) -> None:
        assert tuple(cohort.columns) == _COHORT_COLUMNS

    def test_programmes_run_six_to_fourteen_weeks(self, summary: pd.DataFrame) -> None:
        assert summary["weeks"].min() >= 6
        assert summary["weeks"].max() <= 14

    def test_every_patient_has_a_usable_history(self, summary: pd.DataFrame) -> None:
        """A patient with almost no completed sessions cannot be forecast,
        and would pollute the models that train on this."""
        assert len(summary) >= N * 0.95
        assert summary["sessions_completed"].min() >= 3

    def test_generation_is_fast(self) -> None:
        """The whole cohort has to build in seconds, since it is regenerated
        whenever the seed or version changes."""
        import time

        start = time.monotonic()
        generate_cohort(N, SEED)
        assert time.monotonic() - start < 10.0


class TestDeterminism:
    def test_same_seed_reproduces_exactly(self) -> None:
        a = generate_cohort(200, 7)
        b = generate_cohort(200, 7)
        pd.testing.assert_frame_equal(a, b)

    def test_different_seeds_differ(self) -> None:
        a = generate_cohort(200, 1)
        b = generate_cohort(200, 2)
        assert not a.equals(b)


class TestArchetypes:
    def test_all_four_are_well_represented(self, summary: pd.DataFrame) -> None:
        """M12 clusters into four groups, so each needs real support."""
        share = summary["archetype"].value_counts(normalize=True)
        assert set(share.index) == set(ARCHETYPES)
        assert share.min() >= 0.10

    def test_archetypes_have_distinguishable_outcomes(
        self, summary: pd.DataFrame
    ) -> None:
        """If the shapes were not separable, M12 would be clustering noise."""
        gain = summary["final_kg"] / summary["baseline_kg"]
        by_archetype = gain.groupby(summary["archetype"]).median()

        assert by_archetype["fast_responder"] > by_archetype["plateaued"]
        assert by_archetype["steady_climber"] > by_archetype["plateaued"]
        # A meaningful separation, not a rounding difference.
        assert by_archetype.max() - by_archetype.min() > 0.3

    def test_late_bloomers_gain_later_than_fast_responders(
        self, summary: pd.DataFrame
    ) -> None:
        """The defining difference between the two shapes."""
        timing = summary.groupby("archetype")["time_to_80pct"].median()
        assert timing["late_bloomer"] > timing["fast_responder"]

    def test_plateaued_patients_stall(self, summary: pd.DataFrame) -> None:
        by_archetype = summary.groupby("archetype")["final_ratio"].median()
        assert by_archetype["plateaued"] < by_archetype["fast_responder"]


class TestAdherence:
    def test_adherence_varies_across_the_cohort(self, summary: pd.DataFrame) -> None:
        assert summary["adherence_rate"].std() > 0.05

    def test_some_patients_adhere_poorly(self, summary: pd.DataFrame) -> None:
        """M13 predicts disengagement, so disengagement has to exist."""
        assert (summary["adherence_rate"] < 0.6).mean() > 0.05

    def test_most_patients_adhere_reasonably(self, summary: pd.DataFrame) -> None:
        """A cohort of near total dropouts would not be plausible."""
        assert summary["adherence_rate"].mean() > 0.6

    def test_missed_sessions_are_recorded_not_dropped(
        self, cohort: pd.DataFrame
    ) -> None:
        """Adherence modelling needs the misses as well as the hits."""
        assert (~cohort["completed"]).sum() > 0
        assert cohort["prescribed"].all()

    def test_missed_sessions_carry_no_measurements(self, cohort: pd.DataFrame) -> None:
        missed = cohort[~cohort["completed"]]
        assert missed["strength_kg"].isna().all()
        assert missed["borg"].isna().all()
        assert (missed["rep_count"] == 0).all()

    def test_gaps_are_tracked(self, cohort: pd.DataFrame) -> None:
        done = cohort[cohort["completed"]]
        assert done["adherence_gap_days"].max() > 7


class TestClinicalPlausibility:
    def test_strength_generally_improves(self, summary: pd.DataFrame) -> None:
        improved = (summary["final_kg"] > summary["baseline_kg"]).mean()
        assert improved > 0.85

    def test_improvement_is_not_monotonic(self, cohort: pd.DataFrame) -> None:
        """Real recovery has bad days and setbacks. A perfectly smooth
        cohort would make the plateau and anomaly models meaningless."""
        done = cohort[cohort["completed"]].sort_values(["patient_id", "session_index"])
        declines = done.groupby("patient_id")["strength_kg"].apply(
            lambda s: (s.diff() < 0).mean()
        )
        assert declines.mean() > 0.05

    def test_strength_stays_below_the_unaffected_side(
        self, cohort: pd.DataFrame
    ) -> None:
        done = cohort[cohort["completed"]]
        ratio = done["strength_kg"] / done["unaffected_kg"]
        # A little overshoot is plausible; wild overshoot is not.
        assert ratio.max() < 1.3
        assert ratio.min() > 0.0

    def test_borg_is_on_the_cr10_scale(self, cohort: pd.DataFrame) -> None:
        borg = cohort[cohort["completed"]]["borg"]
        assert borg.min() >= 0
        assert borg.max() <= 10

    def test_borg_correlates_with_measured_effort(self, cohort: pd.DataFrame) -> None:
        """M7 models this relationship and surfaces the residual, so the
        relationship must be real but not deterministic."""
        done = cohort[cohort["completed"]]
        r = float(done["borg"].corr(done["mean_mvc"]))
        assert 0.4 < r < 0.95, f"correlation was {r:.2f}"

    def test_effort_is_expressed_as_percent_mvc(self, cohort: pd.DataFrame) -> None:
        done = cohort[cohort["completed"]]
        assert done["mean_mvc"].between(0, 100).all()
        assert done["peak_mvc"].between(0, 100).all()
        assert (done["peak_mvc"] >= done["mean_mvc"]).all()

    def test_fatigue_slopes_are_generally_negative(self, cohort: pd.DataFrame) -> None:
        """Median frequency falls as a muscle tires."""
        done = cohort[cohort["completed"]]
        assert done["fatigue_slope"].median() < 0

    def test_signal_quality_varies_by_patient(self, summary: pd.DataFrame) -> None:
        """Electrode technique and body habitus differ, which is what makes
        the quality index worth having."""
        assert summary["mean_sqi"].std() > 3.0
        assert summary["mean_sqi"].between(0, 100).all()

    def test_demographics_are_populated(self, summary: pd.DataFrame) -> None:
        assert summary["age_band"].nunique() >= 4
        assert summary["sex"].nunique() == 2
        assert summary["injury_type"].nunique() >= 4


class TestCaching:
    """The cache has to actually write. It failed silently once already,
    because pandas needs a separate engine for parquet and the error was
    being swallowed."""

    def test_cache_round_trips(self, tmp_path, monkeypatch) -> None:
        from app.config import settings
        from app.sim.cohort_gen import _paths, load_or_generate

        monkeypatch.setattr(settings, "cohort_dir", tmp_path)

        first = load_or_generate(200, 5)
        data_path, manifest_path = _paths(5)

        assert data_path.exists(), "cohort cache was not written"
        assert manifest_path.exists(), "cohort manifest was not written"

        second = load_or_generate(200, 5)
        pd.testing.assert_frame_equal(first, second)

    def test_manifest_records_provenance(self, tmp_path, monkeypatch) -> None:
        import json

        from app.config import settings
        from app.sim.cohort_gen import COHORT_VERSION, _paths, load_or_generate

        monkeypatch.setattr(settings, "cohort_dir", tmp_path)
        load_or_generate(200, 5)

        manifest = json.loads(_paths(5)[1].read_text(encoding="utf-8"))
        assert manifest["version"] == COHORT_VERSION
        assert manifest["seed"] == 5
        assert manifest["n_patients"] == 200

    def test_a_different_seed_does_not_reuse_the_cache(
        self, tmp_path, monkeypatch
    ) -> None:
        from app.config import settings
        from app.sim.cohort_gen import load_or_generate

        monkeypatch.setattr(settings, "cohort_dir", tmp_path)

        assert not load_or_generate(200, 5).equals(load_or_generate(200, 6))


class TestSummaryFeatures:
    def test_shape_features_are_finite(self, summary: pd.DataFrame) -> None:
        """These are M12's clustering inputs."""
        for column in (
            "initial_slope",
            "final_ratio",
            "time_to_80pct",
            "plateau_index",
            "variability",
        ):
            assert np.all(np.isfinite(summary[column])), f"{column} has non finite values"

    def test_adherence_rate_is_a_proportion(self, summary: pd.DataFrame) -> None:
        assert summary["adherence_rate"].between(0, 1).all()

    def test_completed_never_exceeds_prescribed(self, summary: pd.DataFrame) -> None:
        assert (summary["sessions_completed"] <= summary["sessions_prescribed"]).all()

    def test_one_row_per_patient(self, summary: pd.DataFrame) -> None:
        assert summary["patient_id"].is_unique
