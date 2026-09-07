/**
 * Where this patient sits among the reference cohort.
 *
 * M12 already returns the whole PCA point list on every request. The page used
 * to throw all of it away and render one sentence, which is a shame twice
 * over: the data was on the wire, and a recovery archetype is a shape you
 * recognise far faster than a description of it.
 *
 * Every series carries a distinct shape as well as a colour, per the rule that
 * nothing in this app is conveyed by colour alone.
 */

import {
  CartesianGrid,
  Legend,
  Scatter,
  ScatterChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  ZAxis,
} from "recharts";

import { ChartFrame } from "../charts/ChartFrame";
import { chartText } from "../../lib/chartText";
import { tokens } from "../../lib/tokens";
import type { CohortPoint } from "../../types/api";

/**
 * Four archetypes, four shapes, four colours.
 *
 * The shapes are Recharts' own symbol names. Order matters only in that no two
 * are alike at a glance in greyscale.
 */
const SERIES: { id: string; label: string; shape: "circle" | "triangle" | "square" | "diamond"; colour: string }[] = [
  { id: "fast_responder", label: "Fast responder", shape: "triangle", colour: tokens.good },
  { id: "steady_climber", label: "Steady climber", shape: "circle", colour: tokens.squish500 },
  { id: "slow_starter", label: "Slow starter", shape: "square", colour: tokens.squish300 },
  { id: "plateaued", label: "Plateaued", shape: "diamond", colour: tokens.alert },
];

interface CohortScatterProps {
  cohort: CohortPoint[];
  /** This patient's own coordinates, drawn larger than the cohort. */
  you: [number, number] | null;
  yourArchetype?: string;
  loading?: boolean;
  error?: string | null;
  onRetry?: () => void;
}

export function CohortScatter({
  cohort,
  you,
  yourArchetype,
  loading = false,
  error = null,
  onRetry,
}: CohortScatterProps) {
  // Any archetype the backend returns that is not in SERIES still has to draw,
  // so unknown ids fall into one neutral group rather than vanishing.
  const known = new Set(SERIES.map((s) => s.id));
  const other = cohort.filter((p) => !known.has(p.archetype));

  return (
    <ChartFrame
      title="Recovery patterns"
      description="Each point is one person in the reference cohort, placed by the shape of their recovery. Yours is the large marker."
      isSynthetic
      loading={loading}
      error={error}
      onRetry={onRetry}
      isEmpty={cohort.length === 0}
      emptyMessage="The reference cohort could not be loaded."
      height={340}
    >
      <ResponsiveContainer width="100%" height="100%">
        <ScatterChart margin={{ top: 8, right: 12, bottom: 8, left: 4 }}>
          <CartesianGrid stroke={tokens.squish100} />
          {/*
            The axes are principal components, which have no unit anyone can
            read, so the ticks are hidden. What the chart says is which cluster
            you fall in, not what your coordinates are.
          */}
          <XAxis
            type="number"
            dataKey="x"
            tick={false}
            stroke={tokens.squish100}
            label={{ value: "Recovery shape", position: "insideBottom", offset: -4, ...chartText.axis }}
          />
          <YAxis
            type="number"
            dataKey="y"
            tick={false}
            stroke={tokens.squish100}
            label={{ value: "Recovery pace", angle: -90, position: "insideLeft", ...chartText.axis }}
          />
          <ZAxis type="number" dataKey="size" range={[60, 620]} />
          <Tooltip
            cursor={{ strokeDasharray: "3 3" }}
            formatter={(_value, _name, entry) => [
              (entry?.payload as { label?: string })?.label ?? "",
              "",
            ]}
          />
          <Legend wrapperStyle={chartText.legend} />

          {SERIES.map((series) => (
            <Scatter
              key={series.id}
              name={series.label}
              data={cohort
                .filter((p) => p.archetype === series.id)
                .map((p) => ({ ...p, size: 1, label: series.label }))}
              fill={series.colour}
              fillOpacity={0.45}
              shape={series.shape}
              isAnimationActive={false}
            />
          ))}

          {other.length ? (
            <Scatter
              name="Other"
              data={other.map((p) => ({ ...p, size: 1, label: "Other" }))}
              fill={tokens.ink}
              fillOpacity={0.25}
              shape="cross"
              isAnimationActive={false}
            />
          ) : null}

          {you ? (
            <Scatter
              name="You"
              data={[{ x: you[0], y: you[1], size: 6, label: "You" }]}
              fill={tokens.squish700}
              stroke={tokens.mist}
              strokeWidth={2}
              shape={
                SERIES.find((s) => s.id === yourArchetype)?.shape ?? "circle"
              }
              isAnimationActive={false}
            />
          ) : null}
        </ScatterChart>
      </ResponsiveContainer>
    </ChartFrame>
  );
}
