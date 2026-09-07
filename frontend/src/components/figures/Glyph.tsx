/**
 * The figure glyphs.
 *
 * Small line drawings that let a step, a failure or a pipeline node be
 * recognised without reading it. Drawn rather than pulled from an icon font so
 * they inherit the palette and stay one stroke weight with the rest of the
 * brand.
 *
 * Decorative by default: every one of these sits beside a real text label, so
 * announcing them as well would only repeat that label.
 */

import type { ReactElement } from "react";

import type { GlyphId } from "../../lib/hardware";

const STROKE = 1.6;

const PATHS: Record<GlyphId, ReactElement> = {
  // A toggle, for the output selector.
  switch: (
    <>
      <rect x="3" y="8" width="18" height="8" rx="4" />
      <circle cx="16" cy="12" r="2.4" />
    </>
  ),
  // Three boards stacked.
  stack: (
    <>
      <path d="M4 8.5 12 5l8 3.5-8 3.5z" />
      <path d="M4 12.5 12 16l8-3.5" />
      <path d="M4 16.5 12 20l8-3.5" />
    </>
  ),
  // A cloth wiping a surface.
  wipe: (
    <>
      <path d="M4 16.5c3-1 5-3.5 7-3.5s3 1.5 5 1.5" />
      <path d="M7.5 9.5 10 4l7 2.5-2 5.5" />
    </>
  ),
  // Two pads and a reference.
  electrode: (
    <>
      <circle cx="8" cy="8.5" r="2.6" />
      <circle cx="16" cy="8.5" r="2.6" />
      <circle cx="12" cy="17" r="2.2" />
      <path d="M8 11.2v2.4M16 11.2v2.4" />
    </>
  ),
  // A USB plug.
  usb: (
    <>
      <path d="M12 20V7" />
      <circle cx="12" cy="4.6" r="1.6" />
      <path d="M12 13 8 9.5V7M12 15.5l4-3.5V9" />
    </>
  ),
  // A flexed arm.
  muscle: (
    <>
      <path d="M4 15c2.5 0 4-1.5 5.5-3.5S13 8 16 9s4 3 4 5.5" />
      <path d="M20 14.5c0 2.5-2 4-4.5 4S11 17 9 17s-3.5.6-5 2" />
    </>
  ),
  // A stopwatch.
  stopwatch: (
    <>
      <circle cx="12" cy="13.5" r="6.5" />
      <path d="M12 10.5v3l2 1.5M10 3.5h4M12 3.5V7" />
    </>
  ),
  // An open hand.
  hand: (
    <>
      <path d="M8.5 12V6.5a1.5 1.5 0 1 1 3 0V11" />
      <path d="M11.5 11V5.5a1.5 1.5 0 1 1 3 0V11" />
      <path d="M14.5 11V7.5a1.5 1.5 0 1 1 3 0V15c0 3-2 5-5 5s-5-2-5-5v-2l-2-2a1.4 1.4 0 0 1 2-2l2 2" />
    </>
  ),
  // A waveform.
  wave: (
    <path d="M2.5 12h2l2-5 2.5 10L12 6l2.5 11 2-8 1.5 3h3.5" />
  ),
  // A microcontroller.
  chip: (
    <>
      <rect x="6.5" y="6.5" width="11" height="11" rx="2" />
      <rect x="10" y="10" width="4" height="4" rx="1" />
      <path d="M9 3.5v3M15 3.5v3M9 17.5v3M15 17.5v3M3.5 9h3M3.5 15h3M17.5 9h3M17.5 15h3" />
    </>
  ),
  // A dial.
  gauge: (
    <>
      <path d="M4 16.5a8 8 0 1 1 16 0" />
      <path d="M12 16.5 16 10" />
      <circle cx="12" cy="16.5" r="1.4" />
    </>
  ),
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
      {PATHS[id]}
    </svg>
  );
}
