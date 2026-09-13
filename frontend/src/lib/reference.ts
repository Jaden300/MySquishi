/**
 * The fallback maximum voluntary contraction reference, per signal source.
 *
 * Calibration's whole job is to measure this from the person, so this table is
 * only the floor: what gets stored when the three trials did not capture a
 * real contraction. Whatever sits here is what a failed calibration divides
 * by, in every later session, so a wrong value is not a cosmetic problem.
 *
 * It is per source because the sources live in amplitude regimes about six
 * times apart, and a single constant cannot serve both. Measured, not
 * estimated:
 *
 * - Simulated: window_rms peaks at 0.74 to 0.76 over a 30 s run, resting near
 *   0.015. Two runs of the generator agreed.
 * - Serial, the real MyoWare: the four Phase 2 traces in backend/calibration
 *   peak at 0.107, 0.118, 0.118 and 0.161, median 0.118, resting near 0.009.
 *   Scaled by COUNTS_PER_UNIT = 100 in backend/app/sources/serial_source.py.
 *   See docs/HARDWARE_FINDINGS.md.
 * - Replay: plays recorded sensor traces through the same scaling, so it
 *   shares the sensor's regime.
 *
 * A single constant here is what broke repetition detection. At 0.12 against
 * the simulated source, every frame clipped at the 150 percent ceiling with a
 * floor of 8 percent, so the envelope never came back under the coach's
 * release threshold, and repetitions opened and never closed. The rep count
 * simply stayed at zero while the trace looked normal.
 *
 * The same failure returned once by a different route: the serial peak, 0.107,
 * was copied into the simulated row, where a real 0.73 peak reads about 680
 * percent and pins at the ceiling identically. The values are near enough to
 * each other to look plausible and are an order of magnitude apart in effect,
 * so reference.test.ts asserts the two regimes stay separated rather than
 * checking each number alone.
 */

/** Measured maxima above. The value is a plausible maximal contraction for the
 *  source, so a spoiled calibration reads near 100 percent rather than pinning
 *  at the ceiling or flattening to single digits. */
const FALLBACK_REFERENCE_RMS: Record<string, number> = {
  simulated: 0.73,
  serial: 0.12,
  replay: 0.12,
};

/** The source used when none was chosen, matching the backend default. */
const DEFAULT_SOURCE = "simulated";

/**
 * The reference to store for a calibration.
 *
 * `measured` is the strongest raw amplitude the trials saw. It is trusted when
 * it clears the floor, which is the point of asking for three maximal efforts.
 * Below the floor the trials did not capture a contraction, so the floor is
 * stored instead: dividing by a near zero reference would clamp every later
 * session at 150 percent.
 */
export function referenceRmsFor(
  sourceId: string | null | undefined,
  measured: number,
): number {
  const floor =
    FALLBACK_REFERENCE_RMS[sourceId ?? DEFAULT_SOURCE] ??
    FALLBACK_REFERENCE_RMS[DEFAULT_SOURCE];

  return Number.isFinite(measured) && measured > floor ? measured : floor;
}

export { FALLBACK_REFERENCE_RMS };
