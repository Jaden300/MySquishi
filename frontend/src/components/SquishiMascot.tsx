/**
 * Squishi.
 *
 * A small round blob that compresses in proportion to the live contraction.
 * Your effort deforms the character in real time, and that is the single
 * memorable interaction in the product, so the boldness is spent here and
 * everything else stays quiet. See docs/DESIGN.md.
 *
 * Two implementation rules come from that file.
 *
 * The component subscribes to exactly one store selector, the live percent
 * MVC scalar, so mascot re-renders never drag the charts along.
 *
 * Under prefers-reduced-motion the spring is *replaced* by a discrete four
 * state swap, not merely shortened. That is a separate branch below rather
 * than a zero duration.
 *
 * The artwork comes from the shared pose library. Poses in that library carry
 * their own squash transforms, so the animated branch suppresses those and
 * drives the geometry itself: applying both would compound the two scales and
 * flatten the blob.
 */

import { useEffect, useState } from "react";
import { motion, useReducedMotion } from "framer-motion";

import { selectMvcPct, useLiveStore } from "../store/live";
import { PoseArt } from "./brand/PoseArt";
import type { PoseId } from "./brand/poses";
import {
  EXPRESSION_DESCRIPTION,
  PROUD_MS,
  expressionFor,
  type Expression,
} from "../lib/expression";

/**
 * The four expression states map onto four of the twenty poses. The mapping
 * lives here rather than in expression.ts so the thresholds stay testable
 * without importing any artwork.
 */
const POSE_FOR_EXPRESSION: Record<Expression, PoseId> = {
  resting: "idle",
  working: "midSqueeze",
  straining: "compressed",
  proud: "cheering",
};

export interface SquishiMascotProps {
  /**
   * Overrides the store, so the landing page can drive Squishi from a preview
   * stream rather than a live session.
   */
  value?: number;
  size?: number;
  className?: string;
  /**
   * Pins Squishi to one pose from the library, for the static placements that
   * illustrate rather than report. Effort still drives the accessible name.
   */
  pose?: PoseId;
}

export function SquishiMascot({
  value,
  size = 160,
  className = "",
  pose,
}: SquishiMascotProps) {
  // Exactly one selector. This is the whole point of the flat scalar in the
  // store: nothing else here re-renders when a frame arrives.
  const storeValue = useLiveStore(selectMvcPct);
  const repCompletedAt = useLiveStore((s) => s.repCompletedAt);
  const reduceMotion = useReducedMotion();

  const mvcPct = value ?? storeValue;

  // The proud face fires on rep completion and decays after a moment.
  // Tracking which repetition we last celebrated, rather than reading the
  // clock during render, keeps the output a pure function of state.
  const [celebrated, setCelebrated] = useState(0);

  useEffect(() => {
    if (value !== undefined || repCompletedAt === 0) return;

    const timer = window.setTimeout(
      () => setCelebrated(repCompletedAt),
      PROUD_MS,
    );
    return () => window.clearTimeout(timer);
  }, [repCompletedAt, value]);

  const justFinishedRep =
    value === undefined && repCompletedAt !== 0 && celebrated !== repCompletedAt;

  const expression = expressionFor(mvcPct, justFinishedRep);
  const effort = Math.max(0, Math.min(100, mvcPct)) / 100;

  const activePose = pose ?? POSE_FOR_EXPRESSION[expression];

  // Squash and stretch: compressing vertically while widening horizontally
  // preserves apparent volume, which is what makes it read as squishy rather
  // than simply smaller. The pose artwork already sits at a comfortable size
  // in its 200 unit box, so the deformation here is gentler than the authored
  // extremes: past about a quarter the blob stops reading as a face.
  const scaleY = 1 - 0.24 * effort;
  const scaleX = 1 + 0.18 * effort;

  // A pinned pose is a still illustration, so it keeps the artwork's own
  // squash and skips the live spring entirely.
  const animated = pose === undefined && !reduceMotion;

  return (
    <div
      className={className}
      role="img"
      aria-label={EXPRESSION_DESCRIPTION[expression]}
      data-expression={expression}
      data-pose={activePose}
    >
      <svg
        width={size}
        height={size}
        viewBox="0 0 200 200"
        aria-hidden="true"
        style={{ overflow: "visible" }}
      >
        {animated ? (
          <motion.g
            /*
              The pivot is the blob's own base, so squashing presses it down
              onto that line rather than shrinking it toward the middle of the
              frame. Arms are inside this group, so they travel with the body
              instead of detaching from it.
            */
            style={{ originX: "100px", originY: "160px" }}
            animate={{ scaleX, scaleY }}
            transition={{ type: "spring", stiffness: 300, damping: 20 }}
          >
            {/*
              bodyTransform null suppresses the pose's authored squash, so the
              spring above is the only thing scaling the character, and the
              arms come from idle so they stay readable at full compression.
            */}
            <PoseArt pose={activePose} bodyTransform={null} armsFrom="idle" />
          </motion.g>
        ) : pose === undefined ? (
          // Discrete swap. No spring, no idle motion, four fixed states.
          <g
            transform={`translate(100 160) scale(${discrete(effort)}) translate(-100 -160)`}
          >
            <PoseArt pose={activePose} bodyTransform={null} armsFrom="idle" />
          </g>
        ) : (
          <PoseArt pose={activePose} />
        )}
      </svg>
    </div>
  );
}

/** Four fixed sizes for the reduced motion branch. */
function discrete(effort: number): string {
  if (effort < 0.05) return "1 1";
  if (effort < 0.4) return "1.08 0.92";
  if (effort <= 0.8) return "1.16 0.84";
  return "1.25 0.75";
}
