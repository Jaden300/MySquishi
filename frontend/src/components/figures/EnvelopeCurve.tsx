/**
 * Why the effort meter is not linear.
 *
 * Phase 2 measured the envelope response and found it strongly non linear
 * (docs/HARDWARE_FINDINGS.md): rest to a quarter effort barely moves the
 * number, while half to maximal nearly quintuples it. A linear meter driven by
 * that is almost motionless through the entire low effort range, which is the
 * range a rehabilitation patient works in.
 *
 * This draws the mapping in src/lib/effort.ts against the linear identity, with
 * the four measured points marked. It replaces no prose, because nobody had
 * written this down: the reasoning existed only in a docblock and a findings
 * file. It is the one figure on this page built from measured hardware data.
 */

import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceDot,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { chartText } from "../../lib/chartText";
import { EFFORT_CEILING_PCT, effortToPercent } from "../../lib/effort";
import { tokens } from "../../lib/tokens";

/**
 * The four bench readings, in volts of envelope amplitude.
 *
 * Held here rather than imported because effort.ts records them as prose in a
 * docblock. They are the evidence for the curve, so the figure states them.
 */
const MEASURED = [
  { mvc: 0, label: "Rest", volts: 0.34 },
  { mvc: 25, label: "Light", volts: 0.49 },
  { mvc: 50, label: "Medium", volts: 0.98 },
  { mvc: 100, label: "Maximal", volts: 4.89 },
];

// One point per percent, which is smooth enough at any width this renders at.
const CURVE = Array.from({ length: EFFORT_CEILING_PCT + 1 }, (_, mvc) => ({
  mvc,
  shown: effortToPercent(mvc),
  linear: (mvc / EFFORT_CEILING_PCT) * 100,
}));

export function EnvelopeCurve() {
  return (
    <div className="h-[300px] w-full">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={CURVE} margin={{ top: 16, right: 16, bottom: 20, left: 8 }}>
          <CartesianGrid stroke={tokens.squish100} />
          <XAxis
            dataKey="mvc"
            type="number"
            domain={[0, EFFORT_CEILING_PCT]}
            ticks={[0, 25, 50, 75, 100, 120]}
            tick={chartText.tick}
            stroke={tokens.ink}
            label={{
              value: "Effort, percent of your maximum",
              position: "insideBottom",
              offset: -12,
              ...chartText.axis,
            }}
          />
          <YAxis
            type="number"
            domain={[0, 100]}
            tick={chartText.tick}
            stroke={tokens.ink}
            label={{
              value: "Meter position",
              angle: -90,
              position: "insideLeft",
              ...chartText.axis,
            }}
          />
          <Tooltip
            formatter={(value, name) => [
              `${Number(value).toFixed(0)}%`,
              name === "shown" ? "What you see" : "If it were linear",
            ]}
            labelFormatter={(label) => `${label}% of maximum`}
          />

          {/* The identity, dashed, so the departure from it is the subject. */}
          <Line
            dataKey="linear"
            stroke={tokens.ink}
            strokeOpacity={0.35}
            strokeDasharray="5 5"
            strokeWidth={2}
            dot={false}
            isAnimationActive={false}
          />
          <Line
            dataKey="shown"
            stroke={tokens.squish500}
            strokeWidth={3}
            dot={false}
            isAnimationActive={false}
          />

          {MEASURED.map((point) => (
            <ReferenceDot
              key={point.label}
              x={point.mvc}
              y={effortToPercent(point.mvc)}
              r={6}
              fill={tokens.squish700}
              stroke={tokens.mist}
              strokeWidth={2}
              label={{
                value: `${point.label} ${point.volts}V`,
                position: point.mvc > 90 ? "left" : "top",
                ...chartText.label,
              }}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
