import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";

import { SquishiMascot } from "./SquishiMascot";
import { expressionFor } from "../lib/expression";
import { useLiveStore } from "../store/live";

describe("expressionFor", () => {
  // Thresholds from docs/DESIGN.md: resting under 5, working 5 to 40,
  // straining 40 to 80, proud above 80.
  it.each([
    [0, "resting"],
    [4.9, "resting"],
    [5, "working"],
    [39, "working"],
    [40, "straining"],
    [80, "straining"],
    [81, "proud"],
    [100, "proud"],
  ])("maps %s percent to %s", (value, expected) => {
    expect(expressionFor(value as number)).toBe(expected);
  });

  it("looks proud on rep completion regardless of effort", () => {
    expect(expressionFor(0, true)).toBe("proud");
  });
});

describe("SquishiMascot", () => {
  beforeEach(() => {
    useLiveStore.getState().reset();
  });

  it("names its expression for assistive technology", () => {
    // State must never be conveyed by shape alone.
    render(<SquishiMascot value={60} />);
    expect(screen.getByRole("img")).toHaveAccessibleName(/straining/i);
  });

  it("takes a value prop so the landing page can drive it", () => {
    render(<SquishiMascot value={90} />);
    expect(screen.getByRole("img")).toHaveAttribute("data-expression", "proud");
  });

  it("follows the store when no value prop is given", () => {
    useLiveStore.setState({ mvcPct: 20 });
    render(<SquishiMascot />);
    expect(screen.getByRole("img")).toHaveAttribute(
      "data-expression",
      "working",
    );
  });

  it("renders under reduced motion", () => {
    // docs/DESIGN.md requires the spring to be replaced by a discrete swap,
    // not merely shortened, so this branch has to render on its own.
    vi.mocked(window.matchMedia).mockImplementation(
      (query: string) =>
        ({
          matches: query.includes("prefers-reduced-motion"),
          media: query,
          onchange: null,
          addListener: vi.fn(),
          removeListener: vi.fn(),
          addEventListener: vi.fn(),
          removeEventListener: vi.fn(),
          dispatchEvent: vi.fn(),
        }) as unknown as MediaQueryList,
    );

    render(<SquishiMascot value={50} />);
    expect(screen.getByRole("img")).toHaveAttribute(
      "data-expression",
      "straining",
    );
  });
});

describe("the live store", () => {
  beforeEach(() => useLiveStore.getState().reset());

  it("keeps mvcPct flat so the mascot can subscribe to it alone", () => {
    // The whole reason the store is split: a scalar selector lets zustand
    // bail out, so a frame does not re-render the charts through the mascot.
    const state = useLiveStore.getState();
    expect(typeof state.mvcPct).toBe("number");
  });

  it("accumulates repetitions as frames arrive", () => {
    const frame = {
      type: "frame" as const,
      t: 1,
      seq: 1,
      fs: 1000,
      raw: [1, 2],
      envelope: [1],
      mvc_pct: 42,
      sqi: 90,
      is_live: false,
      source_id: "simulated",
      calibrated: true,
      coach: null as never,
      rep_event: {
        index: 0,
        peak_mvc: 60,
        quality: { point: 70, lower: 60, upper: 80, level: 0.8, unit: "" },
        factor: "hold_cv",
        feedback: "Your hold was steady.",
      },
    };

    useLiveStore.getState().applyFrame(frame);

    const state = useLiveStore.getState();
    expect(state.mvcPct).toBe(42);
    expect(state.reps).toHaveLength(1);
    expect(state.repCompletedAt).toBeGreaterThan(0);
  });
});
