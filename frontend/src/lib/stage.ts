/**
 * The training flow's stage machine.
 *
 * Separate from the page so that file exports components only and fast refresh
 * keeps working, which is the same reason lib/expression.ts exists.
 *
 * The stage lives in a search param rather than in component state so that a
 * refresh lands where you were, the back button steps backward through the
 * flow instead of leaving it, and a demo can deep link straight to the part it
 * wants to show.
 */

import { useSearchParams } from "react-router-dom";

export const STAGES = ["profile", "calibrate", "live", "done"] as const;
export type Stage = (typeof STAGES)[number];

export const STAGE_LABELS: Record<Stage, string> = {
  profile: "Profile",
  calibrate: "Calibrate",
  live: "Train",
  done: "Summary",
};

export function useStage(): [Stage, (next: Stage) => void] {
  const [params, setParams] = useSearchParams();
  const raw = params.get("stage");
  // An unrecognised or absent stage lands on the live session, because the
  // common case is someone who has already been set up wanting to train.
  const stage = (STAGES as readonly string[]).includes(raw ?? "")
    ? (raw as Stage)
    : "live";

  const setStage = (next: Stage) => {
    const updated = new URLSearchParams(params);
    updated.set("stage", next);
    setParams(updated);
  };

  return [stage, setStage];
}
