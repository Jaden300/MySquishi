/**
 * The brand mark: Squishi's face, without arms.
 *
 * This is the still mark used as furniture around the app. The animated
 * character lives in SquishiMascot, which is the only place effort drives the
 * artwork.
 *
 * The silhouette comes from PoseArt rather than from a second copy of the path.
 * It used to restate the body in its own 620x520 crop, which made the mark and
 * the mascot subtly different shapes. Nobody noticed while they never appeared
 * at the same size; the header now sets a 20px wordmark beside 88px poses, so
 * they do.
 */

import { PoseArt } from "./PoseArt";

interface SquishiMarkProps {
  size?: number;
  className?: string;
  /**
   * Supplying a title gives the mark an accessible name. Left off, the mark
   * is decorative and is hidden from assistive technology, which is the right
   * default for the watermark and empty state placements.
   */
  title?: string;
}

/*
  The body occupies x 38..162 and y 53..148 of the pose box, so the mark crops
  to that with a little air rather than using the full 200x200. Without the
  crop the mark carries roughly forty percent empty margin and reads far
  smaller than the size prop implies.
*/
const CROP = { x: 32, y: 47, w: 136, h: 107 } as const;

export function SquishiMark({ size = 24, className = "", title }: SquishiMarkProps) {
  return (
    <svg
      width={size}
      height={(size * CROP.h) / CROP.w}
      viewBox={`${CROP.x} ${CROP.y} ${CROP.w} ${CROP.h}`}
      className={className}
      role={title ? "img" : undefined}
      aria-label={title}
      aria-hidden={title ? undefined : true}
      focusable="false"
    >
      <PoseArt pose="idle" bodyOnly />
    </svg>
  );
}
