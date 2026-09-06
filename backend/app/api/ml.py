"""Model endpoints.

Every route returns the same PredictionOut envelope, so the frontend renders
them uniformly and every surfaced number arrives with its explanation, its
provenance, and a flag saying whether a trained model or a fallback produced
it.
"""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session as DbSession
from sqlmodel import select

from app.clinical_gate import NON_GRIP_NOTE, is_grip
from app.db import get_session
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
from app.ml.explain import Explanation
from app.ml.registry import registry
from app.models import InsightCache, Patient, Session
from app.schemas import ExplanationOut, ModelRecordOut, PredictionOut

router = APIRouter(prefix="/api/ml", tags=["ml"])


def _patient(db: DbSession, patient_id: str) -> Patient:
    patient = db.get(Patient, patient_id)
    if patient is None:
        raise HTTPException(status_code=404, detail=f"No patient '{patient_id}'.")
    return patient


def _completed(db: DbSession, patient_id: str) -> list[Session]:
    """A patient's completed sessions, oldest first."""
    return list(
        db.exec(
            select(Session)
            .where(Session.patient_id == patient_id)
            .where(Session.rep_count.is_not(None))  # type: ignore[union-attr]
            .order_by(Session.started_at)  # type: ignore[arg-type]
        ).all()
    )


def _wrap(
    model_id: str,
    value: object,
    explanation: Explanation,
    *,
    degraded: bool,
    is_synthetic: bool = False,
) -> PredictionOut:
    """Build the envelope, including when the artifact was trained."""
    record = next(
        (r for r in registry.records() if r.model_id == model_id),
        None,
    )
    return PredictionOut(
        model_id=model_id,
        value=value,
        explanation=ExplanationOut.from_domain(explanation),
        is_synthetic=is_synthetic,
        trained_at=record.trained_at if record else None,
        degraded=degraded,
    )


def _session_features(session: Session) -> dict[str, float]:
    return {
        "mean_mvc": session.mean_mvc or 0.0,
        "peak_mvc": session.peak_mvc or 0.0,
        "rep_count": float(session.rep_count or 0),
        "fatigue_slope": session.fatigue_slope or 0.0,
        "hold_cv": session.hold_cv_mean or 0.0,
        "adherence_gap_days": session.adherence_gap_days or 0.0,
        "sqi_mean": session.sqi_mean or 0.0,
    }


@router.get("/models", response_model=list[ModelRecordOut])
def list_models() -> list[ModelRecordOut]:
    """What is trained and on disk, for the Responsible AI page."""
    return [ModelRecordOut(**vars(record)) for record in registry.records()]


@router.get("/forecast/{patient_id}", response_model=PredictionOut)
def get_forecast(
    patient_id: str,
    db: DbSession = Depends(get_session),
) -> PredictionOut:
    """M9 and M10 together: the fan chart and time to goal are one card."""
    patient = _patient(db, patient_id)
    sessions = _completed(db, patient_id)
    strengths = [s.strength_kg for s in sessions if s.strength_kg is not None]

    # Memoized on patient and completed session count, per docs/ML.md: the
    # cached forecast stays valid until another session lands.
    key = f"{patient_id}:{len(strengths)}"
    cached = db.exec(
        select(InsightCache)
        .where(InsightCache.patient_id == patient_id)
        .where(InsightCache.model_id == "M9")
        .where(InsightCache.key == key)
    ).first()

    if cached:
        payload = json.loads(cached.payload_json)
        return _wrap(
            "M9",
            payload["value"],
            Explanation(**payload["explanation_raw"]),
            # A cache hit is the same answer as a fresh fit, not a degraded
            # one. degraded means a heuristic stood in for a trained model.
            degraded=False,
            is_synthetic=patient.is_synthetic,
        )

    trajectory = forecast.fit_trajectory(strengths)
    value: dict[str, object] = trajectory.to_dict()

    if patient.goal_kg:
        goal = time_to_goal.estimate(trajectory, patient.goal_kg)
        value["time_to_goal"] = goal.to_dict()

    explanation = trajectory.explanation
    assert isinstance(explanation, Explanation)

    if not trajectory.insufficient_data:
        db.add(
            InsightCache(
                patient_id=patient_id,
                model_id="M9",
                key=key,
                payload_json=json.dumps(
                    {
                        "value": value,
                        "explanation_raw": {
                            "summary": explanation.summary,
                            "factors": [],
                            "method": explanation.method,
                        },
                    }
                ),
            )
        )
        db.commit()

    # M9 fits per request and has no artifact, so it is never degraded in the
    # sense the flag means: there is no trained model it is standing in for.
    return _wrap(
        "M9",
        value,
        explanation,
        degraded=False,
        is_synthetic=patient.is_synthetic,
    )


@router.get("/plateau/{patient_id}", response_model=PredictionOut)
def get_plateau(
    patient_id: str,
    db: DbSession = Depends(get_session),
) -> PredictionOut:
    """M11."""
    _patient(db, patient_id)
    strengths = [
        s.strength_kg for s in _completed(db, patient_id) if s.strength_kg is not None
    ]

    result = plateau.detect(strengths)
    return _wrap("M11", result.to_dict(), result.explanation, degraded=False)


@router.get("/archetype/{patient_id}", response_model=PredictionOut)
def get_archetype(
    patient_id: str,
    db: DbSession = Depends(get_session),
) -> PredictionOut:
    """M12, including the cohort scatter coordinates."""
    patient = _patient(db, patient_id)
    strengths = [
        s.strength_kg for s in _completed(db, patient_id) if s.strength_kg is not None
    ]

    artifact = registry.try_load("M12")
    shape = _shape_features(strengths)
    result = archetype.assign(shape, artifact)

    value = result.to_dict()
    if artifact:
        value["cohort"] = artifact["points"]

    return _wrap(
        "M12",
        value,
        result.explanation,
        degraded=artifact is None,
        # The cohort scatter is synthetic wherever it is drawn.
        is_synthetic=True,
    )


def _shape_features(strengths: list[float]) -> dict[str, float]:
    """Trajectory shape, matching what cohort_gen.patient_summary computes."""
    import numpy as np

    values = np.asarray(strengths, dtype=float)
    if values.size < 3:
        return dict.fromkeys(archetype.SHAPE_FEATURES, 0.0)

    first, last, peak = float(values[0]), float(values[-1]), float(values.max())
    window = min(6, values.size)

    gain = last - first
    if abs(gain) > 1e-6:
        progress = (values - first) / gain
        reached = np.where(progress >= 0.8)[0]
        time_to_80 = float(reached[0] / values.size) if reached.size else 1.0
    else:
        time_to_80 = 1.0

    return {
        "initial_slope": float(np.polyfit(np.arange(window), values[:window], 1)[0]),
        "final_ratio": last / first if first > 0 else 1.0,
        "time_to_80pct": time_to_80,
        "plateau_index": 1.0 - (last / peak) if peak > 0 else 0.0,
        "variability": float(np.std(np.diff(values))),
    }


@router.get("/adherence/{patient_id}", response_model=PredictionOut)
def get_adherence(
    patient_id: str,
    db: DbSession = Depends(get_session),
) -> PredictionOut:
    """M13."""
    _patient(db, patient_id)

    all_sessions = list(
        db.exec(
            select(Session)
            .where(Session.patient_id == patient_id)
            .order_by(Session.started_at)  # type: ignore[arg-type]
        ).all()
    )
    completed = [s for s in all_sessions if s.rep_count is not None]

    if not completed:
        raise HTTPException(
            status_code=404, detail="No completed sessions to assess adherence from."
        )

    import numpy as np

    recent = [s.strength_kg for s in completed[-5:] if s.strength_kg is not None]
    trend = (
        float(np.polyfit(np.arange(len(recent)), recent, 1)[0])
        if len(recent) >= 3
        else 0.0
    )

    from datetime import datetime, timezone

    first, last = completed[0].started_at, completed[-1].started_at

    # Days since the last session is measured from now, not read off the row.
    # The stored gap describes the interval before that session, which is a
    # different question and is None for a session recorded live.
    now = datetime.now(timezone.utc)
    last_aware = last if last.tzinfo else last.replace(tzinfo=timezone.utc)
    days_since_last = max(0.0, (now - last_aware).total_seconds() / 86400.0)

    features = {
        "sessions_completed": float(len(completed)),
        "days_since_last": days_since_last,
        "completion_rate": len(completed) / max(1, len(all_sessions)),
        "recent_trend": trend,
        "weeks_elapsed": max(0.0, (last - first).days / 7.0),
    }

    artifact = registry.try_load("M13")
    result = adherence.assess(features, artifact)

    return _wrap("M13", result.to_dict(), result.explanation, degraded=artifact is None)


@router.get("/percentile/{patient_id}", response_model=PredictionOut)
def get_percentile(
    patient_id: str,
    db: DbSession = Depends(get_session),
) -> PredictionOut:
    """M14. Always synthetic: the reference population is generated.

    Grip only. The EWGSOP2 thresholds this places a patient against are
    sarcopenia references validated on hand dynamometry, so the comparison is
    meaningless for a biceps or a calf. Only grip sessions are considered, and
    a patient with none gets a 404 rather than a percentile against the wrong
    reference. See app/clinical_gate.py.
    """
    patient = _patient(db, patient_id)
    sessions = [s for s in _completed(db, patient_id) if is_grip(s.muscle)]
    latest = next(
        (s.strength_kg for s in reversed(sessions) if s.strength_kg is not None), None
    )

    if latest is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "No grip strength estimate to place in context yet. "
                + NON_GRIP_NOTE
            ),
        )

    artifact = registry.try_load("M14")
    result = percentile.assess(
        latest,
        sex=patient.sex or "female",
        age_band=patient.age_band or "50-64",
        artifact=artifact,
    )

    return _wrap(
        "M14",
        result.to_dict(),
        result.explanation,
        degraded=artifact is None,
        is_synthetic=True,
    )


@router.get("/perceived/{patient_id}", response_model=PredictionOut)
def get_perceived(
    patient_id: str,
    db: DbSession = Depends(get_session),
) -> PredictionOut:
    """M7, over every session that carries a Borg rating."""
    _patient(db, patient_id)
    sessions = _completed(db, patient_id)
    artifact = registry.try_load("M7")

    points = []
    for session in sessions:
        if session.borg is None:
            continue
        result = perceived.assess(
            _session_features(session),
            actual_borg=float(session.borg),
            artifact=artifact,
        )
        points.append(
            {
                "session_id": session.id,
                "measured_mvc": session.mean_mvc,
                "predicted_borg": result.predicted_borg.to_dict(),
                "actual_borg": result.actual_borg,
                "residual": result.residual,
                "flag": result.flag,
            }
        )

    notable = [p for p in points if p["flag"] != "as_expected"]
    explanation = Explanation(
        summary=(
            f"{len(notable)} of {len(points)} rated sessions felt notably "
            "different from what they measured."
            if points
            else "Rate a few sessions to compare how they felt against what they measured."
        ),
        method="ridge regression over session measures",
    )

    return _wrap("M7", points, explanation, degraded=artifact is None)


@router.get("/anomalies/{patient_id}", response_model=PredictionOut)
def get_anomalies(
    patient_id: str,
    db: DbSession = Depends(get_session),
) -> PredictionOut:
    """M6 across the patient's history."""
    _patient(db, patient_id)
    sessions = _completed(db, patient_id)
    artifact = registry.try_load("M6")

    results = []
    history: list[dict[str, float]] = []

    for session in sessions:
        features = _session_features(session)
        result = anomaly.assess(features, history=history, artifact=artifact)
        history.append(features)

        results.append(
            {
                "session_id": session.id,
                "started_at": session.started_at.isoformat(),
                "score": result.score.to_dict(),
                "is_anomaly": result.is_anomaly,
                "direction": result.direction,
                "summary": result.explanation.summary,
            }
        )

    flagged = [r for r in results if r["is_anomaly"]]
    standouts = [r for r in flagged if r["direction"] == "positive"]

    explanation = Explanation(
        summary=(
            f"{len(flagged)} of {len(results)} sessions stood out from your "
            f"usual pattern, {len(standouts)} of them in a good way."
            if results
            else "No completed sessions to compare yet."
        ),
        method="isolation forest, explained by leaving one feature out",
    )

    return _wrap("M6", results, explanation, degraded=artifact is None)


@router.get("/prescription/{patient_id}", response_model=PredictionOut)
def get_prescription(
    patient_id: str,
    db: DbSession = Depends(get_session),
) -> PredictionOut:
    """M8: what to do in the next session, and why."""
    _patient(db, patient_id)
    sessions = _completed(db, patient_id)
    last = sessions[-1] if sessions else None

    qualities = [
        s.mean_rep_quality for s in sessions[-3:] if s.mean_rep_quality is not None
    ]

    plan, explanation = prescriber.prescribe(
        recent_quality=qualities,
        fatigue_slope=last.fatigue_slope if last else None,
        anomaly_direction=last.anomaly_direction if last else None,
        last_sqi=last.sqi_mean if last else None,
    )

    return _wrap("M8", plan.to_dict(), explanation, degraded=False)


@router.get("/insights/{patient_id}", response_model=list[PredictionOut])
def get_insights(
    patient_id: str,
    db: DbSession = Depends(get_session),
) -> list[PredictionOut]:
    """Every insight worth surfacing, most clinically salient first.

    Assembled rather than computed here: each card comes from the endpoint
    that owns that model, so there is one implementation of each.
    """
    cards: list[PredictionOut] = []

    # Ordered by what most warrants attention.
    for builder in (
        lambda: get_plateau(patient_id, db),
        lambda: get_forecast(patient_id, db),
        lambda: get_adherence(patient_id, db),
        lambda: get_percentile(patient_id, db),
        lambda: get_archetype(patient_id, db),
    ):
        try:
            cards.append(builder())
        except HTTPException:
            # An insight that needs data this patient does not have yet is
            # simply not shown.
            continue

    return cards


__all__ = ["router"]
