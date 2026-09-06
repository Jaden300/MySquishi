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

import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { api } from "../lib/api";
import { useLiveStore } from "../store/live";
import { liveConnection } from "../lib/ws";
import { SquishiMascot } from "../components/SquishiMascot";
import { KG_ESTIMATE_NOTE } from "../lib/clinical";
import { NON_GRIP_NOTE, allowsKilograms, muscleLabel } from "../lib/muscle";

type Stage = "intro" | "maximum" | "rest" | "reference" | "done";

/** Three maximal efforts, and the highest wins. One trial can be spoiled by a
 *  slipped grip or a moment of hesitation, and three is enough to make that
 *  unlikely without fatiguing the muscle into a lower reading. */
const TRIALS = 3;

/** Five seconds of effort, thirty seconds of recovery between. Phase 2 watched
 *  a maximal grip fall from 10.99 to 4.07 across three runs in four minutes,
 *  which is ordinary fatigue: without real rest the later trials measure
 *  tiredness rather than strength. See docs/HARDWARE_FINDINGS.md. */
const REST_SECONDS = 30;

export function CalibratePage() {
  const navigate = useNavigate();
  const mvcPct = useLiveStore((s) => s.mvcPct);
  const status = useLiveStore((s) => s.status);
  const muscle = useLiveStore((s) => s.muscle);

  const [stage, setStage] = useState<Stage>("intro");
  const [referenceKg, setReferenceKg] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  // What each trial peaked at. The highest becomes the reference.
  const [trials, setTrials] = useState<number[]>([]);
  const [restRemaining, setRestRemaining] = useState(REST_SECONDS);

  useEffect(() => () => liveConnection.disconnect(), []);

  // The strongest effort of the current trial. Accumulated in the store as
  // frames arrive, so this page only reads it.
  const peak = useLiveStore((s) => s.peakMvcPct);
  const best = trials.length ? Math.max(...trials) : 0;

  // Kilograms are validated on hand dynamometry, so the reference step only
  // makes sense for grip. Every other muscle calibrates straight to percent
  // MVC, which is the honest measure everywhere. See lib/muscle.ts.
  const wantsKilograms = allowsKilograms(muscle);

  // Memoized so the countdown effect below does not restart its timer on
  // every render, which would stop the clock from ever reaching zero.
  const startTrial = useCallback(() => {
    liveConnection.connect({ muscle });
    setStage("maximum");
  }, [muscle]);

  // The rest countdown between trials. The timer owns the transition rather
  // than the effect body, so the next trial starts from the tick that reached
  // zero instead of from a render.
  useEffect(() => {
    if (stage !== "rest") return;

    const timer = setTimeout(() => {
      setRestRemaining((remaining) => {
        if (remaining <= 1) {
          startTrial();
          return 0;
        }
        return remaining - 1;
      });
    }, 1000);

    return () => clearTimeout(timer);
  }, [stage, restRemaining, startTrial]);

  function finishTrial() {
    liveConnection.stop();
    liveConnection.disconnect();

    const recorded = [...trials, peak];
    setTrials(recorded);

    if (recorded.length >= TRIALS) {
      // A non grip muscle has no kilogram anchor to ask for, so it calibrates
      // straight to percent MVC and skips that step entirely.
      if (wantsKilograms) {
        setStage("reference");
      } else {
        void save();
      }
      return;
    }

    setRestRemaining(REST_SECONDS);
    setStage("rest");
  }

  async function save() {
    setSaving(true);
    setError(null);

    // The trial produces amplitude features at a spread of effort levels,
    // anchored on the strongest of the three attempts.
    const fractions = [0.3, 0.45, 0.6, 0.75, 0.9, 1.0];
    const mvcReferenceRms = 0.9;

    const result = await api.calibrate({
      patient_id: "demo",
      muscle,
      feature_rows: fractions.map((f) => ({
        rms: mvcReferenceRms * f,
        mav: mvcReferenceRms * f * 0.82,
        waveform_length: mvcReferenceRms * f * 46,
      })),
      // Percent MVC is what a non grip calibration produces, so the kilogram
      // anchor is nominal there and the app never surfaces it.
      reference_kg: wantsKilograms ? Number(referenceKg) : 1,
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
            effort, so we need to see it. Three tries of about five seconds
            each, with a rest in between, and we keep the best one.
          </p>
          <p className="text-sm text-ink/60">
            Calibrating: {muscleLabel(muscle)}. Change the muscle on the session
            page if that is not what you are training.
          </p>
          <button
            type="button"
            onClick={startTrial}
            className="rounded-card bg-squish-500 px-5 py-2.5 text-mist hover:bg-squish-700"
          >
            Start the first try
          </button>
        </>
      ) : null}

      {stage === "maximum" ? (
        <>
          <h1 className="text-xl text-squish-700">Squeeze as hard as you can</h1>
          <p className="text-sm text-ink/60">
            Try {trials.length + 1} of {TRIALS}. Hold it for about five seconds.
          </p>
          <p className="tabular text-4xl text-squish-700">{peak.toFixed(0)}</p>
          <p className="text-sm text-ink/60">
            {status === "running" ? "Recording..." : "Connecting..."}
          </p>
          <button
            type="button"
            onClick={finishTrial}
            className="rounded-card border border-squish-300 px-5 py-2.5 text-squish-700 hover:bg-squish-50"
          >
            That was my maximum
          </button>
        </>
      ) : null}

      {stage === "rest" ? (
        <>
          <h1 className="text-xl text-squish-700">Rest</h1>
          <p className="tabular text-4xl text-squish-700">{restRemaining}</p>
          <p className="text-sm text-ink/70">
            Let the muscle recover fully. Without a real rest the next try
            measures how tired you are rather than how strong you are.
          </p>
          <p className="text-sm text-ink/60">
            Best so far: {best.toFixed(0)} percent. Try {trials.length + 1} of{" "}
            {TRIALS} starts automatically.
          </p>
          <button
            type="button"
            onClick={startTrial}
            className="rounded-card border border-squish-300 px-5 py-2.5 text-squish-700 hover:bg-squish-50"
          >
            Skip the rest and go now
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
            onClick={() => void save()}
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
            {wantsKilograms
              ? "Your readings will now be shown as a percentage of your own maximum, and estimated in kilograms."
              : `Your ${muscleLabel(muscle).toLowerCase()} readings will now be shown as a percentage of your own maximum.`}
          </p>
          <p className="text-sm text-ink/60">
            Best of {TRIALS} tries: {best.toFixed(0)} percent.
          </p>
          {!wantsKilograms ? (
            <p className="text-xs text-ink/60">{NON_GRIP_NOTE}</p>
          ) : null}
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
