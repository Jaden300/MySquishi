"""CSV row building.

Kept out of the router so the endpoint stays thin and the column order has one
owner. Exports carry the synthetic flag: a spreadsheet that leaves the
building should still say what it is.
"""

from __future__ import annotations

import csv
import io
from collections.abc import Iterable

from app.models import Rep, Session

SESSION_COLUMNS = (
    "session_id",
    "started_at",
    "ended_at",
    "source_id",
    "is_live",
    "is_synthetic",
    "rep_count",
    "mean_mvc_pct",
    "peak_mvc_pct",
    "mean_rep_quality",
    "hold_cv_mean",
    "sqi_mean",
    "fatigue_slope",
    "fatigue_r_squared",
    "fatigue_p_value",
    "total_impulse",
    "duration_s",
    "estimated_grip_kg",
    "borg_cr10",
    "quickdash_score",
    "quickdash_valid",
    "adherence_gap_days",
)

REP_COLUMNS = (
    "session_id",
    "rep_index",
    "start_s",
    "peak_s",
    "end_s",
    "duration_s",
    "peak_mvc_pct",
    "mean_mvc_pct",
    "time_to_peak_s",
    "rfd",
    "relaxation_time_s",
    "hold_cv",
    "plateau_flatness",
    "impulse",
    "median_frequency_hz",
    "mean_frequency_hz",
    "dimitrov_index",
    "quality_score",
    "quality_lower",
    "quality_upper",
    "quality_feedback",
)


def _session_row(session: Session) -> list[object]:
    return [
        session.id,
        session.started_at.isoformat(),
        session.ended_at.isoformat() if session.ended_at else "",
        session.source_id,
        session.is_live,
        session.is_synthetic,
        session.rep_count,
        session.mean_mvc,
        session.peak_mvc,
        session.mean_rep_quality,
        session.hold_cv_mean,
        session.sqi_mean,
        session.fatigue_slope,
        session.fatigue_r_squared,
        session.fatigue_p_value,
        session.total_impulse,
        session.duration_s,
        session.strength_kg,
        session.borg,
        session.quickdash_score,
        session.quickdash_valid,
        session.adherence_gap_days,
    ]


def _rep_row(rep: Rep) -> list[object]:
    return [
        rep.session_id,
        rep.index,
        rep.start_s,
        rep.peak_s,
        rep.end_s,
        rep.duration_s,
        rep.peak_mvc,
        rep.mean_mvc,
        rep.time_to_peak_s,
        rep.rfd,
        rep.relaxation_time_s,
        rep.hold_cv,
        rep.plateau_flatness,
        rep.impulse,
        rep.median_frequency,
        rep.mean_frequency,
        rep.dimitrov_index,
        rep.quality_point,
        rep.quality_lower,
        rep.quality_upper,
        rep.quality_feedback,
    ]


def _render(header: Iterable[str], rows: Iterable[list[object]]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(header)
    for row in rows:
        writer.writerow(row)
    return buffer.getvalue()


def sessions_csv(sessions: list[Session]) -> str:
    """A patient's session history.

    Grip figures are estimates calibrated to a self reported reference, not
    dynamometer measurements. The column is named estimated_grip_kg so that
    survives the export.
    """
    return _render(SESSION_COLUMNS, (_session_row(s) for s in sessions))


def reps_csv(reps: list[Rep]) -> str:
    """Repetition level detail for one session."""
    return _render(REP_COLUMNS, (_rep_row(r) for r in reps))


__all__ = ["REP_COLUMNS", "SESSION_COLUMNS", "reps_csv", "sessions_csv"]
