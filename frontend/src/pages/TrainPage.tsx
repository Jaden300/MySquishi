/**
 * The training flow: profile, calibration, the live session, the summary.
 *
 * One page with a stage machine rather than three routes. Onboarding,
 * calibration and a session were never three destinations you chose between,
 * they were one task with three parts, and routing them separately meant the
 * navigation bar offered you the middle of a flow as a place to go.
 *
 * The stage machine itself lives in lib/stage.ts.
 */

import { useStage } from "../lib/stage";
import { OnboardingPage } from "./OnboardingPage";
import { CalibratePage } from "./CalibratePage";
import { SessionPage } from "./SessionPage";

export function TrainPage() {
  const [stage] = useStage();

  if (stage === "profile") return <OnboardingPage />;
  if (stage === "calibrate") return <CalibratePage />;
  return <SessionPage />;
}
