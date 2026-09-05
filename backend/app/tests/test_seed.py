"""The demo account.

The seed is what makes the app look lived in on first click, so its job is not
only to insert rows but to insert rows that make every chart show something
real.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlmodel import Session as DbSession
from sqlmodel import select

from app.db import get_engine
from app.models import Calibration, Goal, Patient, Session
from app.seed import DEMO_PATIENT_ID, seed_demo


@pytest.fixture(scope="module")
def seeded():
    seed_demo(force_reseed=True)
    with DbSession(get_engine()) as db:
        yield db


class TestDemoPatient:
    def test_is_labeled_synthetic(self, seeded: DbSession) -> None:
        patient = seeded.get(Patient, DEMO_PATIENT_ID)
        assert patient is not None
        assert patient.is_synthetic is True
        assert patient.source_cohort_id

    def test_has_a_goal_not_yet_reached(self, seeded: DbSession) -> None:
        """An already met goal makes time to goal a non question, and the
        forecast has nothing to aim at."""
        patient = seeded.get(Patient, DEMO_PATIENT_ID)
        sessions = seeded.exec(
            select(Session)
            .where(Session.patient_id == DEMO_PATIENT_ID)
            .order_by(Session.started_at)  # type: ignore[arg-type]
        ).all()

        latest = [s.strength_kg for s in sessions if s.strength_kg is not None][-1]
        assert patient.goal_kg is not None
        assert latest < patient.goal_kg

    def test_has_an_active_calibration_that_actually_fits(
        self, seeded: DbSession
    ) -> None:
        calibration = seeded.exec(
            select(Calibration).where(Calibration.patient_id == DEMO_PATIENT_ID)
        ).first()

        assert calibration is not None
        assert calibration.is_active
        # A poor fit here means the seeded features are on the wrong scale.
        assert calibration.r_squared > 0.9

    def test_records_a_goal_row(self, seeded: DbSession) -> None:
        goal = seeded.exec(
            select(Goal).where(Goal.patient_id == DEMO_PATIENT_ID)
        ).first()
        assert goal is not None


class TestDemoHistory:
    @pytest.fixture(scope="class")
    def sessions(self) -> list[Session]:
        with DbSession(get_engine()) as db:
            return list(
                db.exec(
                    select(Session)
                    .where(Session.patient_id == DEMO_PATIENT_ID)
                    .order_by(Session.started_at)  # type: ignore[arg-type]
                ).all()
            )

    def test_is_long_enough_to_forecast(self, sessions: list[Session]) -> None:
        completed = [s for s in sessions if s.rep_count is not None]
        assert len(completed) >= 20

    def test_keeps_missed_sessions_as_gaps(self, sessions: list[Session]) -> None:
        """A missed session is data: it is what the adherence heatmap draws
        and what M13 learns from."""
        missed = [s for s in sessions if s.rep_count is None]
        assert missed

    def test_ends_close_to_today(self, sessions: list[Session]) -> None:
        """The cohort carries its own absolute dates, which can sit far in the
        past. Left alone, every measure over time since the programme started
        would be wrong, and a live session would appear after a long silence.
        """
        last = sessions[-1].started_at
        last = last if last.tzinfo else last.replace(tzinfo=timezone.utc)
        days_ago = (datetime.now(timezone.utc) - last).days

        assert 0 <= days_ago <= 3, f"demo history ends {days_ago} days ago"

    def test_spans_a_plausible_programme_length(self, sessions: list[Session]) -> None:
        weeks = (sessions[-1].started_at - sessions[0].started_at).days / 7.0
        assert 4 <= weeks <= 20, f"programme spans {weeks:.1f} weeks"

    def test_shows_real_improvement(self, sessions: list[Session]) -> None:
        strengths = [s.strength_kg for s in sessions if s.strength_kg is not None]
        assert strengths[-1] > strengths[0]

    def test_every_session_is_labeled_synthetic(self, sessions: list[Session]) -> None:
        assert all(s.is_synthetic for s in sessions)

    def test_no_seeded_session_claims_to_be_live(
        self, sessions: list[Session]
    ) -> None:
        assert not any(s.is_live for s in sessions)

    def test_carries_borg_ratings_for_perceived_effort(
        self, sessions: list[Session]
    ) -> None:
        # M7 has nothing to compare without these.
        rated = [s for s in sessions if s.borg is not None]
        assert len(rated) >= 10


class TestReseed:
    def test_is_idempotent(self) -> None:
        """Seeding twice must not double the history."""
        seed_demo(force_reseed=True)
        with DbSession(get_engine()) as db:
            first = len(
                db.exec(
                    select(Session).where(Session.patient_id == DEMO_PATIENT_ID)
                ).all()
            )

        seed_demo(force_reseed=True)
        with DbSession(get_engine()) as db:
            second = len(
                db.exec(
                    select(Session).where(Session.patient_id == DEMO_PATIENT_ID)
                ).all()
            )

        assert first == second

    def test_skips_when_already_present(self) -> None:
        seed_demo(force_reseed=True)
        assert seed_demo() is None
