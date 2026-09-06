/**
 * The brand mark: Squishi's face, without arms, in the tighter logo crop.
 *
 * This is the still mark used as furniture around the app. The animated
 * character lives in SquishiMascot, which is the only place effort drives the
 * artwork.
 */

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

export function SquishiMark({ size = 24, className = "", title }: SquishiMarkProps) {
  return (
    <svg
      width={size}
      height={(size * 520) / 620}
      viewBox="0 0 620 520"
      className={className}
      role={title ? "img" : undefined}
      aria-label={title}
      aria-hidden={title ? undefined : true}
      focusable="false"
    >
      <path
        d="M310,60 C498,60 598,168 598,286 C598,416 488,488 310,488 C132,488 22,416 22,286 C22,168 122,60 310,60 Z"
        fill="var(--squishi-body)"
      />
      <circle cx="243" cy="272" r="31" fill="var(--squishi-face)" />
      <circle cx="377" cy="272" r="31" fill="var(--squishi-face)" />
      <path
        d="M258,352 Q310,396 362,352"
        fill="none"
        stroke="var(--squishi-face)"
        strokeWidth="23"
        strokeLinecap="round"
      />
    </svg>
  );
}
