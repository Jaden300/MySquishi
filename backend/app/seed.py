"""The demo account.

The app should look lived in on first click, not like an empty shell that
needs twenty minutes of use before any chart has something to show. So one
cohort patient is promoted into real rows: a patient, a calibration, and one
session per prescribed session in their programme.

The patient is chosen rather than picked at random. A good demo needs a
history long enough for the forecast to be meaningful, adherence gaps so the
heatmap and M13 have something real to describe, and a goal not yet reached
so time to goal has an actual answer. A perfectly adherent patient who has
already finished makes every longitudinal chart boring.

Everything seeded here carries is_synthetic, which is what makes the badge
appear in the UI. See the ethics requirement in docs/ML.md.

Run standalone with:
    .venv/bin/python -m app.seed
"""

from __future__ import annotations

from datetime import datetime, time, timezone

import numpy as np
import pandas as pd
from sqlmodel import Session as DbSession
from sqlmodel import select

from app.config import settings
from app.db import create_db_and_tables, get_engine
from app.ml import force
from app.models import Calibration, Goal, Patient, Session

DEMO_PATIENT_ID = "demo"

# A goal set just below the unaffected side. Recovering to the other hand is
# the honest target, and leaving a little headroom keeps it unreached so the
# forecast has somewhere to go.
GOAL_FRACTION = 0.9

# The calibration reference, as a fraction of baseline strength. Stands in for
# the maximum voluntary contraction trial the patient would otherwise run.
MVC_RMS_PER_KG = 0.006


def _choose_patient(summary: pd.DataFrame) -> pd.Series:
    """Pick the cohort patient that makes the best demonstration.

    Scored rather than filtered, so this always returns someone even if the
    cohort seed changes and no patient meets every preference.
    """
    scored = summary.copy()

    # A long history, but not so long the trend chart turns into a smear.
    length = 1.0 - (scored["sessions_completed"] - 30).abs() / 30.0

    # Imperfect adherence, so the heatmap has gaps and M13 has signal. Around
    # 85 percent is realistic and still encouraging.
    adherence = 1.0 - (scored["adherence_rate"] - 0.85).abs() * 3.0

    # Real improvement, so the forecast rises.
    gain = ((scored["final_kg"] - scored["baseline_kg"]) / scored["baseline_kg"]).clip(0, 2)

    # Still short of the unaffected side, so a goal remains outstanding.
    headroom = (
        (scored["unaffected_kg"] * GOAL_FRACTION - scored["final_kg"])
        / scored["unaffected_kg"]
    ).clip(-1, 1)

    scored["demo_score"] = length + adherence + gain + headroom * 2.0
    scored = scored.sort_values("demo_score", ascending=False)

    return scored.iloc[0]


def _as_datetime(value: object) -> datetime:
    stamp = pd.Timestamp(value).to_pydatetime()
    if stamp.tzinfo is None:
        stamp = datetime.combine(stamp.date(), time(9, 0), tzinfo=timezone.utc)
    return stamp


def seed_demo(*, force_reseed: bool = False) -> str | None:
    """Create the demo patient if it is not already there.

    Returns the patient id when seeding happened, None when it was skipped.
    """
    from app.sim.cohort_gen import load_or_generate, patient_summary

    create_db_and_tables()
    engine = get_engine()

    with DbSession(engine) as db:
        existing = db.get(Patient, DEMO_PATIENT_ID)
        if existing is not None and not force_reseed:
            return None
        if existing is not None:
            _clear_demo(db)

        cohort = load_or_generate()
        summary = patient_summary(cohort)
        chosen = _choose_patient(summary)
        source_id = str(chosen["patient_id"])

        rows = cohort[cohort["patient_id"] == source_id].sort_values("session_index")

        patient = Patient(
            id=DEMO_PATIENT_ID,
            display_name="Demo patient",
            age_band=str(chosen["age_band"]),
            sex=str(chosen["sex"]),
            injury_type=str(chosen["injury_type"]),
            dominant_hand="right",
            unaffected_kg=float(chosen["unaffected_kg"]),
            goal_kg=round(float(chosen["unaffected_kg"]) * GOAL_FRACTION, 1),
            archetype=str(chosen["archetype"]),
            consent_accepted=True,
            is_synthetic=True,
            source_cohort_id=source_id,
        )
        db.add(patient)

        calibration = _seed_calibration(db, float(chosen["baseline_kg"]))
        db.add(
            Goal(
                patient_id=DEMO_PATIENT_ID,
                target_kg=patient.goal_kg,  # type: ignore[arg-type]
            )
        )
        db.commit()
        db.refresh(calibration)

        _seed_sessions(db, rows, calibration.id)
        db.commit()

    return DEMO_PATIENT_ID


def _clear_demo(db: DbSession) -> None:
    """Remove a previous demo patient so a reseed is clean."""
    from sqlmodel import delete

    from app.models import InsightCache, Rep

    session_ids = db.exec(
        select(Session.id).where(Session.patient_id == DEMO_PATIENT_ID)
    ).all()
    if session_ids:
        db.exec(delete(Rep).where(Rep.session_id.in_(session_ids)))  # type: ignore[union-attr,arg-type]

    for table in (Session, Calibration, Goal, InsightCache):
        db.exec(delete(table).where(table.patient_id == DEMO_PATIENT_ID))  # type: ignore[arg-type]
    db.exec(delete(Patient).where(Patient.id == DEMO_PATIENT_ID))  # type: ignore[arg-type]
    db.commit()


def _seed_calibration(db: DbSession, baseline_kg: float) -> Calibration:
    """A plausible calibration, fitted the same way a real one would be.

    The calibration holds are generated as actual synthetic signal and passed
    through the real feature extractor, rather than being written by hand.
    Two reasons. It exercises the same code path a calibrated user does, and
    the features land on the scale the model expects: M3's ridge penalty is
    calibrated for features computed from signal, so hand written values a
    couple of orders of magnitude smaller would be shrunk to nothing and
    produce a fit that looks broken.
    """
    from app.signal.features import window_features
    from app.signal.filters import preprocess
    from app.sim.signal_gen import RepSpec, SessionProtocol, SyntheticEmgGenerator

    fs = settings.sample_rate
    generator = SyntheticEmgGenerator(sample_rate=fs, seed=settings.cohort_seed)

    fractions = np.linspace(0.3, 1.0, 6)
    feature_rows = []
    rms_values = []

    for fraction in fractions:
        # One held contraction at this effort level. The ground truth
        # boundaries say exactly where the hold is, so the features describe
        # the contraction rather than the rest either side of it.
        generated = generator.build_session(
            SessionProtocol(
                reps=1,
                lead_in_s=0.5,
                rep=RepSpec(target_mvc=float(fraction), hold_s=3.0),
            )
        )
        truth = generated.reps[0]
        result = preprocess(generated.samples, fs)
        features = window_features(
            result.filtered[int(truth.start_s * fs) : int(truth.end_s * fs)], fs
        )
        feature_rows.append(features)
        rms_values.append(features["rms"])

    # The reference is the strongest hold, which is what a maximum voluntary
    # contraction trial measures.
    mvc_reference_rms = float(max(rms_values))
    reference_kg = baseline_kg * fractions

    model = force.fit(
        feature_rows,
        reference_kg,
        mvc_reference_rms=mvc_reference_rms,
    )

    calibration = Calibration(
        patient_id=DEMO_PATIENT_ID,
        mvc_reference_rms=mvc_reference_rms,
        reference_kg=round(baseline_kg, 2),
        force_model_json=model.to_json(),
        r_squared=model.r_squared,
        n_points=model.n_points,
        is_active=True,
        is_synthetic=True,
    )
    db.add(calibration)
    return calibration


def _seed_sessions(db: DbSession, rows: pd.DataFrame, calibration_id: int | None) -> None:
    """One Session row per prescribed session, ending near today.

    The cohort carries its own absolute dates, which sit wherever the
    generator put them. Used as they are, the seeded history would end months
    or years before any session recorded now, and every measure computed over
    "time since the programme started" would be wrong: the demo patient would
    look like they had been training for eighty weeks with a long silence at
    the end. So the whole history is shifted to finish yesterday, and a live
    session today continues it rather than appearing after a gap.

    Missed sessions are written too, with their summary columns left null.
    That is what gives the adherence heatmap its gaps and M13 its signal: a
    missed session is data, not an absence of data.

    No Rep rows are created. None of the dashboard charts read them, and
    synthesizing thousands of feature rows would slow startup for nothing. The
    rep level charts show their empty state for historical sessions, which is
    honest: those repetitions were never recorded.
    """
    previous_date: pd.Timestamp | None = None

    # Shift so the last prescribed session falls yesterday.
    last_date = pd.Timestamp(rows["session_date"].iloc[-1])
    offset = pd.Timestamp(datetime.now(timezone.utc).date()) - last_date - pd.Timedelta(days=1)

    for _, row in rows.iterrows():
        session_date = pd.Timestamp(row["session_date"]) + offset
        started = _as_datetime(session_date)
        completed = bool(row["completed"])

        session = Session(
            patient_id=DEMO_PATIENT_ID,
            calibration_id=calibration_id,
            started_at=started,
            source_id="simulated",
            is_live=False,
            is_synthetic=True,
        )

        if completed:
            gap = (
                float((session_date - previous_date).days)
                if previous_date is not None
                else 0.0
            )

            session.ended_at = started
            session.rep_count = int(row["rep_count"])
            session.mean_mvc = float(row["mean_mvc"])
            session.peak_mvc = float(row["peak_mvc"])
            session.hold_cv_mean = float(row["hold_cv"])
            session.sqi_mean = float(row["sqi_mean"])
            session.fatigue_slope = float(row["fatigue_slope"])
            session.strength_kg = float(row["strength_kg"])
            session.borg = int(row["borg"])
            session.adherence_gap_days = gap
            session.duration_s = float(row["rep_count"]) * 10.5

            previous_date = session_date

        db.add(session)


def main() -> None:
    settings.ensure_dirs()
    result = seed_demo(force_reseed=True)
    if result is None:
        print("Demo patient already present.")
        return

    engine = get_engine()
    with DbSession(engine) as db:
        patient = db.get(Patient, DEMO_PATIENT_ID)
        sessions = db.exec(
            select(Session).where(Session.patient_id == DEMO_PATIENT_ID)
        ).all()
        done = [s for s in sessions if s.rep_count is not None]

    print(f"Seeded '{result}' from cohort patient {patient.source_cohort_id}")
    print(f"  archetype: {patient.archetype}")
    print(f"  sessions: {len(done)} completed of {len(sessions)} prescribed")
    if done:
        print(
            f"  strength: {done[0].strength_kg:.1f} kg to "
            f"{done[-1].strength_kg:.1f} kg, goal {patient.goal_kg:.1f} kg"
        )


if __name__ == "__main__":
    main()
