"""Database tables.

Six tables: Patient, Calibration, Session, Rep, Goal and InsightCache.

Two conventions run through all of them.

**Intervals persist as three columns**, never as a JSON blob. A stored
`_point` with its `_lower` and `_upper` stays queryable and chartable without
deserializing every row, and the no bare point estimates rule survives the
trip through the database rather than being reassembled at the edge.

**Session carries denormalized summary statistics.** The progress dashboard
reads whole session histories, and recomputing them from Rep rows on every
request is what would make it slow. The summary columns are written once when
a session closes. See docs/ARCHITECTURE.md.

A note on naming: `Session` here is the domain object, a rehabilitation
session. `sqlmodel.Session` is the database handle. Modules needing both
import the database one as `DbSession`. The domain name wins because the API,
the schemas and the UI all say "session", and one import alias is cheaper
than a vocabulary that does not match the product.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

from sqlmodel import Field, SQLModel

from app.clinical_gate import DEFAULT_MUSCLE


def _utcnow() -> datetime:
    """Timezone aware creation timestamp."""
    return datetime.now(timezone.utc)


class Patient(SQLModel, table=True):
    """One person using the app.

    The id is a string rather than an integer so the seeded demo account can
    be addressed as "demo" in URLs during a live demonstration.
    """

    id: str = Field(primary_key=True)
    display_name: str = ""

    # Demographics. Age band rather than age, because M14 normalizes by band
    # and storing the narrower value would be collecting more than is used.
    age_band: str | None = None
    sex: str | None = None
    injury_type: str | None = None
    injury_date: date | None = None
    dominant_hand: str | None = None

    # The unaffected side, where the patient has one. This is the honest
    # reference for a recovery target: a percentage of your own other hand
    # beats a percentage of a population norm.
    unaffected_kg: float | None = None
    goal_kg: float | None = None

    # M12's cached assignment, refreshed when the model retrains. Cached
    # rather than computed per request because the archetype only moves when
    # the trajectory does.
    archetype: str | None = None

    consent_accepted: bool = False
    created_at: datetime = Field(default_factory=_utcnow)

    # True for the seeded demo patient. Drives SyntheticBadge in the UI.
    is_synthetic: bool = False
    # Which cohort patient this was seeded from, for traceability.
    source_cohort_id: str | None = None


class Calibration(SQLModel, table=True):
    """A per user force model, fitted at calibration time.

    This is where M3 lives. docs/ML.md is explicit that the force model is
    fitted per user and persisted on the calibration row rather than trained
    against the cohort, because it maps this person's signal amplitude to
    kilograms on this electrode placement.
    """

    id: int | None = Field(default=None, primary_key=True)
    patient_id: str = Field(foreign_key="patient.id", index=True)
    created_at: datetime = Field(default_factory=_utcnow)

    # Which muscle this calibration was measured on. A maximum voluntary
    # contraction is specific to the muscle as well as the person, so a biceps
    # calibration says nothing about grip. One calibration stays active per
    # patient per muscle rather than per patient.
    muscle: str = Field(default=DEFAULT_MUSCLE, index=True)

    # The maximum voluntary contraction reference. Every percent MVC in the
    # system divides by this one number, server side. See docs/ARCHITECTURE.md.
    mvc_reference_rms: float

    # What the patient reported their reference effort was worth in kilograms.
    # Self reported, not a dynamometer reading, and labeled that way wherever
    # a force estimate is surfaced.
    reference_kg: float

    # ForceModel.to_json(). Reconstituted with ForceModel.from_json().
    force_model_json: str

    r_squared: float = 0.0
    n_points: int = 0

    # Only one calibration is active per patient per muscle. Superseded rows
    # are kept so a session can still be interpreted against the calibration in
    # force when it was recorded.
    is_active: bool = True
    is_synthetic: bool = False


class Session(SQLModel, table=True):
    """One rehabilitation session.

    Summary columns below are null until the session closes. They are written
    once, in the same transaction as the reps, so a dashboard query never
    touches the Rep table.
    """

    id: int | None = Field(default=None, primary_key=True)
    patient_id: str = Field(foreign_key="patient.id", index=True)
    calibration_id: int | None = Field(default=None, foreign_key="calibration.id")

    started_at: datetime = Field(default_factory=_utcnow, index=True)
    ended_at: datetime | None = None

    # Honesty metadata, derived from the SignalSource itself and never from
    # page copy. A simulated session cannot be presented as a live one.
    source_id: str = "simulated"
    is_live: bool = False
    is_synthetic: bool = False

    # Which muscle was trained. Phase 2 found that effort grading and fatigue
    # are properties of motor unit recruitment and so generalize to any
    # skeletal muscle, while kilograms and EWGSOP2 are validated on hand
    # dynamometry alone. This field is what gates that distinction. See
    # app/clinical_gate.py and docs/HARDWARE_FINDINGS.md.
    muscle: str = Field(default=DEFAULT_MUSCLE, index=True)

    # M8's prescription for this session, as JSON: targets plus the reasons
    # the rule engine gave for them.
    protocol_json: str | None = None

    # Borg CR10, reported by the patient after the session. M7's target.
    borg: int | None = None

    # QuickDASH. The score is only valid when at most one item is unanswered,
    # so the count is stored alongside it and validity is derived rather than
    # assumed. See docs/CLINICAL.md.
    quickdash_score: float | None = None
    quickdash_items_answered: int | None = None

    notes: str | None = None

    # Denormalized summary. Written on close.
    rep_count: int | None = None
    mean_mvc: float | None = None
    peak_mvc: float | None = None
    mean_rep_quality: float | None = None
    hold_cv_mean: float | None = None
    sqi_mean: float | None = None
    total_impulse: float | None = None
    duration_s: float | None = None

    # M5 spectral fatigue, computed once when the session closes.
    fatigue_slope: float | None = None
    fatigue_r_squared: float | None = None
    fatigue_p_value: float | None = None

    # M3's force estimate for this session, in kilograms.
    strength_kg: float | None = None

    # M6 session anomaly. Direction matters: "positive" marks an exceptional
    # session, which must never be rendered as a problem.
    anomaly_score: float | None = None
    anomaly_direction: str | None = None

    # Days since the previous completed session. Denormalized because M13 and
    # the adherence heatmap both read it across a whole history.
    adherence_gap_days: float | None = None

    @property
    def quickdash_valid(self) -> bool:
        """QuickDASH needs at least 10 of its 11 items answered."""
        if self.quickdash_items_answered is None:
            return False
        return self.quickdash_items_answered >= 10


class Rep(SQLModel, table=True):
    """One repetition within a session.

    The twelve feature columns are REP_FEATURE_KEYS from app.signal.features,
    stored flat rather than as JSON so the summary charts can query them.
    """

    id: int | None = Field(default=None, primary_key=True)
    session_id: int = Field(foreign_key="session.id", index=True)
    index: int

    # Boundaries from M2, in seconds from the start of the session.
    start_s: float
    peak_s: float
    end_s: float

    # REP_FEATURE_KEYS. duration_s appears here once, serving as both the
    # boundary derived duration and the feature of the same name.
    peak_mvc: float
    mean_mvc: float
    time_to_peak_s: float
    rfd: float
    duration_s: float
    relaxation_time_s: float
    hold_cv: float
    plateau_flatness: float
    impulse: float
    median_frequency: float
    mean_frequency: float
    dimitrov_index: float

    # M4. Three columns rather than a serialized Interval.
    quality_point: float | None = None
    quality_lower: float | None = None
    quality_upper: float | None = None
    quality_top_factor: str | None = None
    quality_feedback: str | None = None


class Goal(SQLModel, table=True):
    """A strength target with a date.

    Separate from Patient.goal_kg so that history survives an edit: a patient
    who raises their goal after reaching the first one should still be able to
    see that they reached it. Patient.goal_kg holds the active value.
    """

    id: int | None = Field(default=None, primary_key=True)
    patient_id: str = Field(foreign_key="patient.id", index=True)
    target_kg: float
    target_date: date | None = None
    created_at: datetime = Field(default_factory=_utcnow)
    achieved_at: datetime | None = None


class InsightCache(SQLModel, table=True):
    """Memoized output for the request time models.

    M9 is the reason this exists. docs/ML.md calls for memoizing it on patient
    and session count, so the key is exactly that: the cached value is valid
    until the patient completes another session, at which point the key
    changes and the forecast is refitted.
    """

    id: int | None = Field(default=None, primary_key=True)
    patient_id: str = Field(foreign_key="patient.id", index=True)
    model_id: str = Field(index=True)

    # patient_id plus completed session count, as a string.
    key: str = Field(index=True)
    payload_json: str
    created_at: datetime = Field(default_factory=_utcnow)


__all__ = [
    "Calibration",
    "Goal",
    "InsightCache",
    "Patient",
    "Rep",
    "Session",
]
