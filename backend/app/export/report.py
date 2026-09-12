"""The clinician PDF report.

A clinician wants to take something away from a session that is not a
spreadsheet: the headline measures, the trend behind them, and the session log
that produced both. That is what this renders.

Two rules govern what reaches the page.

**The clinical gate is applied per session, not per report.** A patient's
history can mix muscles, and kilograms are only honest on forearm grip. So the
kilogram column is filled for grip sessions and left blank for the rest, with a
note saying why. See app/clinical_gate.py.

**No bare point estimates.** Every headline figure carries the spread of the
sessions behind it, per the requirement in docs/ML.md. A number with no sense of
its own uncertainty is the thing this project exists not to print.

reportlab is imported inside the functions rather than at module scope. The
router registration in app/api/__init__.py swallows ImportError, so a module
level import that failed would silently remove the working CSV routes along
with this one, with nothing in the logs to say why.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from app.clinical_gate import (
    GATED_METRICS,
    MUSCLE_LABELS,
    NON_GRIP_NOTE,
    allows_kilograms,
)

if TYPE_CHECKING:  # pragma: no cover
    from app.models import Patient, Session

# Matches the disclaimer the API serves at /api/health. A report that leaves
# the building carries it too.
DISCLAIMER = (
    "Not a medical device: MySquishi is a training aid and does not replace a "
    "clinician."
)

# The six measures the clinician view puts up front, in the same order, with
# the clinical term alongside each. Kept here as data so the table and the
# gating read from one list.
METRICS: tuple[tuple[str, str, str, str], ...] = (
    ("strength_kg", "Estimated grip", "Jamar dynamometer equivalent", "kg"),
    ("mean_mvc", "Mean effort", "percent MVC", "%"),
    ("peak_mvc", "Peak effort", "percent MVC", "%"),
    ("fatigue_slope", "Fatigue slope", "median frequency slope", ""),
    ("hold_cv_mean", "Hold steadiness", "coefficient of variation", ""),
    ("sqi_mean", "Signal quality", "SQI", ""),
)

def _spread(values: list[float]) -> tuple[float, float, float]:
    """Mean with the observed range around it.

    Deliberately the range rather than a confidence interval. These are the
    sessions themselves, not a sample drawn from a population, so what a
    clinician wants is the spread actually recorded.
    """
    if not values:
        return (0.0, 0.0, 0.0)
    return (sum(values) / len(values), min(values), max(values))


def _metric_rows(sessions: list[Session]) -> list[list[str]]:
    """The headline table, gated per metric.

    A metric is only summarized over the sessions it is honest for. Averaging
    a kilogram figure across a history that mixes grip with biceps would
    produce a number that means nothing.
    """
    rows: list[list[str]] = [["Measure", "Clinical term", "Mean", "Range", "n"]]

    for field, label, term, unit in METRICS:
        eligible = (
            [s for s in sessions if allows_kilograms(s.muscle)]
            if field in GATED_METRICS
            else sessions
        )
        values = [
            float(getattr(s, field))
            for s in eligible
            if getattr(s, field, None) is not None
        ]

        if not values:
            # Omitted rather than nulled, so a blank reads as a decision.
            rows.append([label, term, "not reported", "", "0"])
            continue

        mean, low, high = _spread(values)
        rows.append(
            [
                label,
                term,
                f"{mean:.1f}{unit}",
                f"{low:.1f} to {high:.1f}{unit}",
                str(len(values)),
            ]
        )

    return rows


def _session_rows(sessions: list[Session]) -> list[list[str]]:
    """The session log, mirroring the columns the clinician view shows."""
    rows: list[list[str]] = [
        ["Date", "Muscle", "Grip (kg)", "Mean MVC", "Reps", "SQI", "Borg"]
    ]

    for session in sessions:
        # The gate, applied to this row alone.
        if allows_kilograms(session.muscle) and session.strength_kg is not None:
            grip = f"{session.strength_kg:.1f}"
        else:
            grip = "not reported"

        rows.append(
            [
                session.started_at.strftime("%Y-%m-%d"),
                MUSCLE_LABELS.get(session.muscle, session.muscle),
                grip,
                f"{session.mean_mvc:.0f}%" if session.mean_mvc is not None else "",
                str(session.rep_count or ""),
                f"{session.sqi_mean:.0f}" if session.sqi_mean is not None else "",
                str(session.borg) if session.borg is not None else "",
            ]
        )

    return rows


def _trend_drawing(sessions: list[Session], goal_kg: float | None) -> Any:
    """Estimated grip over time, drawn with reportlab primitives.

    Grip sessions only, because the series is in kilograms. Returns None when
    there are too few points to draw a line that means anything.
    """
    from reportlab.graphics.charts.lineplots import LinePlot
    from reportlab.graphics.shapes import Drawing, String
    from reportlab.lib import colors

    points = [
        (i, float(s.strength_kg))
        for i, s in enumerate(
            [
                s
                for s in sessions
                if allows_kilograms(s.muscle) and s.strength_kg is not None
            ]
        )
    ]
    if len(points) < 2:
        return None

    drawing = Drawing(460, 180)
    plot = LinePlot()
    plot.x = 45
    plot.y = 30
    plot.height = 120
    plot.width = 390
    plot.data = [points]
    plot.lines[0].strokeColor = colors.HexColor("#6350C4")
    plot.lines[0].strokeWidth = 1.6
    plot.joinedLines = 1

    values = [v for _, v in points]
    low = min(values)
    high = max(v for _, v in points)
    if goal_kg is not None:
        high = max(high, float(goal_kg))

    # A little air above and below so the line is not flush with the frame.
    margin = max(1.0, (high - low) * 0.15)
    plot.yValueAxis.valueMin = max(0.0, low - margin)
    plot.yValueAxis.valueMax = high + margin
    plot.xValueAxis.valueMin = 0
    plot.xValueAxis.valueMax = len(points) - 1

    drawing.add(plot)
    drawing.add(
        String(45, 162, "Estimated grip, kg, by grip session", fontSize=9)
    )
    return drawing


def build_report(patient_id: str, db: Any) -> bytes:
    """Render a clinician report as PDF.

    Raises LookupError when the patient does not exist, which the route turns
    into a 404. Keeping HTTP out of here leaves the builder usable from a
    script or a test.
    """
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        PageBreak,
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )
    import io

    from sqlmodel import select

    from app.models import Patient, Session

    patient = db.get(Patient, patient_id)
    if patient is None:
        raise LookupError(f"No patient '{patient_id}'.")

    sessions = list(
        db.exec(
            select(Session)
            .where(Session.patient_id == patient_id)
            .where(Session.rep_count.is_not(None))  # type: ignore[union-attr]
            .order_by(Session.started_at)  # type: ignore[arg-type]
        ).all()
    )

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        title=f"MySquishi report: {patient_id}",
        author="MySquishi",
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
    )

    styles = getSampleStyleSheet()
    small = ParagraphStyle(
        "small", parent=styles["BodyText"], fontSize=8.5, leading=11.5
    )
    story: list[Any] = []

    story.append(Paragraph("MySquishi clinician report", styles["Title"]))
    story.append(
        Paragraph(
            f"{patient.display_name or patient_id} "
            f"(id {patient_id}), generated "
            f"{datetime.now(timezone.utc).strftime('%Y-%m-%d')}",
            styles["BodyText"],
        )
    )

    # Said before any number, not in a footer after them.
    story.append(Spacer(1, 4))
    story.append(Paragraph(f"<b>{DISCLAIMER}</b>", small))

    if patient.is_synthetic:
        story.append(
            Paragraph(
                "<b>Synthetic data.</b> This patient is generated for "
                "demonstration. No figure here came from a person.",
                small,
            )
        )

    details = [
        f"Age band {patient.age_band}" if patient.age_band else "",
        f"Sex {patient.sex}" if patient.sex else "",
        f"Injury {patient.injury_type}" if patient.injury_type else "",
        f"Goal {patient.goal_kg:.1f} kg" if patient.goal_kg else "",
        f"{len(sessions)} completed sessions",
    ]
    story.append(Spacer(1, 6))
    story.append(Paragraph(", ".join(d for d in details if d), styles["BodyText"]))

    if not sessions:
        story.append(Spacer(1, 10))
        story.append(
            Paragraph(
                "No completed sessions yet, so there is nothing to summarize.",
                styles["BodyText"],
            )
        )
        doc.build(story)
        return buffer.getvalue()

    table_style = TableStyle(
        [
            ("FONTSIZE", (0, 0), (-1, -1), 8.5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("LINEBELOW", (0, 0), (-1, 0), 0.6, colors.HexColor("#4B3B96")),
            ("LINEBELOW", (0, 1), (-1, -2), 0.25, colors.HexColor("#E6E1FA")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]
    )

    story.append(Spacer(1, 14))
    story.append(Paragraph("Headline measures", styles["Heading2"]))
    story.append(
        Paragraph(
            "Mean across completed sessions, with the range actually recorded. "
            "Ranges are the observed spread, not a confidence interval.",
            small,
        )
    )
    story.append(Spacer(1, 6))
    metrics = Table(_metric_rows(sessions), colWidths=[95, 135, 65, 105, 30])
    metrics.setStyle(table_style)
    story.append(metrics)

    # Only say why a figure is missing when one actually is.
    if any(not allows_kilograms(s.muscle) for s in sessions):
        story.append(Spacer(1, 6))
        story.append(Paragraph(NON_GRIP_NOTE, small))

    trend = _trend_drawing(sessions, patient.goal_kg)
    if trend is not None:
        story.append(Spacer(1, 16))
        story.append(Paragraph("Strength trend", styles["Heading2"]))
        story.append(Spacer(1, 4))
        story.append(trend)

    story.append(PageBreak())
    story.append(Paragraph("Session log", styles["Heading2"]))
    story.append(Spacer(1, 6))
    log = Table(
        _session_rows(sessions),
        colWidths=[70, 85, 70, 60, 40, 40, 40],
        repeatRows=1,
    )
    log.setStyle(table_style)
    story.append(log)

    doc.build(story)
    return buffer.getvalue()


__all__ = ["build_report"]
