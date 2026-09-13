/**
 * The live session.
 *
 * Charts 1 to 7 plus Squishi. Everything here is driven by the websocket.
 *
 * The mascot column is sticky on a wide screen, so Squishi stays in view while
 * the charts scroll past. Squishi is the feedback loop a person actually
 * watches while contracting: losing it off the top of the screen the moment
 * you look at your repetitions defeats the point of having it.
 */

import { useEffect, useRef, useState } from "react";

import {
  CoachPrompt,
  EffortGauge,
  EnvelopeArea,
  LiveOscilloscope,
  RepTimeline,
  SignalQualityBadge,
} from "../../components/charts/LiveCharts";
import { SquishiMascot } from "../../components/SquishiMascot";
import { PoseSpot } from "../../components/brand/PoseSpot";
import { HandPanel } from "./HandPanel";
import { handTracker } from "../../lib/handTracker";
import { MuscleSelector } from "../../components/MuscleSelector";
import { SourceSelector } from "../../components/SourceSelector";
import { SourceChip } from "../../components/Honesty";
import { liveConnection } from "../../lib/ws";
import { voiceCoach } from "../../lib/speech";
import { useLiveStore } from "../../store/live";
import { speechAvailable, useVoiceStore } from "../../store/voice";
import { Button, Card } from "../../components/ui";

export function LiveStage({ onFinished }: { onFinished: (id: number) => void }) {
  const status = useLiveStore((s) => s.status);
  const isLive = useLiveStore((s) => s.isLive);
  const error = useLiveStore((s) => s.error);
  const summary = useLiveStore((s) => s.summary);
  const elapsed = useLiveStore((s) => s.elapsed);
  const reps = useLiveStore((s) => s.reps);
  const repCompletedAt = useLiveStore((s) => s.repCompletedAt);

  const muscle = useLiveStore((s) => s.muscle);
  const [junkiness, setJunkiness] = useState(0);
  const [source, setSource] = useState("simulated");

  // Leaving the page must not leave a socket open behind it.
  useEffect(() => () => liveConnection.disconnect(), []);

  // Voice belongs to this page alone: without the teardown the app carries on
  // talking over the progress dashboard.
  useEffect(() => {
    voiceCoach.start();
    return () => voiceCoach.stop();
  }, []);

  // The camera belongs to this page while it is open, exactly as it belongs to
  // the Lab tab while that is open. Without the teardown the indicator light
  // stays on after the session is over, which is the most alarming thing the
  // camera could do. Deliberately not tied to the session ending: somebody
  // reading the summary has not left yet, and killing the preview the instant
  // the last repetition lands looks like a crash.
  useEffect(() => () => handTracker.stop(), []);

  useEffect(() => {
    if (summary?.session_id) onFinished(summary.session_id);
  }, [summary, onFinished]);

  const running = status === "running";
  const idle = status === "idle" || status === "ended";

  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-h1 text-squish-700">Session</h1>
        <div className="flex items-center gap-3">
          <SourceChip isLive={isLive} />
          <span className="tabular text-label text-ink/70">
            {elapsed.toFixed(0)} s
          </span>
        </div>
      </header>

      {error ? (
        <div role="alert">
          <Card tone="alert">
            <p className="text-body text-ink">{error}</p>
          </Card>
        </div>
      ) : null}

      {/*
        Setup collapses once a session is running. Both choices are locked
        then anyway, so leaving two open selects competing with the live
        readings was giving the least useful thing on screen the most room.
      */}
      <details open={idle} className="rounded-panel border border-squish-100 bg-mist">
        <summary className="cursor-pointer px-5 py-4 text-label text-squish-700">
          Setup
        </summary>
        <div className="grid gap-5 px-5 pb-5 sm:grid-cols-2">
          <MuscleSelector disabled={!idle} />
          <SourceSelector value={source} onChange={setSource} disabled={!idle} />
        </div>
      </details>

      <div className="flex flex-wrap items-center gap-3">
        {idle ? (
          <Button
            size="lg"
            onClick={() => {
              // Browsers drop speech that no user gesture initiated, so the
              // queue is unlocked here or the first prompt is swallowed.
              voiceCoach.prime();
              liveConnection.connect({ junkiness, muscle, source });
            }}
          >
            Start session
          </Button>
        ) : (
          <>
            <Button
              variant="secondary"
              onClick={() =>
                running ? liveConnection.pause() : liveConnection.start()
              }
            >
              {running ? "Pause" : "Resume"}
            </Button>
            <Button onClick={() => liveConnection.stop()}>Finish session</Button>
          </>
        )}

        {/* Only the synthetic generator has a noise dial to turn. On a real
            sensor the quality badge reacts to the electrodes themselves. */}
        {source === "simulated" ? (
          <label className="ml-auto flex items-center gap-3 text-label text-ink/70">
            <span className="sr-only">Signal noise</span>
            <input
              type="range"
              min={0}
              max={1}
              step={0.1}
              value={junkiness}
              onChange={(e) => setJunkiness(Number(e.target.value))}
              className="w-32 accent-[var(--squish-500)]"
              aria-label="Simulated signal noise, for demonstrating the quality badge"
            />
          </label>
        ) : null}
      </div>

      <div className="grid gap-6 lg:grid-cols-[320px_1fr] lg:items-start">
        <Card
          watermark
          pad="lg"
          tone="raised"
          className="flex flex-col items-center gap-5 lg:sticky lg:top-24"
        >
          <div className="relative">
            <RepPulse at={repCompletedAt} />
            {idle && reps.length === 0 ? (
              <PoseSpot
                pose="sleeping"
                size={180}
                motion="bob"
                label="Squishi is waiting for you to start"
              />
            ) : (
              <SquishiMascot size={180} />
            )}
          </div>
          <CoachPrompt />
          <VoiceToggle />
          <HandPanel />
          <SignalQualityBadge />
          <p className="tabular text-label text-ink/70">
            {reps.length} {reps.length === 1 ? "repetition" : "repetitions"}
          </p>
        </Card>

        <div className="flex flex-col gap-6">
          <LiveOscilloscope />
          <div className="grid gap-6 md:grid-cols-2">
            <EffortGauge />
            <EnvelopeArea />
          </div>
          <RepTimeline />
        </div>
      </div>
    </div>
  );
}

/**
 * Turn the spoken coaching on and off, without leaving the session.
 *
 * Settings has the same switch, but somebody who wants the app to stop talking
 * mid contraction is not going to navigate to another page to do it. Hidden
 * outright where the browser has no speech, rather than offering a control
 * that does nothing.
 */
function VoiceToggle() {
  const voiceOn = useVoiceStore((s) => s.voiceOn);
  const setVoiceOn = useVoiceStore((s) => s.setVoiceOn);

  if (!speechAvailable()) return null;

  return (
    <button
      type="button"
      aria-pressed={voiceOn}
      onClick={() => {
        // Priming has to happen inside the gesture that turns voice on.
        if (!voiceOn) voiceCoach.prime();
        setVoiceOn(!voiceOn);
      }}
      className="rounded-pill border border-squish-300 px-3 py-1.5 text-label text-squish-700 transition-colors hover:bg-squish-50"
      title="Speak the coaching prompts, repetition counts and the session summary."
    >
      <span aria-hidden="true">{voiceOn ? "◉" : "◌"}</span>{" "}
      {voiceOn ? "Voice on" : "Voice off"}
    </button>
  );
}

/**
 * One expanding ring behind the mascot when a repetition closes.
 *
 * Keyed on the store's existing completion timestamp: a new key remounts the
 * span and so restarts the animation, which is the entire mechanism. The first
 * value seen is skipped, so remounting the page mid session does not fire a
 * celebration for a repetition that finished before you arrived.
 */
function RepPulse({ at }: { at: number | null }) {
  /**
   * The last timestamp this component has reacted to. Starts unset, and the
   * first effect run records whatever the store already held without firing,
   * so a repetition that closed before the mascot mounted is not celebrated on
   * arrival.
   */
  const seen = useRef<number | null | undefined>(undefined);
  const [show, setShow] = useState<number | null>(null);

  useEffect(() => {
    const previous = seen.current;
    seen.current = at;
    if (previous === undefined) return;
    if (at !== null && at !== previous) setShow(at);
  }, [at]);

  if (show === null) return null;

  return (
    <span
      key={show}
      aria-hidden="true"
      className="pulse-ring pointer-events-none absolute inset-0 rounded-full bg-squishi-body"
    />
  );
}
