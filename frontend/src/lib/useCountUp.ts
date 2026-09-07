/**
 * Counts a number up from zero once, when it first becomes available.
 *
 * Scoped tightly on purpose. This runs on mount only, never on update, so a
 * value that changes while you watch it changes immediately rather than
 * re rolling. A stat tile arriving is chrome; a measurement changing is data,
 * and docs/DESIGN.md does not let us animate data.
 *
 * Returns the target verbatim under reduced motion.
 */

import { useEffect, useRef, useState } from "react";

const DURATION_MS = 520;

function prefersReducedMotion(): boolean {
  return (
    typeof window !== "undefined" &&
    typeof window.matchMedia === "function" &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches
  );
}

export function useCountUp(target: number | null, enabled = true): number | null {
  /**
   * The fraction of the way through the sweep, 0 to 1. Only the progress is
   * state; the displayed number is derived from it during render, so a target
   * that arrives or changes is reflected immediately without an effect having
   * to write it back.
   */
  const [progress, setProgress] = useState(() =>
    // A reader who has asked for less motion gets the finished number on the
    // first paint, never a sweep they then have to wait out.
    !enabled || prefersReducedMotion() ? 1 : 0,
  );
  /** Guards the mount only rule: once a value has been animated, never again. */
  const hasRun = useRef(false);

  useEffect(() => {
    if (target === null || !Number.isFinite(target)) return;
    if (hasRun.current) return;
    if (!enabled || prefersReducedMotion()) return;

    hasRun.current = true;

    let frame = 0;
    const started = performance.now();

    const step = (now: number) => {
      const t = Math.min(1, (now - started) / DURATION_MS);
      setProgress(t);
      if (t < 1) frame = requestAnimationFrame(step);
    };

    frame = requestAnimationFrame(step);
    return () => cancelAnimationFrame(frame);
  }, [target, enabled]);

  if (target === null || !Number.isFinite(target)) return null;

  // Ease out cubic, so it decelerates into the real value rather than
  // stopping dead on it.
  const eased = 1 - Math.pow(1 - progress, 3);
  return target * eased;
}
