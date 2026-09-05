"""Export routes.

CSV now. PDF is Phase 4 and says so rather than pretending to be missing.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
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
def export_report() -> None:
    """The clinician PDF. Phase 4."""
    raise HTTPException(
        status_code=501,
        detail=(
            "The PDF report arrives in Phase 4. Session data is available as "
            "CSV today, from /api/export/sessions.csv."
        ),
    )


__all__ = ["router"]
