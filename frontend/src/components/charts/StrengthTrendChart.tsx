/**
 * Charts 13, 16 and 21 as one composition.
 *
 * The forecast fan, the anomaly markers and the plateau annotation all draw
 * on the same axes over the same strength history. Building them as three
 * separate Recharts trees would mean three sets of axes that have to be kept
 * in agreement by hand, so they are layers on one chart instead.
 */

import {
  Area,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ReferenceDot,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { chartText } from "../../lib/chartText";
import { tokens } from "../../lib/tokens";
import { useNarrow } from "../../lib/useNarrow";
import { KG_ESTIMATE_NOTE, MCID_KG } from "../../lib/clinical";
import { ChartFrame } from "./ChartFrame";

export interface TrendPoint {
  index: number;
  label: string;
  strength: number | null;
  /** Forecast median, only on future points. */
  forecast?: number | null;
  lower?: number | null;
  upper?: number | null;
  anomaly?: "positive" | "negative" | null;
}

export interface StrengthTrendChartProps {
  data: TrendPoint[];
  goalKg?: number | null;
  baselineKg?: number | null;
  /** Where a changepoint was detected, as an index into data. */
  plateauFrom?: number | null;
  loading?: boolean;
  error?: string | null;
  isSynthetic?: boolean;
  onRetry?: () => void;
  title?: string;
  description?: string;
}

export function StrengthTrendChart({
  data,
  goalKg,
  baselineKg,
  plateauFrom,
  loading,
  error,
  isSynthetic,
  onRetry,
  title = "Strength over time",
  description,
}: StrengthTrendChartProps) {
  const anomalies = data.filter((d) => d.anomaly);

  // The Goal and MCID labels sit outside the plot, so they need a right
  // margin to land in. At 390px that margin was 52 of roughly 290 usable
  // pixels, nearly a fifth of the chart given over to two words. Below sm the
  // labels move inside the plot instead and the margin comes back.
  const narrow = useNarrow();
  const labelPosition = narrow ? "insideTopRight" : "right";

  return (
    <ChartFrame
      title={title}
      unit="kg"
      tooltipTerm="Jamar dynamometer"
      description={description ?? KG_ESTIMATE_NOTE}
      loading={loading}
      error={error}
      onRetry={onRetry}
      isEmpty={data.length === 0}
      emptyMessage="Complete a few sessions and your progress will appear here."
      isSynthetic={isSynthetic}
      height={320}
    >
      <ResponsiveContainer width="100%" height="100%">
        {/* The right margin is where the goal and MCID labels land, so without
            it they would be clipped. Below sm they move inside the plot and
            the margin is not needed. */}
        <ComposedChart
          data={data}
          margin={{ top: 8, right: narrow ? 8 : 52, bottom: 4, left: 4 }}
        >
          <CartesianGrid stroke={tokens.squish100} vertical={false} />
          <XAxis dataKey="label" tick={chartText.tick} stroke={tokens.ink} />
          <YAxis
            tick={chartText.tick}
            stroke={tokens.ink}
            label={{
              value: "kg",
              angle: -90,
              position: "insideLeft",
              ...chartText.label,
            }}
          />
          <Tooltip
            formatter={(value, name) => [`${Number(value).toFixed(1)} kg`, name]}
          />
          <Legend wrapperStyle={chartText.legend} />

          {/* The 80 percent band. Drawn first so the lines sit on top. */}
          <Area
            dataKey="upper"
            stroke="none"
            fill={tokens.squish100}
            name="Likely range"
            isAnimationActive={false}
          />
          <Area
            dataKey="lower"
            stroke="none"
            fill={tokens.mist}
            legendType="none"
            isAnimationActive={false}
          />

          <Line
            type="monotone"
            dataKey="strength"
            name="Measured"
            stroke={tokens.squish700}
            strokeWidth={2}
            dot={{ r: 2 }}
            connectNulls
            isAnimationActive={false}
          />
          <Line
            type="monotone"
            dataKey="forecast"
            name="Projected"
            stroke={tokens.squish500}
            strokeWidth={2}
            strokeDasharray="5 4"
            dot={false}
            connectNulls
            isAnimationActive={false}
          />

          {goalKg ? (
            <ReferenceLine
              y={goalKg}
              stroke={tokens.good}
              strokeDasharray="4 4"
              label={{ value: "Goal", ...chartText.label, position: labelPosition }}
            />
          ) : null}

          {/* The smallest change that is actually meaningful. */}
          {baselineKg ? (
            <ReferenceLine
              y={baselineKg + MCID_KG}
              stroke={tokens.squish300}
              strokeDasharray="2 4"
              label={{ value: "MCID", ...chartText.label, position: labelPosition }}
            />
          ) : null}

          {plateauFrom != null && data[plateauFrom] ? (
            <ReferenceLine
              x={data[plateauFrom].label}
              stroke={tokens.alert}
              label={{ value: "Plateau", ...chartText.label, position: "top" }}
            />
          ) : null}

          {/*
            Anomalies carry a label as well as a colour, so the distinction
            survives for anyone who cannot rely on hue. An exceptional session
            is marked as such rather than being flagged as a problem.
          */}
          {anomalies.map((point) => (
            <ReferenceDot
              key={point.index}
              x={point.label}
              y={point.strength ?? 0}
              r={5}
              fill={point.anomaly === "positive" ? tokens.good : tokens.alert}
              stroke={tokens.mist}
              label={{
                value: point.anomaly === "positive" ? "Standout" : "Off pattern",
                ...chartText.label,
                position: "top",
              }}
            />
          ))}
        </ComposedChart>
      </ResponsiveContainer>
    </ChartFrame>
  );
}
