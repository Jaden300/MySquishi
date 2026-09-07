/**
 * Settings: source selection, diagnostics, export and deletion.
 *
 * Diagnostics used to be a definition list of four small rows. They are four
 * numbers about whether the system is working, which is what a stat tile is
 * for, so they are read at a glance rather than scanned.
 */

import { useState } from "react";

import { api } from "../../lib/api";
import { useApi } from "../../lib/useApi";
import { SourceChip } from "../../components/Honesty";
import { SquishiMark } from "../../components/brand/SquishiMark";
import { PoseSpot } from "../../components/brand/PoseSpot";
import { Button, Card, SectionHeader, StatTile } from "../../components/ui";

const PATIENT = "demo";

export function SettingsTab() {
  const sources = useApi(() => api.listSources(), []);
  const health = useApi(() => api.health(), []);
  const calibration = useApi(() => api.getCalibration(PATIENT), []);
  const [deleted, setDeleted] = useState(false);

  return (
    <div className="flex flex-col gap-10">
      <section>
        <SectionHeader
          title="Signal source"
          note="Where readings come from. The simulator is always available."
        />

        <ul className="flex flex-col gap-3">
          {(sources.data ?? []).map((source) => (
            <li key={source.id}>
              <Card
                tone={source.available ? "plain" : "plain"}
                className={`flex flex-wrap items-center justify-between gap-4 ${
                  source.available ? "" : "opacity-60"
                }`}
                title={source.note}
              >
                <div className="flex items-center gap-3">
                  <span className="text-h3 text-squish-700">{source.label}</span>
                  <SourceChip isLive={source.is_live} />
                </div>
                <span className="text-label text-ink/70">
                  {source.available ? "Available" : "Not available"}
                </span>
                {source.note ? (
                  <span className="sr-only">{source.note}</span>
                ) : null}
              </Card>
            </li>
          ))}

          {sources.loading ? (
            <li className="flex items-center gap-2" role="status">
              <SquishiMark size={26} className="animate-pulse opacity-50" />
              <span className="sr-only">Loading sources</span>
            </li>
          ) : null}

          {sources.error ? (
            <li role="alert">
              <Card tone="alert" className="flex items-center gap-4">
                <PoseSpot pose="confused" size={52} />
                <p className="text-body text-ink">{sources.error}</p>
              </Card>
            </li>
          ) : null}
        </ul>
      </section>

      <section>
        <SectionHeader
          title="Diagnostics"
          note="Whether the backend, the sampling and your calibration are all in order."
        />
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <StatTile
            label="Backend"
            value={health.data ? "Connected" : (health.error ?? "Checking")}
            pose={health.error ? "confused" : undefined}
            poseLabel={health.error ? "Squishi cannot reach the server" : undefined}
          />
          <StatTile
            label="Sample rate"
            value={health.data?.sample_rate ?? null}
            unit="Hz"
          />
          <StatTile
            label="Analysis window"
            value={health.data?.window_samples ?? null}
            unit="samples"
          />
          <StatTile
            label="Calibration fit"
            value={
              calibration.data
                ? calibration.data.r_squared
                : "Not calibrated"
            }
            decimals={2}
            note="R squared of the fit between signal amplitude and force. Closer to one is a better fit."
          />
        </div>
      </section>

      <section>
        <SectionHeader title="Your data" />
        <div className="flex flex-wrap gap-3">
          <Button
            variant="secondary"
            href={`/api/export/sessions.csv?patient_id=${PATIENT}`}
          >
            Export sessions as CSV
          </Button>
          <Button
            variant="danger"
            onClick={async () => {
              if (
                !window.confirm("Delete all of your data? This cannot be undone.")
              ) {
                return;
              }
              await api.deletePatientData(PATIENT);
              setDeleted(true);
            }}
          >
            {deleted ? "Deleted, reload to start again" : "Delete all my data"}
          </Button>
        </div>

        {/* The button's own label is the visible confirmation. The sentence is
            kept for screen readers, which have no changed label to notice. */}
        {deleted ? (
          <p role="status" className="sr-only">
            Your data has been deleted. Reload to start again.
          </p>
        ) : null}
      </section>
    </div>
  );
}
