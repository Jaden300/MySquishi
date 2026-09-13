/**
 * The calibration floor.
 *
 * These assertions are about a failure that is silent in the UI: a reference
 * below the source's real amplitude clips every later session at the ceiling,
 * the envelope never returns under the release threshold, and repetitions stop
 * being counted while the trace still looks normal.
 */

import { describe, expect, it } from "vitest";

import { FALLBACK_REFERENCE_RMS, referenceRmsFor } from "./reference";

describe("referenceRmsFor", () => {
  it("keeps a genuine maximum that clears the floor", () => {
    expect(referenceRmsFor("simulated", 0.82)).toBe(0.82);
    expect(referenceRmsFor("serial", 0.16)).toBe(0.16);
  });

  it("floors a simulated trial that came in at the serial regime", () => {
    // A simulated run peaking at 0.107 did not capture a contraction, since
    // the generator rests near 0.015 and peaks near 0.73.
    expect(referenceRmsFor("simulated", 0.107)).toBe(0.73);
  });

  it("falls back when the trials caught no contraction", () => {
    // The reset bug produced exactly this: a trial recorded as zero.
    expect(referenceRmsFor("simulated", 0)).toBe(0.73);
    expect(referenceRmsFor("serial", 0)).toBe(0.12);
  });

  it("keeps every source's floor within reach of its real maximum", () => {
    // The two sources live about six times apart, so a single constant cannot
    // serve both and this is asserted per source. The simulated generator
    // peaks near 0.73 over a 30 s run; the four Phase 2 serial traces peak at
    // 0.107 to 0.161. A floor far under the real peak is the dangerous
    // direction: every frame then clips at the 150 percent ceiling, the
    // envelope never returns under the release threshold, and reps stop being
    // counted while the trace still looks normal.
    expect(FALLBACK_REFERENCE_RMS.simulated).toBeGreaterThan(0.5);
    expect(FALLBACK_REFERENCE_RMS.simulated).toBeLessThanOrEqual(0.76);
    expect(FALLBACK_REFERENCE_RMS.serial).toBeGreaterThan(0.1);
    expect(FALLBACK_REFERENCE_RMS.serial).toBeLessThan(0.161);
  });

  it("keeps the simulated floor clear of the serial regime", () => {
    // 0.107 is the serial peak. It sat in the simulated row once, which is
    // the copied-value bug this pins: a real 0.73 peak read about 680 percent
    // against it.
    expect(FALLBACK_REFERENCE_RMS.simulated).toBeGreaterThan(
      FALLBACK_REFERENCE_RMS.serial * 3,
    );
  });

  it("treats an unknown source as simulated rather than throwing", () => {
    expect(referenceRmsFor("nonesuch", 0)).toBe(0.73);
    expect(referenceRmsFor(null, 0)).toBe(0.73);
    expect(referenceRmsFor(undefined, 0)).toBe(0.73);
  });

  it("rejects a non finite measurement", () => {
    expect(referenceRmsFor("simulated", NaN)).toBe(0.73);
    expect(referenceRmsFor("simulated", Infinity)).toBe(0.73);
  });
});
