/**
 * The presentation side of the muscle gate.
 *
 * The backend is the enforcement point and has its own tests. What matters
 * here is that the UI agrees with it, so the two cannot drift apart and start
 * disagreeing about which claims are honest.
 */

import { describe, expect, it } from "vitest";

import {
  DEFAULT_MUSCLE,
  MUSCLES,
  MUSCLE_LABELS,
  MUSCLE_PLACEMENT,
  allowsKilograms,
  muscleLabel,
} from "./muscle";

describe("the muscle list", () => {
  it("matches the backend's clinical_gate", () => {
    expect([...MUSCLES]).toEqual(["forearm_grip", "biceps", "calf", "other"]);
    expect(DEFAULT_MUSCLE).toBe("forearm_grip");
  });

  it("labels and places every muscle it offers", () => {
    for (const muscle of MUSCLES) {
      expect(MUSCLE_LABELS[muscle]).toBeTruthy();
      expect(MUSCLE_PLACEMENT[muscle]).toBeTruthy();
    }
  });

  it("gives placement guidance mentioning the 2 cm spacing", () => {
    // Placement decides signal quality more than anything else in the chain.
    for (const muscle of MUSCLES) {
      expect(MUSCLE_PLACEMENT[muscle]).toContain("2 cm");
    }
  });
});

describe("allowsKilograms", () => {
  it("permits kilograms on grip only", () => {
    expect(allowsKilograms("forearm_grip")).toBe(true);

    for (const muscle of ["biceps", "calf", "other"]) {
      expect(allowsKilograms(muscle)).toBe(false);
    }
  });

  it("refuses on missing or unknown values rather than assuming grip", () => {
    // Withholding a claim is the safe failure. Asserting one is not.
    expect(allowsKilograms(null)).toBe(false);
    expect(allowsKilograms(undefined)).toBe(false);
    expect(allowsKilograms("tentacle")).toBe(false);
  });
});

describe("muscleLabel", () => {
  it("names each muscle", () => {
    expect(muscleLabel("biceps")).toBe("Biceps");
  });

  it("falls back to the default rather than showing a raw id", () => {
    expect(muscleLabel(null)).toBe(MUSCLE_LABELS[DEFAULT_MUSCLE]);
    expect(muscleLabel("tentacle")).toBe(MUSCLE_LABELS[DEFAULT_MUSCLE]);
  });
});
