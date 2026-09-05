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
 */

import { useEffect, useState } from "react";
import { motion, useReducedMotion } from "framer-motion";

import { selectMvcPct, useLiveStore } from "../store/live";
import {
  EXPRESSION_DESCRIPTION,
  PROUD_MS,
  expressionFor,
  type Expression,
} from "../lib/expression";

export interface SquishiMascotProps {
  /**
   * Overrides the store, so the landing page can drive Squishi from a preview
   * stream rather than a live session.
   */
  value?: number;
  size?: number;
  className?: string;
}

export function SquishiMascot({
  value,
  size = 160,
  className = "",
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

  // Squash and stretch: compressing vertically while widening horizontally
  // preserves apparent volume, which is what makes it read as squishy rather
  // than simply smaller.
  const scaleY = 1 - 0.35 * effort;
  const scaleX = 1 + 0.25 * effort;

  return (
    <div
      className={className}
      role="img"
      aria-label={EXPRESSION_DESCRIPTION[expression]}
      data-expression={expression}
    >
      <svg
        width={size}
        height={size}
        viewBox="0 0 100 100"
        aria-hidden="true"
        style={{ overflow: "visible" }}
      >
        {reduceMotion ? (
          // Discrete swap. No spring, no idle motion, four fixed states.
          <g transform={`translate(50 62) scale(${discrete(effort)})`}>
            <Body expression={expression} />
          </g>
        ) : (
          <motion.g
            style={{ originX: "50px", originY: "88px" }}
            animate={{ scaleX, scaleY }}
            transition={{ type: "spring", stiffness: 300, damping: 20 }}
          >
            <g transform="translate(50 62)">
              <Body expression={expression} />
            </g>
          </motion.g>
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

function Body({ expression }: { expression: Expression }) {
  const eyeY = expression === "straining" ? -6 : -8;

  return (
    <>
      <ellipse cx="0" cy="0" rx="34" ry="30" fill="var(--squish-300)" />
      <ellipse cx="0" cy="-6" rx="26" ry="20" fill="var(--squish-100)" opacity="0.5" />

      {expression === "straining" ? (
        <>
          <path d="M -18 -14 L -6 -10" stroke="var(--squish-700)" strokeWidth="2.5" strokeLinecap="round" fill="none" />
          <path d="M 18 -14 L 6 -10" stroke="var(--squish-700)" strokeWidth="2.5" strokeLinecap="round" fill="none" />
        </>
      ) : null}

      {expression === "proud" ? (
        <>
          <path d="M -16 -8 q 5 -6 10 0" stroke="var(--squish-700)" strokeWidth="3" strokeLinecap="round" fill="none" />
          <path d="M 6 -8 q 5 -6 10 0" stroke="var(--squish-700)" strokeWidth="3" strokeLinecap="round" fill="none" />
        </>
      ) : (
        <>
          <circle cx="-11" cy={eyeY} r="3.5" fill="var(--squish-700)" />
          <circle cx="11" cy={eyeY} r="3.5" fill="var(--squish-700)" />
        </>
      )}

      <Mouth expression={expression} />
    </>
  );
}

function Mouth({ expression }: { expression: Expression }) {
  const stroke = "var(--squish-700)";
  const common = {
    stroke,
    strokeWidth: 2.5,
    strokeLinecap: "round" as const,
    fill: "none",
  };

  if (expression === "proud") {
    return <path d="M -10 6 q 10 9 20 0" {...common} />;
  }
  if (expression === "straining") {
    return <ellipse cx="0" cy="9" rx="6" ry="4.5" fill={stroke} />;
  }
  if (expression === "working") {
    return <path d="M -7 7 q 7 5 14 0" {...common} />;
  }
  return <path d="M -6 7 h 12" {...common} />;
}
