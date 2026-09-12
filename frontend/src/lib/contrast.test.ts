// @vitest-environment node
import { describe, expect, it } from "vitest";

import { tokens } from "./tokens";

/**
 * The accessibility floor in docs/DESIGN.md promises AA contrast throughout.
 * That was a sentence in a document, and three tokens quietly failed it:
 * white on the primary violet measured 4.40, the alert red 3.50, and the good
 * teal 2.99 despite a comment claiming it had been darkened to pass.
 *
 * None of that is visible by eye, which is the point of measuring it. This
 * file turns the promise into a test so the next palette edit has to keep it.
 *
 * Thresholds are WCAG 2.1 AA: 4.5 for normal text, 3.0 for large text, UI
 * components and graphical objects.
 */

const AA_TEXT = 4.5;
const AA_LARGE = 3.0;

function channel(value: number): number {
  const c = value / 255;
  return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
}

function luminance(hex: string): number {
  const h = hex.replace("#", "");
  const [r, g, b] = [0, 2, 4].map((i) => parseInt(h.slice(i, i + 2), 16));
  return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b);
}

/** WCAG contrast ratio, 1 to 21. */
export function contrastRatio(a: string, b: string): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
}

/** Flatten a token drawn at partial opacity over its background. */
function blend(fg: string, bg: string, alpha: number): string {
  const strip = (h: string) => h.replace("#", "");
  const parts = [0, 2, 4].map((i) => {
    const f = parseInt(strip(fg).slice(i, i + 2), 16);
    const b = parseInt(strip(bg).slice(i, i + 2), 16);
    return Math.round(f * alpha + b * (1 - alpha))
      .toString(16)
      .padStart(2, "0");
  });
  return `#${parts.join("")}`;
}

describe("palette contrast", () => {
  // The two surfaces everything is read on: the page and a card.
  const surfaces: Array<[string, string]> = [
    ["page", tokens.squish50],
    ["card", tokens.mist],
  ];

  it.each(surfaces)("reads body text on %s", (_name, surface) => {
    expect(contrastRatio(tokens.ink, surface)).toBeGreaterThanOrEqual(AA_TEXT);
  });

  it.each(surfaces)("reads headings on %s", (_name, surface) => {
    expect(contrastRatio(tokens.squish700, surface)).toBeGreaterThanOrEqual(
      AA_TEXT,
    );
  });

  it("reads white on the primary fill", () => {
    // The active nav pill, the active tab and every primary button.
    expect(contrastRatio(tokens.mist, tokens.squish500)).toBeGreaterThanOrEqual(
      AA_TEXT,
    );
  });

  it("reads the primary violet as text on a card", () => {
    // Same token, used the other way round. Both directions have to pass.
    expect(contrastRatio(tokens.squish500, tokens.mist)).toBeGreaterThanOrEqual(
      AA_TEXT,
    );
  });

  it("reads error copy on a card", () => {
    expect(contrastRatio(tokens.alert, tokens.mist)).toBeGreaterThanOrEqual(
      AA_TEXT,
    );
  });

  it("reads the good state on a card", () => {
    expect(contrastRatio(tokens.good, tokens.mist)).toBeGreaterThanOrEqual(
      AA_TEXT,
    );
  });

  it("draws the chip text on its own tint", () => {
    expect(
      contrastRatio(tokens.squish700, tokens.squish100),
    ).toBeGreaterThanOrEqual(AA_TEXT);
  });

  it("draws the raw signal trace visibly", () => {
    // A one pixel line carrying data, so the graphical-object floor applies
    // rather than the text one.
    expect(contrastRatio(tokens.squish300, tokens.mist)).toBeGreaterThanOrEqual(
      AA_LARGE,
    );
  });
});

describe("ink at partial opacity", () => {
  /**
   * text-ink/NN is the systemic risk: it looks like a shade of the body
   * colour and behaves like a different token. Anything below /70 fails as
   * normal text on white, so the rule is that readable copy stops at /70.
   */
  it.each([
    [70, tokens.mist],
    [80, tokens.mist],
    [70, tokens.squish50],
    [80, tokens.squish50],
  ])("passes at /%i", (opacity, surface) => {
    const flattened = blend(tokens.ink, surface, opacity / 100);
    expect(contrastRatio(flattened, surface)).toBeGreaterThanOrEqual(AA_TEXT);
  });

  it.each([40, 45, 50, 60])(
    "fails at /%i, which is why readable copy may not use it",
    (opacity) => {
      const flattened = blend(tokens.ink, tokens.mist, opacity / 100);
      expect(contrastRatio(flattened, tokens.mist)).toBeLessThan(AA_TEXT);
    },
  );
});
