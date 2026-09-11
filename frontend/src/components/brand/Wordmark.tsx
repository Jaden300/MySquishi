/**
 * The wordmark: "MySquishi" with the blob standing in for the S.
 *
 * The letter spans and the mark are hidden from assistive technology and the
 * whole lockup carries one aria-label, so it is announced as a single name
 * rather than as "My" then "quishi".
 */

import { SquishiMark } from "./SquishiMark";

interface WordmarkProps {
  /** Cap height of the lettering in pixels. The mark scales from this. */
  size?: number;
  className?: string;
}

export function Wordmark({ size = 19, className = "" }: WordmarkProps) {
  const letter = {
    fontFamily: "var(--font-display)",
    /* Matches the heading rule in index.css, opsz included. The wordmark sits
       inches from an h1 in the header, so a different optical size on the two
       would read as two different typefaces. */
    fontVariationSettings: '"opsz" 48, "SOFT" 60, "WONK" 1',
    fontSize: size,
    fontWeight: 600,
    lineHeight: 1,
    letterSpacing: "-0.03em",
  } as const;

  return (
    <span
      className={`inline-flex items-center text-squish-700 ${className}`}
      aria-label="MySquishi"
      role="img"
    >
      <span style={letter} aria-hidden="true">
        My
      </span>
      {/* The mark now crops tight to the silhouette rather than carrying the
          old logo box's margin, so it needs less multiplier to read at the
          same weight beside the lettering. */}
      <SquishiMark
        size={size * 1.12}
        className="mx-[2px] mb-[-2px] shrink-0"
      />
      <span style={letter} aria-hidden="true">
        quishi
      </span>
    </span>
  );
}
