"""M4: repetition quality scorer.

A gradient boosted regressor over per repetition features, producing a 0 to
100 score plus the single factor that most shaped it, phrased as something a
patient can act on: "your hold was steady, but you released too quickly."

Training data is synthesized rather than drawn from the cohort. Repetitions
are generated across a spread of deliberate quality levels by varying ramp
speed, hold steadiness, release abruptness and peak accuracy, and each one is
labeled by the quality that produced it. That gives the model a clean signal
to learn, and it means the scorer works from the first session rather than
waiting for a history to accumulate.

Depends on M2: without correct repetition boundaries the features describe
the wrong span of signal.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from app.ml.explain import Explanation, Interval, label_for, permutation_factors

# Features the scorer reads. Amplitude is deliberately excluded: a light
# repetition performed well should score well. This model judges execution,
# not effort.
QUALITY_FEATURES: tuple[str, ...] = (
    "time_to_peak_s",
    "rfd",
    "duration_s",
    "relaxation_time_s",
    "hold_cv",
    "plateau_flatness",
)

# Plain language for what each feature says when it dominates a score.
_FEEDBACK_GOOD = {
    "hold_cv": "your hold was steady",
    "plateau_flatness": "you held a flat, even contraction",
    "rfd": "you built up force quickly",
    "time_to_peak_s": "you reached your target promptly",
    "relaxation_time_s": "you released smoothly",
    "duration_s": "you held for the full duration",
}

_FEEDBACK_POOR = {
    "hold_cv": "your hold wavered",
    "plateau_flatness": "your contraction drifted during the hold",
    "rfd": "you built up force slowly",
    "time_to_peak_s": "you took a while to reach your target",
    "relaxation_time_s": "you released abruptly",
    "duration_s": "you cut the hold short",
}


@dataclass(frozen=True)
class RepQuality:
    """A quality score for one repetition."""

    score: Interval
    top_factor: str
    feedback: str
    explanation: Explanation

    def to_dict(self) -> dict[str, object]:
        return {
            "score": self.score.to_dict(),
            "top_factor": self.top_factor,
            "feedback": self.feedback,
            "explanation": self.explanation.to_dict(),
        }


def _synthesize_rep(
    quality: float,
    rng: np.random.Generator,
) -> dict[str, float]:
    """Build one repetition's features at a target quality level.

    quality runs 0 to 1. Each feature degrades in its own direction as
    quality falls, so the model learns which direction is good rather than
    just which magnitude.
    """
    q = float(np.clip(quality, 0.0, 1.0))
    jitter = lambda scale: float(rng.normal(0.0, scale))  # noqa: E731

    # A good repetition ramps briskly, holds steadily and flatly, and
    # releases in a controlled way over roughly a second.
    return {
        "time_to_peak_s": float(np.clip(0.5 + (1.0 - q) * 1.6 + jitter(0.12), 0.1, 4.0)),
        "rfd": float(np.clip(140.0 * q + 25.0 + jitter(14.0), 1.0, 400.0)),
        "duration_s": float(np.clip(3.0 + q * 2.6 + jitter(0.3), 0.6, 9.0)),
        "relaxation_time_s": float(
            np.clip(0.35 + q * 0.9 + jitter(0.12), 0.05, 3.0)
        ),
        "hold_cv": float(np.clip(0.30 - q * 0.26 + jitter(0.025), 0.005, 0.6)),
        "plateau_flatness": float(np.clip(0.35 + q * 0.6 + jitter(0.05), 0.0, 1.0)),
    }


def build_training_set(
    n_samples: int = 1200,
    seed: int = 0,
) -> tuple[np.ndarray, np.ndarray]:
    """Synthesize labeled repetitions across the quality range."""
    rng = np.random.default_rng(seed)
    qualities = rng.uniform(0.0, 1.0, size=n_samples)

    rows = [_synthesize_rep(q, rng) for q in qualities]
    X = np.array([[row[name] for name in QUALITY_FEATURES] for row in rows])
    y = qualities * 100.0

    return X, y


def train(seed: int = 0) -> dict[str, object]:
    """Fit the quality scorer. Returns the artifact to persist."""
    from sklearn.ensemble import HistGradientBoostingRegressor
    from sklearn.model_selection import cross_val_score

    X, y = build_training_set(seed=seed)

    model = HistGradientBoostingRegressor(
        max_depth=4,
        max_iter=150,
        learning_rate=0.1,
        random_state=seed,
    )

    scores = cross_val_score(model, X, y, cv=5, scoring="r2")
    model.fit(X, y)

    # Held back for permutation importance at explanation time.
    explain_X, explain_y = build_training_set(n_samples=300, seed=seed + 1)

    return {
        "model": model,
        "features": list(QUALITY_FEATURES),
        "cv_r2": float(scores.mean()),
        "n_rows": int(X.shape[0]),
        "explain_X": explain_X,
        "explain_y": explain_y,
    }


def score(
    rep_feature_row: dict[str, float],
    artifact: dict[str, object] | None = None,
) -> RepQuality:
    """Score one repetition.

    Falls back to a transparent rule based score when no artifact is
    available, so a session still gives feedback before the models have been
    trained.
    """
    if artifact is None:
        return _heuristic_score(rep_feature_row)

    model = artifact["model"]
    names = list(artifact["features"])  # type: ignore[arg-type]
    vector = np.array([rep_feature_row[name] for name in names], dtype=float)

    point = float(model.predict(vector.reshape(1, -1))[0])
    point = float(np.clip(point, 0.0, 100.0))

    # The interval reflects the model's own cross validated error rather than
    # a per prediction estimate, which a boosted tree does not provide
    # directly. Stated honestly in the explanation.
    cv_r2 = float(artifact.get("cv_r2", 0.8))  # type: ignore[arg-type]
    spread = max(4.0, (1.0 - cv_r2) * 60.0)

    interval = Interval(
        point=point,
        lower=point - spread,
        upper=point + spread,
        level=0.8,
    ).clamped(0.0, 100.0)

    factors = permutation_factors(
        model,
        np.asarray(artifact["explain_X"]),
        np.asarray(artifact["explain_y"]),
        names,
        top_n=3,
    )

    top = factors[0].name if factors else "hold_cv"
    feedback = _feedback_for(top, rep_feature_row, point)

    return RepQuality(
        score=interval,
        top_factor=top,
        feedback=feedback,
        explanation=Explanation(
            summary=f"Repetition scored {point:.0f} out of 100. {feedback}",
            factors=factors,
            method="permutation importance over a gradient boosted regressor",
        ),
    )


def _feedback_for(feature: str, row: dict[str, float], score_value: float) -> str:
    """Turn the dominant feature into something actionable.

    Chooses the phrasing by whether this particular repetition was good or
    poor on that feature, not by the overall score, so the sentence matches
    what the patient actually did.
    """
    good_direction = {
        "hold_cv": row.get("hold_cv", 0.2) < 0.12,
        "plateau_flatness": row.get("plateau_flatness", 0.5) > 0.7,
        "rfd": row.get("rfd", 50.0) > 90.0,
        "time_to_peak_s": row.get("time_to_peak_s", 1.5) < 1.0,
        "relaxation_time_s": row.get("relaxation_time_s", 0.5) > 0.6,
        "duration_s": row.get("duration_s", 4.0) > 4.0,
    }

    was_good = good_direction.get(feature, score_value >= 60.0)
    table = _FEEDBACK_GOOD if was_good else _FEEDBACK_POOR
    phrase = table.get(feature, f"{label_for(feature)} shaped this the most")

    return phrase[0].upper() + phrase[1:] + "."


def _heuristic_score(row: dict[str, float]) -> RepQuality:
    """Transparent fallback, used before any model has been trained."""
    steadiness = float(np.clip(1.0 - row.get("hold_cv", 0.2) / 0.3, 0.0, 1.0))
    flatness = float(np.clip(row.get("plateau_flatness", 0.5), 0.0, 1.0))
    ramp = float(np.clip(row.get("rfd", 50.0) / 150.0, 0.0, 1.0))

    point = float(np.clip((steadiness * 0.45 + flatness * 0.35 + ramp * 0.2) * 100, 0, 100))

    parts = {"hold_cv": steadiness, "plateau_flatness": flatness, "rfd": ramp}
    top = min(parts, key=parts.get)
    feedback = _feedback_for(top, row, point)

    return RepQuality(
        score=Interval(
            point=point,
            lower=max(0.0, point - 15.0),
            upper=min(100.0, point + 15.0),
            level=0.8,
        ),
        top_factor=top,
        feedback=feedback,
        explanation=Explanation(
            summary=f"Repetition scored {point:.0f} out of 100. {feedback}",
            method="heuristic fallback, no trained model available",
        ),
    )


__all__ = [
    "QUALITY_FEATURES",
    "RepQuality",
    "build_training_set",
    "score",
    "train",
]
