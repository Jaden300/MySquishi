"""The muscle gate: which claims are honest for which muscle.

This is a clinical rule rather than a preference, so it is tested at the
boundary the UI actually sees. Phase 2 found effort and fatigue generalize to
any skeletal muscle while kilograms and EWGSOP2 do not, and these tests are
what stop that distinction eroding. See docs/HARDWARE_FINDINGS.md.
"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app.clinical_gate import (
    GRIP,
    MUSCLES,
    allows_kilograms,
    is_grip,
    normalize,
)
from app.main import app
from app.schemas import SessionSummaryOut


@pytest.fixture(scope="module")
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client


class TestNormalization:
    def test_known_muscles_pass_through(self) -> None:
        for muscle in MUSCLES:
            assert normalize(muscle) == muscle

    def test_missing_muscle_defaults_to_grip(self) -> None:
        """A session recorded before the selector existed was a grip session,
        so this default is also correct for old rows."""
        assert normalize(None) == GRIP
        assert normalize("") == GRIP

    def test_unknown_muscle_becomes_other(self) -> None:
        """The honest response to an unrecognised site is to withhold the grip
        only claims, which is exactly what "other" does."""
        assert normalize("tentacle") == "other"
        assert not allows_kilograms("tentacle")

    def test_case_and_padding_are_tolerated(self) -> None:
        assert normalize("  Biceps  ") == "biceps"


class TestWhichClaimsAreAllowed:
    def test_only_grip_allows_kilograms(self) -> None:
        assert is_grip(GRIP)
        assert allows_kilograms(GRIP)

        for muscle in ("biceps", "calf", "other"):
            assert not is_grip(muscle)
            assert not allows_kilograms(muscle)


class TestSerializationOmitsRatherThanNulls:
    """A null still occupies the field, and a UI that rendered a stale value
    into it would be making a claim the measurement does not support. An
    absent key cannot be rendered at all."""

    def _summary(self, muscle: str, strength_kg: float | None) -> dict:
        payload = SessionSummaryOut(
            id=1,
            patient_id="demo",
            started_at="2026-09-05T12:00:00Z",
            source_id="simulated",
            is_live=False,
            is_synthetic=True,
            muscle=muscle,
            strength_kg=strength_kg,
        )
        return json.loads(payload.model_dump_json())

    def test_grip_keeps_kilograms(self) -> None:
        body = self._summary(GRIP, 31.4)
        assert body["strength_kg"] == 31.4

    def test_non_grip_omits_the_field_entirely(self) -> None:
        for muscle in ("biceps", "calf", "other"):
            body = self._summary(muscle, 31.4)
            assert "strength_kg" not in body, (
                f"{muscle} leaked a kilogram figure"
            )

    def test_muscle_agnostic_fields_survive(self) -> None:
        """Percent MVC, fatigue and rep counts are valid on every muscle and
        must not be collateral damage from the gate."""
        body = self._summary("biceps", None)
        for key in ("mean_mvc", "peak_mvc", "rep_count", "fatigue_slope"):
            assert key in body


class TestPercentileIsGripOnly:
    def test_grip_patient_gets_a_percentile(self, client: TestClient) -> None:
        """The seeded demo patient trains grip, so the reference comparison is
        valid and the endpoint answers."""
        response = client.get("/api/ml/percentile/demo")
        assert response.status_code == 200

        body = response.json()
        assert body["model_id"] == "M14"

    def test_non_grip_session_yields_no_percentile(
        self, client: TestClient
    ) -> None:
        """A patient with only biceps sessions has nothing to place against a
        hand dynamometry reference, and the refusal explains why."""
        client.post(
            "/api/patients",
            json={"id": "biceps-only", "display_name": "Biceps only"},
        )

        with client.websocket_connect(
            "/api/signal/live?source=simulated&patient_id=biceps-only&muscle=biceps"
        ) as ws:
            ws.send_text(json.dumps({"type": "start"}))
            for _ in range(60):
                json.loads(ws.receive_text())
            ws.send_text(json.dumps({"type": "stop"}))
            summary = json.loads(ws.receive_text())

        assert summary["muscle"] == "biceps"

        response = client.get("/api/ml/percentile/biceps-only")
        assert response.status_code == 404
        assert "grip" in response.json()["detail"].lower()

    def test_no_kilograms_or_ewgsop2_wording_reaches_a_biceps_session(
        self, client: TestClient
    ) -> None:
        """Gating structured fields is not enough on its own: the percentile
        explanation embeds kilogram figures and EWGSOP2 language in prose, and
        that prose must not reach a muscle the reference does not cover."""
        sessions = client.get("/api/sessions?patient_id=biceps-only").json()
        assert sessions, "the biceps session should have been stored"

        for session in sessions:
            assert session["muscle"] == "biceps"
            assert "strength_kg" not in session

        insights = client.get("/api/ml/insights/biceps-only").json()
        blob = json.dumps(insights).lower()
        assert "ewgsop2" not in blob
        assert " kg" not in blob


class TestCalibrationIsPerMuscle:
    def test_calibrating_one_muscle_leaves_another_active(
        self, client: TestClient
    ) -> None:
        """A maximum voluntary contraction belongs to the muscle as well as
        the person, so calibrating a biceps must not retire the grip
        calibration a kilogram estimate depends on."""
        client.post(
            "/api/patients", json={"id": "two-muscle", "display_name": "Two muscle"}
        )

        rows = [
            {"rms": 0.30, "mav": 0.24, "waveform_length": 30.0},
            {"rms": 0.60, "mav": 0.48, "waveform_length": 60.0},
            {"rms": 0.90, "mav": 0.72, "waveform_length": 90.0},
        ]

        for muscle, reference_kg in (("forearm_grip", 30.0), ("biceps", 18.0)):
            response = client.post(
                "/api/signal/calibrate",
                json={
                    "patient_id": "two-muscle",
                    "feature_rows": rows,
                    "reference_kg": reference_kg,
                    "mvc_reference_rms": 0.9,
                    "muscle": muscle,
                },
            )
            assert response.status_code == 200, response.text

        grip = client.get(
            "/api/signal/calibration?patient_id=two-muscle&muscle=forearm_grip"
        ).json()
        biceps = client.get(
            "/api/signal/calibration?patient_id=two-muscle&muscle=biceps"
        ).json()

        assert grip is not None and biceps is not None
        assert grip["muscle"] == "forearm_grip"
        assert biceps["muscle"] == "biceps"
        assert grip["id"] != biceps["id"]
        assert grip["reference_kg"] == 30.0
