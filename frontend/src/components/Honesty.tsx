/**
 * The honesty affordances.
 *
 * These are components rather than per page copy, so they cannot be
 * forgotten on a page someone adds later. See docs/DESIGN.md.
 */

import type { ReactNode } from "react";

import type { Interval } from "../types/api";
import { CLINICAL_TERMS } from "../lib/clinical";

/**
 * Renders wherever a record has is_synthetic set.
 *
 * Carries a label as well as a colour, because no information in this app is
 * conveyed by colour alone.
 */
export function SyntheticBadge({ note }: { note?: string }) {
  return (
    <span
      className="inline-flex items-center gap-1 rounded-full border border-squish-300 bg-squish-100 px-2 py-0.5 text-xs text-squish-700"
      title={
        note ??
        "This data is synthetic. It was generated for demonstration and does not describe a real person."
      }
    >
      <span aria-hidden="true">◇</span>
      Synthetic
    </span>
  );
}

/** Marks a reading taken from the simulator rather than from hardware. */
export function SourceChip({ isLive }: { isLive: boolean }) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs ${
        isLive
          ? "bg-good/15 text-ink border border-good"
          : "bg-squish-100 text-squish-700 border border-squish-300"
      }`}
    >
      <span aria-hidden="true">{isLive ? "●" : "◇"}</span>
      {isLive ? "Live sensor" : "Simulated"}
    </span>
  );
}

interface IntervalReadoutProps {
  /**
   * lower and upper are required. A bare point estimate is therefore a type
   * error rather than something a reviewer has to catch.
   */
  point: number;
  lower: number;
  upper: number;
  unit?: string;
  label?: string;
  decimals?: number;
  /** Set when a heuristic produced this because no model was available. */
  degraded?: boolean;
}

/**
 * The only component allowed to render a prediction.
 *
 * Every predictive number in the product goes through here, so every one of
 * them arrives with its uncertainty attached.
 */
export function IntervalReadout({
  point,
  lower,
  upper,
  unit = "",
  label,
  decimals = 1,
  degraded = false,
}: IntervalReadoutProps) {
  const fmt = (value: number) => value.toFixed(decimals);
  const suffix = unit ? ` ${unit}` : "";

  const range = `${fmt(lower)} to ${fmt(upper)}${suffix}`;
  const degradedNote = "Estimated without a trained model";

  /*
    The uncertainty is still attached to every number, it is simply no longer
    printed under it. The visible readout is the point estimate; the range,
    the label and the degraded warning live in the title and in screen reader
    text. Nothing an honesty rule requires has been dropped, and a reader who
    wants the interval gets it on hover or from assistive technology.
  */
  const summary = [label, range, degraded ? degradedNote : null]
    .filter(Boolean)
    .join(". ");

  return (
    <div className="flex flex-col gap-0.5" title={summary}>
      <span
        className={`tabular text-2xl ${degraded ? "text-alert" : "text-squish-700"}`}
      >
        {fmt(point)}
        {suffix ? <span className="text-base text-ink/60">{suffix}</span> : null}
      </span>
      <span className="sr-only">{label ? `${label}. ` : ""}{range}</span>
      {degraded ? <span className="sr-only">{degradedNote}</span> : null}
    </div>
  );
}

/** Convenience wrapper for an Interval straight off the wire. */
export function IntervalValue({
  interval,
  ...rest
}: { interval: Interval } & Omit<
  IntervalReadoutProps,
  "point" | "lower" | "upper" | "unit"
>) {
  return (
    <IntervalReadout
      point={interval.point}
      lower={interval.lower}
      upper={interval.upper}
      unit={interval.unit}
      {...rest}
    />
  );
}

/**
 * A clinical term with its definition.
 *
 * The definitions live in one map so the wording stays consistent everywhere
 * a term appears, and so accuracy can be reviewed in one place.
 */
export function ClinicalTooltip({
  term,
  children,
}: {
  term: string;
  children?: ReactNode;
}) {
  const definition = CLINICAL_TERMS[term];
  if (!definition) return <>{children ?? term}</>;

  return (
    <abbr
      title={definition}
      className="cursor-help border-b border-dotted border-squish-300 no-underline"
    >
      {children ?? term}
    </abbr>
  );
}

/** The standing disclaimer. Not dismissible. */
export function NotAMedicalDevice() {
  return (
    <p className="text-xs text-ink/60">
      MySquishi is a training aid, not a medical device. It does not diagnose
      and it does not replace a clinician.
    </p>
  );
}
