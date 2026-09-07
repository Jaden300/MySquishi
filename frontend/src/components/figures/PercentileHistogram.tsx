/**
 * Where this patient's grip sits in the reference distribution.
 *
 * Replaces a single interval readout and a sentence. The endpoint already
 * returns the histogram binned, so this draws what the model computed rather
 * than rebinning in the browser and risking a different answer to the one the
 * percentile endpoint gives.
 *
 * Grip only. Kilograms and the EWGSOP2 threshold are validated on hand
 * dynamometry, so this figure does not render at all for another muscle: the
 * caller gates it, and the clinical gate on the backend refuses the data
 * anyway. See docs/CLINICAL.md.
 *
 * The threshold line is a screening reference, not a diagnosis, and the note
 * on the frame says so.
 */

import {
  Bar,
  BarChart,
  CartesianGrid,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { ChartFrame } from "../charts/ChartFrame";
import { chartText } from "../../lib/chartText";
import { tokens } from "../../lib/tokens";
import { PERCENTILE_NOTE } from "../../lib/clinical";
import type { CohortPercentiles } from "../../types/api";

interface PercentileHistogramProps {
  data: CohortPercentiles | null;
  /** This patient's estimated grip, drawn as a line across the distribution. */
  yourKg: number | null;
  loading?: boolean;
  error?: string | null;
  onRetry?: () => void;
}

export function PercentileHistogram({
  data,
  yourKg,
  loading = false,
  error = null,
  onRetry,
}: PercentileHistogramProps) {
  const rows = (data?.histogram ?? []).map((bin) => ({
    kg: bin.strength_kg.toFixed(0),
    value: bin.strength_kg,
    count: bin.count,
  }));

  return (
    <ChartFrame
      title="How your grip compares"
      unit="kilograms"
      tooltipTerm="EWGSOP2"
      description={
        data
          ? `Reference group: ${data.reference_group}, ${data.n_reference} people. ${PERCENTILE_NOTE}` +
            (data.pooled
              ? " The requested band was too small, so a wider reference was used."
              : "")
          : PERCENTILE_NOTE
      }
      isSynthetic
      loading={loading}
      error={error}
      onRetry={onRetry}
      isEmpty={rows.length === 0}
      emptyMessage="The reference distribution could not be loaded."
      height={300}
    >
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={rows} margin={{ top: 20, right: 12, bottom: 4, left: 4 }}>
          <CartesianGrid stroke={tokens.squish100} vertical={false} />
          <XAxis dataKey="kg" tick={chartText.tick} stroke={tokens.ink} />
          <YAxis tick={chartText.tick} stroke={tokens.ink} allowDecimals={false} />
          <Tooltip
            formatter={(value) => [`${value} people`, ""]}
            labelFormatter={(label) => `${label} kg`}
          />

          <Bar
            dataKey="count"
            fill={tokens.squish300}
            radius={[4, 4, 0, 0]}
            isAnimationActive={false}
          />

          {/*
            A screening reference line, not a diagnosis. The app does not
            diagnose sarcopenia or anything else, and the term carries its
            definition through the frame's tooltip.
          */}
          {data ? (
            <ReferenceLine
              x={nearestBin(rows, data.ewgsop2_threshold)}
              stroke={tokens.alert}
              strokeDasharray="5 4"
              label={{ value: "Screening threshold", position: "top", ...chartText.label }}
            />
          ) : null}

          {yourKg != null ? (
            <ReferenceLine
              x={nearestBin(rows, yourKg)}
              stroke={tokens.squish700}
              strokeWidth={2}
              label={{ value: "You", position: "top", ...chartText.label }}
            />
          ) : null}
        </BarChart>
      </ResponsiveContainer>
    </ChartFrame>
  );
}

/**
 * A categorical x axis can only take a line at a category it actually has, so
 * a kilogram figure has to snap to the nearest bin rather than sitting at its
 * true position. The bins are roughly one kilogram wide, so the error is
 * smaller than the bar the line is drawn against.
 */
function nearestBin(
  rows: { kg: string; value: number }[],
  target: number,
): string | undefined {
  if (rows.length === 0) return undefined;
  let best = rows[0];
  for (const row of rows) {
    if (Math.abs(row.value - target) < Math.abs(best.value - target)) best = row;
  }
  return best.kg;
}
