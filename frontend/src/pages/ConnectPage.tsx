/**
 * How to connect the sensor, for someone who has never seen the kit.
 *
 * docs/HARDWARE_CHECKLIST.md is the builder facing version with tiers and
 * failure modes. This is the shipped page, written for a first time user.
 *
 * Two things it insists on. The output selector must be set to RAW, because
 * ENV is the factory default and wrong for this pipeline, so that step goes
 * first and is visually prominent. And the live preview is the single most
 * valuable element here: someone who sees the trace move when they squeeze
 * knows immediately that it works, and no amount of prose substitutes.
 */

import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  XAxis,
  YAxis,
} from "recharts";

import { ChartFrame } from "../components/charts/ChartFrame";
import { SourceChip } from "../components/Honesty";
import { MUSCLES, MUSCLE_LABELS, MUSCLE_PLACEMENT } from "../lib/muscle";
import { tokens } from "../lib/tokens";
import { liveConnection } from "../lib/ws";
import { useLiveStore } from "../store/live";

const STEPS = [
  {
    title: "Set the output selector to RAW",
    body:
      "The MyoWare 2.0 ships set to ENV. This pipeline needs RAW. It is the single " +
      "setting most likely to be wrong, and everything downstream depends on it, so " +
      "check it before anything else.",
  },
  {
    title: "Stack the hardware",
    body:
      "Snap the sensor onto the three electrodes, connect the Link Shield with the " +
      "3.5 mm cable, and seat the Arduino Shield on the Uno headers. No soldering. " +
      "Push the plug fully in until it clicks.",
  },
  {
    title: "Prepare the skin",
    body:
      "Wash the area, wipe it with alcohol, and let it dry completely. A damp site " +
      "bridges the electrodes and flattens the reading.",
  },
  {
    title: "Place the electrodes",
    body:
      "Two over the belly of the muscle, 2 cm apart and lined up with the muscle " +
      "fibres. The third goes on nearby bone as a reference. Placement decides " +
      "signal quality more than anything else in the chain.",
  },
  {
    title: "Plug in over USB",
    body:
      "Use a data cable, not a charge only one. Close the Arduino Serial Monitor if " +
      "it is open: it holds the port exclusively. Nano clones usually need the CH340 " +
      "driver.",
  },
  {
    title: "Pick the muscle",
    body:
      "Choose it on the session page, so the app reports the measurements that are " +
      "valid for that muscle and withholds the ones that are not.",
  },
  {
    title: "Calibrate",
    body:
      "Three maximal efforts, five seconds each, with thirty seconds of rest between. " +
      "The highest becomes your reference, and every later reading is a percentage of " +
      "it.",
  },
  {
    title: "Start a session",
    body: "Squeeze and hold when Squishi asks. Rest between repetitions.",
  },
];

const FAILURES = [
  {
    symptom: "No port listed",
    cause: "Almost always a charge only USB cable. Try a different one.",
  },
  {
    symptom: "Garbled characters",
    cause: "Baud mismatch. The sketch runs at 230400.",
  },
  {
    symptom: "Flat trace that never moves",
    cause: "Dead or dried out electrodes, or the selector is still on ENV.",
  },
  {
    symptom: "Erratic, drifting trace",
    cause: "The reference electrode is on muscle instead of bone.",
  },
];

/** The wiring chain, as text so it reads correctly in a screen reader. */
const CHAIN = [
  "MyoWare 2.0 sensor, on the muscle, switch set to RAW",
  "3 electrodes: 2 on the muscle belly, 1 on nearby bone",
  "Link Shield, over the 3.5 mm cable",
  "Arduino Shield, seated on the Uno headers",
  "Arduino Uno, reading pin A0",
  "Computer, over a USB data cable",
  "MySquishi, over serial at 230400 baud",
];

function SignalPreview() {
  const [previewing, setPreviewing] = useState(false);
  const raw = useLiveStore((s) => s.raw);
  const sqi = useLiveStore((s) => s.sqi);
  const isLive = useLiveStore((s) => s.isLive);
  const error = useLiveStore((s) => s.error);
  const status = useLiveStore((s) => s.status);

  // Leaving the page must not leave a socket open behind it.
  useEffect(() => () => liveConnection.disconnect(), []);

  const data = raw.slice(-300).map((value, index) => ({ index, value }));

  return (
    <ChartFrame
      title="Live signal preview"
      description="Squeeze the muscle. If the trace jumps, everything is wired correctly."
      height={220}
      isEmpty={!previewing && data.length === 0}
      emptyMessage="Start the preview to see the signal from your sensor."
      action={
        <button
          type="button"
          onClick={() => {
            if (previewing) {
              liveConnection.disconnect();
              setPreviewing(false);
            } else {
              liveConnection.connect({ source: "serial" });
              setPreviewing(true);
            }
          }}
          className="rounded-card border border-squish-300 px-3 py-1 text-xs text-squish-700 hover:bg-squish-50"
        >
          {previewing ? "Stop preview" : "Start preview"}
        </button>
      }
    >
      <div className="flex h-full flex-col gap-2">
        {error ? (
          <p role="alert" className="text-sm text-ink">
            {error}
          </p>
        ) : null}

        {status === "running" ? (
          <div className="flex items-center gap-3 text-sm text-ink/70">
            <SourceChip isLive={isLive} />
            <span className="tabular">Signal quality {sqi.toFixed(0)}</span>
          </div>
        ) : null}

        <div className="min-h-0 flex-1">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={data} margin={{ top: 4, right: 4, bottom: 4, left: 4 }}>
              <CartesianGrid stroke={tokens.squish100} vertical={false} />
              <XAxis dataKey="index" hide />
              <YAxis tick={{ fontSize: 11 }} stroke={tokens.ink} width={40} />
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
        </div>
      </div>
    </ChartFrame>
  );
}

export function ConnectPage() {
  return (
    <div className="flex flex-col gap-6">
      <header>
        <h1 className="text-xl text-squish-700">Connect your sensor</h1>
      </header>

      {/* Simulation is a first class feature and a selling point, so it is
          stated up front rather than offered as an apology at the bottom. */}
      <div className="rounded-panel border border-squish-100 bg-mist p-4">
        <p className="text-sm text-ink">
          You do not need any of this to use MySquishi. Every part of the app
          works on the built in simulator, including the full session flow and
          all the analytics.{" "}
          <Link to="/session" className="text-squish-700 underline">
            Start a simulated session
          </Link>{" "}
          if you would rather not set up hardware.
        </p>
      </div>

      {/* Highest risk setting on the board, so it goes first and it is loud. */}
      <div className="rounded-panel border-2 border-alert bg-mist p-4">
        <h2 className="text-base text-squish-700">
          Before anything else: set the output selector to RAW
        </h2>
        <p className="mt-1 text-sm text-ink/80">
          The MyoWare 2.0 leaves the factory set to ENV, and this app cannot
          read that. The switch is on the sensor board itself. If the trace
          below stays flat no matter how hard you squeeze, this is almost
          always why.
        </p>
      </div>

      <SignalPreview />

      <section className="rounded-panel border border-squish-100 bg-mist p-4">
        <h2 className="text-base text-squish-700">What connects to what</h2>
        <ol className="mt-3 flex flex-col gap-1">
          {CHAIN.map((item, index) => (
            <li key={item} className="flex gap-3 text-sm text-ink/80">
              <span aria-hidden="true" className="text-ink/40">
                {index === 0 ? " " : "|"}
              </span>
              <span>{item}</span>
            </li>
          ))}
        </ol>
      </section>

      <section className="flex flex-col gap-3">
        <h2 className="text-base text-squish-700">Step by step</h2>
        <ol className="flex flex-col gap-3">
          {STEPS.map((step, index) => (
            <li
              key={step.title}
              className="rounded-panel border border-squish-100 bg-mist p-4"
            >
              <h3 className="text-sm text-squish-700">
                <span className="tabular text-ink/40">{index + 1}. </span>
                {step.title}
              </h3>
              <p className="mt-1 text-sm text-ink/80">{step.body}</p>
            </li>
          ))}
        </ol>
      </section>

      <section className="rounded-panel border border-squish-100 bg-mist p-4">
        <h2 className="text-base text-squish-700">Where the electrodes go</h2>
        <dl className="mt-3 flex flex-col gap-3">
          {MUSCLES.map((muscle) => (
            <div key={muscle}>
              <dt className="text-sm text-squish-700">{MUSCLE_LABELS[muscle]}</dt>
              <dd className="text-sm text-ink/80">{MUSCLE_PLACEMENT[muscle]}</dd>
            </div>
          ))}
        </dl>
      </section>

      <section className="rounded-panel border border-squish-100 bg-mist p-4">
        <h2 className="text-base text-squish-700">If something looks wrong</h2>
        <div className="mt-3 overflow-x-auto">
          <table className="w-full min-w-[32rem] text-left text-sm">
            <thead>
              <tr className="border-b border-squish-100 text-xs text-ink/60">
                <th className="py-2">What you see</th>
                <th className="py-2">What it usually means</th>
              </tr>
            </thead>
            <tbody>
              {FAILURES.map((row) => (
                <tr key={row.symptom} className="border-b border-squish-50">
                  <td className="py-2 text-ink/80">{row.symptom}</td>
                  <td className="py-2 text-ink/80">{row.cause}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
