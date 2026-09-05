/**
 * Squishi's four expressions.
 *
 * Lives outside the component file so that file exports only components,
 * which is what keeps fast refresh working, and so the thresholds can be
 * tested without rendering anything.
 */

export type Expression = "resting" | "working" | "straining" | "proud";

/** Thresholds from docs/DESIGN.md. */
export function expressionFor(mvcPct: number, proud = false): Expression {
  if (proud) return "proud";
  if (mvcPct < 5) return "resting";
  if (mvcPct < 40) return "working";
  if (mvcPct <= 80) return "straining";
  return "proud";
}

export const EXPRESSION_DESCRIPTION: Record<Expression, string> = {
  resting: "Squishi is resting",
  working: "Squishi is working",
  straining: "Squishi is straining",
  proud: "Squishi is proud of you",
};

/** How long the proud face holds after a repetition closes, in milliseconds. */
export const PROUD_MS = 900;
