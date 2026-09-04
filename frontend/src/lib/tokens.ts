/**
 * Literal token values for Recharts, which cannot consume var() in every prop.
 *
 * src/index.css is the source of truth. These must stay in sync with the
 * :root block there, and a test asserts that they do.
 */

export const tokens = {
  squish50: "#F2F9FE",
  squish100: "#DCEEFB",
  squish300: "#7DC5F0",
  squish500: "#2E9BDB",
  squish700: "#1B6C9E",
  ink: "#132430",
  mist: "#FFFFFF",
  alert: "#E8825A",
  good: "#4FBFA0",
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
