/**
 * The progress dashboard, charts 13 to 21.
 *
 * Reads the denormalized session summaries plus the longitudinal models.
 * Model backed cards degrade honestly: when a model has not been trained the
 * card says so rather than hiding.
 */

import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { api } from "../lib/api";
import { useApi } from "../lib/useApi";
import { tokens } from "../lib/tokens";
import { PERCENTILE_NOTE } from "../lib/clinical";
import { ChartFrame } from "../components/charts/ChartFrame";
import {
  StrengthTrendChart,
  type TrendPoint,
} from "../components/charts/StrengthTrendChart";
import { IntervalReadout, SyntheticBadge } from "../components/Honesty";
import { NON_GRIP_NOTE, allowsKilograms } from "../lib/muscle";
import type { SessionSummary } from "../types/api";

const PATIENT = "demo";

export function ProgressPage() {
  const sessions = useApi(() => api.listSessions(PATIENT), []);
  const goal = useApi(() => api.getGoal(PATIENT), []);
  const forecast = useApi(() => api.forecast(PATIENT), []);
  const plateau = useApi(() => api.plateau(PATIENT), []);
  const anomalies = useApi(() => api.anomalies(PATIENT), []);
  const percentile = useApi(() => api.percentile(PATIENT), []);
  const perceived = useApi(() => api.perceived(PATIENT), []);
  const archetype = useApi(() => api.archetype(PATIENT), []);

  // Oldest first for a trend line.
  const completed = (sessions.data ?? [])
    .filter((s) => s.strength_kg != null)
    .slice()
    .reverse();

  // How many sessions the kilogram views leave out, so the omission can be
  // stated rather than silently applied.
  const nonGripCount = (sessions.data ?? []).filter(
    (s) => s.rep_count != null && !allowsKilograms(s.muscle),
  ).length;

  const trend = buildTrend(completed, forecast.data, anomalies.data);

  return (
    <div className="flex flex-col gap-6">
      <header>
        <h1 className="text-xl text-squish-700">Progress</h1>
      </header>

      <StrengthTrendChart
        data={trend}
        goalKg={goal.data?.target_kg ?? null}
        baselineKg={goal.data?.baseline_kg ?? null}
        plateauFrom={plateauIndex(plateau.data, completed.length)}
        loading={sessions.loading}
        error={sessions.error ?? forecast.error}
        onRetry={sessions.reload}
        isSynthetic={completed.some((s) => s.is_synthetic)}
        description={
          nonGripCount > 0
            ? `Measured grip sessions with a projection and its likely range. ${nonGripCount} ${
                nonGripCount === 1 ? "session on another muscle is" : "sessions on other muscles are"
              } not shown here: ${NON_GRIP_NOTE}`
            : "Measured sessions with a projection and its likely range."
        }
      />

      <div className="grid gap-6 lg:grid-cols-2">
        <GoalCard
          goal={goal.data}
          loading={goal.loading}
          error={goal.error}
          onRetry={goal.reload}
        />
        <AdherenceHeatmap
          sessions={sessions.data ?? []}
          loading={sessions.loading}
          error={sessions.error}
          onRetry={sessions.reload}
        />
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <CumulativeWork
          sessions={completed}
          loading={sessions.loading}
          error={sessions.error}
          onRetry={sessions.reload}
        />
        <PerceivedVsActual
          sessions={completed}
          loading={sessions.loading || perceived.loading}
          error={sessions.error}
          onRetry={sessions.reload}
        />
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <ModelCard
          title="Recovery archetype"
          state={archetype}
          description="Which recovery shape your trajectory most resembles."
        />
        <ModelCard
          title="Population percentile"
          state={percentile}
          description={PERCENTILE_NOTE}
          synthetic
        />
      </div>
    </div>
  );
}

function buildTrend(
  sessions: SessionSummary[],
  forecast: unknown,
  anomalies: unknown,
): TrendPoint[] {
  const anomalyById = new Map<number, "positive" | "negative">();
  const anomalyValue = (anomalies as { value?: unknown } | null)?.value;
  if (Array.isArray(anomalyValue)) {
    for (const entry of anomalyValue as Array<Record<string, unknown>>) {
      if (entry.is_anomaly && typeof entry.session_id === "number") {
        anomalyById.set(
          entry.session_id,
          entry.direction === "positive" ? "positive" : "negative",
        );
      }
    }
  }

  // Grip sessions only. The chart is in kilograms, and kilograms are validated
  // on hand dynamometry, so a biceps session has no comparable value to plot.
  // Those sessions are still shown everywhere percent MVC, fatigue and rep
  // counts appear. See lib/muscle.ts.
  const points: TrendPoint[] = sessions
    .filter((session) => allowsKilograms(session.muscle))
    .map((session, index) => ({
      index,
      label: `S${index + 1}`,
      strength: session.strength_kg ?? null,
      anomaly: anomalyById.get(session.id) ?? null,
    }));

  const forecastValue = (forecast as { value?: unknown } | null)?.value as
    | { forecast?: Array<{ point: number; lower: number; upper: number }> }
    | undefined;

  if (forecastValue?.forecast?.length) {
    const offset = points.length;
    forecastValue.forecast.forEach((step, i) => {
      points.push({
        index: offset + i,
        label: `+${i + 1}`,
        strength: null,
        forecast: step.point,
        lower: step.lower,
        upper: step.upper,
      });
    });
  }

  return points;
}

function plateauIndex(plateau: unknown, length: number): number | null {
  const value = (plateau as { value?: unknown } | null)?.value as
    | { changepoints?: number[] }
    | undefined;
  const point = value?.changepoints?.[0];
  return typeof point === "number" && point < length ? point : null;
}

function GoalCard({
  goal,
  loading,
  error,
  onRetry,
}: {
  goal: { target_kg: number | null; current_kg: number | null; baseline_kg: number | null; progress_pct: number | null } | null;
  loading: boolean;
  error: string | null;
  onRetry: () => void;
}) {
  const pct = goal?.progress_pct ?? 0;

  return (
    <ChartFrame
      title="Goal progress"
      tooltipTerm="MCID"
      loading={loading}
      error={error}
      onRetry={onRetry}
      isEmpty={!goal?.target_kg}
      emptyMessage="Set a goal to track progress toward it."
      height={200}
    >
      <div className="flex h-full items-center gap-6">
        <ProgressRing percent={pct} />
        <div className="flex flex-col gap-1">
          <span className="tabular text-3xl text-squish-700">
            {goal?.current_kg?.toFixed(1) ?? "-"} kg
          </span>
          <span className="text-sm text-ink/60">
            of {goal?.target_kg?.toFixed(1) ?? "-"} kg goal
          </span>
        </div>
      </div>
    </ChartFrame>
  );
}

function ProgressRing({ percent }: { percent: number }) {
  const radius = 44;
  const circumference = 2 * Math.PI * radius;
  const filled = (Math.max(0, Math.min(100, percent)) / 100) * circumference;

  return (
    <svg width="110" height="110" viewBox="0 0 110 110" role="img"
      aria-label={`${percent.toFixed(0)} percent of the way to your goal`}>
      <circle cx="55" cy="55" r={radius} fill="none" stroke={tokens.squish100} strokeWidth="10" />
      <circle
        cx="55"
        cy="55"
        r={radius}
        fill="none"
        stroke={tokens.good}
        strokeWidth="10"
        strokeLinecap="round"
        strokeDasharray={`${filled} ${circumference}`}
        transform="rotate(-90 55 55)"
      />
      <text x="55" y="60" textAnchor="middle" className="tabular" fontSize="18" fill={tokens.squish700}>
        {percent.toFixed(0)}%
      </text>
    </svg>
  );
}

function AdherenceHeatmap({
  sessions,
  loading,
  error,
  onRetry,
}: {
  sessions: SessionSummary[];
  loading: boolean;
  error: string | null;
  onRetry: () => void;
}) {
  const ordered = sessions.slice().reverse();
  const done = ordered.filter((s) => s.rep_count != null).length;

  return (
    <ChartFrame
      title="Adherence"
      tooltipTerm="Adherence rate"
      description={`${done} of ${ordered.length} prescribed sessions completed.`}
      loading={loading}
      error={error}
      onRetry={onRetry}
      isEmpty={ordered.length === 0}
      emptyMessage="Your session history will appear here."
      height={200}
    >
      <div className="flex h-full flex-col justify-center">
        <div className="flex flex-wrap gap-1.5">
          {ordered.map((session) => {
            const completed = session.rep_count != null;
            return (
              <span
                key={session.id}
                title={`${new Date(session.started_at).toLocaleDateString()}: ${
                  completed ? "completed" : "missed"
                }`}
                className="flex h-6 w-6 items-center justify-center rounded text-[10px]"
                style={{
                  backgroundColor: completed ? tokens.good : tokens.squish100,
                  color: completed ? tokens.mist : tokens.ink,
                }}
              >
                {/* A shape as well as a colour. */}
                {completed ? "✓" : "·"}
              </span>
            );
          })}
        </div>
      </div>
    </ChartFrame>
  );
}

function CumulativeWork({
  sessions,
  loading,
  error,
  onRetry,
}: {
  sessions: SessionSummary[];
  loading: boolean;
  error: string | null;
  onRetry: () => void;
}) {
  // Accumulated with a reduce rather than a mutable counter, so the series is
  // derived cleanly from the input on every render.
  const data = sessions.reduce<Array<{ label: string; total: number }>>(
    (acc, session, i) => {
      const previous = acc[i - 1]?.total ?? 0;
      acc.push({
        label: `S${i + 1}`,
        total: Math.round(previous + (session.total_impulse ?? 0)),
      });
      return acc;
    },
    [],
  );

  return (
    <ChartFrame
      title="Cumulative work"
      tooltipTerm="Force time integral"
      loading={loading}
      error={error}
      onRetry={onRetry}
      isEmpty={data.every((d) => d.total === 0)}
      emptyMessage="Work adds up once you record live sessions."
      height={200}
    >
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={{ top: 8, right: 8, bottom: 4, left: 4 }}>
          <CartesianGrid stroke={tokens.squish100} vertical={false} />
          <XAxis dataKey="label" tick={{ fontSize: 11 }} stroke={tokens.ink} />
          <YAxis tick={{ fontSize: 11 }} stroke={tokens.ink} />
          <Tooltip />
          <Area
            type="monotone"
            dataKey="total"
            stroke={tokens.squish500}
            fill={tokens.squish100}
            isAnimationActive={false}
          />
        </AreaChart>
      </ResponsiveContainer>
    </ChartFrame>
  );
}

function PerceivedVsActual({
  sessions,
  loading,
  error,
  onRetry,
}: {
  sessions: SessionSummary[];
  loading: boolean;
  error: string | null;
  onRetry: () => void;
}) {
  const data = sessions
    .filter((s) => s.borg != null && s.mean_mvc != null)
    .map((s) => ({ effort: s.mean_mvc as number, borg: s.borg as number }));

  return (
    <ChartFrame
      title="Perceived against measured effort"
      tooltipTerm="Borg CR10"
      description="Sessions that felt harder than they measured are worth noticing."
      loading={loading}
      error={error}
      onRetry={onRetry}
      isEmpty={data.length === 0}
      emptyMessage="Rate a few sessions and the comparison appears here."
      height={200}
    >
      <ResponsiveContainer width="100%" height="100%">
        <ScatterChart margin={{ top: 8, right: 12, bottom: 4, left: 4 }}>
          <CartesianGrid stroke={tokens.squish100} />
          <XAxis
            type="number"
            dataKey="effort"
            name="Measured"
            unit="%"
            tick={{ fontSize: 11 }}
            stroke={tokens.ink}
          />
          <YAxis
            type="number"
            dataKey="borg"
            name="Reported"
            domain={[0, 10]}
            tick={{ fontSize: 11 }}
            stroke={tokens.ink}
          />
          <Tooltip cursor={{ strokeDasharray: "3 3" }} />
          <Scatter data={data} fill={tokens.squish500} />
        </ScatterChart>
      </ResponsiveContainer>
    </ChartFrame>
  );
}

/**
 * A card for a model backed insight.
 *
 * When the endpoint is missing or the model is untrained this says so
 * plainly. A model that has not been trained is a fact about the system, not
 * something to paper over.
 */
function ModelCard({
  title,
  state,
  description,
  synthetic = false,
}: {
  title: string;
  state: { data: unknown; loading: boolean; error: string | null; reload: () => void };
  description?: string;
  synthetic?: boolean;
}) {
  const prediction = state.data as
    | { value?: unknown; explanation?: { summary?: string }; degraded?: boolean }
    | null;

  const interval = extractInterval(prediction?.value);

  return (
    <ChartFrame
      title={title}
      description={description}
      loading={state.loading}
      error={state.error}
      onRetry={state.reload}
      isEmpty={!prediction}
      emptyMessage="This insight needs more sessions before it can be computed."
      isSynthetic={synthetic}
      height={200}
    >
      <div className="flex h-full flex-col justify-center gap-3">
        {interval ? (
          <IntervalReadout
            point={interval.point}
            lower={interval.lower}
            upper={interval.upper}
            unit={interval.unit}
            degraded={prediction?.degraded}
          />
        ) : null}
        {prediction?.explanation?.summary ? (
          <p className="text-sm text-ink/70">{prediction.explanation.summary}</p>
        ) : null}
        {synthetic ? <SyntheticBadge /> : null}
      </div>
    </ChartFrame>
  );
}

function extractInterval(
  value: unknown,
): { point: number; lower: number; upper: number; unit: string } | null {
  if (!value || typeof value !== "object") return null;
  const candidate = value as Record<string, unknown>;

  if (typeof candidate.point === "number" && typeof candidate.lower === "number") {
    return {
      point: candidate.point,
      lower: candidate.lower,
      upper: candidate.upper as number,
      unit: (candidate.unit as string) ?? "",
    };
  }

  for (const nested of Object.values(candidate)) {
    const found = extractInterval(nested);
    if (found) return found;
  }
  return null;
}
