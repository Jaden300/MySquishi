/**
 * The effort display scale.
 *
 * These test the thing Phase 2 warned about: a linear bar driven by the raw
 * envelope is nearly motionless through the low effort range, which is exactly
 * where a rehabilitation patient works. See docs/HARDWARE_FINDINGS.md.
 */

import { describe, expect, it } from "vitest";

import {
  EFFORT_CEILING_PCT,
  EFFORT_LEVELS,
  effortLevel,
  effortLevelLabel,
  effortToDisplay,
  effortToPercent,
} from "./effort";

describe("effortToDisplay", () => {
  it("anchors the ends", () => {
    expect(effortToDisplay(0)).toBe(0);
    expect(effortToDisplay(EFFORT_CEILING_PCT)).toBe(1);
  });

  it("expands the low effort range where rehabilitation happens", () => {
    // The whole point: at a quarter effort the bar is nearly half full rather
    // than barely off the floor, so a patient sees their work register.
    const linear = 25 / EFFORT_CEILING_PCT;
    expect(effortToDisplay(25)).toBeGreaterThan(linear * 2);
  });

  it("stays monotonic, so more effort always reads as more", () => {
    let previous = -1;
    for (let pct = 0; pct <= EFFORT_CEILING_PCT; pct += 5) {
      const value = effortToDisplay(pct);
      expect(value).toBeGreaterThanOrEqual(previous);
      previous = value;
    }
  });

  it("clamps rather than overflowing the meter", () => {
    expect(effortToDisplay(-20)).toBe(0);
    expect(effortToDisplay(400)).toBe(1);
  });

  it("reports percentages for CSS widths", () => {
    expect(effortToPercent(EFFORT_CEILING_PCT)).toBe(100);
    expect(effortToPercent(0)).toBe(0);
  });
});

describe("effort levels", () => {
  it("offers exactly three", () => {
    // Phase 2 separated the tightest adjacent pair at d = 1.54. Below 1.0 two
    // levels overlap and no classifier separates them, so three is defensible
    // and ten is not.
    expect(EFFORT_LEVELS).toHaveLength(3);
  });

  it("classifies each band", () => {
    expect(effortLevel(10)).toBe("light");
    expect(effortLevel(50)).toBe("medium");
    expect(effortLevel(90)).toBe("hard");
  });

  it("covers the whole range without a gap", () => {
    for (let pct = 0; pct <= EFFORT_CEILING_PCT; pct += 1) {
      expect(["light", "medium", "hard"]).toContain(effortLevel(pct));
    }
  });

  it("labels in plain words", () => {
    expect(effortLevelLabel(10)).toBe("Light");
    expect(effortLevelLabel(90)).toBe("Hard");
  });
});
