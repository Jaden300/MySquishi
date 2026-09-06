/**
 * Which muscle is being trained.
 *
 * This is the control that turns a grip device into a general strength and
 * fatigue trainer. Phase 2 found that effort grading and fatigue are
 * properties of motor unit recruitment, so they hold on any skeletal muscle,
 * while kilograms and the EWGSOP2 references do not. Selecting a muscle here
 * decides which claims the app makes. See lib/muscle.ts.
 */

import { useLiveStore } from "../store/live";
import {
  MUSCLES,
  MUSCLE_LABELS,
  NON_GRIP_NOTE,
  allowsKilograms,
} from "../lib/muscle";

interface MuscleSelectorProps {
  /** Disabled mid session: changing muscle would invalidate the calibration
   *  the readings are normalized against. */
  disabled?: boolean;
}

export function MuscleSelector({ disabled = false }: MuscleSelectorProps) {
  const muscle = useLiveStore((s) => s.muscle);
  const setMuscle = useLiveStore((s) => s.setMuscle);

  return (
    <div className="flex flex-col gap-2">
      <label
        htmlFor="muscle-select"
        className="text-sm text-ink/80"
      >
        Muscle
      </label>

      <select
        id="muscle-select"
        value={muscle}
        disabled={disabled}
        onChange={(event) =>
          setMuscle(event.target.value as (typeof MUSCLES)[number])
        }
        className="rounded-xl border border-squish-100 bg-mist px-3 py-2 text-sm text-ink focus:outline-none focus:ring-2 focus:ring-squish-500 disabled:opacity-60"
      >
        {MUSCLES.map((option) => (
          <option key={option} value={option}>
            {MUSCLE_LABELS[option]}
          </option>
        ))}
      </select>

      {/* The absence of kilograms is a deliberate clinical decision, so it is
          stated rather than left as a gap on the screen. */}
      {!allowsKilograms(muscle) && (
        <p className="text-xs text-ink/60">{NON_GRIP_NOTE}</p>
      )}

      {disabled && (
        <p className="text-xs text-ink/60">
          Finish the session to change muscle.
        </p>
      )}
    </div>
  );
}
