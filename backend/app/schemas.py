"""API response shapes.

The domain objects already know how to describe themselves: `Interval`,
`Explanation` and `Factor` in app.ml.explain each have a `to_dict`. These
schemas mirror those shapes so FastAPI can document them, and routers build
them through `from_domain` rather than assembling dictionaries by hand. One
definition of the wire format, in one place.

`PredictionOut` is the envelope every model endpoint returns. Its `degraded`
flag is the important field: when no trained artifact is on disk the models
fall back to a documented heuristic, and the UI has to be able to say so
rather than presenting heuristic output as a model result.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, model_serializer

from app.clinical_gate import DEFAULT_MUSCLE, allows_kilograms
from app.ml.explain import Explanation, Factor, Interval


class IntervalOut(BaseModel):
    """A prediction with its uncertainty. Never a bare float."""

    point: float
    lower: float
    upper: float
    level: float = 0.8
    unit: str = ""

    @classmethod
    def from_domain(cls, interval: Interval) -> IntervalOut:
        return cls(**interval.to_dict())  # type: ignore[arg-type]


class FactorOut(BaseModel):
    """One contributor to a model's output."""

    name: str
    contribution: float
    direction: str
    plain_text: str

    @classmethod
    def from_domain(cls, factor: Factor) -> FactorOut:
        return cls(**factor.to_dict())  # type: ignore[arg-type]


class ExplanationOut(BaseModel):
    """Why a model said what it said. Renders in the WhyThis drawer."""

    summary: str
    factors: list[FactorOut] = []
    method: str = ""

    @classmethod
    def from_domain(cls, explanation: Explanation) -> ExplanationOut:
        return cls(
            summary=explanation.summary,
            factors=[FactorOut.from_domain(f) for f in explanation.factors],
            method=explanation.method,
        )


class PredictionOut(BaseModel):
    """The envelope for every surfaced model output.

    `value` is model specific and stays loosely typed: an interval for M10, a
    list of changepoints for M11, a series for M9. What is uniform is the
    provenance around it, which is what the UI needs in order to be honest
    about where a number came from.
    """

    model_id: str
    value: Any
    explanation: ExplanationOut
    is_synthetic: bool = False

    # When the artifact behind this was trained. None for request time models
    # that fit fresh each call.
    trained_at: str | None = None

    # True when the heuristic fallback produced this because no trained model
    # was available. The UI must surface this rather than hide it.
    degraded: bool = False

    # Pydantic reserves the model_ prefix for its own configuration, so the
    # protected namespace is cleared to allow model_id.
    model_config = {"protected_namespaces": ()}


class PatientOut(BaseModel):
    id: str
    display_name: str
    age_band: str | None = None
    sex: str | None = None
    injury_type: str | None = None
    injury_date: date | None = None
    dominant_hand: str | None = None
    unaffected_kg: float | None = None
    goal_kg: float | None = None
    archetype: str | None = None
    consent_accepted: bool = False
    is_synthetic: bool = False

    model_config = {"from_attributes": True}


class PatientCreate(BaseModel):
    """Onboarding payload."""

    id: str = "demo"
    display_name: str = ""
    age_band: str | None = None
    sex: str | None = None
    injury_type: str | None = None
    injury_date: date | None = None
    dominant_hand: str | None = None
    unaffected_kg: float | None = None
    goal_kg: float | None = None
    consent_accepted: bool = False


class PatientUpdate(BaseModel):
    """Profile edits. Every field optional: only what is sent is changed."""

    display_name: str | None = None
    age_band: str | None = None
    sex: str | None = None
    injury_type: str | None = None
    injury_date: date | None = None
    dominant_hand: str | None = None
    unaffected_kg: float | None = None
    goal_kg: float | None = None
    consent_accepted: bool | None = None


class SessionSummaryOut(BaseModel):
    """One session as the dashboard sees it.

    These are exactly the denormalized columns on the Session row, so a list
    of these costs one query and never touches the Rep table.
    """

    id: int
    patient_id: str
    started_at: datetime
    ended_at: datetime | None = None
    source_id: str
    is_live: bool
    is_synthetic: bool
    muscle: str = DEFAULT_MUSCLE

    borg: int | None = None
    quickdash_score: float | None = None
    quickdash_valid: bool = False

    rep_count: int | None = None
    mean_mvc: float | None = None
    peak_mvc: float | None = None
    mean_rep_quality: float | None = None
    hold_cv_mean: float | None = None
    sqi_mean: float | None = None
    total_impulse: float | None = None
    duration_s: float | None = None

    fatigue_slope: float | None = None
    fatigue_r_squared: float | None = None
    fatigue_p_value: float | None = None

    strength_kg: float | None = None
    anomaly_score: float | None = None
    anomaly_direction: str | None = None
    adherence_gap_days: float | None = None

    model_config = {"from_attributes": True}

    @model_serializer(mode="wrap")
    def _gate_kilograms(self, handler):  # type: ignore[no-untyped-def]
        """Drop strength_kg entirely on a non grip muscle.

        Omitted rather than nulled, deliberately. A null still occupies the
        field and a UI that renders a stale value into it would be making a
        clinical claim the measurement does not support. An absent key cannot
        be rendered at all. See app/clinical_gate.py.
        """
        data = handler(self)
        if not allows_kilograms(self.muscle):
            data.pop("strength_kg", None)
        return data


class RepOut(BaseModel):
    """One repetition, with its M4 score as an interval."""

    id: int
    session_id: int
    index: int
    start_s: float
    peak_s: float
    end_s: float

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

    quality: IntervalOut | None = None
    quality_top_factor: str | None = None
    quality_feedback: str | None = None

    model_config = {"from_attributes": True}


class SessionDetailOut(BaseModel):
    """A session with its repetitions."""

    session: SessionSummaryOut
    reps: list[RepOut] = []


class CalibrationOut(BaseModel):
    id: int
    patient_id: str
    created_at: datetime
    muscle: str = DEFAULT_MUSCLE
    mvc_reference_rms: float
    reference_kg: float
    r_squared: float
    n_points: int
    is_active: bool
    is_synthetic: bool

    model_config = {"from_attributes": True}


class CalibrationRequest(BaseModel):
    """A calibration trial.

    `feature_rows` are amplitude feature dictionaries, one per held
    contraction. `reference_kg` is what the patient reports that effort is
    worth. Self reported, and labeled as such wherever the estimate surfaces.
    """

    patient_id: str
    feature_rows: list[dict[str, float]]
    reference_kg: float
    mvc_reference_rms: float

    # A maximum voluntary contraction belongs to a muscle as well as a person,
    # so calibrations are held one per patient per muscle.
    muscle: str = DEFAULT_MUSCLE


class SourceOut(BaseModel):
    """A signal source, as the settings page renders it.

    `is_live` is what drives the honesty chip. It comes from the source
    catalogue, never from page copy.
    """

    id: str
    label: str
    is_live: bool
    available: bool
    note: str


class BorgRequest(BaseModel):
    """Borg CR10 rating of perceived exertion, 0 to 10."""

    borg: int


class QuickDashRequest(BaseModel):
    """QuickDASH submission.

    The item count travels with the score because the instrument is only
    scoreable when at most one of its eleven items is missing.
    """

    score: float
    items_answered: int


class QuickDashOut(BaseModel):
    score: float
    items_answered: int
    valid: bool
    note: str = ""


class GoalOut(BaseModel):
    target_kg: float | None = None
    target_date: date | None = None
    current_kg: float | None = None
    baseline_kg: float | None = None
    progress_pct: float | None = None
    achieved: bool = False


class ModelRecordOut(BaseModel):
    """Provenance for one trained artifact, for the Responsible AI page."""

    model_id: str
    version: str
    trained_at: str
    metric_name: str
    metric_value: float
    cohort_version: str
    n_training_rows: int
    notes: str = ""

    model_config = {"protected_namespaces": ()}


__all__ = [
    "BorgRequest",
    "CalibrationOut",
    "CalibrationRequest",
    "ExplanationOut",
    "FactorOut",
    "GoalOut",
    "IntervalOut",
    "ModelRecordOut",
    "PatientCreate",
    "PatientOut",
    "PatientUpdate",
    "PredictionOut",
    "QuickDashOut",
    "QuickDashRequest",
    "RepOut",
    "SessionDetailOut",
    "SessionSummaryOut",
    "SourceOut",
]
