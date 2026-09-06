"""Patient routes: profile, goal, and data deletion."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session as DbSession
from sqlmodel import delete, select

from app.clinical_gate import GRIP
from app.db import get_session
from app.models import Calibration, Goal, InsightCache, Patient, Rep, Session
from app.schemas import GoalOut, PatientCreate, PatientOut, PatientUpdate

router = APIRouter(prefix="/api/patients", tags=["patients"])


@router.post("", response_model=PatientOut, status_code=201)
def create_patient(
    payload: PatientCreate,
    db: DbSession = Depends(get_session),
) -> Patient:
    """Onboarding."""
    if db.get(Patient, payload.id) is not None:
        raise HTTPException(status_code=409, detail=f"Patient '{payload.id}' already exists.")

    patient = Patient(**payload.model_dump())
    db.add(patient)

    if payload.goal_kg is not None:
        db.add(Goal(patient_id=patient.id, target_kg=payload.goal_kg))

    db.commit()
    db.refresh(patient)
    return patient


@router.get("/{patient_id}", response_model=PatientOut)
def get_patient(patient_id: str, db: DbSession = Depends(get_session)) -> Patient:
    patient = db.get(Patient, patient_id)
    if patient is None:
        raise HTTPException(status_code=404, detail=f"No patient '{patient_id}'.")
    return patient


@router.patch("/{patient_id}", response_model=PatientOut)
def update_patient(
    patient_id: str,
    payload: PatientUpdate,
    db: DbSession = Depends(get_session),
) -> Patient:
    patient = db.get(Patient, patient_id)
    if patient is None:
        raise HTTPException(status_code=404, detail=f"No patient '{patient_id}'.")

    changes = payload.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(patient, field, value)

    # A changed goal opens a new Goal row rather than editing the old one, so
    # a target the patient already reached stays visible in their history.
    if "goal_kg" in changes and changes["goal_kg"] is not None:
        db.add(Goal(patient_id=patient_id, target_kg=float(changes["goal_kg"])))

    db.add(patient)
    db.commit()
    db.refresh(patient)
    return patient


@router.get("/{patient_id}/goal", response_model=GoalOut)
def get_goal(patient_id: str, db: DbSession = Depends(get_session)) -> GoalOut:
    """Goal progress, for the progress ring."""
    patient = db.get(Patient, patient_id)
    if patient is None:
        raise HTTPException(status_code=404, detail=f"No patient '{patient_id}'.")

    goal = db.exec(
        select(Goal)
        .where(Goal.patient_id == patient_id)
        .order_by(Goal.created_at.desc())  # type: ignore[union-attr]
    ).first()

    # Grip sessions only. The goal is expressed in kilograms, and kilograms are
    # validated on hand dynamometry, so a biceps session has nothing to
    # contribute to it. A patient training several muscles still gets a correct
    # grip goal rather than one contaminated by an incomparable measurement.
    # See app/clinical_gate.py.
    sessions = db.exec(
        select(Session)
        .where(Session.patient_id == patient_id)
        .where(Session.muscle == GRIP)
        .where(Session.strength_kg.is_not(None))  # type: ignore[union-attr]
        .order_by(Session.started_at)  # type: ignore[arg-type]
    ).all()

    baseline = sessions[0].strength_kg if sessions else None
    current = sessions[-1].strength_kg if sessions else None
    target = goal.target_kg if goal else patient.goal_kg

    progress = None
    if target and baseline is not None and current is not None and target > baseline:
        progress = (current - baseline) / (target - baseline) * 100.0
        progress = max(0.0, min(100.0, progress))

    return GoalOut(
        target_kg=target,
        target_date=goal.target_date if goal else None,
        current_kg=current,
        baseline_kg=baseline,
        progress_pct=round(progress, 1) if progress is not None else None,
        achieved=bool(target and current and current >= target),
    )


@router.delete("/{patient_id}/data", status_code=204)
def delete_patient_data(patient_id: str, db: DbSession = Depends(get_session)) -> None:
    """Delete everything belonging to a patient.

    The Responsible AI page promises this, so it has to actually remove the
    rows rather than hide them. Reps go first, then the tables that reference
    the patient, then the patient.
    """
    if db.get(Patient, patient_id) is None:
        raise HTTPException(status_code=404, detail=f"No patient '{patient_id}'.")

    session_ids = db.exec(
        select(Session.id).where(Session.patient_id == patient_id)
    ).all()
    if session_ids:
        db.exec(delete(Rep).where(Rep.session_id.in_(session_ids)))  # type: ignore[union-attr,arg-type]

    for table in (Session, Calibration, Goal, InsightCache):
        db.exec(delete(table).where(table.patient_id == patient_id))  # type: ignore[arg-type]

    db.exec(delete(Patient).where(Patient.id == patient_id))  # type: ignore[arg-type]
    db.commit()


__all__ = ["router"]
