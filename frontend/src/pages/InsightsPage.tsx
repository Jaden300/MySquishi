/**
 * Insights, each with a "why am I seeing this" drawer.
 *
 * docs/ML.md requires that affordance on every insight card, so the drawer
 * lives in the card component rather than being added per insight.
 */

import { useState } from "react";

import { api } from "../lib/api";
import { useApi } from "../lib/useApi";
import { IntervalReadout, SyntheticBadge } from "../components/Honesty";
import { SquishiMascot } from "../components/SquishiMascot";
import type { Explanation, Prediction } from "../types/api";

const PATIENT = "demo";

export function InsightsPage() {
  const insights = useApi(() => api.insights(PATIENT), []);
  const prescription = useApi(() => api.prescription(PATIENT), []);

  const cards = [
    ...(prescription.data ? [prescription.data] : []),
    ...(insights.data ?? []),
  ];

  return (
    <div className="flex flex-col gap-6">
      <header>
        <h1 className="text-xl text-squish-700">Insights</h1>
      </header>

      {insights.loading || prescription.loading ? (
        <div role="status" className="flex items-center gap-2">
          <SquishiMascot value={8} size={40} pose="thinking" />
          <span className="sr-only">Working it out</span>
        </div>
      ) : null}

      {cards.length === 0 && !insights.loading ? (
        <div className="brand-watermark flex flex-col items-center gap-3 rounded-panel border border-squish-100 bg-mist p-10 text-center">
          <SquishiMascot value={8} size={110} pose="presenting" />
          <p className="text-sm text-ink/70">
            Complete a few sessions and insights will start appearing here.
          </p>
        </div>
      ) : null}

      <div className="grid gap-4">
        {cards.map((card, i) => (
          <InsightCard key={`${card.model_id}-${i}`} prediction={card} />
        ))}
      </div>
    </div>
  );
}

function InsightCard({ prediction }: { prediction: Prediction }) {
  const [open, setOpen] = useState(false);
  const readout = readoutFor(prediction);

  return (
    <article className="brand-watermark brand-watermark-sm rounded-panel border border-squish-100 bg-mist p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div
          className="min-w-0 flex-1"
          title={
            prediction.degraded
              ? "Produced without a trained model, using transparent rules."
              : undefined
          }
        >
          <p className="text-ink">{prediction.explanation.summary}</p>
          {prediction.degraded ? (
            <span className="sr-only">
              Produced without a trained model, using transparent rules.
            </span>
          ) : null}
        </div>

        {prediction.is_synthetic ? <SyntheticBadge /> : null}
      </div>

      {readout ? (
        <div className="mt-4">
          <IntervalReadout
            point={readout.point}
            lower={readout.lower}
            upper={readout.upper}
            unit={readout.unit}
            label={readout.label}
            decimals={readout.decimals}
            degraded={prediction.degraded}
          />
        </div>
      ) : null}

      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="mt-4 text-sm text-squish-700 underline underline-offset-4"
      >
        Why am I seeing this?
      </button>

      {open ? <WhyThis explanation={prediction.explanation} trainedAt={prediction.trained_at} /> : null}
    </article>
  );
}

function WhyThis({
  explanation,
  trainedAt,
}: {
  explanation: Explanation;
  trainedAt: string | null;
}) {
  // The method line is provenance for a drawer the reader deliberately
  // opened, so it stays available, but on the drawer rather than printed as a
  // footnote inside it.
  const method = `Method: ${explanation.method || "not recorded"}${
    trainedAt
      ? `. Model trained ${new Date(trainedAt).toLocaleDateString()}.`
      : "."
  }`;

  return (
    <div className="mt-3 rounded-card bg-squish-50 p-4 text-sm" title={method}>
      {explanation.factors.length > 0 ? (
        <ul className="flex flex-col gap-1.5">
          {explanation.factors.map((factor) => (
            <li key={factor.name} className="flex items-start gap-2 text-ink/80">
              <span aria-hidden="true" className="text-squish-500">
                {factor.direction === "increases"
                  ? "▲"
                  : factor.direction === "decreases"
                    ? "▼"
                    : "■"}
              </span>
              {factor.plain_text}
            </li>
          ))}
        </ul>
      ) : null}

      <span className="sr-only">{method}</span>
    </div>
  );
}

interface Readout {
  point: number;
  lower: number;
  upper: number;
  unit: string;
  label?: string;
  decimals?: number;
}

/**
 * Which number a card should lead with.
 *
 * Chosen per model rather than by hunting for the first interval in the
 * payload. A forecast contains an interval for every future week, and showing
 * whichever one happened to come first would put an unlabelled number on
 * screen that means nothing to the reader.
 */
function readoutFor(prediction: Prediction): Readout | null {
  const value = prediction.value as Record<string, unknown> | null;
  if (!value || typeof value !== "object") return null;

  switch (prediction.model_id) {
    case "M9": {
      // The forecast's own headline is when the goal is reached, not an
      // arbitrary week of the projection.
      const goal = value.time_to_goal as Record<string, unknown> | undefined;
      const weeks = goal?.weeks as Readout | null | undefined;
      if (!weeks) return null;
      return { ...weeks, label: "Time to your goal", unit: "weeks", decimals: 0 };
    }

    case "M11": {
      const slope = asInterval(value.recent_slope);
      return slope ? { ...slope, label: "Recent trend", decimals: 2 } : null;
    }

    case "M13": {
      // A probability reads as a percentage, not as "1.0".
      const p = asInterval(value.probability);
      if (!p) return null;
      return {
        point: p.point * 100,
        lower: p.lower * 100,
        upper: p.upper * 100,
        unit: "percent",
        label: "Chance of a gap in the next two weeks",
        decimals: 0,
      };
    }

    case "M14": {
      const pct = asInterval(value.percentile);
      return pct ? { ...pct, label: "Against the reference population", decimals: 0 } : null;
    }

    // M8 and M12 lead with words rather than a number: a prescription and an
    // archetype are not quantities.
    default:
      return null;
  }
}

function asInterval(value: unknown): Readout | null {
  if (!value || typeof value !== "object") return null;
  const c = value as Record<string, unknown>;

  if (
    typeof c.point === "number" &&
    typeof c.lower === "number" &&
    typeof c.upper === "number"
  ) {
    return {
      point: c.point,
      lower: c.lower,
      upper: c.upper,
      unit: (c.unit as string) ?? "",
    };
  }
  return null;
}
