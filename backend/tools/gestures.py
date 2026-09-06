"""Structured gesture survey for the MyoWare rig.

The graded probe in tools/probe.py answers one question: is this rig good
enough, and for what. This script answers a different one: which hand poses
can a single differential channel actually tell apart?

Three things are deliberately different from the graded protocol.

First, every pose gets a countdown before its window opens, so the seconds
spent reading the prompt land in the lead in rather than in the measurement.
The graded protocol prints its prompt and starts timing in the same instant,
which pushes the first second or two of every window into whatever the wearer
was doing while reading. On a five second window that is a large fraction of
the sample, and it depresses exactly the light effort levels that the
separability score depends on.

Second, poses are held for eight seconds rather than five, and the first and
last 1.5 seconds of every window are trimmed before measuring, so ramping in
and relaxing out do not count as the pose.

Third, the survey is ordered so no two maximal efforts sit next to each other.
Grip strength falls measurably across repeated maximal contractions, and an
unrested hard squeeze measured against a faint light squeeze cannot separate.

Nothing here writes a tier. Pose to pose separability is the output, and
tools/probe.py remains the only thing that grades the rig.
"""

from __future__ import annotations

import argparse
import itertools
import time
from pathlib import Path

import numpy as np

from app.signal.filters import preprocess
from tools import probe

# Each entry is a prompt, a hold duration, and the label the analysis groups
# by. Rest spans are labelled too, unlike the graded protocol: this survey
# compares poses against each other rather than against one clean baseline, so
# each rest is also evidence about whether the muscle actually returned to
# baseline between poses.
#
# Order matters. The two maximal poses (hard grip, firm pinch) sit at opposite
# ends with lighter work between them, so neither is measured on an already
# fatigued forearm. The four single finger poses are last because they are the
# least likely to resolve and the most likely to be contaminated by fatigue,
# and finding that out should not cost the gradeable part of the survey.
SURVEY: tuple[tuple[str, float, str | None], ...] = (
    ("Relax completely. Arm supported, hand open.", 12.0, "rest_1"),
    ("Squeeze LIGHTLY, about a quarter effort. Hold it.", 8.0, "grip_light"),
    ("Relax.", 10.0, "rest_2"),
    ("Squeeze MEDIUM, about half effort. Hold it.", 8.0, "grip_medium"),
    ("Relax.", 10.0, "rest_3"),
    ("Squeeze HARD, as hard as is comfortable. Hold it.", 8.0, "grip_hard"),
    ("Relax.", 12.0, "rest_4"),
    ("PINCH thumb to index finger, firmly. Hold it.", 8.0, "pinch"),
    ("Relax.", 10.0, "rest_5"),
    ("Bend your WRIST, curling the palm toward you. Hold it.", 8.0, "wrist_flex"),
    ("Relax.", 10.0, "rest_6"),
    ("Curl your INDEX finger only, others relaxed. Hold it.", 8.0, "index"),
    ("Relax.", 8.0, "rest_7"),
    ("Curl your MIDDLE finger only, others relaxed. Hold it.", 8.0, "middle"),
    ("Relax.", 8.0, "rest_8"),
    ("Curl your RING finger only, others relaxed. Hold it.", 8.0, "ring"),
    ("Relax.", 8.0, "rest_9"),
    ("Curl your LITTLE finger only, others relaxed. Hold it.", 8.0, "little"),
    ("Relax. One more after this.", 10.0, "rest_10"),
    ("Spread your fingers WIDE open. Hold it.", 8.0, "extend"),
    ("Done. Relax.", 6.0, "rest_11"),
)

POSES: tuple[str, ...] = tuple(
    label for _, _, label in SURVEY if label and not label.startswith("rest")
)

# Trimmed from each end of a pose window before measuring. The wearer is still
# ramping into the pose at the start and releasing at the end, and neither
# transient describes the pose.
EDGE_TRIM_S = 1.5

# Cohen's d thresholds. Below 1 two distributions overlap so heavily that no
# classifier separates them reliably; above 2 the gap is wide enough to act on.
D_OVERLAP = 1.0
D_CLEAN = 2.0


def separation(a: np.ndarray, b: np.ndarray) -> float:
    """Effect size between two pose envelopes, as Cohen's d.

    The distance between the means over the pooled spread. Amplitude alone
    cannot answer whether two poses are distinguishable, because a wide gap
    between two very noisy levels is still not a gap a classifier can use.
    """
    if a.size < 2 or b.size < 2:
        return 0.0
    pooled = float(np.sqrt((a.var(ddof=1) + b.var(ddof=1)) / 2.0))
    if pooled <= 1e-12:
        return 0.0
    return float(abs(a.mean() - b.mean()) / pooled)


def _label(d: float) -> str:
    if d < D_OVERLAP:
        return "overlapping"
    if d < D_CLEAN:
        return "usable, noisy"
    return "clean"


def pose_levels(
    counts: np.ndarray,
    phases: dict[str, tuple[float, float]],
    fs: int,
) -> dict[str, np.ndarray]:
    """Return the rectified envelope for each labelled span.

    Uses the same preprocessing the graded probe uses, so the levels reported
    here are directly comparable to the ones it prints.
    """
    prepared = preprocess(np.asarray(counts, dtype=float), fs)
    env = prepared.envelope

    levels: dict[str, np.ndarray] = {}
    for label, (start_s, end_s) in phases.items():
        start = int((start_s + EDGE_TRIM_S) * fs)
        end = int((end_s - EDGE_TRIM_S) * fs)
        start = max(0, start)
        end = min(env.size, end)
        if end - start < fs:
            # Under a second left after trimming says nothing about the pose.
            continue
        levels[label] = env[start:end]
    return levels


def report(levels: dict[str, np.ndarray]) -> None:
    rest_keys = [k for k in levels if k.startswith("rest")]
    pose_keys = [k for k in POSES if k in levels]

    if not pose_keys:
        known = ", ".join(sorted(levels)) or "none"
        print(
            "\n  No survey poses in this recording. Its labelled spans are:"
            f"\n    {known}"
            "\n\n  A trace from tools/probe.py carries the graded protocol's"
            "\n  phases, not the survey's poses. Record one with this script.\n"
        )
        return

    # A rest span the wearer did not actually relax through drags the pooled
    # baseline up, which can push a genuinely light pose below it and make a
    # real contraction read as undetectable. Flag those spans rather than
    # letting them quietly distort every ratio on the page.
    rest_means = {k: float(levels[k].mean()) for k in rest_keys}
    typical = float(np.median(list(rest_means.values()))) if rest_means else 0.0
    contaminated = [
        k for k, m in rest_means.items() if typical > 0 and m > 2.0 * typical
    ]
    clean_rests = [k for k in rest_keys if k not in contaminated]

    rest_pool = (
        np.concatenate([levels[k] for k in (clean_rests or rest_keys)])
        if rest_keys
        else np.array([], dtype=float)
    )
    baseline = float(rest_pool.mean()) if rest_pool.size else 0.0
    width = max(len(k) for k in pose_keys)

    print("\n" + "=" * 66)
    print("  Gesture survey")
    print("=" * 66)
    print(
        f"\n  Baseline, pooled across {len(clean_rests or rest_keys)} rest"
        f" spans: {baseline:.4f}"
    )
    if contaminated:
        print(
            f"\n  Excluded from baseline: {', '.join(sorted(contaminated))}."
            "\n  Those spans sit well above the other rests, so the muscle had"
            "\n  not returned to baseline. Levels there are not resting levels."
        )
    print()

    print("  Pose level, and how far above rest\n")
    for key in pose_keys:
        mean = float(levels[key].mean())
        ratio = mean / baseline if baseline > 0 else float("inf")
        bar = "#" * int(min(round(ratio), 40))
        print(f"    {key:<{width}}  {mean:8.4f}  {ratio:6.1f}x  {bar}")

    print("\n  Is the pose detectable at all, against rest\n")
    for key in pose_keys:
        d = separation(levels[key], rest_pool)
        print(f"    {key:<{width}}  d = {d:5.2f}   {_label(d)}")

    print("\n  Can two poses be told apart\n")
    print("  Below 1.00 they overlap and a classifier cannot separate them.\n")
    pair_width = width * 2 + 4
    for left, right in itertools.combinations(pose_keys, 2):
        d = separation(levels[left], levels[right])
        print(f"    {f'{left} vs {right}':<{pair_width}}  d = {d:5.2f}   {_label(d)}")

    _summarise(levels, rest_pool, pose_keys)


def _summarise(
    levels: dict[str, np.ndarray],
    rest_pool: np.ndarray,
    pose_keys: list[str],
) -> None:
    """State the two conclusions the survey exists to reach."""
    print("\n  What this means\n")

    efforts = [k for k in ("grip_light", "grip_medium", "grip_hard") if k in levels]
    if len(efforts) >= 2:
        worst = min(
            separation(levels[a], levels[b])
            for a, b in itertools.combinations(efforts, 2)
        )
        if worst >= D_OVERLAP:
            print(
                f"    - effort levels separate (worst adjacent pair d = {worst:.2f}),"
                "\n      so grading how hard a grip was is defensible."
            )
        else:
            print(
                f"    - effort levels overlap (worst pair d = {worst:.2f}), so a"
                "\n      force estimate in kg would be fitting noise."
            )

    # Only fingers that actually produced a contraction can speak to whether
    # fingers are separable. A pose the wearer could not perform sits at rest,
    # and pairing it against one that worked yields a large effect size that
    # measures the failed pose rather than any finger discrimination.
    fingers = [
        k
        for k in ("index", "middle", "ring", "little")
        if k in levels and separation(levels[k], rest_pool) >= D_CLEAN
    ]
    if len(fingers) >= 2:
        pairs = {
            (a, b): separation(levels[a], levels[b])
            for a, b in itertools.combinations(fingers, 2)
        }
        worst_pair, worst = min(pairs.items(), key=lambda kv: kv[1])
        indistinct = [p for p, d in pairs.items() if d < D_OVERLAP]
        scope = ", ".join(fingers)

        # The worst pair is the honest statistic here, not the best one. Every
        # finger curl recruits the same flexor mass, so a wide gap between two
        # of them reports that one was pressed harder, not that the channel
        # knows which finger moved. A single indistinguishable pair is enough
        # to sink per finger decoding, however well other pairs happen to score.
        if indistinct:
            names = "; ".join(f"{a} vs {b}" for a, b in indistinct)
            print(
                f"    - individual fingers do not separate (across {scope})."
                f"\n      Indistinguishable: {names}."
                f"\n      Closest pair {worst_pair[0]} vs {worst_pair[1]} at"
                f" d = {worst:.2f}."
                "\n      Expected on one channel: the finger compartments of"
                "\n      flexor digitorum superficialis sum into a single"
                "\n      differential pair, so what varies between these poses is"
                "\n      how hard you pressed, not which finger moved. Decoding"
                "\n      fingers needs an 8 to 16 channel array."
            )
        else:
            print(
                f"    - every finger pair separates (across {scope}, worst pair"
                f"\n      {worst_pair[0]} vs {worst_pair[1]} at d = {worst:.2f}),"
                "\n      which is unusual on one channel. Repeat the run before"
                "\n      believing it: pressing each finger with a different force"
                "\n      reproduces this without any finger information."
            )
    elif len(fingers) < 2:
        print(
            "    - too few finger poses rose above rest to say whether fingers"
            "\n      separate. Repeat with firmer single finger curls."
        )

    detectable = [
        k for k in pose_keys if separation(levels[k], rest_pool) >= D_OVERLAP
    ]
    print(
        f"    - {len(detectable)} of {len(pose_keys)} poses are detectable against"
        f" rest:\n      {', '.join(detectable) if detectable else 'none'}"
    )
    print()


def run_survey(port: str) -> probe.Recording:
    """Record the whole survey in one pass, counting into each pose.

    This is a single call into probe.record() with the survey table and a lead
    in hook, rather than one call per pose. Reopening the serial port between
    poses resets the link, which drops samples across every boundary and
    leaves the recorded phase offsets out of step with the samples they are
    supposed to index.
    """
    return probe.record(port, guided=True, protocol=SURVEY, lead_in=_countdown)


def _countdown(prompt: str, label: str | None, seconds: int = 3) -> None:
    """Announce the next span, then count into it.

    The whole point: the wearer reads during the countdown, not during the
    window that is about to be measured. Rests are announced without a
    countdown, since relaxing needs no preparation and the pause between poses
    is already long enough to read a single word.
    """
    if label is not None and label.startswith("rest"):
        print(f"\n  {prompt}")
        return

    print(f"\n  NEXT: {prompt}")
    for remaining in range(seconds, 0, -1):
        print(f"\r        starting in {remaining}...", end="", flush=True)
        time.sleep(1.0)
    print("\r        GO, hold it steadily" + " " * 20)


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="gestures",
        description="Survey which hand poses this rig can tell apart.",
    )
    parser.add_argument("--port", help="serial port, otherwise auto detected")
    parser.add_argument(
        "--replay", type=Path, help="re analyse a saved survey CSV, no hardware"
    )
    args = parser.parse_args()

    if args.replay:
        recording = probe.load(args.replay)
        print(f"\n  Re analysing {args.replay}")
        if not recording.phases:
            print(
                "\n  That CSV carries no phase labels, so poses cannot be"
                "\n  separated. Only a run recorded by this script has them.\n"
            )
            return 1
    else:
        total = sum(d for _, d, _ in SURVEY) / 60.0
        print("\n" + "=" * 66)
        print("  MySquishi gesture survey")
        print("=" * 66)
        print(f"\n  About {total:.0f} minutes. Before starting, confirm:")
        print("    - the MyoWare output selector is on RAW")
        print("    - electrodes are fresh and firmly attached")
        print("    - the laptop charger is unplugged")
        print("    - the Arduino Serial Monitor is closed")
        print("\n  Each pose is announced with a 3 second countdown. Read the")
        print("  prompt during the countdown, then HOLD the pose steadily for")
        print("  the whole window. Hold it, do not pulse it.\n")

        recording = probe.trim_warmup(run_survey(probe.discover_port(args.port)))

    report(pose_levels(recording.counts, recording.phases, probe.SAMPLE_HZ))

    if not args.replay:
        print(f"  Trace saved to {probe.save(recording, 'survey')}\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
