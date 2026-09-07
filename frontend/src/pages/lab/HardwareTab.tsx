/**
 * How to connect the sensor, for someone who has never seen the kit.
 *
 * docs/HARDWARE_CHECKLIST.md is the builder facing version with tiers and
 * failure modes. This is the shipped page, written for a first time user.
 *
 * Two things it insists on. The output selector must be set to RAW, because
 * ENV is the factory default and wrong for this pipeline, so that step opens
 * first and is drawn as a warning. And the live preview is the single most
 * valuable element here: someone who sees the trace move when they squeeze
 * knows immediately that it works, and no amount of prose substitutes. It is
 * at the top for that reason.
 *
 * The eight setup steps used to print as eight paragraphs, roughly four
 * hundred words of standing prose. They are now eight glyphs and eight
 * titles, with each body one click away. Nothing was deleted: someone who
 * needs step four reads step four, rather than everyone reading all eight to
 * find it.
 */

import { useEffect, useState } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  XAxis,
  YAxis,
} from "recharts";

import { ChartFrame } from "../../components/charts/ChartFrame";
import { SourceChip } from "../../components/Honesty";
import { Glyph } from "../../components/figures/Glyph";
import { PipelineDiagram } from "../../components/figures/PipelineDiagram";
import { MUSCLES, MUSCLE_LABELS, MUSCLE_PLACEMENT } from "../../lib/muscle";
import { FAILURES, STEPS, WIRING_CHAIN } from "../../lib/hardware";
import { chartText } from "../../lib/chartText";
import { tokens } from "../../lib/tokens";
import { liveConnection } from "../../lib/ws";
import { useLiveStore } from "../../store/live";
import { Button, Card, SectionHeader } from "../../components/ui";

export function HardwareTab() {
  return (
    <div className="flex flex-col gap-10">
      {/* Simulation is a first class feature and a selling point, so it is
          stated up front rather than offered as an apology at the bottom. The
          three sentence version of this is gone: the claim is now made by the
          heading and the button rather than explained. */}
      <Card tone="accent" pad="lg" className="flex flex-wrap items-center justify-between gap-6">
        <h2 className="text-h2 text-squish-700">Works with no hardware</h2>
        <Button to="/train?stage=live" size="lg">
          Start a simulated session
        </Button>
      </Card>

      <SignalPreview />

      <section>
        <SectionHeader
          title="What connects to what"
          note="The physical chain, from the muscle through to the app."
        />
        <PipelineDiagram nodes={WIRING_CHAIN} />
      </section>

      <section>
        <SectionHeader title="Step by step" />
        <ol className="flex flex-col gap-3">
          {STEPS.map((step, i) => (
            <li key={step.title}>
              <Card
                as="div"
                tone={step.critical ? "alert" : "plain"}
                pad="none"
              >
                <details open={step.critical}>
                  <summary className="flex cursor-pointer list-none items-center gap-4 px-5 py-4">
                    <span
                      className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-card ${
                        step.critical
                          ? "bg-alert/10 text-alert"
                          : "bg-squish-50 text-squish-500"
                      }`}
                    >
                      <Glyph id={step.glyph} size={24} />
                    </span>
                    <span className="flex-1 text-h3 text-squish-700">
                      {step.title}
                    </span>
                    <span
                      aria-hidden="true"
                      className="tabular text-label text-ink/40"
                    >
                      {i + 1}
                    </span>
                  </summary>
                  <p className="px-5 pb-5 pl-20 text-body text-ink/80">
                    {step.body}
                  </p>
                </details>
              </Card>
            </li>
          ))}
        </ol>
      </section>

      <section>
        <SectionHeader
          title="Where the electrodes go"
          note="Placement decides signal quality more than anything else in the chain."
        />
        <div className="grid gap-4 sm:grid-cols-2">
          {MUSCLES.map((muscle) => (
            <Card key={muscle} watermark="sm">
              <h3 className="text-h3 text-squish-700">
                {MUSCLE_LABELS[muscle]}
              </h3>
              <p className="mt-2 text-body text-ink/80">
                {MUSCLE_PLACEMENT[muscle]}
              </p>
            </Card>
          ))}
        </div>
      </section>

      <section>
        <SectionHeader title="If something looks wrong" />
        {/* Four rows never justified a table, and its header row was one of
            the smallest things on the page. Symptom is the card title and
            cause is its body, so the columns are the card itself. */}
        <div className="grid gap-4 sm:grid-cols-2">
          {FAILURES.map((failure) => (
            <Card key={failure.symptom} className="flex gap-4">
              <span className="mt-0.5 flex h-11 w-11 shrink-0 items-center justify-center rounded-card bg-alert/10 text-alert">
                <Glyph id={failure.glyph} size={24} />
              </span>
              <div>
                <h3 className="text-h3 text-squish-700">{failure.symptom}</h3>
                <p className="mt-1.5 text-body text-ink/80">{failure.cause}</p>
              </div>
            </Card>
          ))}
        </div>
      </section>
    </div>
  );
}

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
      height={280}
      isEmpty={!previewing && data.length === 0}
      emptyMessage="Start the preview to see the signal from your sensor."
      action={
        <Button
          variant="secondary"
          onClick={() => {
            if (previewing) {
              liveConnection.disconnect();
              setPreviewing(false);
            } else {
              liveConnection.connect({ source: "serial" });
              setPreviewing(true);
            }
          }}
        >
          {previewing ? "Stop preview" : "Start preview"}
        </Button>
      }
    >
      <div className="flex h-full flex-col gap-3">
        {error ? (
          <p role="alert" className="text-body text-ink">
            {error}
          </p>
        ) : null}

        {status === "running" ? (
          <div className="flex items-center gap-3 text-label text-ink/70">
            <SourceChip isLive={isLive} />
            <span className="tabular">Signal quality {sqi.toFixed(0)}</span>
          </div>
        ) : null}

        <div className="min-h-0 flex-1">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={data} margin={{ top: 4, right: 4, bottom: 4, left: 4 }}>
              <CartesianGrid stroke={tokens.squish100} vertical={false} />
              <XAxis dataKey="index" hide />
              <YAxis tick={chartText.tick} stroke={tokens.ink} width={44} />
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
