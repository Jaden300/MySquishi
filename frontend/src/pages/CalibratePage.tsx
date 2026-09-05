/**
 * Calibration.
 *
 * Fits M3, the per user force model. This is what turns signal amplitude into
 * kilograms, and it belongs to a person and an electrode placement rather
 * than to the population, which is why it is fitted here rather than trained
 * against the cohort.
 *
 * The reference is self reported. That framing travels with every estimate
 * the model later produces.
 */

import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { api } from "../lib/api";
import { useLiveStore } from "../store/live";
import { liveConnection } from "../lib/ws";
import { SquishiMascot } from "../components/SquishiMascot";
import { KG_ESTIMATE_NOTE } from "../lib/clinical";

type Stage = "intro" | "maximum" | "reference" | "done";

export function CalibratePage() {
  const navigate = useNavigate();
  const mvcPct = useLiveStore((s) => s.mvcPct);
  const status = useLiveStore((s) => s.status);

  const [stage, setStage] = useState<Stage>("intro");
  const [referenceKg, setReferenceKg] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => () => liveConnection.disconnect(), []);

  // The strongest effort of the trial. Accumulated in the store as frames
  // arrive, so this page only reads it.
  const peak = useLiveStore((s) => s.peakMvcPct);

  async function save() {
    setSaving(true);
    setError(null);

    // The trial produces amplitude features at a spread of effort levels. The
    // simulator drives this in Phase 1; with hardware attached these come from
    // the held contractions themselves.
    const fractions = [0.3, 0.45, 0.6, 0.75, 0.9, 1.0];
    const mvcReferenceRms = 0.9;

    const result = await api.calibrate({
      patient_id: "demo",
      feature_rows: fractions.map((f) => ({
        rms: mvcReferenceRms * f,
        mav: mvcReferenceRms * f * 0.82,
        waveform_length: mvcReferenceRms * f * 46,
      })),
      reference_kg: Number(referenceKg),
      mvc_reference_rms: mvcReferenceRms,
    });

    setSaving(false);
    if (result.ok) {
      setStage("done");
    } else {
      setError(result.error);
    }
  }

  return (
    <div className="mx-auto flex max-w-xl flex-col items-center gap-6 text-center">
      <SquishiMascot value={stage === "maximum" ? mvcPct : 20} size={150} />

      {stage === "intro" ? (
        <>
          <h1 className="text-xl text-squish-700">Let us find your maximum</h1>
          <p className="text-sm text-ink/70">
            Everything in MySquishi is measured against your own strongest
            effort, so we need to see it once. You will squeeze as hard as you
            comfortably can for about five seconds.
          </p>
          <button
            type="button"
            onClick={() => {
              liveConnection.connect();
              setStage("maximum");
            }}
            className="rounded-card bg-squish-500 px-5 py-2.5 text-mist hover:bg-squish-700"
          >
            Start the trial
          </button>
        </>
      ) : null}

      {stage === "maximum" ? (
        <>
          <h1 className="text-xl text-squish-700">Squeeze as hard as you can</h1>
          <p className="tabular text-4xl text-squish-700">{peak.toFixed(0)}</p>
          <p className="text-sm text-ink/60">
            {status === "running" ? "Recording..." : "Connecting..."}
          </p>
          <button
            type="button"
            onClick={() => {
              liveConnection.stop();
              liveConnection.disconnect();
              setStage("reference");
            }}
            className="rounded-card border border-squish-300 px-5 py-2.5 text-squish-700 hover:bg-squish-50"
          >
            That was my maximum
          </button>
        </>
      ) : null}

      {stage === "reference" ? (
        <>
          <h1 className="text-xl text-squish-700">
            Roughly how much can you grip?
          </h1>
          <p className="text-sm text-ink/70">
            If you know your grip strength in kilograms, from a clinic visit or
            a hand dynamometer, enter it here. It anchors the estimate to a
            real number. A rough figure is fine.
          </p>

          <input
            type="number"
            inputMode="decimal"
            value={referenceKg}
            onChange={(e) => setReferenceKg(e.target.value)}
            className="input tabular max-w-[10rem] text-center"
            placeholder="25"
            aria-label="Your grip strength in kilograms"
          />

          <p className="text-xs text-ink/60">{KG_ESTIMATE_NOTE}</p>

          {error ? (
            <p role="alert" className="text-sm text-alert">
              {error}
            </p>
          ) : null}

          <button
            type="button"
            onClick={save}
            disabled={!referenceKg || saving}
            className="rounded-card bg-squish-500 px-5 py-2.5 text-mist hover:bg-squish-700 disabled:opacity-50"
          >
            {saving ? "Saving..." : "Finish calibration"}
          </button>
        </>
      ) : null}

      {stage === "done" ? (
        <>
          <h1 className="text-xl text-squish-700">You are set up</h1>
          <p className="text-sm text-ink/70">
            Your readings will now be shown as a percentage of your own
            maximum, and estimated in kilograms.
          </p>
          <button
            type="button"
            onClick={() => navigate("/session")}
            className="rounded-card bg-squish-500 px-5 py-2.5 text-mist hover:bg-squish-700"
          >
            Start your first session
          </button>
        </>
      ) : null}
    </div>
  );
}
