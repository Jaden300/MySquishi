"""Signal routes: sources, calibration, and the live websocket.

The socket carries frames. Everything else in the app is REST.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone

import numpy as np
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlmodel import Session as DbSession
from sqlmodel import select

from app.api.live import DEFAULT_MVC_REFERENCE_RMS, LiveSessionRunner, frame_json
from app.clinical_gate import DEFAULT_MUSCLE, allows_kilograms
from app.clinical_gate import normalize as normalize_muscle
from app.db import get_session
from app.ml import force
from app.models import Calibration, Rep, Session
from app.schemas import CalibrationOut, CalibrationRequest, SourceOut
from app.sources.base import list_sources

router = APIRouter(prefix="/api/signal", tags=["signal"])


@router.get("/sources", response_model=list[SourceOut])
def get_sources() -> list[SourceOut]:
    """The source catalogue the settings page renders.

    Sources that do not exist yet are listed but marked unavailable, so the
    roadmap is visible rather than hidden. `is_live` here is what drives the
    honesty chip in the UI.
    """
    return [SourceOut(**vars(info)) for info in list_sources()]


@router.get("/calibration", response_model=CalibrationOut | None)
def get_calibration(
    patient_id: str,
    muscle: str = DEFAULT_MUSCLE,
    db: DbSession = Depends(get_session),
) -> Calibration | None:
    """The active calibration for a patient on one muscle, if there is one."""
    return _active_calibration(db, patient_id, muscle)


@router.post("/calibrate", response_model=CalibrationOut)
def calibrate(
    request: CalibrationRequest,
    db: DbSession = Depends(get_session),
) -> Calibration:
    """Fit this patient's force model.

    The only place M3 is fitted. docs/ML.md is explicit that the force model
    belongs to the person and the electrode placement rather than to the
    cohort, so it is fitted here and persisted on the calibration row.

    The reference is self reported, not a dynamometer reading. That framing
    travels with every estimate the model produces.
    """
    if len(request.feature_rows) < 2:
        raise HTTPException(
            status_code=422,
            detail="Calibration needs at least two held contractions.",
        )
    if request.mvc_reference_rms <= 0:
        raise HTTPException(
            status_code=422,
            detail="The maximum voluntary contraction reference must be positive.",
        )

    reference_kg = np.full(len(request.feature_rows), float(request.reference_kg))

    try:
        model = force.fit(
            request.feature_rows,
            reference_kg,
            mvc_reference_rms=request.mvc_reference_rms,
        )
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    # Only one calibration is active per patient per muscle. Scoping the
    # deactivation by muscle matters: a maximum voluntary contraction belongs
    # to the muscle as well as the person, so calibrating a biceps must not
    # retire the grip calibration that a kilogram estimate depends on.
    # Superseded rows are kept so a past session can still be read against the
    # calibration it was recorded under.
    muscle = normalize_muscle(request.muscle)
    previous = db.exec(
        select(Calibration)
        .where(Calibration.patient_id == request.patient_id)
        .where(Calibration.muscle == muscle)
        .where(Calibration.is_active)
    ).all()
    for row in previous:
        row.is_active = False
        db.add(row)

    calibration = Calibration(
        patient_id=request.patient_id,
        muscle=muscle,
        mvc_reference_rms=request.mvc_reference_rms,
        reference_kg=request.reference_kg,
        force_model_json=model.to_json(),
        r_squared=model.r_squared,
        n_points=model.n_points,
        is_active=True,
    )
    db.add(calibration)
    db.commit()
    db.refresh(calibration)
    return calibration


def _active_calibration(
    db: DbSession,
    patient_id: str,
    muscle: str = DEFAULT_MUSCLE,
) -> Calibration | None:
    """The calibration in force for one patient on one muscle."""
    return db.exec(
        select(Calibration)
        .where(Calibration.patient_id == patient_id)
        .where(Calibration.muscle == normalize_muscle(muscle))
        .where(Calibration.is_active)
        .order_by(Calibration.created_at.desc())  # type: ignore[union-attr]
    ).first()


def _persist(
    db: DbSession,
    runner: LiveSessionRunner,
    session_id: int | None,
    calibration_id: int | None,
) -> int | None:
    """Write the session and its repetitions in one transaction.

    Called on stop and again on an unexpected disconnect, so an abandoned
    session still keeps what it captured. Reps live in memory during the
    session and are written once, here.
    """
    if not runner.reps and runner.seq == 0:
        return None

    summary = runner.summary()

    session = db.get(Session, session_id) if session_id else None
    if session is None:
        session = Session(patient_id=runner.patient_id)

    session.started_at = runner.started_at
    session.ended_at = datetime.now(timezone.utc)
    session.source_id = runner.source_id
    session.is_live = runner.is_live
    session.calibration_id = calibration_id
    session.muscle = runner.muscle

    # Both flags derive from the source object rather than from anything the
    # caller passed in. A session recorded from the synthetic generator is
    # synthetic, and it says so, so the badge cannot be wrong.
    session.is_synthetic = not runner.is_live

    session.rep_count = int(summary["rep_count"])  # type: ignore[arg-type]
    session.mean_mvc = float(summary["mean_mvc"])  # type: ignore[arg-type]
    session.peak_mvc = float(summary["peak_mvc"])  # type: ignore[arg-type]
    session.mean_rep_quality = summary["mean_rep_quality"]  # type: ignore[assignment]
    session.sqi_mean = summary["sqi_mean"]  # type: ignore[assignment]
    session.total_impulse = float(summary["total_impulse"])  # type: ignore[arg-type]
    session.duration_s = float(summary["duration_s"])  # type: ignore[arg-type]

    fatigue_payload = summary.get("fatigue")
    if isinstance(fatigue_payload, dict):
        slope = fatigue_payload.get("slope")
        if isinstance(slope, dict):
            session.fatigue_slope = float(slope["point"])
        session.fatigue_r_squared = fatigue_payload.get("r_squared")  # type: ignore[assignment]
        session.fatigue_p_value = fatigue_payload.get("p_value")  # type: ignore[assignment]

    hold_cvs = [float(r["features"]["hold_cv"]) for r in runner.reps]  # type: ignore[index]
    session.hold_cv_mean = float(np.mean(hold_cvs)) if hold_cvs else None

    # M3's force estimate, in kilograms, and only ever for grip. The model maps
    # this person's amplitude on this placement to kilograms; the EWGSOP2
    # references it feeds are validated on hand dynamometry alone, so on any
    # other muscle the field is left null and the gate omits it from responses.
    # See app/clinical_gate.py.
    session.strength_kg = None
    if allows_kilograms(runner.muscle) and calibration_id is not None:
        calibration = db.get(Calibration, calibration_id)
        peak = runner.peak_window_features
        if calibration is not None and peak is not None:
            try:
                model = force.ForceModel.from_json(calibration.force_model_json)
                session.strength_kg = float(model.predict(peak).point)
            except (ValueError, KeyError):
                # A calibration fitted against different features cannot be
                # applied to this session. No estimate is better than a wrong
                # one, and the interval requirement means a bare guess is not
                # an option either.
                session.strength_kg = None

    db.add(session)
    db.commit()
    db.refresh(session)

    for record in runner.reps:
        features = record["features"]
        quality = record["quality"]
        db.add(
            Rep(
                session_id=session.id,  # type: ignore[arg-type]
                index=int(record["index"]),  # type: ignore[arg-type]
                start_s=float(record["start_s"]),  # type: ignore[arg-type]
                peak_s=float(record["peak_s"]),  # type: ignore[arg-type]
                end_s=float(record["end_s"]),  # type: ignore[arg-type]
                quality_point=float(quality["point"]),  # type: ignore[index]
                quality_lower=float(quality["lower"]),  # type: ignore[index]
                quality_upper=float(quality["upper"]),  # type: ignore[index]
                quality_top_factor=str(record["top_factor"]),
                quality_feedback=str(record["feedback"]),
                **{key: float(value) for key, value in features.items()},  # type: ignore[union-attr]
            )
        )

    db.commit()
    return session.id


@router.websocket("/live")
async def live(
    websocket: WebSocket,
    source: str = "simulated",
    patient_id: str = "demo",
    session_id: int | None = None,
    junkiness: float = 0.0,
    muscle: str = DEFAULT_MUSCLE,
) -> None:
    """Stream a live session.

    The client sends only start, stop and pause. See the frame contract in
    docs/ARCHITECTURE.md.
    """
    await websocket.accept()

    db_gen = get_session()
    db = next(db_gen)

    # The calibration is looked up per muscle, so a biceps session normalizes
    # against the biceps maximum rather than borrowing the grip one.
    selected_muscle = normalize_muscle(muscle)
    calibration = _active_calibration(db, patient_id, selected_muscle)
    runner = LiveSessionRunner(
        source_id=source,
        patient_id=patient_id,
        muscle=selected_muscle,
        mvc_reference_rms=(
            calibration.mvc_reference_rms if calibration else DEFAULT_MVC_REFERENCE_RMS
        ),
        calibrated=calibration is not None,
        junkiness=junkiness,
    )

    running = False
    saved_id: int | None = session_id

    try:
        runner.connect()
    except (NotImplementedError, ValueError, RuntimeError) as exc:
        # A sensor that is not plugged in, a trace that is not there, or an
        # unrecognised source id are all normal conditions rather than crashes.
        # SerialUnavailable and ReplayUnavailable are RuntimeErrors carrying an
        # operator facing message, so pass it straight through: it says what to
        # do next, which a stack trace does not.
        await websocket.send_text(
            json.dumps({"type": "error", "message": str(exc)})
        )
        await websocket.close()
        db_gen.close()
        return

    try:
        while True:
            if running:
                # Drain any control message without blocking the stream.
                try:
                    message = await asyncio.wait_for(
                        websocket.receive_text(), timeout=0.001
                    )
                except (asyncio.TimeoutError, TimeoutError):
                    message = None
            else:
                message = await websocket.receive_text()

            if message is not None:
                command = json.loads(message).get("type")

                if command == "start":
                    running = True
                elif command == "pause":
                    running = False
                elif command == "stop":
                    saved_id = _persist(db, runner, saved_id, calibration.id if calibration else None)
                    payload = runner.summary()
                    payload["session_id"] = saved_id
                    await websocket.send_text(frame_json(payload))
                    break

            if running:
                window = await runner.read_window()
                await websocket.send_text(frame_json(runner.process(window)))

    except WebSocketDisconnect:
        # An abandoned session still keeps what it captured.
        _persist(db, runner, saved_id, calibration.id if calibration else None)
    finally:
        runner.disconnect()
        db_gen.close()


__all__ = ["router"]
