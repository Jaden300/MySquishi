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
 *
 * The explanations that used to sit under each heading as grey paragraphs now
 * ride on the heading itself, as a title and as screen reader text. Someone
 * mid contraction is not reading a paragraph, and someone resting needs the
 * countdown, not a rationale for it.
 */

import { useCallback, useEffect, useState } from "react";

import { api } from "../../lib/api";
import { useLiveStore } from "../../store/live";
import { liveConnection } from "../../lib/ws";
import { SquishiMascot } from "../../components/SquishiMascot";
import { KG_ESTIMATE_NOTE } from "../../lib/clinical";
import { NON_GRIP_NOTE, allowsKilograms, muscleLabel } from "../../lib/muscle";
import { Button } from "../../components/ui";

type Step = "intro" | "maximum" | "rest" | "reference" | "done";

/** Three maximal efforts, and the highest wins. One trial can be spoiled by a
 *  slipped grip or a moment of hesitation, and three is enough to make that
 *  unlikely without fatiguing the muscle into a lower reading. */
const TRIALS = 3;

/** Five seconds of effort, thirty seconds of recovery between. Phase 2 watched
 *  a maximal grip fall from 10.99 to 4.07 across three runs in four minutes,
 *  which is ordinary fatigue: without real rest the later trials measure
 *  tiredness rather than strength. See docs/HARDWARE_FINDINGS.md. */
const REST_SECONDS = 30;

export function CalibrateStage({ onDone }: { onDone: () => void }) {
  const mvcPct = useLiveStore((s) => s.mvcPct);
  const status = useLiveStore((s) => s.status);
  const muscle = useLiveStore((s) => s.muscle);

  const [step, setStep] = useState<Step>("intro");
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
    setStep("maximum");
  }, [muscle]);

  // The rest countdown between trials. The timer owns the transition rather
  // than the effect body, so the next trial starts from the tick that reached
  // zero instead of from a render.
  useEffect(() => {
    if (step !== "rest") return;

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
  }, [step, restRemaining, startTrial]);

  const save = useCallback(async () => {
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
      setStep("done");
    } else {
      setError(result.error);
    }
  }, [muscle, referenceKg, wantsKilograms]);

  function finishTrial() {
    liveConnection.stop();
    liveConnection.disconnect();

    const recorded = [...trials, peak];
    setTrials(recorded);

    if (recorded.length >= TRIALS) {
      // A non grip muscle has no kilogram anchor to ask for, so it calibrates
      // straight to percent MVC and skips that step entirely.
      if (wantsKilograms) {
        setStep("reference");
      } else {
        void save();
      }
      return;
    }

    setRestRemaining(REST_SECONDS);
    setStep("rest");
  }

  return (
    <div className="mx-auto flex max-w-xl flex-col items-center gap-7 text-center">
      {/* Squishi tracks the step: live during a trial, and a fitting still
          pose the rest of the time. */}
      <SquishiMascot
        value={step === "maximum" ? mvcPct : 20}
        size={170}
        pose={
          step === "maximum"
            ? undefined
            : step === "rest"
              ? "resting"
              : step === "done"
                ? "celebrating"
                : step === "reference"
                  ? "explaining"
                  : "encouraging"
        }
      />

      {step === "intro" ? (
        <>
          <Heading
            title="Let us find your maximum"
            note="Everything in MySquishi is measured against your own strongest effort, so we need to see it. Three tries of about five seconds each, with a rest in between, and we keep the best one."
          />
          <Button size="lg" onClick={startTrial}>
            Start the first try
          </Button>
        </>
      ) : null}

      {step === "maximum" ? (
        <>
          <Heading
            title="Squeeze as hard as you can"
            note={`Try ${trials.length + 1} of ${TRIALS}. Hold it for about five seconds.`}
          />
          <p className="tabular text-mega text-squish-700">{peak.toFixed(0)}</p>
          <p className="text-label text-ink/70">
            Try {trials.length + 1} of {TRIALS}
            {status === "running" ? ", recording" : ", connecting"}
          </p>
          <Button size="lg" variant="secondary" onClick={finishTrial}>
            That was my maximum
          </Button>
        </>
      ) : null}

      {step === "rest" ? (
        <>
          {/*
            A resting person needs the number and nothing else. The reason a
            real rest matters is on the heading rather than beneath it.
          */}
          <Heading
            title="Rest"
            note="Let the muscle recover fully. Without a real rest the next try measures how tired you are rather than how strong you are."
          />
          <p className="tabular text-mega text-squish-700">{restRemaining}</p>
          <p className="text-label text-ink/70">
            Best so far {best.toFixed(0)} percent. Try {trials.length + 1} starts
            on its own.
          </p>
          <Button variant="secondary" onClick={startTrial}>
            Skip the rest and go now
          </Button>
        </>
      ) : null}

      {step === "reference" ? (
        <>
          <Heading
            title="Roughly how much can you grip?"
            note="If you know your grip strength in kilograms, from a clinic visit or a hand dynamometer, enter it here. It anchors the estimate to a real number. A rough figure is fine."
          />

          <input
            type="number"
            inputMode="decimal"
            value={referenceKg}
            onChange={(e) => setReferenceKg(e.target.value)}
            className="input tabular max-w-[12rem] text-center text-stat"
            placeholder="25"
            aria-label="Your grip strength in kilograms"
            title={KG_ESTIMATE_NOTE}
          />
          <span className="sr-only">{KG_ESTIMATE_NOTE}</span>

          {error ? (
            <p role="alert" className="text-body text-alert">
              {error}
            </p>
          ) : null}

          <Button
            size="lg"
            onClick={() => void save()}
            disabled={!referenceKg || saving}
          >
            {saving ? "Saving..." : "Finish calibration"}
          </Button>
        </>
      ) : null}

      {step === "done" ? (
        <>
          <Heading
            title="You are set up"
            note={
              wantsKilograms
                ? "Your readings will now be shown as a percentage of your own maximum, and estimated in kilograms."
                : `Your ${muscleLabel(muscle).toLowerCase()} readings will now be shown as a percentage of your own maximum. ${NON_GRIP_NOTE}`
            }
          />
          <p className="tabular text-mega text-squish-700">
            {best.toFixed(0)}
          </p>
          <p className="text-label text-ink/70">
            Best of {TRIALS} tries, percent of your maximum
          </p>
          <Button size="lg" onClick={onDone}>
            Start your first session
          </Button>
        </>
      ) : null}
    </div>
  );
}

/**
 * A stage heading with its explanation attached rather than printed.
 *
 * Local to this file because the note here is genuinely per step rather than
 * per section, so SectionHeader would be the wrong shape.
 */
function Heading({ title, note }: { title: string; note: string }) {
  return (
    <div title={note}>
      <h1 className="text-h1 text-squish-700">{title}</h1>
      <span className="sr-only">{note}</span>
    </div>
  );
}
