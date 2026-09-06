/**
 * The live session charts, 1 to 7.
 *
 * All of these read the websocket store rather than REST: during a session
 * the socket is the only source of truth. Each subscribes to the narrowest
 * slice it needs, so the oscilloscope redrawing does not re-render the gauge.
 */

import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  Cell,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { useLiveStore } from "../../store/live";
import { tokens } from "../../lib/tokens";
import {
  EFFORT_CEILING_PCT,
  effortLevelLabel,
  effortToPercent,
} from "../../lib/effort";
import { ChartFrame } from "./ChartFrame";
import { ClinicalTooltip } from "../Honesty";

/** Chart 1 and 2: the raw trace with its envelope drawn over it. */
export function LiveOscilloscope() {
  const raw = useLiveStore((s) => s.raw);
  const envelope = useLiveStore((s) => s.envelope);

  const data = raw.map((value, i) => ({
    i,
    raw: value,
    envelope: envelope[i] ?? null,
  }));

  return (
    <ChartFrame
      title="Live signal"
      tooltipTerm="sEMG"
      description="Raw muscle activity with its smoothed effort line."
      isEmpty={raw.length === 0}
      emptyMessage="Start a session to see your signal."
      height={200}
    >
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 4, right: 4, bottom: 4, left: 4 }}>
          <YAxis hide domain={["dataMin", "dataMax"]} />
          <Line
            type="monotone"
            dataKey="raw"
            stroke={tokens.squish300}
            strokeWidth={1}
            dot={false}
            isAnimationActive={false}
          />
          <Line
            type="monotone"
            dataKey="envelope"
            stroke={tokens.squish700}
            strokeWidth={2}
            dot={false}
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </ChartFrame>
  );
}

/** Chart 3 and 4: current effort against the prescribed target. */
export function EffortGauge() {
  const mvcPct = useLiveStore((s) => s.mvcPct);
  const coach = useLiveStore((s) => s.coach);
  const calibrated = useLiveStore((s) => s.calibrated);

  const target = coach?.target_mvc_pct ?? 50;
  const onTarget = Math.abs(mvcPct - target) <= 10;

  // The bar is placed on a square root scale, not a linear one. The measured
  // envelope response barely moves through the low effort range where a
  // rehabilitation patient works, so a linear bar reads as broken. See
  // lib/effort.ts and docs/HARDWARE_FINDINGS.md. The number above it stays the
  // true percent MVC: only the bar position is rescaled.
  const fillPct = effortToPercent(mvcPct);
  const targetPct = effortToPercent(target);

  return (
    <ChartFrame
      title="Effort"
      unit="percent MVC"
      tooltipTerm="percent MVC"
      height={200}
      description={
        calibrated ? undefined : "Uncalibrated: run calibration for real figures."
      }
    >
      <div className="flex h-full flex-col justify-center gap-3">
        <div className="flex items-baseline gap-2">
          <span className="tabular text-5xl text-squish-700">
            {mvcPct.toFixed(0)}
          </span>
          <span className="text-sm text-ink/60">
            of target {target.toFixed(0)}
          </span>
        </div>

        <div
          className="relative h-6 w-full overflow-hidden rounded-full bg-squish-50"
          role="meter"
          aria-valuenow={Math.round(mvcPct)}
          aria-valuemin={0}
          aria-valuemax={EFFORT_CEILING_PCT}
          aria-label="Effort as a percentage of your maximum"
        >
          <div
            className="h-full transition-[width] duration-100"
            style={{
              width: `${fillPct}%`,
              backgroundColor: onTarget ? tokens.good : tokens.squish500,
            }}
          />
          <div
            className="absolute top-0 h-full border-l-2 border-dashed border-ink/40"
            style={{ left: `${targetPct}%` }}
          />
        </div>

        {/* State is never conveyed by colour alone. */}
        <p className="text-xs text-ink/60">
          {onTarget ? "On target" : mvcPct < target ? "Below target" : "Above target"}
          {" - "}
          {effortLevelLabel(mvcPct).toLowerCase()} effort
        </p>
      </div>
    </ChartFrame>
  );
}

/** Chart 6: repetitions so far, coloured by their M4 quality score. */
export function RepTimeline() {
  const reps = useLiveStore((s) => s.reps);

  const data = reps.map((rep) => ({
    name: `Rep ${rep.index + 1}`,
    quality: rep.quality.point,
    peak: rep.peak_mvc,
    feedback: rep.feedback,
  }));

  return (
    <ChartFrame
      title="Repetitions"
      description="Each block is one repetition, shaded by how it was executed."
      isEmpty={reps.length === 0}
      emptyMessage="Your repetitions will appear here as you complete them."
      height={180}
    >
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 4, right: 4, bottom: 4, left: 4 }}>
          <XAxis dataKey="name" tick={{ fontSize: 11 }} stroke={tokens.ink} />
          <YAxis domain={[0, 100]} tick={{ fontSize: 11 }} stroke={tokens.ink} />
          <Tooltip
            formatter={(value) => [`${Number(value).toFixed(0)} of 100`, "Quality"]}
          />
          <Bar dataKey="quality" radius={[4, 4, 0, 0]}>
            {data.map((entry, i) => (
              <Cell
                key={i}
                fill={entry.quality >= 70 ? tokens.good : tokens.squish500}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </ChartFrame>
  );
}

/**
 * Chart 7: the signal quality badge.
 *
 * This is the project's integrity feature: it says when not to trust the
 * reading. It is deliberately always visible rather than appearing only when
 * quality is poor.
 */
export function SignalQualityBadge() {
  const sqi = useLiveStore((s) => s.sqi);

  const band = sqi >= 80 ? "Good" : sqi >= 60 ? "Fair" : sqi >= 40 ? "Poor" : "Unusable";
  const colour = sqi >= 80 ? tokens.good : sqi >= 60 ? tokens.squish500 : tokens.alert;

  return (
    <div className="flex items-center gap-3 rounded-card border border-squish-100 bg-mist px-4 py-3">
      <div className="flex flex-col">
        <span className="text-xs text-ink/60">
          <ClinicalTooltip term="SQI">Signal quality</ClinicalTooltip>
        </span>
        <span className="tabular text-lg text-squish-700">{sqi.toFixed(0)}</span>
      </div>
      <span
        className="rounded-full px-2 py-0.5 text-xs"
        style={{ backgroundColor: `${colour}22`, color: tokens.ink }}
        title={sqi < 60 ? "Check the electrodes are firmly attached." : undefined}
      >
        {band}
      </span>
    </div>
  );
}

/** The coach prompt. Plain language, per docs/DESIGN.md. */
export function CoachPrompt() {
  const coach = useLiveStore((s) => s.coach);
  if (!coach) return null;

  return (
    <div className="rounded-card border border-squish-100 bg-squish-50 px-4 py-3">
      <p className="text-lg text-squish-700">{coach.prompt}</p>
      {coach.seconds_remaining > 0 ? (
        <p className="tabular text-sm text-ink/60">
          {coach.seconds_remaining.toFixed(1)} s
        </p>
      ) : null}
    </div>
  );
}

/** Chart 5 lives in SquishiMascot. Chart 9's force time curve, reused live. */
export function EnvelopeArea() {
  const envelope = useLiveStore((s) => s.envelope);
  const data = envelope.map((value, i) => ({ i, value }));

  return (
    <ChartFrame
      title="Effort over time"
      tooltipTerm="RMS envelope"
      isEmpty={envelope.length === 0}
      emptyMessage="Start a session to see your effort trace."
      height={160}
    >
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={{ top: 4, right: 4, bottom: 4, left: 4 }}>
          <YAxis hide />
          <ReferenceLine y={0} stroke={tokens.squish100} />
          <Area
            type="monotone"
            dataKey="value"
            stroke={tokens.squish500}
            fill={tokens.squish100}
            isAnimationActive={false}
          />
        </AreaChart>
      </ResponsiveContainer>
    </ChartFrame>
  );
}
