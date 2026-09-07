/**
 * Type inside charts.
 *
 * Recharts sets its text through props, not classes, so the Tailwind scale
 * cannot reach it. Without this module the axis type stayed at the eleven
 * pixel literals it was authored with while the rest of the app moved up, and
 * the charts would have ended up the smallest type on the page.
 *
 * The floor here is 13px rather than the 16px floor the rest of the app holds
 * to, and that is a deliberate exception. docs/DESIGN.md bans standing small
 * text because grey explanatory prose at nine pixels goes unread. An axis tick
 * is not prose: it is scale furniture, read in the context of the mark it
 * labels, and pushing ticks to 16px takes the space away from the plot and
 * makes the chart worse at the job it is there to do. A guard test holds the
 * 13px floor so it stays a decision rather than drifting back down.
 */

import { tokens } from "./tokens";

const FAMILY = "var(--font-body)";

export const chartText = {
  /** Axis ticks. The smallest type the app renders anywhere. */
  tick: { fontSize: 13, fill: tokens.ink, fontFamily: FAMILY, opacity: 0.75 },
  /** Axis names and units. */
  axis: { fontSize: 14, fill: tokens.ink, fontFamily: FAMILY },
  /** Labels attached to a reference line or a marked point. */
  label: { fontSize: 14, fill: tokens.ink, fontFamily: FAMILY },
  /** Series legend. */
  legend: { fontSize: 14, fontFamily: FAMILY },
} as const;
