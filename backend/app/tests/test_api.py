"""The REST surface and the websocket, end to end.

docs/ARCHITECTURE.md names test_api.py::test_no_serial_imports specifically as
what enforces the Phase 2 hard stop. It lives here as well as in
test_sources.py: the boundary is worth guarding twice.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
APP_DIR = BACKEND_DIR / "app"


@pytest.fixture(scope="module")
def client() -> TestClient:
    """A client with the application lifespan run, so the demo seed exists."""
    with TestClient(app) as test_client:
        yield test_client


class TestPhaseTwoHardStop:
    """Phase 1 writes no serial port code."""

    def test_no_serial_imports(self) -> None:
        """Fails the suite if serial appears anywhere under app/.

        This is what makes the hard stop before hardware bring up enforced
        rather than merely remembered.
        """
        offenders = []
        for path in APP_DIR.rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            for line in text.splitlines():
                stripped = line.strip()
                if stripped.startswith(("import serial", "from serial")):
                    offenders.append(f"{path.relative_to(BACKEND_DIR)}: {stripped}")

        assert not offenders, f"serial imports found: {offenders}"

    def test_pyserial_is_not_a_dependency(self) -> None:
        requirements = (BACKEND_DIR / "requirements.txt").read_text(encoding="utf-8")
        assert "pyserial" not in requirements.lower()


class TestHealth:
    def test_reports_acquisition_constants(self, client: TestClient) -> None:
        body = client.get("/api/health").json()
        assert body["status"] == "ok"
        assert body["sample_rate"] == 1000
        assert body["window_samples"] == 200

    def test_publishes_the_frame_contract(self, client: TestClient) -> None:
        """The frontend asserts against this rather than discovering a renamed
        field as undefined in a chart."""
        from app.api.live import FRAME_KEYS

        body = client.get("/api/health").json()
        assert body["frame_keys"] == list(FRAME_KEYS)


class TestSources:
    def test_lists_every_source_including_unavailable_ones(
        self, client: TestClient
    ) -> None:
        """Sources that arrive later are listed but marked unavailable, so the
        roadmap is visible rather than hidden."""
        sources = client.get("/api/signal/sources").json()
        by_id = {s["id"]: s for s in sources}

        assert by_id["simulated"]["available"] is True
        assert by_id["serial"]["available"] is False
        assert by_id["replay"]["available"] is False

    def test_simulated_never_claims_to_be_live(self, client: TestClient) -> None:
        """The honesty chip derives from this field."""
        sources = client.get("/api/signal/sources").json()
        simulated = next(s for s in sources if s["id"] == "simulated")
        assert simulated["is_live"] is False


class TestPatients:
    def test_demo_patient_is_seeded_and_labeled_synthetic(
        self, client: TestClient
    ) -> None:
        patient = client.get("/api/patients/demo").json()
        assert patient["id"] == "demo"
        assert patient["is_synthetic"] is True

    def test_unknown_patient_is_a_404(self, client: TestClient) -> None:
        assert client.get("/api/patients/nobody").status_code == 404

    def test_goal_reports_progress_without_a_bare_claim(
        self, client: TestClient
    ) -> None:
        goal = client.get("/api/patients/demo/goal").json()
        assert goal["target_kg"] > 0
        assert goal["baseline_kg"] is not None
        assert 0.0 <= goal["progress_pct"] <= 100.0


class TestSessions:
    def test_history_is_returned_newest_first(self, client: TestClient) -> None:
        sessions = client.get("/api/sessions", params={"patient_id": "demo"}).json()
        assert len(sessions) > 10

        starts = [s["started_at"] for s in sessions]
        assert starts == sorted(starts, reverse=True)

    def test_seeded_sessions_are_labeled_synthetic(self, client: TestClient) -> None:
        sessions = client.get("/api/sessions", params={"patient_id": "demo"}).json()
        assert all(s["is_synthetic"] for s in sessions)

    def test_missed_sessions_are_kept_as_gaps(self, client: TestClient) -> None:
        """A missed session is data, not an absence of data: it is what the
        adherence heatmap and M13 read."""
        sessions = client.get("/api/sessions", params={"patient_id": "demo"}).json()
        missed = [s for s in sessions if s["rep_count"] is None]
        assert missed, "the demo history should contain missed sessions"

    def test_unknown_session_is_a_404(self, client: TestClient) -> None:
        assert client.get("/api/sessions/999999").status_code == 404


class TestQuickDash:
    """docs/CLINICAL.md: the score is invalid above one missing item."""

    def _a_session_id(self, client: TestClient) -> int:
        sessions = client.get("/api/sessions", params={"patient_id": "demo"}).json()
        return sessions[0]["id"]

    def test_complete_response_is_valid(self, client: TestClient) -> None:
        session_id = self._a_session_id(client)
        body = client.post(
            f"/api/sessions/{session_id}/quickdash",
            json={"score": 42.0, "items_answered": 11},
        ).json()
        assert body["valid"] is True

    def test_two_missing_items_makes_it_unscoreable(self, client: TestClient) -> None:
        session_id = self._a_session_id(client)
        body = client.post(
            f"/api/sessions/{session_id}/quickdash",
            json={"score": 42.0, "items_answered": 9},
        ).json()

        assert body["valid"] is False
        assert body["note"], "an invalid score must say why it does not count"

    def test_borg_outside_the_scale_is_rejected(self, client: TestClient) -> None:
        session_id = self._a_session_id(client)
        response = client.post(
            f"/api/sessions/{session_id}/borg", json={"borg": 14}
        )
        assert response.status_code == 422


class TestCalibration:
    def test_demo_has_an_active_calibration(self, client: TestClient) -> None:
        body = client.get(
            "/api/signal/calibration", params={"patient_id": "demo"}
        ).json()
        assert body["is_active"] is True
        assert body["r_squared"] > 0.5

    def test_too_few_points_is_rejected(self, client: TestClient) -> None:
        response = client.post(
            "/api/signal/calibrate",
            json={
                "patient_id": "demo",
                "feature_rows": [{"rms": 1.0, "mav": 1.0, "waveform_length": 1.0}],
                "reference_kg": 20.0,
                "mvc_reference_rms": 1.0,
            },
        )
        assert response.status_code == 422


class TestLiveWebsocket:
    def test_streams_frames_and_persists_on_stop(self, client: TestClient) -> None:
        with client.websocket_connect(
            "/api/signal/live?source=simulated&patient_id=demo"
        ) as ws:
            ws.send_text(json.dumps({"type": "start"}))
            frames = [json.loads(ws.receive_text()) for _ in range(30)]

            assert all(f["type"] == "frame" for f in frames)
            assert all(f["is_live"] is False for f in frames)

            ws.send_text(json.dumps({"type": "stop"}))
            summary = json.loads(ws.receive_text())

        assert summary["type"] == "summary"
        assert summary["session_id"] is not None

        detail = client.get(f"/api/sessions/{summary['session_id']}").json()
        assert detail["session"]["rep_count"] == summary["rep_count"]
        assert len(detail["reps"]) == summary["rep_count"]

    def test_unavailable_source_says_so_rather_than_crashing(
        self, client: TestClient
    ) -> None:
        """A source that arrives in Phase 3 is a normal condition today."""
        with client.websocket_connect(
            "/api/signal/live?source=serial&patient_id=demo"
        ) as ws:
            message = json.loads(ws.receive_text())

        assert message["type"] == "error"
        assert "Phase 3" in message["message"]

    def test_stored_reps_carry_a_quality_interval(self, client: TestClient) -> None:
        with client.websocket_connect(
            "/api/signal/live?source=simulated&patient_id=demo"
        ) as ws:
            ws.send_text(json.dumps({"type": "start"}))
            for _ in range(90):
                json.loads(ws.receive_text())
            ws.send_text(json.dumps({"type": "stop"}))
            summary = json.loads(ws.receive_text())

        reps = client.get(f"/api/sessions/{summary['session_id']}/reps").json()
        assert reps, "a minute of session should record repetitions"

        for rep in reps:
            interval = rep["quality"]
            assert interval["lower"] <= interval["point"] <= interval["upper"]
