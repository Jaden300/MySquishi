/**
 * One number, named.
 *
 * Replaces the local Stat in the session summary, the local Row in settings,
 * and several one off tabular spans. The label names the number; it never
 * explains it, which is what keeps this on the right side of the standing
 * small text rule.
 */

import { PoseSpot } from "../brand/PoseSpot";
import type { PoseId } from "../brand/poses";
import { useCountUp } from "../../lib/useCountUp";
import { Card } from "./Card";

interface StatTileProps {
  label: string;
  value: number | string | null;
  unit?: string;
  decimals?: number;
  /**
   * Change against the previous period. Rendered as a glyph and a number, so
   * the direction is never carried by colour alone.
   */
  trend?: number | null;
  pose?: PoseId;
  poseLabel?: string;
  /** hero is the one enormous number a page is allowed. */
  size?: "md" | "hero";
  /** Context. Carried on hover and to assistive technology, never printed. */
  note?: string;
  tone?: "plain" | "raised" | "accent";
  className?: string;
}

export function StatTile({
  label,
  value,
  unit,
  decimals = 0,
  trend = null,
  pose,
  poseLabel,
  size = "md",
  note,
  tone = "plain",
  className = "",
}: StatTileProps) {
  const numeric = typeof value === "number" ? value : null;
  const animated = useCountUp(numeric);
  const shown = numeric === null ? null : (animated ?? 0);

  const display =
    typeof value === "string"
      ? value
      : shown === null
        ? "-"
        : shown.toFixed(decimals);

  return (
    <Card
      tone={tone}
      pad={size === "hero" ? "lg" : "md"}
      title={note}
      className={`relative flex flex-col justify-between gap-2 ${className}`}
    >
      <p className="text-label text-ink/70">{label}</p>

      <p
        className={`tabular text-squish-700 ${
          size === "hero" ? "text-mega" : "text-stat"
        }`}
      >
        {display}
        {unit ? (
          <span className="ml-1.5 font-body text-h3 text-ink/70">{unit}</span>
        ) : null}
      </p>

      {trend !== null && Number.isFinite(trend) ? (
        <p className="text-label text-ink/70">
          <span aria-hidden="true">
            {trend > 0 ? "▲" : trend < 0 ? "▼" : "■"}
          </span>{" "}
          <span className="tabular">{Math.abs(trend).toFixed(decimals)}</span>
          <span className="sr-only">
            {trend > 0 ? " higher" : trend < 0 ? " lower" : " unchanged"}
          </span>
        </p>
      ) : null}

      {note ? <span className="sr-only">{note}</span> : null}

      {pose ? (
        <PoseSpot pose={pose} size={56} placement="corner-br" label={poseLabel} />
      ) : null}
    </Card>
  );
}
