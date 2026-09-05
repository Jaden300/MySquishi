/**
 * The live session.
 *
 * Charts 1 to 7 plus Squishi. Everything here is driven by the websocket.
 */

import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import {
  CoachPrompt,
  EffortGauge,
  EnvelopeArea,
  LiveOscilloscope,
  RepTimeline,
  SignalQualityBadge,
} from "../components/charts/LiveCharts";
import { SquishiMascot } from "../components/SquishiMascot";
import { SourceChip } from "../components/Honesty";
import { liveConnection } from "../lib/ws";
import { useLiveStore } from "../store/live";

export function SessionPage() {
  const navigate = useNavigate();
  const status = useLiveStore((s) => s.status);
  const isLive = useLiveStore((s) => s.isLive);
  const error = useLiveStore((s) => s.error);
  const summary = useLiveStore((s) => s.summary);
  const elapsed = useLiveStore((s) => s.elapsed);
  const reps = useLiveStore((s) => s.reps);

  const [junkiness, setJunkiness] = useState(0);

  // Leaving the page must not leave a socket open behind it.
  useEffect(() => () => liveConnection.disconnect(), []);

  useEffect(() => {
    if (summary?.session_id) {
      navigate(`/session/${summary.session_id}/summary`);
    }
  }, [summary, navigate]);

  const running = status === "running";

  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl text-squish-700">Session</h1>
          <p className="text-sm text-ink/60">
            Squeeze and hold when Squishi asks. Rest between repetitions.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <SourceChip isLive={isLive} />
          <span className="tabular text-sm text-ink/60">
            {elapsed.toFixed(0)} s
          </span>
        </div>
      </header>

      {error ? (
        <div role="alert" className="rounded-panel border border-alert bg-mist p-4">
          <p className="text-sm text-ink">{error}</p>
        </div>
      ) : null}

      <div className="flex flex-wrap items-center gap-3">
        {status === "idle" || status === "ended" ? (
          <button
            type="button"
            onClick={() => liveConnection.connect({ junkiness })}
            className="rounded-card bg-squish-500 px-5 py-2 text-mist hover:bg-squish-700"
          >
            Start session
          </button>
        ) : (
          <>
            <button
              type="button"
              onClick={() => (running ? liveConnection.pause() : liveConnection.start())}
              className="rounded-card border border-squish-300 px-4 py-2 text-squish-700 hover:bg-squish-50"
            >
              {running ? "Pause" : "Resume"}
            </button>
            <button
              type="button"
              onClick={() => liveConnection.stop()}
              className="rounded-card bg-squish-700 px-4 py-2 text-mist hover:bg-squish-500"
            >
              Finish session
            </button>
          </>
        )}

        <label className="ml-auto flex items-center gap-2 text-xs text-ink/60">
          Signal noise
          <input
            type="range"
            min={0}
            max={1}
            step={0.1}
            value={junkiness}
            onChange={(e) => setJunkiness(Number(e.target.value))}
            className="w-32"
            aria-label="Simulated signal noise, for demonstrating the quality badge"
          />
        </label>
      </div>

      <div className="grid gap-6 lg:grid-cols-[300px_1fr]">
        <div className="flex flex-col items-center gap-4 rounded-panel border border-squish-100 bg-mist p-6">
          <SquishiMascot />
          <CoachPrompt />
          <SignalQualityBadge />
          <p className="tabular text-sm text-ink/60">
            {reps.length} {reps.length === 1 ? "repetition" : "repetitions"}
          </p>
        </div>

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
