"""Session routes: history, detail, and the post session questionnaires.

The list endpoint reads only the denormalized summary columns on the Session
row. That is what keeps the dashboard fast: a history of sixty sessions is one
query that never touches the Rep table. See docs/ARCHITECTURE.md.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session as DbSession
from sqlmodel import delete, select

from app.db import get_session
from app.models import Rep, Session
from app.schemas import (
    BorgRequest,
    QuickDashOut,
    QuickDashRequest,
    RepOut,
    SessionDetailOut,
    SessionSummaryOut,
)
from app.schemas import IntervalOut

router = APIRouter(prefix="/api/sessions", tags=["sessions"])

# QuickDASH is scoreable only when at most one of its eleven items is
# missing. See docs/CLINICAL.md.
QUICKDASH_ITEMS = 11
QUICKDASH_MIN_ANSWERED = 10


def _to_summary(session: Session) -> SessionSummaryOut:
    out = SessionSummaryOut.model_validate(session)
    out.quickdash_valid = session.quickdash_valid
    return out


def _to_rep(rep: Rep) -> RepOut:
    out = RepOut.model_validate(rep)
    if rep.quality_point is not None:
        out.quality = IntervalOut(
            point=rep.quality_point,
            lower=rep.quality_lower if rep.quality_lower is not None else rep.quality_point,
            upper=rep.quality_upper if rep.quality_upper is not None else rep.quality_point,
            unit="score",
        )
    return out


@router.get("", response_model=list[SessionSummaryOut])
def list_sessions(
    patient_id: str,
    limit: int = 100,
    offset: int = 0,
    db: DbSession = Depends(get_session),
) -> list[SessionSummaryOut]:
    """A patient's session history, newest first."""
    rows = db.exec(
        select(Session)
        .where(Session.patient_id == patient_id)
        .order_by(Session.started_at.desc())  # type: ignore[union-attr]
        .offset(offset)
        .limit(limit)
    ).all()
    return [_to_summary(row) for row in rows]


@router.get("/{session_id}", response_model=SessionDetailOut)
def get_session_detail(
    session_id: int,
    db: DbSession = Depends(get_session),
) -> SessionDetailOut:
    session = db.get(Session, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"No session {session_id}.")

    reps = db.exec(
        select(Rep).where(Rep.session_id == session_id).order_by(Rep.index)  # type: ignore[arg-type]
    ).all()

    return SessionDetailOut(
        session=_to_summary(session),
        reps=[_to_rep(rep) for rep in reps],
    )


@router.get("/{session_id}/reps", response_model=list[RepOut])
def get_reps(session_id: int, db: DbSession = Depends(get_session)) -> list[RepOut]:
    if db.get(Session, session_id) is None:
        raise HTTPException(status_code=404, detail=f"No session {session_id}.")

    rows = db.exec(
        select(Rep).where(Rep.session_id == session_id).order_by(Rep.index)  # type: ignore[arg-type]
    ).all()
    return [_to_rep(row) for row in rows]


@router.post("/{session_id}/borg", response_model=SessionSummaryOut)
def set_borg(
    session_id: int,
    payload: BorgRequest,
    db: DbSession = Depends(get_session),
) -> SessionSummaryOut:
    """Borg CR10 rating of perceived exertion, collected after the session.

    This is M7's target: the gap between what the patient felt and what they
    produced is the clinically interesting part.
    """
    session = db.get(Session, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"No session {session_id}.")
    if not 0 <= payload.borg <= 10:
        raise HTTPException(
            status_code=422, detail="Borg CR10 runs from 0 to 10."
        )

    session.borg = payload.borg
    db.add(session)
    db.commit()
    db.refresh(session)
    return _to_summary(session)


@router.post("/{session_id}/quickdash", response_model=QuickDashOut)
def set_quickdash(
    session_id: int,
    payload: QuickDashRequest,
    db: DbSession = Depends(get_session),
) -> QuickDashOut:
    """QuickDASH.

    The score is stored with the number of items answered, because the
    instrument is not scoreable when more than one of its eleven items is
    missing. Validity is derived rather than assumed, and reported back so the
    UI can say the score does not count rather than showing a number that
    looks authoritative.
    """
    session = db.get(Session, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"No session {session_id}.")
    if not 0 <= payload.items_answered <= QUICKDASH_ITEMS:
        raise HTTPException(
            status_code=422,
            detail=f"QuickDASH has {QUICKDASH_ITEMS} items.",
        )

    valid = payload.items_answered >= QUICKDASH_MIN_ANSWERED

    session.quickdash_score = payload.score
    session.quickdash_items_answered = payload.items_answered
    db.add(session)
    db.commit()

    return QuickDashOut(
        score=payload.score,
        items_answered=payload.items_answered,
        valid=valid,
        note=(
            ""
            if valid
            else (
                "QuickDASH needs at least 10 of its 11 items answered to be "
                "scored. This response is kept but not counted."
            )
        ),
    )


@router.delete("/{session_id}", status_code=204)
def delete_session(session_id: int, db: DbSession = Depends(get_session)) -> None:
    if db.get(Session, session_id) is None:
        raise HTTPException(status_code=404, detail=f"No session {session_id}.")

    db.exec(delete(Rep).where(Rep.session_id == session_id))  # type: ignore[arg-type]
    db.exec(delete(Session).where(Session.id == session_id))  # type: ignore[arg-type]
    db.commit()


__all__ = ["router"]
