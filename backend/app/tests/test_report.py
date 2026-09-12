"""The clinician PDF report.

Most of what matters here is not that a PDF appears but that the clinical gate
survives the trip into it. A kilogram figure printed against a biceps session
is a false clinical claim, and it is harder to notice inside a binary than on a
screen.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session as DbSession

from app.db import get_engine
from app.export.report import _metric_rows, _session_rows, build_report
from app.main import app
from app.models import Patient, Session
from app.seed import DEMO_PATIENT_ID, seed_demo


def _session(muscle: str, strength_kg: float | None) -> Session:
    return Session(
        patient_id="gate-test",
        started_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        muscle=muscle,
        rep_count=10,
        mean_mvc=55.0,
        peak_mvc=70.0,
        sqi_mean=90.0,
        hold_cv_mean=0.1,
        fatigue_slope=-1.0,
        strength_kg=strength_kg,
    )


class TestClinicalGate:
    """kg, EWGSOP2 and percentile are forearm grip only. See
    app/clinical_gate.py."""

    def test_omits_kilograms_for_non_grip_sessions(self) -> None:
        rows = _session_rows([_session("biceps", 99.0)])
        assert "99" not in "".join(rows[1])

    def test_keeps_kilograms_for_grip_sessions(self) -> None:
        rows = _session_rows([_session("forearm_grip", 20.0)])
        assert "20.0" in rows[1]

    def test_summarizes_grip_only_over_grip_sessions(self) -> None:
        """A kilogram mean taken across a mixed history would describe
        nothing, so the grip row counts grip sessions alone while the effort
        rows count all three."""
        sessions = [
            _session("forearm_grip", 20.0),
            _session("biceps", 99.0),
            _session("calf", 99.0),
        ]
        rows = {row[0]: row for row in _metric_rows(sessions)}

        assert rows["Estimated grip"][-1] == "1"
        assert rows["Mean effort"][-1] == "3"
        assert "99" not in "".join(rows["Estimated grip"])

    def test_reports_nothing_rather_than_zero_when_no_grip_session(self) -> None:
        rows = {row[0]: row for row in _metric_rows([_session("calf", None)])}
        assert rows["Estimated grip"][2] == "not reported"


class TestBuildReport:
    @pytest.fixture(scope="class")
    def seeded(self) -> None:
        seed_demo()

    def test_renders_a_pdf(self, seeded: None) -> None:
        with DbSession(get_engine()) as db:
            pdf = build_report(DEMO_PATIENT_ID, db)

        assert pdf.startswith(b"%PDF")
        assert len(pdf) > 2000

    def test_raises_lookup_error_for_an_unknown_patient(self) -> None:
        """HTTP stays in the router, so the builder is usable from a script."""
        with DbSession(get_engine()) as db:
            with pytest.raises(LookupError):
                build_report("no-such-patient", db)

    def test_renders_for_a_patient_with_no_sessions(self) -> None:
        """An empty report beats a traceback: a clinician who exports before
        the first session should get a page that says so."""
        with DbSession(get_engine()) as db:
            existing = db.get(Patient, "empty-patient")
            if existing is not None:
                db.delete(existing)
                db.commit()

            db.add(Patient(id="empty-patient", display_name="Empty"))
            db.commit()
            try:
                pdf = build_report("empty-patient", db)
            finally:
                db.delete(db.get(Patient, "empty-patient"))
                db.commit()

        assert pdf.startswith(b"%PDF")


class TestExportRoutes:
    @pytest.fixture(scope="class")
    def client(self) -> TestClient:
        seed_demo()
        return TestClient(app)

    def test_serves_the_pdf(self, client: TestClient) -> None:
        response = client.get(f"/api/export/report.pdf?patient_id={DEMO_PATIENT_ID}")

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/pdf"
        assert "attachment" in response.headers["content-disposition"]
        assert response.content.startswith(b"%PDF")

    def test_404s_for_an_unknown_patient(self, client: TestClient) -> None:
        response = client.get("/api/export/report.pdf?patient_id=nobody")
        assert response.status_code == 404

    def test_csv_routes_still_register(self, client: TestClient) -> None:
        """register_routers swallows ImportError, so a reportlab import at
        module scope in api/export.py would silently take the CSV routes down
        with it. This is the test that notices."""
        response = client.get(
            f"/api/export/sessions.csv?patient_id={DEMO_PATIENT_ID}"
        )

        assert response.status_code == 200
        assert "muscle" in response.text.splitlines()[0]
