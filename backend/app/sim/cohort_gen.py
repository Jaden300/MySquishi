"""Synthetic patient cohort.

Two to four hundred simulated patients, each with six to fourteen weeks of
sessions. This is what M12 (archetypes), M13 (adherence risk) and M14
(percentile norms) train on, and what M6 and M7 use as their reference
population. It also seeds the demo account so the dashboard is never empty
on first click.

The cohort is synthetic and is labeled as synthetic in the UI. See the
ethics requirement in docs/ML.md.

Four recovery archetypes, drawn from the shapes real rehabilitation
trajectories take:

- fast responder: quick early gains, saturating early at a good ceiling
- steady climber: near linear improvement throughout
- late bloomer: slow start, inflecting upward partway through
- plateaued: early gains that stall well short of the goal
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from app.config import settings

COHORT_VERSION = "v1"

ARCHETYPES = ("fast_responder", "steady_climber", "late_bloomer", "plateaued")

ARCHETYPE_LABELS = {
    "fast_responder": "Fast responder",
    "steady_climber": "Steady climber",
    "late_bloomer": "Late bloomer",
    "plateaued": "Plateaued",
}

AGE_BANDS = ("18-34", "35-49", "50-64", "65-79", "80+")
SEXES = ("female", "male")
INJURY_TYPES = (
    "distal radius fracture",
    "post stroke hemiparesis",
    "carpal tunnel release",
    "flexor tendon repair",
    "age related sarcopenia",
)

# Baseline grip strength in kg by age band and sex. Loosely informed by
# published norms and used only to give the synthetic cohort a plausible
# shape. Documented as approximate wherever it surfaces.
_BASELINE_KG = {
    ("female", "18-34"): 30.0,
    ("female", "35-49"): 28.0,
    ("female", "50-64"): 24.0,
    ("female", "65-79"): 19.0,
    ("female", "80+"): 14.0,
    ("male", "18-34"): 50.0,
    ("male", "35-49"): 47.0,
    ("male", "50-64"): 40.0,
    ("male", "65-79"): 32.0,
    ("male", "80+"): 24.0,
}

# How far an injury knocks strength down at the start of rehabilitation.
_INJURY_DEFICIT = {
    "distal radius fracture": 0.45,
    "post stroke hemiparesis": 0.30,
    "carpal tunnel release": 0.60,
    "flexor tendon repair": 0.40,
    "age related sarcopenia": 0.70,
}

_COHORT_COLUMNS = (
    "patient_id",
    "archetype",
    "age_band",
    "sex",
    "injury_type",
    "week",
    "session_index",
    "session_date",
    "prescribed",
    "completed",
    "mean_mvc",
    "peak_mvc",
    "rep_count",
    "fatigue_slope",
    "hold_cv",
    "sqi_mean",
    "adherence_gap_days",
    "borg",
    "strength_kg",
    "unaffected_kg",
)


@dataclass(frozen=True)
class CohortManifest:
    """What produced a cached cohort, so it can be invalidated correctly."""

    version: str
    seed: int
    n_patients: int
    n_sessions: int

    def to_dict(self) -> dict[str, object]:
        return {
            "version": self.version,
            "seed": self.seed,
            "n_patients": self.n_patients,
            "n_sessions": self.n_sessions,
        }


def _trajectory(
    archetype: str,
    weeks: np.ndarray,
    ceiling: float,
    start: float,
    rng: np.random.Generator,
) -> np.ndarray:
    """Strength over time for one archetype, as a fraction of unaffected."""
    span = ceiling - start
    total_weeks = float(weeks.max()) if weeks.size else 1.0
    t = weeks / max(total_weeks, 1e-9)

    if archetype == "fast_responder":
        # Sharp exponential approach to a high ceiling.
        shape = 1.0 - np.exp(-3.6 * t)
    elif archetype == "steady_climber":
        # Close to linear, with a gentle bend.
        shape = 0.82 * t + 0.18 * (1.0 - np.exp(-2.0 * t))
    elif archetype == "late_bloomer":
        # Logistic, inflecting around two thirds of the way through.
        shape = 1.0 / (1.0 + np.exp(-9.0 * (t - 0.62)))
        shape = (shape - shape[0]) / max(shape[-1] - shape[0], 1e-9)
    elif archetype == "plateaued":
        # Early gains that stall well short.
        shape = 0.62 * (1.0 - np.exp(-5.5 * t))
    else:
        raise ValueError(f"unknown archetype '{archetype}'")

    return start + span * shape


def _adherence_pattern(
    n_sessions: int,
    archetype: str,
    rng: np.random.Generator,
) -> np.ndarray:
    """Which prescribed sessions actually happened.

    Real adherence is not independent coin flips: it comes in runs, with gaps
    and returns, and some patients drop out entirely.
    """
    base = {
        "fast_responder": 0.94,
        "steady_climber": 0.90,
        "late_bloomer": 0.84,
        "plateaued": 0.78,
    }[archetype]

    # Individual variation on top of the archetype tendency. This is the
    # per session hit rate before gaps and dropout are layered on, so it sits
    # high: the structured absences below are what pull the realized rate
    # down to something clinically plausible.
    rate = float(np.clip(rng.normal(base, 0.07), 0.55, 0.99))
    completed = rng.random(n_sessions) < rate

    # Gaps: illness, holidays, losing motivation.
    for _ in range(rng.poisson(0.9)):
        if n_sessions < 4:
            break
        start = int(rng.integers(0, n_sessions - 2))
        length = int(rng.integers(2, max(3, n_sessions // 5)))
        completed[start : start + length] = False

    # Some patients disengage and never come back. Kept in the minority so
    # the cohort is not dominated by dropouts, but common enough that M13 has
    # a real signal to learn.
    if rng.random() < 0.14 and n_sessions > 8:
        dropout = int(rng.integers(int(n_sessions * 0.6), n_sessions))
        completed[dropout:] = False

    # The first session always happens, otherwise there is no patient.
    completed[0] = True
    return completed


def generate_cohort(
    n_patients: int | None = None,
    seed: int | None = None,
) -> pd.DataFrame:
    """Generate the cohort at session grain.

    One row per prescribed session, whether or not it was completed, so
    adherence modelling has the misses as well as the hits.
    """
    n_patients = n_patients or settings.cohort_size
    seed = settings.cohort_seed if seed is None else seed

    if not 200 <= n_patients <= 400:
        raise ValueError(f"cohort size should be 200 to 400, got {n_patients}")

    rng = np.random.default_rng(seed)
    rows: list[dict[str, object]] = []
    start_date = date(2025, 1, 6)

    for patient_num in range(n_patients):
        patient_id = f"synth-{patient_num:04d}"

        # Even archetype representation, then shuffled by the draw order.
        archetype = ARCHETYPES[patient_num % len(ARCHETYPES)]

        age_band = str(rng.choice(AGE_BANDS, p=[0.18, 0.22, 0.26, 0.24, 0.10]))
        sex = str(rng.choice(SEXES))
        injury = str(rng.choice(INJURY_TYPES))

        unaffected = _BASELINE_KG[(sex, age_band)] * float(rng.normal(1.0, 0.11))
        unaffected = max(unaffected, 8.0)

        deficit = _INJURY_DEFICIT[injury] * float(rng.normal(1.0, 0.12))
        start_fraction = float(np.clip(deficit, 0.15, 0.85))

        # Where this patient tops out, by archetype.
        ceiling_fraction = {
            "fast_responder": rng.uniform(0.88, 1.02),
            "steady_climber": rng.uniform(0.80, 0.95),
            "late_bloomer": rng.uniform(0.78, 0.94),
            "plateaued": rng.uniform(0.55, 0.72),
        }[archetype]
        ceiling_fraction = max(ceiling_fraction, start_fraction + 0.05)

        weeks_total = int(rng.integers(6, 15))
        per_week = int(rng.integers(2, 5))
        n_sessions = weeks_total * per_week

        session_weeks = np.repeat(np.arange(weeks_total), per_week).astype(float)
        session_weeks += np.tile(np.arange(per_week) / per_week, weeks_total)

        curve = _trajectory(archetype, session_weeks, ceiling_fraction, start_fraction, rng)
        completed = _adherence_pattern(n_sessions, archetype, rng)

        # An occasional genuine setback: re-injury or illness, persisting for
        # several sessions rather than a single bad day.
        if rng.random() < 0.22 and n_sessions > 8:
            at = int(rng.integers(3, n_sessions - 4))
            depth = float(rng.uniform(0.08, 0.2))
            length = int(rng.integers(3, 8))
            curve[at : at + length] -= depth
            curve = np.maximum(curve, start_fraction * 0.6)

        # Individual bias in how hard sessions feel, held constant per
        # patient. Real people differ in how they report exertion, but the
        # bias stays modest so measured effort remains the dominant term:
        # M7 models the relationship and surfaces the residual, which needs
        # the relationship to exist in the first place.
        borg_bias = float(rng.normal(0.0, 0.7))
        # Baseline signal quality: electrode technique, skin, body habitus.
        sqi_bias = float(np.clip(rng.normal(78.0, 9.0), 45.0, 96.0))

        last_completed_day: int | None = None

        for index in range(n_sessions):
            day = int(session_weeks[index] * 7)
            session_date = start_date + timedelta(days=day)
            was_completed = bool(completed[index])

            gap = 0 if last_completed_day is None else day - last_completed_day

            if not was_completed:
                rows.append(
                    {
                        "patient_id": patient_id,
                        "archetype": archetype,
                        "age_band": age_band,
                        "sex": sex,
                        "injury_type": injury,
                        "week": int(session_weeks[index]),
                        "session_index": index,
                        "session_date": session_date.isoformat(),
                        "prescribed": True,
                        "completed": False,
                        "mean_mvc": np.nan,
                        "peak_mvc": np.nan,
                        "rep_count": 0,
                        "fatigue_slope": np.nan,
                        "hold_cv": np.nan,
                        "sqi_mean": np.nan,
                        "adherence_gap_days": gap,
                        "borg": np.nan,
                        "strength_kg": np.nan,
                        "unaffected_kg": round(unaffected, 2),
                    }
                )
                continue

            fraction = float(np.clip(curve[index] + rng.normal(0, 0.022), 0.05, 1.15))
            strength = fraction * unaffected

            # Effort as a percentage of the patient's own current maximum.
            mean_mvc = float(np.clip(rng.normal(58.0, 7.0), 25.0, 88.0))
            peak_mvc = float(np.clip(mean_mvc + rng.normal(18.0, 5.0), mean_mvc, 100.0))
            rep_count = int(np.clip(rng.normal(10, 1.6), 5, 15))

            # Fatigue is steeper when a patient pushes harder and when they
            # are further from recovered.
            fatigue = float(
                rng.normal(-2.4 - (mean_mvc - 58.0) * 0.03 + fraction * 1.1, 0.7)
            )
            hold_cv = float(np.clip(rng.normal(0.13 - fraction * 0.05, 0.03), 0.02, 0.4))
            sqi = float(np.clip(rng.normal(sqi_bias, 6.0), 20.0, 99.0))

            # Perceived exertion tracks measured effort and fatigue, plus the
            # individual's own bias. M7 exists to model this relationship and
            # flag the residual.
            borg = (
                0.9
                + 0.082 * mean_mvc
                + 0.30 * (-fatigue)
                + 1.5 * (1.0 - fraction)
                + borg_bias
                + float(rng.normal(0, 0.4))
            )
            borg_value = int(np.clip(round(borg), 0, 10))

            rows.append(
                {
                    "patient_id": patient_id,
                    "archetype": archetype,
                    "age_band": age_band,
                    "sex": sex,
                    "injury_type": injury,
                    "week": int(session_weeks[index]),
                    "session_index": index,
                    "session_date": session_date.isoformat(),
                    "prescribed": True,
                    "completed": True,
                    "mean_mvc": round(mean_mvc, 2),
                    "peak_mvc": round(peak_mvc, 2),
                    "rep_count": rep_count,
                    "fatigue_slope": round(fatigue, 3),
                    "hold_cv": round(hold_cv, 4),
                    "sqi_mean": round(sqi, 1),
                    "adherence_gap_days": gap,
                    "borg": borg_value,
                    "strength_kg": round(strength, 2),
                    "unaffected_kg": round(unaffected, 2),
                }
            )
            last_completed_day = day

    frame = pd.DataFrame(rows, columns=list(_COHORT_COLUMNS))
    return frame


def patient_summary(cohort: pd.DataFrame) -> pd.DataFrame:
    """Collapse the cohort to one row per patient.

    This is what M12 clusters on and what the archetype scatter renders, so
    it stays queryable without loading every session.
    """
    done = cohort[cohort["completed"]]
    rows: list[dict[str, object]] = []

    # Prescribed programme length and session count per patient. Taken from
    # the full frame rather than the completed rows, so a patient who dropped
    # out is not mistaken for one on a shorter programme.
    prescribed_counts = cohort.groupby("patient_id")["session_index"].count()
    programme_weeks = cohort.groupby("patient_id")["week"].max() + 1

    for patient_id, group in done.groupby("patient_id", sort=True):
        group = group.sort_values("session_index")
        strengths = group["strength_kg"].to_numpy(dtype=float)
        if strengths.size < 3:
            continue

        prescribed = int(prescribed_counts.loc[patient_id])
        completed_count = int(len(group))

        first, last = float(strengths[0]), float(strengths[-1])
        peak = float(strengths.max())

        # Trajectory shape features. These are M12's inputs, and they are
        # deliberately scale free so clustering keys on shape rather than on
        # how strong the patient happens to be.
        initial_slope = (
            float(np.polyfit(np.arange(min(6, strengths.size)), strengths[:6], 1)[0])
            if strengths.size >= 3
            else 0.0
        )
        final_ratio = last / first if first > 0 else 1.0

        # How far through the series the patient reached 80 percent of their
        # total gain: early for a fast responder, late for a late bloomer.
        gain = last - first
        if abs(gain) > 1e-6:
            progress = (strengths - first) / gain
            reached = np.where(progress >= 0.8)[0]
            time_to_80 = float(reached[0] / strengths.size) if reached.size else 1.0
        else:
            time_to_80 = 1.0

        plateau_index = 1.0 - (last / peak) if peak > 0 else 0.0
        variability = float(np.std(np.diff(strengths))) if strengths.size > 2 else 0.0

        rows.append(
            {
                "patient_id": patient_id,
                "archetype": group["archetype"].iloc[0],
                "age_band": group["age_band"].iloc[0],
                "sex": group["sex"].iloc[0],
                "injury_type": group["injury_type"].iloc[0],
                "weeks": int(programme_weeks.loc[patient_id]),
                "sessions_prescribed": prescribed,
                "sessions_completed": completed_count,
                "adherence_rate": completed_count / prescribed if prescribed else 0.0,
                "baseline_kg": round(first, 2),
                "final_kg": round(last, 2),
                "peak_kg": round(peak, 2),
                "unaffected_kg": float(group["unaffected_kg"].iloc[0]),
                "initial_slope": round(initial_slope, 4),
                "final_ratio": round(final_ratio, 4),
                "time_to_80pct": round(time_to_80, 4),
                "plateau_index": round(plateau_index, 4),
                "variability": round(variability, 4),
                "mean_borg": round(float(group["borg"].mean()), 2),
                "mean_sqi": round(float(group["sqi_mean"].mean()), 1),
            }
        )

    return pd.DataFrame(rows)


def _paths(seed: int) -> tuple[Path, Path]:
    # Gzipped CSV rather than parquet: pandas needs pyarrow or fastparquet for
    # parquet, which is a large dependency to carry for one cache file. The
    # cohort builds in well under a second, so the cache exists to give the
    # trainer and the seed script a stable artifact to point at, not to save
    # time. CSV keeps that without the extra wheel.
    stem = f"cohort_{COHORT_VERSION}_seed{seed}"
    return (
        settings.cohort_dir / f"{stem}.csv.gz",
        settings.cohort_dir / f"{stem}.manifest.json",
    )


def load_or_generate(
    n_patients: int | None = None,
    seed: int | None = None,
    *,
    force: bool = False,
) -> pd.DataFrame:
    """Return the cohort, generating and caching it when needed.

    The cache is keyed by generator version and seed, so bumping either one
    produces a fresh cohort rather than silently reusing a stale one.
    """
    n_patients = n_patients or settings.cohort_size
    seed = settings.cohort_seed if seed is None else seed

    settings.ensure_dirs()
    data_path, manifest_path = _paths(seed)

    if not force and data_path.exists() and manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if (
            manifest.get("version") == COHORT_VERSION
            and manifest.get("n_patients") == n_patients
        ):
            return pd.read_csv(data_path, dtype={"patient_id": str})

    cohort = generate_cohort(n_patients, seed)

    try:
        cohort.to_csv(data_path, index=False)
        manifest = CohortManifest(
            version=COHORT_VERSION,
            seed=seed,
            n_patients=n_patients,
            n_sessions=int(len(cohort)),
        )
        manifest_path.write_text(json.dumps(manifest.to_dict(), indent=2), encoding="utf-8")
    except OSError:
        # Caching is an optimization: an unwritable data directory must not
        # break generation, which takes well under a second anyway.
        pass

    return cohort
