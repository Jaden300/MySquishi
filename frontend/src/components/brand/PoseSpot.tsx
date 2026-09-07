/**
 * A single still pose, placed.
 *
 * The one way a pose reaches the page. Everything else in the app that wants
 * Squishi in a fixed attitude goes through here, so a pose can never arrive as
 * a stray inline svg with its own sizing and its own accessibility mistakes.
 *
 * Placement discipline, from docs/DESIGN.md: a pose is anchored to a heading,
 * to a state, or to a datum. It never floats in whitespace on its own. At most
 * one per screenful.
 */

import type { PoseId } from "./poses";
import { PoseArt } from "./PoseArt";

interface PoseSpotProps {
  pose: PoseId;
  /** Rendered width in pixels. The box is square. */
  size?: number;
  /**
   * inline sits in the flow. The corner variants pin to a positioned parent
   * and take no pointer events, so they cannot intercept a click.
   */
  placement?: "inline" | "corner-br" | "corner-bl";
  /**
   * Give a label only when the pose carries meaning, which is the conditional
   * placements: a thumbs up on a met goal, a slump on a detected plateau, a
   * shrug on an error. Decorative poses stay hidden from assistive technology.
   */
  label?: string;
  /** Idle float. Decorative placements only, and off under reduced motion. */
  motion?: "bob" | "none";
  className?: string;
}

const PLACEMENT: Record<NonNullable<PoseSpotProps["placement"]>, string> = {
  inline: "",
  "corner-br": "pointer-events-none absolute bottom-0 right-0 translate-x-2 translate-y-2",
  "corner-bl": "pointer-events-none absolute bottom-0 left-0 -translate-x-2 translate-y-2",
};

export function PoseSpot({
  pose,
  size = 72,
  placement = "inline",
  label,
  motion = "none",
  className = "",
}: PoseSpotProps) {
  const classes = [
    "shrink-0",
    PLACEMENT[placement],
    motion === "bob" ? "bob" : "",
    className,
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 200 200"
      className={classes}
      role={label ? "img" : undefined}
      aria-label={label}
      aria-hidden={label ? undefined : true}
      focusable="false"
    >
      <PoseArt pose={pose} />
    </svg>
  );
}
