/**
 * Session summary, charts 8 to 12.
 *
 * Historical seeded sessions have no repetition rows: those repetitions were
 * never recorded, so the rep level charts show their empty state rather than
 * inventing data to fill the space.
 */

import { useState } from "react";
import { useParams } from "react-router-dom";

import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  PolarAngleAxis,
  PolarGrid,
  PolarRadiusAxis,
  Radar,
  RadarChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { api } from "../lib/api";
import { useApi } from "../lib/useApi";
import { chartText } from "../lib/chartText";
import { tokens } from "../lib/tokens";
import { ChartFrame } from "../components/charts/ChartFrame";
import { SourceChip, SyntheticBadge } from "../components/Honesty";
import { Button, Card, PageHeader, StatTile } from "../components/ui";
import { FATIGUE_BANDWIDTH_NOTE, muscleLabel } from "../lib/muscle";
import type { Rep } from "../types/api";

interface SessionSummaryPageProps {
  /**
   * Set when the summary is rendered inline as the last stage of the training
   * flow. Left off, it reads the id from the route, which is how a historical
   * session opened from the session log arrives.
   */
  sessionId?: number;
  /** The celebration only belongs on a session you have just finished. */
  justFinished?: boolean;
}

export function SessionSummaryPage({
  sessionId: given,
  justFinished = false,
}: SessionSummaryPageProps = {}) {
  const { id } = useParams();
  const sessionId = given ?? Number(id);
  const detail = useApi(() => api.getSession(sessionId), [sessionId]);

  const session = detail.data?.session;
  const reps = detail.data?.reps ?? [];
  const noReps = reps.length === 0;

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title={justFinished ? "Nice work" : "Session summary"}
        kicker={
          session
            ? `${new Date(session.started_at).toLocaleString()} - ${muscleLabel(session.muscle)}`
            : undefined
        }
        pose={justFinished ? "celebrating" : undefined}
        poseLabel={justFinished ? "Squishi is celebrating" : undefined}
        action={
          <>
            {session?.is_synthetic ? <SyntheticBadge /> : null}
            {session ? <SourceChip isLive={session.is_live} /> : null}
          </>
        }
      />

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatTile label="Repetitions" value={session?.rep_count ?? null} />
        <StatTile
          label="Peak effort"
          value={session?.peak_mvc ?? null}
          unit="%"
        />
        <StatTile
          label="Average quality"
          value={session?.mean_rep_quality ?? null}
        />
        <StatTile label="Signal quality" value={session?.sqi_mean ?? null} />
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <ChartFrame
          title="Peak effort by repetition"
          unit="percent MVC"
          tooltipTerm="percent MVC"
          loading={detail.loading}
          error={detail.error}
          onRetry={detail.reload}
          isEmpty={noReps}
          emptyMessage="This session has no repetition detail recorded."
        >
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={repRows(reps)} margin={{ top: 8, right: 8, bottom: 4, left: 4 }}>
              <CartesianGrid stroke={tokens.squish100} vertical={false} />
              <XAxis dataKey="label" tick={chartText.tick} stroke={tokens.ink} />
              <YAxis tick={chartText.tick} stroke={tokens.ink} />
              <Tooltip />
              <Bar dataKey="peak" radius={[4, 4, 0, 0]} isAnimationActive={false}>
                {repRows(reps).map((row, i) => (
                  <Cell key={i} fill={row.quality >= 70 ? tokens.good : tokens.squish500} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </ChartFrame>

        <ChartFrame
          title="Fatigue"
          tooltipTerm="MDF slope"
          description={
            // At 500 Hz the observable spectrum stops at 250 Hz, so the upper
            // part of the sEMG band is simply not seen and the absolute
            // numbers are not textbook comparable. The within session trend,
            // which is what fatigue actually is, holds regardless.
            session?.is_live
              ? `Median frequency against repetition index. A falling line is objective evidence of fatigue. ${FATIGUE_BANDWIDTH_NOTE}`
              : "Median frequency against repetition index. A falling line is objective evidence of fatigue."
          }
          loading={detail.loading}
          error={detail.error}
          onRetry={detail.reload}
          isEmpty={noReps}
          emptyMessage="Fatigue needs repetition level data from a live session."
        >
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={repRows(reps)} margin={{ top: 8, right: 8, bottom: 4, left: 4 }}>
              <CartesianGrid stroke={tokens.squish100} vertical={false} />
              <XAxis dataKey="label" tick={chartText.tick} stroke={tokens.ink} />
              <YAxis tick={chartText.tick} stroke={tokens.ink} unit=" Hz" />
              <Tooltip />
              <Line
                type="monotone"
                dataKey="mdf"
                stroke={tokens.squish700}
                strokeWidth={2}
                isAnimationActive={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </ChartFrame>

        <ChartFrame
          title="Hold steadiness"
          tooltipTerm="CV of force"
          description="Lower is steadier."
          loading={detail.loading}
          error={detail.error}
          onRetry={detail.reload}
          isEmpty={noReps}
          emptyMessage="Steadiness needs repetition level data from a live session."
        >
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={repRows(reps)} margin={{ top: 8, right: 8, bottom: 4, left: 4 }}>
              <CartesianGrid stroke={tokens.squish100} vertical={false} />
              <XAxis dataKey="label" tick={chartText.tick} stroke={tokens.ink} />
              <YAxis tick={chartText.tick} stroke={tokens.ink} />
              <Tooltip />
              <ReferenceLine y={0.12} stroke={tokens.good} strokeDasharray="4 4" />
              <Line
                type="monotone"
                dataKey="holdCv"
                stroke={tokens.squish500}
                strokeWidth={2}
                isAnimationActive={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </ChartFrame>

        <ChartFrame
          title="Session profile"
          description="This session across its main measures."
          loading={detail.loading}
          error={detail.error}
          onRetry={detail.reload}
          isEmpty={!session?.rep_count}
          emptyMessage="Complete a session to see its profile."
        >
          <ResponsiveContainer width="100%" height="100%">
            <RadarChart data={profile(session)}>
              <PolarGrid stroke={tokens.squish100} />
              <PolarAngleAxis dataKey="metric" tick={chartText.tick} />
              <PolarRadiusAxis domain={[0, 100]} tick={chartText.tick} />
              <Radar
                dataKey="value"
                stroke={tokens.squish500}
                fill={tokens.squish300}
                fillOpacity={0.4}
                isAnimationActive={false}
              />
            </RadarChart>
          </ResponsiveContainer>
        </ChartFrame>
      </div>

      {session ? <AfterSession sessionId={session.id} /> : null}

      <div>
        <Button to="/progress" variant="secondary">
          See your progress over time
        </Button>
      </div>
    </div>
  );
}

function repRows(reps: Rep[]) {
  return reps.map((rep) => ({
    label: `${rep.index + 1}`,
    peak: rep.peak_mvc,
    quality: rep.quality?.point ?? 0,
    mdf: rep.median_frequency,
    holdCv: rep.hold_cv,
  }));
}

function profile(session: { mean_mvc: number | null; mean_rep_quality: number | null; sqi_mean: number | null; rep_count: number | null } | undefined) {
  if (!session) return [];
  return [
    { metric: "Effort", value: Math.min(100, session.mean_mvc ?? 0) },
    { metric: "Quality", value: session.mean_rep_quality ?? 0 },
    { metric: "Signal", value: session.sqi_mean ?? 0 },
    { metric: "Volume", value: Math.min(100, (session.rep_count ?? 0) * 10) },
  ];
}

/** Borg and QuickDASH, collected after the session. */
function AfterSession({ sessionId }: { sessionId: number }) {
  const [borg, setBorg] = useState<number | null>(null);
  const [saved, setSaved] = useState(false);

  return (
    <Card watermark>
      <h2
        className="text-h3 text-squish-700"
        title="Rate your effort from 0 to 10. Comparing this against what was measured is itself informative."
      >
        How did that feel?
      </h2>

      <div className="mt-4 flex flex-wrap gap-2">
        {Array.from({ length: 11 }, (_, i) => (
          <button
            key={i}
            type="button"
            onClick={async () => {
              setBorg(i);
              await api.setBorg(sessionId, i);
              setSaved(true);
            }}
            aria-pressed={borg === i}
            className={`tabular h-12 w-12 rounded-card border text-label transition-transform active:scale-[0.94] ${
              borg === i
                ? "border-squish-500 bg-squish-500 text-mist"
                : "border-squish-100 text-ink hover:bg-squish-50"
            }`}
          >
            {i}
          </button>
        ))}
      </div>

      {/* The selected button is the visible confirmation. The word is kept for
          screen readers, which have no pressed state to see. */}
      {saved ? (
        <p role="status" className="sr-only">
          Saved.
        </p>
      ) : null}
    </Card>
  );
}
