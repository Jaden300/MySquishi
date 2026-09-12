/**
 * Literal token values for Recharts, which cannot consume var() in every prop.
 *
 * src/index.css is the source of truth. These must stay in sync with the
 * :root block there, and a test asserts that they do.
 */

export const tokens = {
  squish50: "#F7F5FE",
  squish100: "#E6E1FA",
  squish300: "#9A84F5",
  squish500: "#6350C4",
  squish700: "#4B3B96",
  ink: "#2A2320",
  mist: "#FFFFFF",
  alert: "#E72414",
  good: "#128572",
} as const;

/** Maps a token key to the CSS custom property name it mirrors. */
export const cssVarNames: Record<keyof typeof tokens, string> = {
  squish50: "--squish-50",
  squish100: "--squish-100",
  squish300: "--squish-300",
  squish500: "--squish-500",
  squish700: "--squish-700",
  ink: "--ink",
  mist: "--mist",
  alert: "--alert",
  good: "--good",
};

export type TokenName = keyof typeof tokens;
