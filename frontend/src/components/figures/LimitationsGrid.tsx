/**
 * What this app cannot tell you.
 *
 * The about page listed four limitations as four multi sentence bullets, which
 * is the exact shape nobody reads. Each becomes a tile with a glyph and a short
 * title, and the full sentence moves to the title attribute and a screen reader
 * only span.
 *
 * Nothing is deleted. docs/DESIGN.md is explicit that honesty copy may be moved
 * off the visible surface but never removed, and a limitation a reader skipped
 * because it was set in twelve pixel type was not communicated either.
 */

import type { GlyphId } from "../../lib/hardware";
import { GlyphTile } from "./Glyph";

interface Limitation {
  glyph: GlyphId;
  title: string;
  /** The original sentence, kept verbatim. */
  detail: string;
}

const LIMITATIONS: Limitation[] = [
  {
    glyph: "electrode",
    title: "Placement changes readings",
    detail:
      "Surface EMG is sensitive to electrode placement. Moving the electrodes changes the readings, which is why calibration belongs to a placement and not just to a person.",
  },
  {
    glyph: "chip",
    title: "The reference is synthetic",
    detail:
      "The normative percentile reference is synthetic and approximate. It gives context, not a diagnosis.",
  },
  {
    glyph: "wave",
    title: "Forecasts assume you keep going",
    detail:
      "Forecasts assume you keep training roughly as you have been. They describe a trend, not a promise.",
  },
  {
    glyph: "hand",
    title: "Not a diagnosis",
    detail:
      "The app does not diagnose anything, and it does not replace an assessment by a clinician.",
  },
];

export function LimitationsGrid() {
  return (
    <ul className="grid gap-4 sm:grid-cols-2">
      {LIMITATIONS.map((item) => (
        <li
          key={item.title}
          title={item.detail}
          className="flex items-start gap-4 rounded-card border border-squish-100 bg-squish-50 p-5"
        >
          <GlyphTile id={item.glyph} size={26} className="mt-0.5" />
          <div>
            <h3 className="text-h3 text-squish-700">{item.title}</h3>
            {/* The full sentence, unabridged, for anyone who wants it. */}
            <span className="sr-only">{item.detail}</span>
          </div>
        </li>
      ))}
    </ul>
  );
}
