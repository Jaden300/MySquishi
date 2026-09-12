/**
 * The card every chart lives in.
 *
 * docs/DESIGN.md requires every chart to accept loading, error and empty
 * states so the states pass is mechanical rather than bespoke per chart.
 * This is the component that delivers that: a chart is ChartFrame plus a
 * Recharts body, so a chart cannot ship without its three states.
 */

import type { ReactNode } from "react";

import { ClinicalTooltip, SyntheticBadge } from "../Honesty";
import { SquishiMark } from "../brand/SquishiMark";
import { Card } from "../ui/Card";

export interface ChartFrameProps {
  title: string;
  /** Units belong in the header, so the axis does not have to repeat them. */
  unit?: string;
  /** A clinical term to define on hover, keyed into docs/CLINICAL.md. */
  tooltipTerm?: string;
  /**
   * Context for the chart. Carried on the heading as a tooltip rather than
   * printed underneath it: the captions were visual noise, so what survives
   * is available on hover and to assistive technology.
   */
  description?: string;

  loading?: boolean;
  error?: string | null;
  isEmpty?: boolean;
  emptyMessage?: string;
  isSynthetic?: boolean;

  onRetry?: () => void;
  action?: ReactNode;
  height?: number;
  children: ReactNode;
}

export function ChartFrame({
  title,
  unit,
  tooltipTerm,
  description,
  loading = false,
  error = null,
  isEmpty = false,
  emptyMessage,
  isSynthetic = false,
  onRetry,
  action,
  height = 240,
  children,
}: ChartFrameProps) {
  return (
    <Card watermark="sm">
      <header className="mb-5 flex items-start justify-between gap-3">
        {/*
          The description stays on this wrapper rather than moving up to the
          Card. It has to sit on the element that holds the heading text, both
          so the tooltip appears over the title itself and because the frame's
          test asserts exactly that relationship.
        */}
        <div className="min-w-0" title={description}>
          <h3 className="text-h3 text-squish-700">
            {tooltipTerm ? (
              <ClinicalTooltip term={tooltipTerm}>{title}</ClinicalTooltip>
            ) : (
              title
            )}
          </h3>
          {/* The unit is not printed. It rides on the heading tooltip and on
              the axis label, so the header carries no parenthetical grey. */}
          {unit ? <span className="sr-only">Measured in {unit}</span> : null}
        </div>
        <div className="flex shrink-0 items-center gap-2">
          {isSynthetic ? <SyntheticBadge /> : null}
          {action}
        </div>
      </header>

      {/*
        clamp rather than the bare number, so a 340px chart does not eat most
        of a phone screen. The lower bound is 62 percent of the requested
        height, reached at about 360px wide and released by 640px, which is the
        same trick the type scale uses to work at 390px without a responsive
        variant at every call site. Charts shorter than the floor are
        unaffected, since the clamp cannot raise them.
      */}
      <div
        style={{
          height: `clamp(${Math.round(height * 0.62)}px, ${Math.round(
            height * 0.62,
          )}px + 14vw, ${height}px)`,
        }}
        className="relative"
      >
        <ChartBody
          loading={loading}
          error={error}
          isEmpty={isEmpty}
          emptyMessage={emptyMessage}
          onRetry={onRetry}
        >
          {children}
        </ChartBody>
      </div>
    </Card>
  );
}

function ChartBody({
  loading,
  error,
  isEmpty,
  emptyMessage,
  onRetry,
  children,
}: {
  loading: boolean;
  error: string | null;
  isEmpty: boolean;
  emptyMessage?: string;
  onRetry?: () => void;
  children: ReactNode;
}) {
  if (loading) {
    return (
      <div
        role="status"
        aria-label="Loading"
        className="flex h-full items-center justify-center"
      >
        <div className="h-full w-full animate-pulse rounded-card bg-squish-50" />
        <span className="sr-only">Loading</span>
      </div>
    );
  }

  if (error) {
    // Errors say what happened and what to do, per docs/DESIGN.md.
    return (
      <div
        role="alert"
        className="flex h-full flex-col items-center justify-center gap-2 text-center"
      >
        <p className="text-body text-ink">{error}</p>
        {onRetry ? (
          <button
            type="button"
            onClick={onRetry}
            className="rounded-pill border border-squish-300 px-5 py-2 text-label text-squish-700 hover:bg-squish-50"
          >
            Try again
          </button>
        ) : null}
      </div>
    );
  }

  if (isEmpty) {
    // Empty states invite action rather than reporting absence.
    return (
      <div className="flex h-full flex-col items-center justify-center gap-3 text-center">
        <SquishiMark size={52} className="opacity-30" />
        <p className="text-body text-ink/70">
          {emptyMessage ?? "Nothing here yet."}
        </p>
      </div>
    );
  }

  return <>{children}</>;
}
