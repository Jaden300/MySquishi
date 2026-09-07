/**
 * The training flow: profile, calibration, the live session, the summary.
 *
 * One page with a stage machine rather than three routes. Onboarding,
 * calibration and a session were never three destinations you chose between,
 * they were one task with three parts, and routing them separately meant the
 * navigation bar offered you the middle of a flow as a place to go.
 *
 * The rail across the top is what makes that legible. Four dots, the current
 * one filled: you can see where you are in the task and how much of it is
 * left, which the eleven route version could only imply.
 *
 * The stage machine itself lives in lib/stage.ts.
 */

import { useState } from "react";
import { motion, useReducedMotion } from "framer-motion";

import { STAGES, STAGE_LABELS, useStage, type Stage } from "../lib/stage";
import { ProfileStage } from "./train/ProfileStage";
import { CalibrateStage } from "./train/CalibrateStage";
import { LiveStage } from "./train/LiveStage";
import { SessionSummaryPage } from "./SessionSummaryPage";

export function TrainPage() {
  const [stage, setStage] = useStage();
  const [finishedId, setFinishedId] = useState<number | null>(null);

  return (
    <div className="flex flex-col gap-8">
      <StageRail stage={stage} onPick={setStage} />

      {stage === "profile" ? (
        <ProfileStage onDone={() => setStage("calibrate")} />
      ) : null}

      {stage === "calibrate" ? (
        <CalibrateStage onDone={() => setStage("live")} />
      ) : null}

      {stage === "live" ? (
        <LiveStage
          onFinished={(id) => {
            setFinishedId(id);
            setStage("done");
          }}
        />
      ) : null}

      {stage === "done" ? (
        finishedId === null ? (
          // Landed on the summary stage without a session behind it, usually
          // by editing the URL. Send them back to where a session starts.
          <LiveStage
            onFinished={(id) => {
              setFinishedId(id);
              setStage("done");
            }}
          />
        ) : (
          <SessionSummaryPage sessionId={finishedId} justFinished />
        )
      ) : null}
    </div>
  );
}

/**
 * Four dots and the current one filled.
 *
 * Only stages you have already reached are clickable. Jumping ahead to the
 * live session without a calibration behind it produces readings normalized
 * against nothing, so the rail shows the whole flow but does not offer the
 * parts you have not earned yet.
 */
function StageRail({
  stage,
  onPick,
}: {
  stage: Stage;
  onPick: (next: Stage) => void;
}) {
  const reduced = useReducedMotion();
  const current = STAGES.indexOf(stage);

  return (
    <nav aria-label="Training progress">
      <ol className="flex flex-wrap items-center gap-x-2 gap-y-3">
        {STAGES.map((id, i) => {
          const active = i === current;
          const reached = i <= current;

          return (
            <li key={id} className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => reached && onPick(id)}
                disabled={!reached}
                aria-current={active ? "step" : undefined}
                className={`relative inline-flex items-center gap-2.5 rounded-pill px-4 py-2 text-label transition-colors ${
                  active
                    ? "text-mist"
                    : reached
                      ? "text-squish-700 hover:bg-squish-50"
                      : "cursor-not-allowed text-ink/35"
                }`}
              >
                {active ? (
                  <motion.span
                    layoutId="stage-indicator"
                    className="absolute inset-0 rounded-pill bg-squish-500"
                    transition={
                      reduced
                        ? { duration: 0 }
                        : { type: "spring", stiffness: 420, damping: 34 }
                    }
                  />
                ) : null}
                <span
                  className={`relative flex h-6 w-6 items-center justify-center rounded-full text-label ${
                    active
                      ? "bg-mist/25 text-mist"
                      : reached
                        ? "bg-squish-100 text-squish-700"
                        : "bg-squish-50 text-ink/35"
                  }`}
                  aria-hidden="true"
                >
                  {i + 1}
                </span>
                <span className="relative">{STAGE_LABELS[id]}</span>
              </button>

              {i < STAGES.length - 1 ? (
                <span
                  aria-hidden="true"
                  className={`hidden h-px w-6 sm:block ${
                    i < current ? "bg-squish-300" : "bg-squish-100"
                  }`}
                />
              ) : null}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
