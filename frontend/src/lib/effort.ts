/**
 * Mapping effort to something a person can see move.
 *
 * Phase 2 measured the envelope response and it is strongly non linear
 * (docs/HARDWARE_FINDINGS.md):
 *
 *   rest        0.34   1.0x
 *   ~25%        0.49   1.4x
 *   ~50%        0.98   2.9x
 *   maximal     4.89  14.4x
 *
 * Going from rest to a quarter effort barely moves the number, while the last
 * step from half to maximal nearly quintuples it. A linear bar driven by that
 * is almost motionless through the entire low effort range, which is exactly
 * the range a rehabilitation patient works in. The findings call this out as
 * the single most likely way to ship something that technically works and
 * feels broken.
 *
 * So the display uses a square root scale. It expands the low end where the
 * work happens and compresses the top, without the zero handling problems a
 * log scale brings.
 *
 * This is presentation only. Percent MVC itself is computed server side, once,
 * and is never recomputed here: the frontend never divides.
 */

/** The top of the meter. Effort above a person's calibrated maximum is real
 *  and worth showing rather than clipping at 100. */
export const EFFORT_CEILING_PCT = 120;

/**
 * Position on the meter, 0 to 1, for a given percent MVC.
 *
 * Square root of the normalized value: at 25% MVC the bar sits at 46% rather
 * than 21%, which is the difference between a patient seeing their effort
 * register and a patient thinking the sensor is broken.
 */
export function effortToDisplay(mvcPct: number): number {
  const clamped = Math.max(0, Math.min(EFFORT_CEILING_PCT, mvcPct));
  return Math.sqrt(clamped / EFFORT_CEILING_PCT);
}

/** The same mapping as a percentage, for CSS widths. */
export function effortToPercent(mvcPct: number): number {
  return effortToDisplay(mvcPct) * 100;
}

/**
 * The three effort levels, and only three.
 *
 * Phase 2 separated light from medium at Cohen's d = 1.54, the tightest real
 * adjacent pair, and medium from hard at 3.56. Below 1.0 two levels overlap
 * and no classifier separates them, so three is defensible and ten is not.
 * Nothing in the measurements supports finer gradation.
 */
export const EFFORT_LEVELS = [
  { id: "light", label: "Light", minPct: 0, maxPct: 35 },
  { id: "medium", label: "Medium", minPct: 35, maxPct: 70 },
  { id: "hard", label: "Hard", minPct: 70, maxPct: EFFORT_CEILING_PCT },
] as const;

export type EffortLevel = (typeof EFFORT_LEVELS)[number]["id"];

/** Which of the three levels a reading falls in. */
export function effortLevel(mvcPct: number): EffortLevel {
  if (mvcPct < 35) return "light";
  if (mvcPct < 70) return "medium";
  return "hard";
}

/** The human label for a level. */
export function effortLevelLabel(mvcPct: number): string {
  const level = effortLevel(mvcPct);
  return EFFORT_LEVELS.find((entry) => entry.id === level)!.label;
}
