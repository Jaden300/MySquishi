"""Export routes.

CSV for the raw numbers, PDF for the clinician summary.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import PlainTextResponse
from sqlmodel import Session as DbSession
from sqlmodel import select

from app.db import get_session
from app.export.csv_export import reps_csv, sessions_csv
from app.models import Patient, Rep, Session

router = APIRouter(prefix="/api/export", tags=["export"])


@router.get("/sessions.csv", response_class=PlainTextResponse)
def export_sessions(
    patient_id: str,
    db: DbSession = Depends(get_session),
) -> PlainTextResponse:
    """A patient's whole session history as CSV."""
    if db.get(Patient, patient_id) is None:
        raise HTTPException(status_code=404, detail=f"No patient '{patient_id}'.")

    sessions = list(
        db.exec(
            select(Session)
            .where(Session.patient_id == patient_id)
            .order_by(Session.started_at)  # type: ignore[arg-type]
        ).all()
    )

    return PlainTextResponse(
        sessions_csv(sessions),
        media_type="text/csv",
        headers={
            "Content-Disposition": (
                f'attachment; filename="mysquishi-{patient_id}-sessions.csv"'
            )
        },
    )


@router.get("/session/{session_id}.csv", response_class=PlainTextResponse)
def export_session_reps(
    session_id: int,
    db: DbSession = Depends(get_session),
) -> PlainTextResponse:
    """One session's repetitions as CSV."""
    if db.get(Session, session_id) is None:
        raise HTTPException(status_code=404, detail=f"No session {session_id}.")

    reps = list(
        db.exec(
            select(Rep).where(Rep.session_id == session_id).order_by(Rep.index)  # type: ignore[arg-type]
        ).all()
    )

    return PlainTextResponse(
        reps_csv(reps),
        media_type="text/csv",
        headers={
            "Content-Disposition": (
                f'attachment; filename="mysquishi-session-{session_id}.csv"'
            )
        },
    )


@router.get("/report.pdf")
def export_report(
    patient_id: str,
    db: DbSession = Depends(get_session),
) -> Response:
    """A patient's clinician report as PDF.

    build_report is imported here rather than at module scope. It pulls in
    reportlab, and register_routers swallows ImportError, so a failure at
    module scope would take the working CSV routes down with it silently.
    """
    from app.export.report import build_report

    try:
        pdf = build_report(patient_id, db)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return Response(
        pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": (
                f'attachment; filename="mysquishi-{patient_id}-report.pdf"'
            )
        },
    )


__all__ = ["router"]
