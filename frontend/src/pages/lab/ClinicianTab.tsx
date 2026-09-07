/**
 * The clinician view, charts 22 and 23.
 *
 * Denser and more technical than the patient pages: clinical terminology
 * lives here, where a clinician reads it. The patient layer stays human.
 */

import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Line, LineChart, ResponsiveContainer, YAxis } from "recharts";

import { api } from "../../lib/api";
import { useApi } from "../../lib/useApi";
import { tokens } from "../../lib/tokens";
import { ChartFrame } from "../../components/charts/ChartFrame";
import { ClinicalTooltip, SyntheticBadge } from "../../components/Honesty";
import { Button } from "../../components/ui";
import { allowsKilograms, muscleLabel } from "../../lib/muscle";
import type { SessionSummary } from "../../types/api";

const PATIENT = "demo";

type SortKey = "started_at" | "strength_kg" | "mean_mvc" | "rep_count" | "sqi_mean";

const METRICS: Array<{ key: keyof SessionSummary; label: string; term?: string }> = [
  { key: "strength_kg", label: "Estimated grip", term: "Jamar dynamometer" },
  { key: "mean_mvc", label: "Mean effort", term: "percent MVC" },
  { key: "peak_mvc", label: "Peak effort", term: "percent MVC" },
  { key: "fatigue_slope", label: "Fatigue slope", term: "MDF slope" },
  { key: "hold_cv_mean", label: "Hold steadiness", term: "CV of force" },
  { key: "sqi_mean", label: "Signal quality", term: "SQI" },
];

export function ClinicianTab() {
  const sessions = useApi(() => api.listSessions(PATIENT), []);
  const [sortKey, setSortKey] = useState<SortKey>("started_at");
  const [completedOnly, setCompletedOnly] = useState(true);

  const rows = useMemo(() => {
    const all = sessions.data ?? [];
    const filtered = completedOnly ? all.filter((s) => s.rep_count != null) : all;

    return filtered.slice().sort((a, b) => {
      const left = a[sortKey];
      const right = b[sortKey];
      if (left == null) return 1;
      if (right == null) return -1;
      return left < right ? 1 : left > right ? -1 : 0;
    });
  }, [sessions.data, sortKey, completedOnly]);

  const chronological = rows.slice().reverse();

  return (
    <div className="flex flex-col gap-6">
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {METRICS.map((metric) => (
          <Sparkline
            key={metric.key as string}
            label={metric.label}
            term={metric.term}
            values={chronological.map((s) => Number(s[metric.key] ?? 0))}
            loading={sessions.loading}
            error={sessions.error}
            onRetry={sessions.reload}
          />
        ))}
      </div>

      <ChartFrame
        title="Session log"
        loading={sessions.loading}
        error={sessions.error}
        onRetry={sessions.reload}
        isEmpty={rows.length === 0}
        emptyMessage="No sessions recorded yet."
        height={420}
        action={
          <div className="flex items-center gap-3 text-label">
            <label className="flex items-center gap-1.5 text-ink/70">
              <input
                type="checkbox"
                checked={completedOnly}
                onChange={(e) => setCompletedOnly(e.target.checked)}
              />
              Completed only
            </label>
            <Button
              variant="secondary"
              href={`/api/export/sessions.csv?patient_id=${PATIENT}`}
            >
              Export CSV
            </Button>
          </div>
        }
      >
        <div className="h-full overflow-auto">
          <table className="w-full min-w-[46rem] text-left text-label">
            <thead className="sticky top-0 bg-mist">
              <tr className="border-b border-squish-100 text-label text-ink/60">
                <SortHeader label="Date" k="started_at" sortKey={sortKey} onSort={setSortKey} />
                <th className="py-2">Muscle</th>
                <SortHeader label="Grip (kg)" k="strength_kg" sortKey={sortKey} onSort={setSortKey} />
                <SortHeader label="Mean MVC" k="mean_mvc" sortKey={sortKey} onSort={setSortKey} />
                <SortHeader label="Reps" k="rep_count" sortKey={sortKey} onSort={setSortKey} />
                <SortHeader label="SQI" k="sqi_mean" sortKey={sortKey} onSort={setSortKey} />
                <th className="py-2">
                  <ClinicalTooltip term="Borg CR10">Borg</ClinicalTooltip>
                </th>
                <th className="py-2">Status</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((session) => (
                <tr key={session.id} className="border-b border-squish-50">
                  {/* The date opens the session, which is the row's natural
                      target: a clinician scanning the log for an outlier
                      wants the repetitions behind it. */}
                  <td className="tabular py-2.5">
                    <Link
                      to={`/progress/session/${session.id}`}
                      className="text-squish-700 underline underline-offset-4"
                    >
                      {new Date(session.started_at).toLocaleDateString()}
                    </Link>
                  </td>
                  <td className="py-2.5 text-ink/80">
                    <span className="flex items-center gap-2">
                      {muscleLabel(session.muscle)}
                      {/* Badged per row rather than once for the page, since
                          a log can mix seeded demo sessions with real ones and
                          a single page level badge cannot say which is which. */}
                      {session.is_synthetic ? <SyntheticBadge /> : null}
                    </span>
                  </td>
                  {/* Kilograms are validated on hand dynamometry, so a non
                      grip session has no figure here rather than a converted
                      one. See lib/muscle.ts. */}
                  <td className="tabular py-2.5 text-ink/80">
                    {allowsKilograms(session.muscle)
                      ? (session.strength_kg?.toFixed(1) ?? "-")
                      : "-"}
                  </td>
                  <td className="tabular py-2.5 text-ink/80">
                    {session.mean_mvc?.toFixed(0) ?? "-"}
                  </td>
                  <td className="tabular py-2.5 text-ink/80">
                    {session.rep_count ?? "-"}
                  </td>
                  <td className="tabular py-2.5 text-ink/80">
                    {session.sqi_mean?.toFixed(0) ?? "-"}
                  </td>
                  <td className="tabular py-2.5 text-ink/80">{session.borg ?? "-"}</td>
                  <td className="py-2.5 text-ink/80">
                    {session.rep_count == null ? "Missed" : "Completed"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </ChartFrame>
    </div>
  );
}

function SortHeader({
  label,
  k,
  sortKey,
  onSort,
}: {
  label: string;
  k: SortKey;
  sortKey: SortKey;
  onSort: (key: SortKey) => void;
}) {
  return (
    <th className="py-2">
      <button
        type="button"
        onClick={() => onSort(k)}
        className={sortKey === k ? "text-squish-700 underline" : "hover:text-squish-700"}
      >
        {label}
      </button>
    </th>
  );
}

function Sparkline({
  label,
  term,
  values,
  loading,
  error,
  onRetry,
}: {
  label: string;
  term?: string;
  values: number[];
  loading: boolean;
  error: string | null;
  onRetry: () => void;
}) {
  const data = values.map((value, i) => ({ i, value }));
  const latest = values.at(-1);

  return (
    <ChartFrame
      title={label}
      tooltipTerm={term}
      loading={loading}
      error={error}
      onRetry={onRetry}
      isEmpty={values.length === 0}
      emptyMessage="No data yet."
      height={90}
      action={
        <span className="tabular text-label text-squish-700">
          {latest == null ? "-" : latest.toFixed(1)}
        </span>
      }
    >
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 4, right: 2, bottom: 2, left: 2 }}>
          <YAxis hide domain={["dataMin", "dataMax"]} />
          <Line
            type="monotone"
            dataKey="value"
            stroke={tokens.squish500}
            strokeWidth={1.5}
            dot={false}
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </ChartFrame>
  );
}
