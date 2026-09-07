/**
 * Settings: source selection, diagnostics, export and deletion.
 */

import { useState } from "react";

import { api } from "../lib/api";
import { useApi } from "../lib/useApi";
import { SourceChip } from "../components/Honesty";
import { SquishiMark } from "../components/brand/SquishiMark";

const PATIENT = "demo";

export function SettingsPage() {
  const sources = useApi(() => api.listSources(), []);
  const health = useApi(() => api.health(), []);
  const calibration = useApi(() => api.getCalibration(PATIENT), []);
  const [deleted, setDeleted] = useState(false);

  return (
    <div className="flex flex-col gap-6">
      <header>
        <h1 className="text-h1 text-squish-700">Settings</h1>
      </header>

      <section className="brand-watermark rounded-panel border border-squish-100 bg-mist p-5">
        <h2 className="text-label font-medium text-squish-700">Signal source</h2>

        <ul className="mt-4 flex flex-col gap-3">
          {(sources.data ?? []).map((source) => (
            <li
              key={source.id}
              className={`flex flex-wrap items-center justify-between gap-3 rounded-card border p-3 ${
                source.available
                  ? "border-squish-300"
                  : "border-squish-100 opacity-60"
              }`}
            >
              <div className="flex items-center gap-2" title={source.note}>
                <span className="text-label text-ink">{source.label}</span>
                <SourceChip isLive={source.is_live} />
              </div>
              <button
                type="button"
                disabled={!source.available}
                className="rounded-card border border-squish-300 px-3 py-1 text-label text-squish-700 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {source.available ? "Use" : "Not available"}
              </button>
            </li>
          ))}
          {sources.loading ? (
            <li className="flex items-center gap-2" role="status">
              <SquishiMark size={20} className="animate-pulse opacity-50" />
              <span className="sr-only">Loading sources</span>
            </li>
          ) : null}
          {sources.error ? (
            <li role="alert" className="text-label text-ink">
              {sources.error}
            </li>
          ) : null}
        </ul>
      </section>

      <section className="brand-watermark rounded-panel border border-squish-100 bg-mist p-5">
        <h2 className="text-label font-medium text-squish-700">Diagnostics</h2>
        <dl className="mt-3 grid gap-2 text-label sm:grid-cols-2">
          <Row label="Backend" value={health.data ? "Connected" : health.error ?? "Checking"} />
          <Row label="Sample rate" value={health.data ? `${health.data.sample_rate} Hz` : "-"} />
          <Row
            label="Analysis window"
            value={health.data ? `${health.data.window_samples} samples` : "-"}
          />
          <Row
            label="Calibration"
            value={
              calibration.data
                ? `Fitted, R squared ${calibration.data.r_squared.toFixed(2)}`
                : "Not calibrated"
            }
          />
        </dl>
      </section>

      <section className="brand-watermark rounded-panel border border-squish-100 bg-mist p-5">
        <h2 className="text-label font-medium text-squish-700">Your data</h2>

        <div className="mt-4 flex flex-wrap gap-3">
          <a
            href={`/api/export/sessions.csv?patient_id=${PATIENT}`}
            className="rounded-card border border-squish-300 px-4 py-2 text-label text-squish-700 hover:bg-squish-50"
          >
            Export sessions as CSV
          </a>
          <button
            type="button"
            onClick={async () => {
              if (!window.confirm("Delete all of your data? This cannot be undone.")) {
                return;
              }
              await api.deletePatientData(PATIENT);
              setDeleted(true);
            }}
            className="rounded-card border border-alert px-4 py-2 text-label text-alert hover:bg-alert/10"
          >
            Delete all my data
          </button>
        </div>

        {deleted ? (
          <p className="mt-2 text-label text-ink">
            Your data has been deleted. Reload to start again.
          </p>
        ) : null}
      </section>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between gap-4 border-b border-squish-50 pb-1">
      <dt className="text-ink/60">{label}</dt>
      <dd className="tabular text-ink">{value}</dd>
    </div>
  );
}
