/**
 * Voice coaching.
 *
 * jsdom implements no speechSynthesis, so it is stubbed here rather than in
 * test/setup.ts: setup stubs what every test file needs, and this is the only
 * one that speaks.
 *
 * The cases below are the bugs this controller can actually have. A stale
 * repetition announced on arrival, a phase spoken once per frame instead of
 * once per phase, a repetition count talking over a coaching prompt, and
 * speech continuing after the preference is switched off.
 */

import { beforeEach, afterEach, describe, expect, it, vi } from "vitest";

import { voiceCoach, summaryUtterance } from "./speech";
import { useLiveStore } from "../store/live";
import { useVoiceStore } from "../store/voice";
import type { Coach, Frame, RepEvent, SummaryFrame } from "../types/api";

let spoken: string[] = [];
let speaking = false;

function stubSpeech() {
  spoken = [];
  speaking = false;

  vi.stubGlobal("speechSynthesis", {
    speak: (utterance: { text: string }) => spoken.push(utterance.text),
    cancel: () => {
      speaking = false;
    },
    getVoices: () => [],
    get speaking() {
      return speaking;
    },
  });

  vi.stubGlobal(
    "SpeechSynthesisUtterance",
    class {
      text: string;
      constructor(text: string) {
        this.text = text;
      }
    },
  );
}

function coach(phase: Coach["phase"], prompt: string): Coach {
  return {
    phase,
    prompt,
    seconds_remaining: 3,
    target_mvc_pct: 50,
    reps_done: 0,
  };
}

function rep(index: number, feedback: string): RepEvent {
  return {
    index,
    peak_mvc: 60,
    quality: { point: 80, lower: 70, upper: 90, level: 0.8, unit: "" },
    factor: "hold steadiness",
    feedback,
  };
}

function frame(overrides: Partial<Frame> = {}): Frame {
  return {
    type: "frame",
    t: 1,
    seq: 1,
    fs: 1000,
    raw: [],
    envelope: [],
    mvc_pct: 40,
    sqi: 95,
    is_live: false,
    source_id: "simulated",
    muscle: "forearm_grip",
    calibrated: true,
    rep_event: null,
    coach: coach("hold", "Hold it steady."),
    ...overrides,
  };
}

function summary(overrides: Partial<SummaryFrame> = {}): SummaryFrame {
  return {
    type: "summary",
    seq: 2,
    session_id: 1,
    rep_count: 8,
    mean_mvc: 54.4,
    peak_mvc: 71,
    mean_rep_quality: 82.3,
    sqi_mean: 94,
    duration_s: 60,
    total_impulse: 100,
    fatigue: null,
    is_live: false,
    source_id: "simulated",
    muscle: "forearm_grip",
    calibrated: true,
    reps: [],
    ...overrides,
  };
}

describe("the voice coach", () => {
  beforeEach(() => {
    stubSpeech();
    useLiveStore.getState().reset();
    useVoiceStore.setState({ voiceOn: true });
    voiceCoach.start();
  });

  afterEach(() => {
    voiceCoach.stop();
    vi.unstubAllGlobals();
  });

  it("speaks a coaching prompt when the phase changes", () => {
    useLiveStore.getState().applyFrame(frame());

    expect(spoken).toContain("Hold it steady.");
  });

  it("speaks the same phase once, not once per frame", () => {
    useLiveStore.getState().applyFrame(frame());
    useLiveStore.getState().applyFrame(frame());
    useLiveStore.getState().applyFrame(frame());

    expect(spoken.filter((t) => t === "Hold it steady.")).toHaveLength(1);
  });

  it("speaks each new phase as it arrives", () => {
    useLiveStore.getState().applyFrame(frame());
    useLiveStore
      .getState()
      .applyFrame(frame({ coach: coach("release", "Ease off slowly.") }));

    expect(spoken).toContain("Hold it steady.");
    expect(spoken).toContain("Ease off slowly.");
  });

  it("does not announce a repetition that closed before it started", () => {
    /* The idiom RepPulse uses. Starting voice on a page mid session must not
       celebrate a repetition the listener was not there for. */
    voiceCoach.stop();
    useLiveStore.getState().applyFrame(frame({ rep_event: rep(0, "Good hold.") }));

    spoken = [];
    voiceCoach.start();
    useLiveStore.getState().applyFrame(frame());

    expect(spoken).not.toContain("One");
    expect(spoken).not.toContain("Good hold.");
  });

  it("counts a repetition that closes while it is listening", () => {
    useLiveStore.getState().applyFrame(frame());
    useLiveStore
      .getState()
      .applyFrame(frame({ rep_event: rep(0, "Good hold.") }));

    expect(spoken).toContain("One");
  });

  it("says nothing at all when the preference is off", () => {
    useVoiceStore.setState({ voiceOn: false });

    useLiveStore.getState().applyFrame(frame());
    useLiveStore
      .getState()
      .applyFrame(frame({ rep_event: rep(0, "Good hold.") }));

    expect(spoken).toEqual([]);
  });

  it("does not announce the previous repetition when switched on mid session", () => {
    useVoiceStore.setState({ voiceOn: false });
    useLiveStore.getState().applyFrame(frame({ rep_event: rep(0, "Good hold.") }));

    useVoiceStore.setState({ voiceOn: true });
    spoken = [];
    useLiveStore.getState().applyFrame(frame());

    expect(spoken).not.toContain("One");
  });

  it("lets a coaching prompt interrupt a repetition count", () => {
    /* Priority, not queueing. "Ease off slowly" matters more than "Two", and
       at five frames a second a queued count would be spoken late. */
    useLiveStore.getState().applyFrame(frame());
    useLiveStore
      .getState()
      .applyFrame(frame({ rep_event: rep(1, "Good hold.") }));

    speaking = true;
    spoken = [];
    useLiveStore
      .getState()
      .applyFrame(frame({ coach: coach("rest", "Rest.") }));

    expect(spoken).toContain("Rest.");
  });

  it("speaks a summary when the session ends", () => {
    useLiveStore.getState().applySummary(summary());

    expect(spoken.join(" ")).toContain("Session complete.");
  });

  it("survives a browser with no speech at all", () => {
    voiceCoach.stop();
    vi.unstubAllGlobals();

    expect(() => {
      voiceCoach.start();
      useLiveStore.getState().applyFrame(frame());
    }).not.toThrow();
  });

  it("keeps the session alive when speaking throws", () => {
    vi.stubGlobal("speechSynthesis", {
      speak: () => {
        throw new Error("synthesis failed");
      },
      cancel: () => {},
      getVoices: () => [],
      speaking: false,
    });

    expect(() =>
      useLiveStore.getState().applyFrame(frame()),
    ).not.toThrow();
  });
});

describe("the spoken summary", () => {
  it("reports repetitions, effort and form", () => {
    const text = summaryUtterance(summary());

    expect(text).toContain("8 repetitions");
    expect(text).toContain("54 percent");
    expect(text).toContain("82");
  });

  it("omits form when it was not scored", () => {
    const text = summaryUtterance(summary({ mean_rep_quality: null }));

    expect(text).not.toContain("form scored");
  });

  it("speaks no kilogram figure on any muscle", () => {
    /* The summary frame carries none, and the clinical gate means a figure
       added later must be gated on the muscle rather than spoken freely. */
    for (const muscle of ["forearm_grip", "biceps", "calf", "other"] as const) {
      const text = summaryUtterance(summary({ muscle })).toLowerCase();
      expect(text).not.toContain(" kg");
      expect(text).not.toContain("kilogram");
    }
  });
});
