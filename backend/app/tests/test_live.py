"""The live session loop.

The frame contract and the incremental repetition detector. M2 recovering
exact repetition counts is the gate docs/ML.md sets before anything
downstream is trusted, and the live path has to clear it independently of the
offline one: it segments a sliding buffer rather than a finished recording,
which is a genuinely different problem.
"""

from __future__ import annotations

import time

import numpy as np
import pytest

from app.api.live import FRAME_KEYS, CoachState, LiveSessionRunner
from app.sim.signal_gen import RepSpec, SessionProtocol
from app.sources.base import get_source

# 10.5 s per prescribed repetition: 0.7 ramp, 4.0 hold, 0.8 release, 5.0 rest.
SECONDS_PER_REP = 10.5
LEAD_IN_S = 5.0


def _runner(seed: int = 1, protocol: SessionProtocol | None = None) -> LiveSessionRunner:
    """A runner wired to an unpaced source, so tests do not run in real time."""
    runner = LiveSessionRunner(source_id="simulated")
    runner.source = get_source(
        "simulated", paced=False, seed=seed, protocol=protocol
    )
    runner.source.connect()
    runner._t0 = time.monotonic()
    return runner


def _run_seconds(runner: LiveSessionRunner, seconds: float) -> list[dict]:
    frames_per_second = runner.sample_rate / 200
    return [
        runner.process(runner.source.read_window())
        for _ in range(int(seconds * frames_per_second))
    ]


class TestFrameContract:
    """The wire format the frontend depends on."""

    def test_frame_carries_exactly_the_documented_keys(self) -> None:
        runner = _runner()
        frame = runner.process(runner.source.read_window())
        assert tuple(frame.keys()) == FRAME_KEYS

    def test_traces_are_decimated_for_transport(self) -> None:
        runner = _runner()
        frame = runner.process(runner.source.read_window())
        # 100 raw points and 20 envelope points, per docs/ARCHITECTURE.md.
        assert len(frame["raw"]) == 100
        assert len(frame["envelope"]) == 20

    def test_percent_mvc_is_computed_server_side(self) -> None:
        """The frontend never divides, so mvc_pct must arrive ready to render."""
        runner = _runner()
        frame = runner.process(runner.source.read_window())
        assert isinstance(frame["mvc_pct"], float)
        assert frame["mvc_pct"] >= 0.0

    def test_honesty_metadata_comes_from_the_source(self) -> None:
        runner = _runner()
        frame = runner.process(runner.source.read_window())
        # A simulated source can never report itself as live.
        assert frame["is_live"] is False
        assert frame["source_id"] == "simulated"

    def test_uncalibrated_sessions_say_so(self) -> None:
        """An uncalibrated session must not present its figures as measured."""
        runner = _runner()
        frame = runner.process(runner.source.read_window())
        assert frame["calibrated"] is False

    def test_sequence_numbers_increment(self) -> None:
        runner = _runner()
        frames = _run_seconds(runner, 2.0)
        assert [f["seq"] for f in frames] == list(range(1, len(frames) + 1))


class TestRepDetection:
    """The incremental detector, against generator ground truth."""

    @pytest.mark.parametrize("seed", [1, 2, 3])
    def test_recovers_exact_rep_count(self, seed: int) -> None:
        """The gate from docs/ML.md, on the live path.

        A subtly wrong segmentation is worse than a broken one, because it
        fails silently through M4, M5, M6 and M8.
        """
        protocol = SessionProtocol(reps=10)
        runner = _runner(seed=seed, protocol=protocol)
        _run_seconds(runner, LEAD_IN_S + 10 * SECONDS_PER_REP + 5.0)

        assert len(runner.reps) == 10

    def test_each_rep_is_emitted_exactly_once(self) -> None:
        """The buffer slides under the detector, so a repetition can easily be
        re-reported on every frame. It must not be."""
        runner = _runner(seed=1)
        frames = _run_seconds(runner, 60.0)

        events = [f["rep_event"] for f in frames if f["rep_event"] is not None]
        indices = [e["index"] for e in events]

        assert indices == sorted(indices)
        assert len(indices) == len(set(indices))
        assert len(events) == len(runner.reps)

    def test_reps_are_spaced_like_the_protocol(self) -> None:
        """Detected onsets should match the prescribed cadence, not the frame
        rate. Catches a detector that fires on the buffer edge."""
        runner = _runner(seed=1)
        _run_seconds(runner, 60.0)

        starts = [float(r["start_s"]) for r in runner.reps]
        gaps = np.diff(starts)

        assert len(runner.reps) >= 4
        assert np.allclose(gaps, SECONDS_PER_REP, atol=0.5)

    def test_rep_durations_match_the_contraction(self) -> None:
        runner = _runner(seed=1)
        _run_seconds(runner, 60.0)

        durations = [float(r["features"]["duration_s"]) for r in runner.reps]
        # 0.7 ramp plus 4.0 hold plus 0.8 release.
        assert np.allclose(durations, 5.5, atol=0.8)

    def test_baseline_is_frozen_once(self) -> None:
        """Re-estimating the baseline mid session would let the thresholds
        drift upward as the patient works."""
        runner = _runner()
        _run_seconds(runner, 3.0)
        first = runner.baseline
        assert first is not None

        _run_seconds(runner, 20.0)
        assert runner.baseline == first

    def test_rep_events_carry_a_quality_interval(self) -> None:
        runner = _runner(seed=1)
        frames = _run_seconds(runner, 30.0)
        events = [f["rep_event"] for f in frames if f["rep_event"] is not None]

        assert events
        for event in events:
            quality = event["quality"]
            assert quality["lower"] <= quality["point"] <= quality["upper"]
            assert event["feedback"]


class TestFrameBudget:
    """The socket carries 5 frames per second, so a frame has 200 ms."""

    def test_frame_processing_fits_the_budget(self) -> None:
        runner = _runner(seed=1)
        _run_seconds(runner, 10.0)  # warm up, including a rep score

        started = time.perf_counter()
        _run_seconds(runner, 20.0)
        per_frame_ms = (time.perf_counter() - started) / 100 * 1000

        assert per_frame_ms < 100.0, f"{per_frame_ms:.1f} ms per frame"


class TestSummary:
    """The single summary frame sent on stop."""

    def test_summary_reports_the_session(self) -> None:
        runner = _runner(seed=1)
        _run_seconds(runner, 60.0)
        summary = runner.summary()

        assert summary["type"] == "summary"
        assert summary["rep_count"] == len(runner.reps)
        assert summary["peak_mvc"] >= summary["mean_mvc"]
        assert len(summary["reps"]) == len(runner.reps)

    def test_fatigue_runs_once_the_session_has_enough_reps(self) -> None:
        """M5 over two repetitions would be noise. The whole measure is the
        trend across a session."""
        runner = _runner(seed=1)
        _run_seconds(runner, 60.0)
        summary = runner.summary()

        assert summary["fatigue"] is not None
        assert "slope" in summary["fatigue"]

    def test_short_session_reports_no_fatigue_rather_than_a_guess(self) -> None:
        runner = _runner(seed=1)
        _run_seconds(runner, 12.0)
        summary = runner.summary()

        assert summary["fatigue"] is None


class TestCoach:
    """The prompt state machine."""

    def test_cycles_through_the_phases(self) -> None:
        coach = CoachState(hold_s=1.0, rest_s=1.0, ramp_s=0.5)
        seen = set()

        t = 0.0
        for _ in range(80):
            # A contraction, then a release, repeating.
            mvc = 60.0 if (int(t) % 4) < 2 else 0.0
            seen.add(coach.update(t, mvc)["phase"])
            t += 0.2

        assert {"ready", "ramp", "hold"} <= seen

    def test_prompts_are_plain_language(self) -> None:
        """docs/DESIGN.md: "Squeeze and hold", not "initiate isometric
        contraction protocol"."""
        coach = CoachState()
        prompt = str(coach.update(0.0, 0.0)["prompt"])

        assert prompt
        assert prompt[0].isupper()
        assert "isometric" not in prompt.lower()
