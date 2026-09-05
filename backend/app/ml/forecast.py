"""M9: recovery trajectory forecasting. The centerpiece.

Three candidate models are fitted to a patient's strength history and the
winner is chosen by cross validated error:

- a linear trend, as the baseline,
- an exponential plateau, a + (b - a) * (1 - exp(-k * t)), which is the
  physiologically realistic shape for rehabilitation and usually wins,
- a Gaussian process with an RBF plus linear kernel, which gives a principled
  uncertainty band.

**Selection uses expanding window cross validation.** Shuffled cross
validation leaks the future into the past and flatters the linear model, so it
is never used here. Each fold trains on a prefix and tests on what comes next,
which is the question actually being asked: given what we knew then, what
happened after?

The eighty percent band comes from the GP posterior when the GP wins, and from
residual bootstrap for the parametric winners, so the fan chart exists
whichever model is selected.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

# Below this many sessions there is not enough history to fit anything
# meaningful. Returning "not yet" is more honest than a curve through three
# points that will be revised beyond recognition next week.
MIN_SESSIONS = 5

# How many bootstrap resamples build the band for a parametric winner.
N_BOOTSTRAP = 200


@dataclass(frozen=True)
class ForecastPoint:
    """One step of the projection."""

    week: float
    point: float
    lower: float
    upper: float

    def to_dict(self) -> dict[str, float]:
        return {
            "week": round(self.week, 2),
            "point": round(self.point, 2),
            "lower": round(self.lower, 2),
            "upper": round(self.upper, 2),
        }


@dataclass(frozen=True)
class TrajectoryForecast:
    """A patient's projected recovery, with the evidence for the choice."""

    winner: str
    forecast: list[ForecastPoint]
    cv_table: dict[str, float]
    history: list[float] = field(default_factory=list)
    insufficient_data: bool = False
    # Draws from the fitted posterior, which M10 samples for goal crossing.
    draws: np.ndarray | None = None
    explanation: object | None = None

    def to_dict(self) -> dict[str, object]:
        from app.ml.explain import Explanation

        explanation = (
            self.explanation.to_dict()
            if isinstance(self.explanation, Explanation)
            else None
        )
        return {
            "winner": self.winner,
            "forecast": [p.to_dict() for p in self.forecast],
            "cv_table": {k: round(v, 4) for k, v in self.cv_table.items()},
            "history": [round(v, 2) for v in self.history],
            "insufficient_data": self.insufficient_data,
            "explanation": explanation,
        }


def _exponential_plateau(t: np.ndarray, a: float, b: float, k: float) -> np.ndarray:
    """Rapid early gains that saturate. The rehabilitation shape."""
    return a + (b - a) * (1.0 - np.exp(-k * t))


def _fit_linear(t: np.ndarray, y: np.ndarray):
    coefficients = np.polyfit(t, y, 1)
    return lambda x: np.polyval(coefficients, x)


def _fit_plateau(t: np.ndarray, y: np.ndarray):
    from scipy.optimize import curve_fit

    # Start from the observed range, which keeps the optimiser well behaved.
    p0 = [float(y[0]), float(y.max()), 0.2]
    bounds = ([-np.inf, -np.inf, 1e-4], [np.inf, np.inf, 5.0])

    params, _ = curve_fit(
        _exponential_plateau, t, y, p0=p0, bounds=bounds, maxfev=10000
    )
    return lambda x: _exponential_plateau(np.asarray(x, dtype=float), *params)


def _fit_gp(t: np.ndarray, y: np.ndarray):
    import warnings

    from sklearn.exceptions import ConvergenceWarning
    from sklearn.gaussian_process import GaussianProcessRegressor
    from sklearn.gaussian_process.kernels import RBF, DotProduct, WhiteKernel

    kernel = DotProduct() + RBF(length_scale=5.0) + WhiteKernel(noise_level=1.0)
    model = GaussianProcessRegressor(kernel=kernel, normalize_y=True, random_state=0)

    # On a clean series the optimiser drives the noise term to its bound and
    # says so. That is the correct answer for near noiseless data, not a
    # problem to report, and it fires on every fold of every fit.
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", ConvergenceWarning)
        model.fit(t.reshape(-1, 1), y)

    return model


CANDIDATES = ("linear", "exponential_plateau", "gaussian_process")

WINNER_LABELS = {
    "linear": "a straight line",
    "exponential_plateau": "a levelling off curve",
    "gaussian_process": "a flexible curve",
}


def _cross_validate(t: np.ndarray, y: np.ndarray) -> dict[str, float]:
    """Expanding window cross validation.

    Never shuffled: each fold trains on a prefix of the history and tests on
    what came next. Shuffling would let a model see the future while
    predicting the past, which flatters the linear fit above all.
    """
    from sklearn.model_selection import TimeSeriesSplit

    n_splits = int(min(5, max(2, len(t) - 3)))
    splitter = TimeSeriesSplit(n_splits=n_splits)

    errors: dict[str, list[float]] = {name: [] for name in CANDIDATES}

    for train_idx, test_idx in splitter.split(t):
        t_train, y_train = t[train_idx], y[train_idx]
        t_test, y_test = t[test_idx], y[test_idx]

        if len(t_train) < 3:
            continue

        for name in CANDIDATES:
            try:
                if name == "linear":
                    predict = _fit_linear(t_train, y_train)
                    predicted = predict(t_test)
                elif name == "exponential_plateau":
                    predict = _fit_plateau(t_train, y_train)
                    predicted = predict(t_test)
                else:
                    model = _fit_gp(t_train, y_train)
                    predicted = model.predict(t_test.reshape(-1, 1))

                errors[name].append(float(np.mean(np.abs(y_test - predicted))))
            except Exception:  # noqa: BLE001
                # A candidate that will not converge on this history is simply
                # not eligible to win it.
                errors[name].append(float("inf"))

    return {
        name: float(np.mean(values)) if values else float("inf")
        for name, values in errors.items()
    }


def fit_trajectory(
    strengths: list[float] | np.ndarray,
    *,
    horizon_weeks: int = 12,
    sessions_per_week: float = 2.5,
) -> TrajectoryForecast:
    """Fit and project a patient's recovery trajectory."""
    from app.ml.explain import Explanation, Factor

    y = np.asarray(strengths, dtype=float)
    y = y[np.isfinite(y)]

    if y.size < MIN_SESSIONS:
        return TrajectoryForecast(
            winner="none",
            forecast=[],
            cv_table={},
            history=y.tolist(),
            insufficient_data=True,
            explanation=Explanation(
                summary=(
                    f"A projection needs at least {MIN_SESSIONS} completed "
                    "sessions. A curve through fewer points would move too "
                    "much to be worth showing."
                ),
                method="not fitted",
            ),
        )

    # Time in weeks, which is what the forecast is reported in.
    t = np.arange(y.size, dtype=float) / sessions_per_week

    cv_table = _cross_validate(t, y)
    winner = min(cv_table, key=lambda name: cv_table[name])

    future = np.arange(1, horizon_weeks + 1, dtype=float) + t[-1]

    if winner == "gaussian_process":
        model = _fit_gp(t, y)
        mean, sd = model.predict(future.reshape(-1, 1), return_std=True)
        # 80 percent interval from the posterior directly.
        lower, upper = mean - 1.28 * sd, mean + 1.28 * sd
        draws = model.sample_y(future.reshape(-1, 1), n_samples=400, random_state=0).T
    else:
        fitter = _fit_linear if winner == "linear" else _fit_plateau
        predict = fitter(t, y)
        mean = np.asarray(predict(future), dtype=float)

        # Residual bootstrap: resample the fit's own errors, refit, re-predict.
        # This is what gives a parametric winner an honest band.
        residuals = y - np.asarray(predict(t), dtype=float)
        rng = np.random.default_rng(0)
        samples = []
        for _ in range(N_BOOTSTRAP):
            resampled = y + rng.choice(residuals, size=y.size, replace=True)
            try:
                samples.append(np.asarray(fitter(t, resampled)(future), dtype=float))
            except Exception:  # noqa: BLE001
                continue

        draws = np.array(samples) if samples else mean.reshape(1, -1)
        lower = np.percentile(draws, 10, axis=0)
        upper = np.percentile(draws, 90, axis=0)

    forecast = [
        ForecastPoint(
            week=float(future[i] - t[-1]),
            point=float(mean[i]),
            # The band must contain the point even when a resample is skewed.
            lower=float(min(lower[i], mean[i])),
            upper=float(max(upper[i], mean[i])),
        )
        for i in range(len(future))
    ]

    finite = {k: v for k, v in cv_table.items() if np.isfinite(v)}
    factors = [
        Factor(
            name=name,
            contribution=-value,
            direction="neutral",
            plain_text=f"{WINNER_LABELS[name]} was out by {value:.2f} kg on average",
        )
        for name, value in sorted(finite.items(), key=lambda kv: kv[1])
    ]

    return TrajectoryForecast(
        winner=winner,
        forecast=forecast,
        cv_table=cv_table,
        history=y.tolist(),
        draws=draws,
        explanation=Explanation(
            summary=(
                f"Your history is best described by {WINNER_LABELS[winner]}, "
                f"which predicted held out sessions to within "
                f"{cv_table[winner]:.2f} kg. The shaded band is where the next "
                "few weeks are most likely to fall."
            ),
            factors=factors,
            method=(
                "three candidate curves compared by expanding window cross "
                "validation, never shuffled"
            ),
        ),
    )


__all__ = [
    "CANDIDATES",
    "MIN_SESSIONS",
    "ForecastPoint",
    "TrajectoryForecast",
    "fit_trajectory",
]
