/**
 * The figure glyphs.
 *
 * Small line drawings that let a step, a failure or a pipeline node be
 * recognised without reading it. Drawn rather than pulled from an icon font so
 * they inherit the palette and stay one stroke weight with the rest of the
 * brand.
 *
 * Duotone: a solid shape sits behind the stroke at low opacity, so the glyph
 * reads as an object with mass rather than as a wire outline. Both halves are
 * currentColor, so a glyph cannot drift off the palette no matter where it is
 * placed. Outlines alone at this size read as a smudge, which is what the
 * duotone pass fixed.
 *
 * Decorative by default: every one of these sits beside a real text label, so
 * announcing them as well would only repeat that label.
 */

import type { ReactElement, ReactNode } from "react";

import type { GlyphId } from "../../lib/hardware";

/* 1.6 was too thin to hold at 24px once the glyphs moved onto a tinted tile. */
const STROKE = 1.9;

/* One colour at two opacities. Low enough that the stroke still leads. */
const FILL_OPACITY = 0.18;

interface GlyphArt {
  stroke: ReactElement;
  /** Optional solid behind the stroke. Omitted where a glyph has no body. */
  fill?: ReactElement;
}

const PATHS: Record<GlyphId, GlyphArt> = {
  // A toggle, for the output selector.
  switch: {
    fill: <rect x="3" y="8" width="18" height="8" rx="4" />,
    stroke: (
      <>
        <rect x="3" y="8" width="18" height="8" rx="4" />
        <circle cx="16" cy="12" r="2.4" />
      </>
    ),
  },
  // Three boards stacked. The top face carries the fill.
  stack: {
    fill: <path d="M4 8.5 12 5l8 3.5-8 3.5z" />,
    stroke: (
      <>
        <path d="M4 8.5 12 5l8 3.5-8 3.5z" />
        <path d="M4 12.5 12 16l8-3.5" />
        <path d="M4 16.5 12 20l8-3.5" />
      </>
    ),
  },
  // A cloth wiping a surface. No closed body to fill.
  wipe: {
    stroke: (
      <>
        <path d="M4 16.5c3-1 5-3.5 7-3.5s3 1.5 5 1.5" />
        <path d="M7.5 9.5 10 4l7 2.5-2 5.5" />
      </>
    ),
  },
  // Two pads and a reference.
  electrode: {
    fill: (
      <>
        <circle cx="8" cy="8.5" r="2.6" />
        <circle cx="16" cy="8.5" r="2.6" />
        <circle cx="12" cy="17" r="2.2" />
      </>
    ),
    stroke: (
      <>
        <circle cx="8" cy="8.5" r="2.6" />
        <circle cx="16" cy="8.5" r="2.6" />
        <circle cx="12" cy="17" r="2.2" />
        <path d="M8 11.2v2.4M16 11.2v2.4" />
      </>
    ),
  },
  // A USB plug.
  usb: {
    fill: <circle cx="12" cy="4.6" r="1.6" />,
    stroke: (
      <>
        <path d="M12 20V7" />
        <circle cx="12" cy="4.6" r="1.6" />
        <path d="M12 13 8 9.5V7M12 15.5l4-3.5V9" />
      </>
    ),
  },
  // A flexed arm. The two strokes close into one belly.
  muscle: {
    fill: (
      <path d="M4 15c2.5 0 4-1.5 5.5-3.5S13 8 16 9s4 3 4 5.5c0 2.5-2 4-4.5 4S11 17 9 17s-3.5.6-5 2z" />
    ),
    stroke: (
      <>
        <path d="M4 15c2.5 0 4-1.5 5.5-3.5S13 8 16 9s4 3 4 5.5" />
        <path d="M20 14.5c0 2.5-2 4-4.5 4S11 17 9 17s-3.5.6-5 2" />
      </>
    ),
  },
  // A stopwatch. The dial is the body.
  stopwatch: {
    fill: <circle cx="12" cy="13.5" r="6.5" />,
    stroke: (
      <>
        <circle cx="12" cy="13.5" r="6.5" />
        <path d="M12 10.5v3l2 1.5M10 3.5h4M12 3.5V7" />
      </>
    ),
  },
  // An open hand. The palm fills, the fingers stay drawn.
  hand: {
    fill: <path d="M7.5 11h10v4c0 3-2 5-5 5s-5-2-5-5v-2z" />,
    stroke: (
      <>
        <path d="M8.5 12V6.5a1.5 1.5 0 1 1 3 0V11" />
        <path d="M11.5 11V5.5a1.5 1.5 0 1 1 3 0V11" />
        <path d="M14.5 11V7.5a1.5 1.5 0 1 1 3 0V15c0 3-2 5-5 5s-5-2-5-5v-2l-2-2a1.4 1.4 0 0 1 2-2l2 2" />
      </>
    ),
  },
  // A waveform. A line by definition, so nothing to fill.
  wave: {
    stroke: <path d="M2.5 12h2l2-5 2.5 10L12 6l2.5 11 2-8 1.5 3h3.5" />,
  },
  // A microcontroller. The die fills, the package and legs stay drawn.
  chip: {
    fill: <rect x="10" y="10" width="4" height="4" rx="1" />,
    stroke: (
      <>
        <rect x="6.5" y="6.5" width="11" height="11" rx="2" />
        <rect x="10" y="10" width="4" height="4" rx="1" />
        <path d="M9 3.5v3M15 3.5v3M9 17.5v3M15 17.5v3M3.5 9h3M3.5 15h3M17.5 9h3M17.5 15h3" />
      </>
    ),
  },
  // A dial. The sweep closes down to the pivot.
  gauge: {
    fill: <path d="M4 16.5a8 8 0 1 1 16 0z" />,
    stroke: (
      <>
        <path d="M4 16.5a8 8 0 1 1 16 0" />
        <path d="M12 16.5 16 10" />
        <circle cx="12" cy="16.5" r="1.4" />
      </>
    ),
  },
};

export function Glyph({
  id,
  size = 24,
  className = "",
}: {
  id: GlyphId;
  size?: number;
  className?: string;
}) {
  const art = PATHS[id];

  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={STROKE}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden="true"
      focusable="false"
    >
      {/* Behind the stroke, so the outline always reads on top of its own
          body rather than being softened by it. */}
      {art.fill ? (
        <g fill="currentColor" stroke="none" opacity={FILL_OPACITY}>
          {art.fill}
        </g>
      ) : null}
      {art.stroke}
    </svg>
  );
}

type TileTone = "brand" | "alert";

/*
  Four call sites hand rolled the same square, which is how two of them ended up
  with a flat wash and the other two with no tile at all. The gradient is what
  stops the tile reading as a grey shade: it runs violet to a hint of the
  mascot's coral, so an icon sits on brand colour rather than on an absence.
*/
const TILE: Record<TileTone, string> = {
  brand:
    "border-squish-100 bg-gradient-to-br from-squish-100 via-squish-50 to-squishi-body/25 text-squish-500",
  alert:
    "border-alert/30 bg-gradient-to-br from-alert/15 via-squish-50 to-squishi-body/30 text-alert",
};

/** A glyph on the standard tile. The one way an icon reaches a card. */
export function GlyphTile({
  id,
  tone = "brand",
  size = 24,
  className = "",
}: {
  id: GlyphId;
  tone?: TileTone;
  size?: number;
  className?: string;
}) {
  return (
    <span
      className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-card border ${TILE[tone]} ${className}`}
    >
      <Glyph id={id} size={size} />
    </span>
  );
}

/** The tile shape without a glyph in it, for a slot that carries its own art. */
export function GlyphTileShell({
  tone = "brand",
  className = "",
  children,
}: {
  tone?: TileTone;
  className?: string;
  children: ReactNode;
}) {
  return (
    <span
      className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-card border ${TILE[tone]} ${className}`}
    >
      {children}
    </span>
  );
}
