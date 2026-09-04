"""M1: Signal Quality Index.

A logistic regression over window features producing a 0 to 100 score for how
much the current signal can be trusted.

This is the project's integrity feature. It exists to tell the user when not
to believe the reading, which matters most with a cheap electrode setup where
a loose lead or a dry pad quietly degrades everything downstream. When
quality is poor the app says so and withholds conclusions rather than
manufacturing confidence.

Training data comes from sweeping the generator's junkiness dial, so M1
needs no cohort: clean and contaminated signals are produced on demand and
labeled by the junkiness that produced them.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from app.ml.explain import Explanation, Interval, coefficient_factors
from app.signal.features import WINDOW_FEATURE_KEYS, window_features

# The subset of window features that describe integrity rather than effort.
# Amplitude features are deliberately excluded: a quiet signal is not a bad
# signal, it is a resting one, and including them would make the model
# score rest as poor quality.
SQI_FEATURES: tuple[str, ...] = (
    "saturation_ratio",
    "baseline_drift",
    "mains_ratio",
    "snr_estimate",
)

# Junkiness at or below this is treated as a good signal during training,
# and at or above the second as poor. The gap is left out so the classifier
# learns from unambiguous examples.
#
# The good threshold is low because the artifact features saturate quickly:
# by a junkiness of about 0.15 the mains ratio in a resting window has
# already gone from 0.06 to 0.58, so labelling anything above that as good
# trains the model on contradictory examples.
_GOOD_BELOW = 0.05
_POOR_ABOVE = 0.35

# Quality bands, mapped to the letter tiers the hardware bring up uses.
QUALITY_BANDS = (
    (80.0, "A", "Good", "Clean signal. Readings are trustworthy."),
    (60.0, "B", "Usable", "Some interference. Readings are broadly reliable."),
    (35.0, "C", "Poor", "Heavy interference. Treat readings with caution."),
    (0.0, "D", "Unusable", "Signal is not usable. Check the electrodes."),
)


@dataclass(frozen=True)
class QualityAssessment:
    """A quality score with its band and explanation."""

    score: Interval
    band: str
    band_label: str
    advice: str
    explanation: Explanation
    trustworthy: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "score": self.score.to_dict(),
            "band": self.band,
            "band_label": self.band_label,
            "advice": self.advice,
            "trustworthy": self.trustworthy,
            "explanation": self.explanation.to_dict(),
        }


def band_for(score: float) -> tuple[str, str, str]:
    """Letter band, label, and advice for a score."""
    for threshold, band, label, advice in QUALITY_BANDS:
        if score >= threshold:
            return band, label, advice
    return QUALITY_BANDS[-1][1:]


def _feature_vector(features: dict[str, float]) -> np.ndarray:
    return np.array([features[key] for key in SQI_FEATURES], dtype=float)


def build_training_set(
    n_per_level: int = 40,
    seed: int = 0,
) -> tuple[np.ndarray, np.ndarray]:
    """Generate labeled windows by sweeping the junkiness dial.

    Returns a feature matrix and binary labels, where 1 means good quality.
    """
    from app.sim.signal_gen import SyntheticEmgGenerator, make_protocol

    rng = np.random.default_rng(seed)
    rows: list[np.ndarray] = []
    labels: list[int] = []

    levels = np.concatenate(
        [
            np.linspace(0.0, _GOOD_BELOW, 6),
            np.linspace(_POOR_ABOVE, 1.0, 6),
        ]
    )

    window = 200

    for level in levels:
        generator = SyntheticEmgGenerator(
            sample_rate=1000,
            seed=int(rng.integers(0, 1_000_000)),
            junkiness=float(level),
        )
        session = generator.build_session(make_protocol(reps=3))
        trace = session.samples

        # Contamination is most visible between contractions. During a hard
        # contraction the EMG itself swamps the hum, so a window taken at the
        # peak looks clean at almost any junkiness. Sampling mostly from rest
        # is what gives the classifier a separable problem, and it matches
        # how the badge is read in practice: quality is judged from the
        # quiet stretches, not mid squeeze.
        rest_starts = _rest_windows(session, window)

        for _ in range(n_per_level):
            if rest_starts.size and rng.random() < 0.75:
                start = int(rng.choice(rest_starts))
            else:
                start = int(rng.integers(0, max(1, trace.size - window)))

            features = window_features(trace[start : start + window], 1000)
            rows.append(_feature_vector(features))
            labels.append(1 if level <= _GOOD_BELOW else 0)

    return np.vstack(rows), np.array(labels)


def _rest_windows(session, window: int) -> np.ndarray:
    """Start indices of windows that fall between contractions."""
    fs = session.sample_rate
    occupied = np.zeros(session.samples.size, dtype=bool)
    for rep in session.reps:
        occupied[int(rep.start_s * fs) : int(rep.end_s * fs)] = True

    candidates = []
    for start in range(0, session.samples.size - window, window // 2):
        if not occupied[start : start + window].any():
            candidates.append(start)

    return np.array(candidates, dtype=int)


def train(seed: int = 0) -> dict[str, object]:
    """Fit the quality classifier. Returns the artifact to persist."""
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import cross_val_score
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler

    X, y = build_training_set(seed=seed)

    pipeline = Pipeline(
        [
            ("scale", StandardScaler()),
            ("model", LogisticRegression(max_iter=1000, random_state=seed)),
        ]
    )

    scores = cross_val_score(pipeline, X, y, cv=5, scoring="accuracy")
    pipeline.fit(X, y)

    return {
        "pipeline": pipeline,
        "features": list(SQI_FEATURES),
        "cv_accuracy": float(scores.mean()),
        "n_rows": int(X.shape[0]),
    }


def assess(
    samples: np.ndarray,
    sample_rate: int,
    artifact: dict[str, object] | None = None,
) -> QualityAssessment:
    """Score one window of raw signal.

    Falls back to a transparent heuristic when no trained artifact is
    available, so the quality badge is never blank. The badge is meant to be
    permanently visible, and a missing model is not a reason to imply the
    signal is fine.
    """
    features = window_features(np.asarray(samples, dtype=float), sample_rate)

    if artifact is None:
        return _heuristic_assessment(features)

    pipeline = artifact["pipeline"]
    feature_names = list(artifact["features"])  # type: ignore[arg-type]
    vector = np.array([features[key] for key in feature_names], dtype=float)

    probability = float(pipeline.predict_proba(vector.reshape(1, -1))[0, 1])
    score = probability * 100.0

    # The interval reflects how close the classifier is to its own decision
    # boundary: a confident call is a narrow one.
    confidence = abs(probability - 0.5) * 2.0
    half_width = (1.0 - confidence) * 18.0

    interval = Interval(
        point=score,
        lower=score - half_width,
        upper=score + half_width,
        level=0.8,
        unit="",
    ).clamped(0.0, 100.0)

    band, label, advice = band_for(score)

    # Explain from the scaled coefficients against this window's values, so
    # the factors describe what drove this particular reading.
    model = pipeline.named_steps["model"]
    scaler = pipeline.named_steps["scale"]
    scaled = scaler.transform(vector.reshape(1, -1))[0]
    factors = coefficient_factors(
        model.coef_[0], feature_names, feature_values=scaled, top_n=3
    )

    return QualityAssessment(
        score=interval,
        band=band,
        band_label=label,
        advice=advice,
        explanation=Explanation(
            summary=f"Signal quality {score:.0f} out of 100 ({label.lower()}).",
            factors=factors,
            method="logistic regression coefficients",
        ),
        trustworthy=score >= 60.0,
    )


def _heuristic_assessment(features: dict[str, float]) -> QualityAssessment:
    """Transparent fallback when no artifact has been trained.

    Deliberately simple and stated as such, rather than pretending a model
    is running.
    """
    penalties = {
        "mains_ratio": min(features["mains_ratio"] * 220.0, 45.0),
        "saturation_ratio": min(features["saturation_ratio"] * 160.0, 35.0),
        "baseline_drift": min(features["baseline_drift"] * 22.0, 30.0),
    }
    score = float(np.clip(100.0 - sum(penalties.values()), 0.0, 100.0))
    band, label, advice = band_for(score)

    worst = max(penalties, key=penalties.get)
    factors = coefficient_factors(
        [-penalties[key] for key in penalties],
        list(penalties),
        top_n=2,
    )

    return QualityAssessment(
        score=Interval(
            point=score,
            lower=max(0.0, score - 15.0),
            upper=min(100.0, score + 15.0),
            level=0.8,
        ),
        band=band,
        band_label=label,
        advice=advice,
        explanation=Explanation(
            summary=(
                f"Signal quality {score:.0f} out of 100 ({label.lower()}), "
                f"driven mainly by {worst.replace('_', ' ')}."
            ),
            factors=factors,
            method="heuristic fallback, no trained model available",
        ),
        trustworthy=score >= 60.0,
    )


__all__ = [
    "QUALITY_BANDS",
    "QualityAssessment",
    "SQI_FEATURES",
    "assess",
    "band_for",
    "build_training_set",
    "train",
]
