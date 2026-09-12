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
from app.models import Calibration, Goal, Patient, Rep, Session

DEMO_PATIENT_ID = "demo"

# A goal set just below the unaffected side. Recovering to the other hand is
# the honest target, and leaving a little headroom keeps it unreached so the
# forecast has somewhere to go.
GOAL_FRACTION = 0.9

# How many of the most recent completed sessions get real Rep rows. See the
# note in _seed_reps: enough that the first session someone opens has its
# repetition charts filled, few enough that startup stays quick.
DETAILED_SESSIONS = 3


def _interior_miss_rate(cohort: pd.DataFrame) -> pd.Series:
    """Fraction of each patient's missed sessions that fall mid programme.

    Adherence rate alone does not say where the gaps are, and the difference
    matters. A patient who trained perfectly and then stopped has the same
    rate as one who missed the odd session throughout, but only the second
    tells a story worth putting on a dashboard: the first, once the trailing
    misses are trimmed, is a flawless run with an empty adherence heatmap.
    """
    completed = cohort["completed"].astype(bool)
    order = cohort.sort_values(["patient_id", "session_index"])

    def rate(group: pd.DataFrame) -> float:
        flags = completed.loc[group.index]
        if bool(flags.all()):
            return 0.0
        last_completed = flags.to_numpy().nonzero()[0]
        if last_completed.size == 0:
            return 0.0
        interior = flags.to_numpy()[: last_completed[-1] + 1]
        return float((~interior).sum()) / float((~flags.to_numpy()).sum())

    return order.groupby("patient_id", sort=False).apply(rate, include_groups=False)


def _choose_patient(summary: pd.DataFrame, cohort: pd.DataFrame) -> pd.Series:
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

    # Gaps spread through the programme rather than bunched at the end. The
    # trailing ones get trimmed, so a patient whose only misses are trailing
    # arrives here looking imperfect and lands in the database perfect.
    interior = (
        scored["patient_id"].map(_interior_miss_rate(cohort)).fillna(0.0).astype(float)
    )

    # Real improvement, so the forecast rises.
    gain = ((scored["final_kg"] - scored["baseline_kg"]) / scored["baseline_kg"]).clip(0, 2)

    # Still short of the unaffected side, so a goal remains outstanding.
    headroom = (
        (scored["unaffected_kg"] * GOAL_FRACTION - scored["final_kg"])
        / scored["unaffected_kg"]
    ).clip(-1, 1)

    scored["demo_score"] = length + adherence + interior * 1.5 + gain + headroom * 2.0
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
        chosen = _choose_patient(summary, cohort)
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

        completed = _seed_sessions(db, rows, calibration.id)
        db.commit()

        # Needs the ids the commit above assigned.
        for session in completed:
            db.refresh(session)
        _seed_reps(db, completed[-DETAILED_SESSIONS:], calibration.mvc_reference_rms)
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


def _trim_trailing_misses(rows: pd.DataFrame) -> pd.DataFrame:
    """Drop prescribed sessions after the last completed one.

    Everything downstream anchors on the final row, so a programme ending on a
    run of misses would either push the real history days into the past or put
    a prescribed session in the future. Gaps before the last completed session
    are left exactly as they are.
    """
    completed = rows.index[rows["completed"].astype(bool)]
    if len(completed) == 0:
        return rows
    return rows.loc[: completed[-1]]


def _seed_reps(db: DbSession, sessions: list[Session], mvc_reference_rms: float) -> None:
    """Real repetitions for the most recent few sessions.

    The rest of the history stores summaries alone. That is a deliberate
    tradeoff rather than an oversight: none of the dashboard charts read Rep
    rows, and synthesizing thousands of feature rows would slow every startup
    for something almost nobody scrolls back to.

    The newest sessions are the exception, because the newest session is the
    one most likely to be opened first, and a session summary whose repetition
    charts are all empty is a poor first impression. So the last few are
    generated as actual signal and passed through the same preprocess, feature
    extraction and scoring path a live session uses. Older sessions still show
    the empty state, which stays honest: those repetitions were never recorded.
    """
    from app.ml import rep_quality
    from app.ml.registry import registry
    from app.signal.features import rep_features
    from app.signal.filters import preprocess
    from app.sim.signal_gen import RepSpec, SessionProtocol, SyntheticEmgGenerator

    fs = settings.sample_rate

    # A fresh clone has no trained artifacts. try_load returns None there, and
    # rep_quality.score falls back to its heuristic, so the reps are still
    # scored rather than the seed failing.
    artifact = registry.try_load("M4")

    for offset, session in enumerate(sessions):
        if session.rep_count is None or session.id is None:
            continue

        # Seeded per session so a reseed reproduces the same repetitions, and
        # so two sessions do not come out identical.
        generator = SyntheticEmgGenerator(
            sample_rate=fs,
            seed=settings.cohort_seed + offset + 1,
        )
        target = float(session.mean_mvc or 55.0) / 100.0
        generated = generator.build_session(
            SessionProtocol(
                reps=int(session.rep_count),
                rep=RepSpec(target_mvc=float(np.clip(target, 0.2, 0.95))),
            )
        )
        result = preprocess(generated.samples, fs)

        for truth in generated.reps:
            start_idx = int(truth.start_s * fs)
            peak_idx = int(truth.peak_s * fs)
            end_idx = min(int(truth.end_s * fs), result.envelope.size)
            if start_idx >= end_idx:
                continue

            features = rep_features(
                result.envelope,
                result.filtered,
                fs,
                start_idx=start_idx,
                peak_idx=peak_idx,
                end_idx=end_idx,
                mvc_reference=mvc_reference_rms,
            )
            quality = rep_quality.score(features, artifact)

            db.add(
                Rep(
                    session_id=session.id,
                    index=truth.index,
                    start_s=truth.start_s,
                    peak_s=truth.peak_s,
                    end_s=truth.end_s,
                    quality_point=quality.score.point,
                    quality_lower=quality.score.lower,
                    quality_upper=quality.score.upper,
                    quality_top_factor=quality.top_factor,
                    quality_feedback=quality.feedback,
                    **{key: float(value) for key, value in features.items()},
                )
            )


def _seed_sessions(
    db: DbSession, rows: pd.DataFrame, calibration_id: int | None
) -> list[Session]:
    """One Session row per prescribed session, ending near today.

    Returns the completed sessions, oldest first, so the caller can attach
    repetitions to the most recent few.

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

    The anchor is the last *completed* session, not the last prescribed one.
    Those differ whenever a programme ends on a run of misses, and anchoring on
    the prescribed date then puts the most recent real session several days
    back. The app opens on a patient who appears to have lapsed, M13 reports a
    raised dropout risk, and the first thing anyone reads is a nudge about
    losing the habit. Gaps earlier in the history are kept exactly as the
    cohort generated them, because those are the ones worth showing. Prescribed
    sessions after the last completed one are dropped rather than shifted, as a
    session dated tomorrow is not something the cohort meant to express.
    """
    rows = _trim_trailing_misses(rows)
    previous_date: pd.Timestamp | None = None
    completed_sessions: list[Session] = []

    # Shift so the last completed session falls yesterday.
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

            # M4 scores a repetition on how steady the hold was and how clean
            # the signal reading it was, so a session level mean can be derived
            # from the two the cohort already carries rather than invented. The
            # steadiness term dominates, which is what M4 does with a real rep.
            steadiness = float(np.clip(1.0 - float(row["hold_cv"]) * 2.5, 0.0, 1.0))
            cleanliness = float(np.clip(float(row["sqi_mean"]) / 100.0, 0.0, 1.0))
            session.mean_rep_quality = round(
                (steadiness * 0.7 + cleanliness * 0.3) * 100.0, 1
            )

            # Impulse is effort integrated over time: mean percent MVC across
            # the reps, times how long they lasted.
            session.total_impulse = round(
                float(row["mean_mvc"]) * session.duration_s / 100.0, 1
            )

            # fatigue_r_squared, fatigue_p_value, anomaly_score and
            # anomaly_direction are deliberately left null. The cohort carries
            # a fatigue slope but not the fit behind it, and no anomaly score
            # at all, so there is nothing to derive them from that would not be
            # a number made up to fill a column. The charts show their empty
            # state instead, which is the honest reading: those quantities were
            # never computed for these sessions.

            previous_date = session_date
            completed_sessions.append(session)

        db.add(session)

    return completed_sessions


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
