/**
 * Progress: strength over time, consistency, and what the models make of it.
 *
 * Three tabs on one route, because these were three destinations describing
 * one thing. Reads the denormalized session summaries plus the longitudinal
 * models. Model backed cards degrade honestly: when a model has not been
 * trained the card says so rather than hiding.
 */

import type { CSSProperties } from "react";
import { useSearchParams } from "react-router-dom";
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
import { chartText } from "../lib/chartText";
import { tokens } from "../lib/tokens";
import { KG_ESTIMATE_NOTE } from "../lib/clinical";
import { ChartFrame } from "../components/charts/ChartFrame";
import {
  StrengthTrendChart,
  type TrendPoint,
} from "../components/charts/StrengthTrendChart";
import { CohortScatter } from "../components/figures/CohortScatter";
import { PercentileHistogram } from "../components/figures/PercentileHistogram";
import { SyntheticBadge } from "../components/Honesty";
import { ErrorBoundary } from "../components/Layout";
import { PoseSpot } from "../components/brand/PoseSpot";
import {
  Card,
  Figure,
  PageHeader,
  Reveal,
  StatTile,
  TabPanel,
  Tabs,
  type TabDef,
} from "../components/ui";
import {
  FATIGUE_BANDWIDTH_NOTE,
  NON_GRIP_NOTE,
  allowsKilograms,
} from "../lib/muscle";
import type { CohortPoint, Prediction, SessionSummary } from "../types/api";
import { InsightsTab } from "./progress/InsightsTab";

const PATIENT = "demo";

type ProgressTab = "strength" | "consistency" | "insights";

const TABS: TabDef<ProgressTab>[] = [
  { id: "strength", label: "Strength" },
  { id: "consistency", label: "Consistency" },
  { id: "insights", label: "Insights" },
];

export function ProgressPage() {
  const [params, setParams] = useSearchParams();
  const rawTab = params.get("tab");
  const tab: ProgressTab = TABS.some((t) => t.id === rawTab)
    ? (rawTab as ProgressTab)
    : "strength";

  const setTab = (next: ProgressTab) => {
    const updated = new URLSearchParams(params);
    updated.set("tab", next);
    setParams(updated, { replace: true });
  };

  const sessions = useApi(() => api.listSessions(PATIENT), []);
  const goal = useApi(() => api.getGoal(PATIENT), []);
  const forecast = useApi(() => api.forecast(PATIENT), []);
  const plateau = useApi(() => api.plateau(PATIENT), []);
  const anomalies = useApi(() => api.anomalies(PATIENT), []);
  const perceived = useApi(() => api.perceived(PATIENT), []);
  const archetype = useApi(() => api.archetype(PATIENT), []);
  const patient = useApi(() => api.getPatient(PATIENT), []);

  // The reference distribution needs the patient's band and sex, so it waits
  // for the profile rather than guessing a group to compare against.
  const band = patient.data?.age_band ?? null;
  const sex = patient.data?.sex ?? null;
  const cohort = useApi(
    () =>
      band && sex
        ? api.cohortPercentiles(band, sex)
        : Promise.resolve({ ok: true as const, data: null }),
    [band, sex],
  );

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
  const done = (sessions.data ?? []).filter((s) => s.rep_count != null);
  const latestKg = completed.length
    ? (completed[completed.length - 1].strength_kg ?? null)
    : null;
  const bestQuality = done.reduce<number | null>(
    (best, s) =>
      s.mean_rep_quality == null
        ? best
        : best == null
          ? s.mean_rep_quality
          : Math.max(best, s.mean_rep_quality),
    null,
  );
  const plateauAt = plateauIndex(plateau.data, completed.length);
  const anySynthetic = (sessions.data ?? []).some((s) => s.is_synthetic);

  return (
    <div className="flex flex-col gap-8">
      <PageHeader
        title="Progress"
        pose="flexing"
        note="Your strength over time, how consistently you have trained, and what the models make of it."
        action={
          <>
            {anySynthetic ? <SyntheticBadge /> : null}
            <Tabs tabs={TABS} value={tab} onChange={setTab} name="progress" />
          </>
        }
      />

      {/*
        Three numbers, before any chart. The first thing the page says should
        be where you are, not how to read a trend line.
      */}
      <div className="grid gap-4 sm:grid-cols-3">
        <StatTile
          size="hero"
          label={latestKg == null ? "Sessions completed" : "Estimated grip"}
          value={latestKg ?? done.length}
          unit={latestKg == null ? undefined : "kg"}
          decimals={latestKg == null ? 0 : 1}
          note={latestKg == null ? undefined : KG_ESTIMATE_NOTE}
        />
        <StatTile
          size="hero"
          label="Sessions completed"
          value={done.length}
        />
        <StatTile
          size="hero"
          label="Best rep quality"
          value={bestQuality}
          note="The highest average repetition quality across any one session, out of 100."
        />
      </div>

      <TabPanel name="progress" id={tab}>
        <ErrorBoundary key={tab}>
          {tab === "strength" ? (
            <div className="flex flex-col gap-6">
              <StrengthTrendChart
                data={trend}
                goalKg={goal.data?.target_kg ?? null}
                baselineKg={goal.data?.baseline_kg ?? null}
                plateauFrom={plateauAt}
                loading={sessions.loading}
                error={sessions.error ?? forecast.error}
                onRetry={sessions.reload}
                isSynthetic={completed.some((s) => s.is_synthetic)}
                description={
                  nonGripCount > 0
                    ? `Measured grip sessions with a projection and its likely range. ${nonGripCount} ${
                        nonGripCount === 1
                          ? "session on another muscle is"
                          : "sessions on other muscles are"
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
                <CumulativeWork
                  sessions={completed}
                  loading={sessions.loading}
                  error={sessions.error}
                  onRetry={sessions.reload}
                />
              </div>

              {/*
                Kilograms, the EWGSOP2 line and a population percentile are
                validated on hand dynamometry, so the comparison is withheld
                entirely for another muscle rather than shown as blanks. The
                backend refuses the data too. See docs/CLINICAL.md.
              */}
              {latestKg != null ? (
                <Reveal>
                  <PercentileHistogram
                    data={cohort.data}
                    yourKg={latestKg}
                    loading={cohort.loading || patient.loading}
                    error={cohort.error}
                    onRetry={cohort.reload}
                  />
                </Reveal>
              ) : null}
            </div>
          ) : null}

          {tab === "consistency" ? (
            <div className="flex flex-col gap-6">
              <div className="grid gap-6 lg:grid-cols-2">
                <AdherenceHeatmap
                  sessions={sessions.data ?? []}
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

              <Reveal>
                <FatigueBySession
                  sessions={completed}
                  loading={sessions.loading}
                  error={sessions.error}
                  onRetry={sessions.reload}
                />
              </Reveal>

              <Reveal>
                <CohortScatter
                  cohort={cohortPoints(archetype.data)}
                  you={archetypeCoordinates(archetype.data)}
                  yourArchetype={archetypeId(archetype.data)}
                  loading={archetype.loading}
                  error={archetype.error}
                  onRetry={archetype.reload}
                />
              </Reveal>

              {/* Only drawn when a changepoint was actually detected, so the
                  slumped pose means something rather than decorating a page. */}
              {plateauAt != null ? (
                <Card tone="accent" className="flex items-center gap-5">
                  <PoseSpot
                    pose="disappointed"
                    size={72}
                    label="Squishi looks concerned"
                  />
                  <div>
                    <h3 className="text-h3 text-squish-700">
                      Your progress has levelled off
                    </h3>
                    <p className="mt-1.5 text-body text-ink/80">
                      {summaryOf(plateau.data) ??
                        "A changepoint was detected in your trend."}
                    </p>
                  </div>
                </Card>
              ) : null}
            </div>
          ) : null}

          {tab === "insights" ? <InsightsTab /> : null}
        </ErrorBoundary>
      </TabPanel>
    </div>
  );
}

/** The M12 cohort point list, which the endpoint returns on every request. */
function cohortPoints(prediction: Prediction | null | undefined): CohortPoint[] {
  const value = prediction?.value as { cohort?: CohortPoint[] } | undefined;
  return value?.cohort ?? [];
}

function archetypeCoordinates(
  prediction: Prediction | null | undefined,
): [number, number] | null {
  const value = prediction?.value as { coordinates?: number[] } | undefined;
  const point = value?.coordinates;
  return point && point.length >= 2 ? [point[0], point[1]] : null;
}

function archetypeId(prediction: Prediction | null | undefined): string | undefined {
  return (prediction?.value as { archetype?: string } | undefined)?.archetype;
}

function summaryOf(prediction: Prediction | null | undefined): string | null {
  return prediction?.explanation?.summary ?? null;
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
          <span className="tabular text-h1 text-squish-700">
            {goal?.current_kg?.toFixed(1) ?? "-"} kg
          </span>
          <span className="text-label text-ink/60">
            of {goal?.target_kg?.toFixed(1) ?? "-"} kg goal
          </span>
        </div>

        {/* Only at the goal, so the pose is a fact about the data rather than
            decoration. It carries a label for the same reason. */}
        {pct >= 100 ? (
          <PoseSpot
            pose="thumbsUp"
            size={64}
            label="Squishi gives a thumbs up: you have reached your goal"
            className="ml-auto"
          />
        ) : null}
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
      {/*
        Drawn on with a dashoffset sweep rather than appearing complete. The
        arc is chrome: it ends at the value the data says and never overshoots
        it, so nothing about the number is animated, only its reveal. The
        global reduced motion block stops the sweep and leaves the final arc.
      */}
      <circle
        cx="55"
        cy="55"
        r={radius}
        fill="none"
        stroke={tokens.good}
        strokeWidth="10"
        strokeLinecap="round"
        strokeDasharray={circumference}
        strokeDashoffset={circumference - filled}
        className="draw-on"
        style={
          {
            "--draw-from": `${circumference}px`,
            "--draw-to": `${circumference - filled}px`,
          } as CSSProperties
        }
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
      action={<PoseSpot pose="stretching" size={56} motion="bob" />}
      loading={loading}
      error={error}
      onRetry={onRetry}
      isEmpty={ordered.length === 0}
      emptyMessage="Your session history will appear here."
      height={200}
    >
      <div className="flex h-full flex-col justify-center">
        <div className="flex flex-wrap gap-2">
          {ordered.map((session) => {
            const completed = session.rep_count != null;
            const date = new Date(session.started_at).toLocaleDateString();
            return (
              <span
                key={session.id}
                title={`${date}: ${completed ? "completed" : "missed"}`}
                className="flex h-9 w-9 items-center justify-center rounded-card"
                style={{
                  backgroundColor: completed ? tokens.good : tokens.squish100,
                }}
              >
                {/*
                  The tick is drawn rather than set as a character. It used to
                  be a ten pixel glyph, which is below the type floor and was
                  illegible at the cell size anyway. A shape scales with the
                  cell and carries the state without relying on colour.
                */}
                <svg
                  width="16"
                  height="16"
                  viewBox="0 0 16 16"
                  aria-hidden="true"
                  focusable="false"
                >
                  {completed ? (
                    <path
                      d="M3.5 8.5 L6.5 11.5 L12.5 4.5"
                      fill="none"
                      stroke={tokens.mist}
                      strokeWidth="2.4"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                  ) : (
                    <circle cx="8" cy="8" r="2" fill={tokens.ink} opacity="0.35" />
                  )}
                </svg>
                <span className="sr-only">
                  {date}: {completed ? "completed" : "missed"}
                </span>
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
          <XAxis dataKey="label" tick={chartText.tick} stroke={tokens.ink} />
          <YAxis tick={chartText.tick} stroke={tokens.ink} />
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

/**
 * How hard each session ran you down.
 *
 * The fatigue slope is the drift in median frequency across a session: a
 * steeper negative slope means the muscle tired faster. It was only ever
 * visible inside one session's summary, so a patient could not see whether
 * they are fatiguing less than they used to, which is the thing that actually
 * changes over a course of rehabilitation.
 *
 * Sessions where the fit was poor are dropped rather than drawn faintly. A
 * slope with an r squared near zero is noise, and noise plotted next to signal
 * reads as signal.
 */
function FatigueBySession({
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
    .filter(
      (s) =>
        s.fatigue_slope != null &&
        s.fatigue_r_squared != null &&
        s.fatigue_r_squared >= 0.2,
    )
    .map((s, i) => ({
      label: `S${i + 1}`,
      // Negated, so a taller bar reads as more fatigue rather than requiring
      // the reader to hold "more negative is worse" in their head.
      fatigue: -(s.fatigue_slope as number),
    }));

  return (
    <Figure
      title="Fatigue per session"
      source="measured"
      pose="exhausted"
      loading={loading}
      error={error}
      onRetry={onRetry}
      isEmpty={data.length === 0}
      emptyMessage="Fatigue appears once a few sessions have enough repetitions to fit a trend."
      note={`Taller means the muscle tired faster within that session. Sessions where the trend did not fit are not shown. ${FATIGUE_BANDWIDTH_NOTE}`}
    >
      <div className="h-[220px] w-full">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data} margin={{ top: 8, right: 8, bottom: 4, left: 4 }}>
            <CartesianGrid stroke={tokens.squish100} vertical={false} />
            <XAxis dataKey="label" tick={chartText.tick} stroke={tokens.ink} />
            <YAxis tick={chartText.tick} stroke={tokens.ink} />
            <Tooltip
              formatter={(value) => [Number(value).toFixed(3), "Fatigue rate"]}
            />
            <Area
              type="monotone"
              dataKey="fatigue"
              stroke={tokens.alert}
              fill={tokens.squish100}
              isAnimationActive={false}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </Figure>
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
            tick={chartText.tick}
            stroke={tokens.ink}
          />
          <YAxis
            type="number"
            dataKey="borg"
            name="Reported"
            domain={[0, 10]}
            tick={chartText.tick}
            stroke={tokens.ink}
          />
          <Tooltip cursor={{ strokeDasharray: "3 3" }} />
          <Scatter data={data} fill={tokens.squish500} />
        </ScatterChart>
      </ResponsiveContainer>
    </ChartFrame>
  );
}

