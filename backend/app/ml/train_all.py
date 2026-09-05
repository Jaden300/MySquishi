"""Train every build time model and persist it to the registry.

Run from the backend directory:

    .venv/bin/python -m app.ml.train_all
    .venv/bin/python -m app.ml.train_all --force

Seven models are trained here, the ones docs/ML.md marks as cohort trained:
M1, M4, M6, M7, M12, M13 and M14. The rest fit per session or per request and
deliberately have no artifact: M2 is deterministic, M3 is fitted per user at
calibration and stored on the calibration row, and M5 and M8 through M11 are
cheap enough to fit on the request.

Until this runs, the registry is empty and M1 and M4 silently fall back to
their heuristic paths. That fallback is honest but weaker, and it is meant as
a degraded mode rather than the normal one, so this is part of setup rather
than an optional step.

The whole run stays under a minute, which is the budget docs/ML.md sets.
"""

from __future__ import annotations

import argparse
import time
from typing import Callable

from app.ml.registry import registry
from app.sim.cohort_gen import COHORT_VERSION


class Step:
    """One model's training step.

    Cohort loading is deferred behind a callable so that M1 and M4, which do
    not need the cohort, are not made to wait for it.
    """

    def __init__(
        self,
        model_id: str,
        name: str,
        metric_name: str,
        notes: str,
        needs_cohort: bool,
        run: Callable[..., dict[str, object]],
    ) -> None:
        self.model_id = model_id
        self.name = name
        self.metric_name = metric_name
        self.notes = notes
        self.needs_cohort = needs_cohort
        self.run = run


def _steps() -> list[Step]:
    """The training plan, in dependency order.

    Imports are local so that a model still under construction cannot break
    the whole run at import time.
    """
    from app.ml import quality, rep_quality

    steps: list[Step] = [
        Step(
            model_id="M1",
            name="signal quality index",
            metric_name="cv_accuracy",
            notes=(
                "Trained on the generator's junkiness sweep rather than the "
                "cohort, so signal quality needs no patient history."
            ),
            needs_cohort=False,
            run=lambda seed: quality.train(seed=seed),
        ),
        Step(
            model_id="M4",
            name="repetition quality scorer",
            metric_name="cv_r2",
            notes=(
                "Trained on synthesized repetitions across the quality range, "
                "so scoring works from the first session."
            ),
            needs_cohort=False,
            run=lambda seed: rep_quality.train(seed=seed),
        ),
    ]

    # Cohort trained models. Each is appended only once its module exists, so
    # this file stays runnable while the remaining slices land.
    steps.extend(_cohort_steps())
    return steps


def _cohort_steps() -> list[Step]:
    """Models that train against the synthetic cohort.

    M12 comes first: its archetype assignment is reference context for the
    models after it.
    """
    steps: list[Step] = []

    specs = (
        ("M12", "archetype", "recovery archetype clustering", "silhouette"),
        ("M6", "anomaly", "session anomaly detection", "contamination"),
        ("M7", "perceived", "perceived versus actual effort", "cv_r2"),
        ("M13", "adherence", "adherence and dropout risk", "cv_auc"),
        ("M14", "percentile", "cohort percentile normalization", "n_reference"),
    )

    for model_id, module_name, label, metric_name in specs:
        try:
            module = __import__(f"app.ml.{module_name}", fromlist=["train"])
        except ImportError:
            # Not yet implemented. Skipped rather than fatal, so the spine
            # stays runnable while the model slices land.
            continue

        steps.append(
            Step(
                model_id=model_id,
                name=label,
                metric_name=metric_name,
                notes=getattr(module, "TRAINING_NOTES", ""),
                needs_cohort=True,
                run=module.train,
            )
        )

    return steps


def train_all(*, seed: int = 0, force: bool = False) -> dict[str, object]:
    """Train and persist every build time model.

    Returns a report per model, so a test can assert on it rather than
    scraping stdout.
    """
    steps = _steps()
    report: dict[str, object] = {}

    cohort = None
    summary = None
    started = time.perf_counter()

    for step in steps:
        if not force and not registry.is_stale(step.model_id):
            print(f"  {step.model_id} {step.name}: already current, skipping")
            report[step.model_id] = {"status": "skipped"}
            continue

        if step.needs_cohort and cohort is None:
            from app.sim.cohort_gen import load_or_generate, patient_summary

            print("  loading cohort ...")
            cohort = load_or_generate()
            summary = patient_summary(cohort)
            print(f"  cohort: {len(cohort)} sessions, {len(summary)} patients")

        t0 = time.perf_counter()
        if step.needs_cohort:
            artifact = step.run(cohort, summary=summary, seed=seed)
        else:
            artifact = step.run(seed=seed)
        elapsed = time.perf_counter() - t0

        metric_value = float(artifact.get(step.metric_name, 0.0))  # type: ignore[arg-type]
        n_rows = int(artifact.get("n_rows", 0))  # type: ignore[arg-type]

        registry.save(
            step.model_id,
            artifact,
            metric_name=step.metric_name,
            metric_value=metric_value,
            cohort_version=COHORT_VERSION if step.needs_cohort else "n/a",
            n_training_rows=n_rows,
            notes=step.notes,
        )

        print(
            f"  {step.model_id} {step.name}: "
            f"{step.metric_name}={metric_value:.4f} "
            f"n={n_rows} ({elapsed:.1f}s)"
        )
        report[step.model_id] = {
            "status": "trained",
            "metric_name": step.metric_name,
            "metric_value": metric_value,
            "n_rows": n_rows,
            "seconds": round(elapsed, 2),
        }

    total = time.perf_counter() - started
    print(f"\nDone in {total:.1f}s. Artifacts in {registry.directory}")
    report["_seconds"] = round(total, 2)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Train MySquishi's build time models.")
    parser.add_argument(
        "--force",
        action="store_true",
        help="retrain every model, even ones already current",
    )
    parser.add_argument("--seed", type=int, default=0, help="training seed")
    args = parser.parse_args()

    print("Training MySquishi models\n")
    train_all(seed=args.seed, force=args.force)


if __name__ == "__main__":
    main()
