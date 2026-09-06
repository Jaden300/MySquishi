/**
 * Which muscle is being trained, and what may honestly be said about it.
 *
 * This mirrors backend/app/clinical_gate.py. The backend is the enforcement
 * point: it omits the gated fields from its responses entirely, so a bug here
 * cannot produce a false clinical claim. What lives here is the presentation
 * side, so the UI asks for the right thing and explains an absence rather than
 * rendering a hole.
 *
 * The rule, from docs/HARDWARE_FINDINGS.md: Phase 2 found that effort grading
 * and fatigue are properties of motor unit recruitment and generalize to any
 * skeletal muscle, while kilograms and the EWGSOP2 sarcopenia thresholds are
 * validated on hand dynamometry alone. So percent MVC, fatigue and repetition
 * counts are honest everywhere; kilograms and population percentiles are
 * honest on grip and nowhere else.
 */

export const MUSCLES = ["forearm_grip", "biceps", "calf", "other"] as const;

export type Muscle = (typeof MUSCLES)[number];

export const DEFAULT_MUSCLE: Muscle = "forearm_grip";

export const MUSCLE_LABELS: Record<Muscle, string> = {
  forearm_grip: "Forearm, grip",
  biceps: "Biceps",
  calf: "Calf",
  other: "Other muscle",
};

/** Where to place the electrodes, per muscle. Placement decides signal quality
 *  more than anything else in the chain. */
export const MUSCLE_PLACEMENT: Record<Muscle, string> = {
  forearm_grip:
    "Two electrodes on the fleshy inner forearm, a third of the way down from the elbow, 2 cm apart along the arm. Reference on the bony point of the elbow.",
  biceps:
    "Two electrodes on the belly of the biceps, halfway between shoulder and elbow, 2 cm apart along the upper arm. Reference on the point of the elbow or the shoulder.",
  calf: "Two electrodes on the fullest part of the calf, 2 cm apart along the leg. Reference on the ankle bone.",
  other:
    "Two electrodes over the thickest part of the muscle, 2 cm apart and lined up with the muscle fibres. Reference on the nearest bone.",
};

/** True when force in kilograms, EWGSOP2 status and population percentile are
 *  valid. They stand or fall together: each rests on the same hand
 *  dynamometry validation. */
export function allowsKilograms(muscle: Muscle | string | null | undefined): boolean {
  return muscle === "forearm_grip";
}

export function muscleLabel(muscle: Muscle | string | null | undefined): string {
  if (muscle && muscle in MUSCLE_LABELS) {
    return MUSCLE_LABELS[muscle as Muscle];
  }
  return MUSCLE_LABELS[DEFAULT_MUSCLE];
}

/** Shown wherever a kilogram claim has been withheld, so the absence reads as
 *  a deliberate clinical decision rather than as missing data. */
export const NON_GRIP_NOTE =
  "Force in kilograms and population percentiles are only shown for forearm grip: " +
  "those reference figures come from hand dynamometry studies. Percent of your own " +
  "maximum, fatigue and repetition counts are valid for every muscle.";

/** Shown wherever a median frequency figure appears from the live sensor. At
 *  500 Hz the observable spectrum stops at 250 Hz, so the upper part of the
 *  sEMG band is simply not seen. See docs/PHASE3_GUIDE.md. */
export const FATIGUE_BANDWIDTH_NOTE =
  "The sensor samples at 500 Hz, so frequencies above 250 Hz are not observed. " +
  "Trends within a session are meaningful; the absolute values are not comparable " +
  "to published figures.";
