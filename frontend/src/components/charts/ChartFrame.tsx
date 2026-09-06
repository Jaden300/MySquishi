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
    <section className="brand-watermark brand-watermark-sm rounded-panel border border-squish-100 bg-mist p-5">
      <header className="mb-4 flex items-start justify-between gap-3">
        <div className="min-w-0" title={description}>
          <h3 className="text-sm font-medium text-squish-700">
            {tooltipTerm ? (
              <ClinicalTooltip term={tooltipTerm}>{title}</ClinicalTooltip>
            ) : (
              title
            )}
            {unit ? (
              <span className="ml-1 text-xs text-ink/50">({unit})</span>
            ) : null}
          </h3>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          {isSynthetic ? <SyntheticBadge /> : null}
          {action}
        </div>
      </header>

      <div style={{ height }} className="relative">
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
    </section>
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
        <p className="text-sm text-ink">{error}</p>
        {onRetry ? (
          <button
            type="button"
            onClick={onRetry}
            className="rounded-card border border-squish-300 px-3 py-1 text-sm text-squish-700 hover:bg-squish-50"
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
        <SquishiMark size={44} className="opacity-30" />
        <p className="text-sm text-ink/70">
          {emptyMessage ?? "Nothing here yet."}
        </p>
      </div>
    );
  }

  return <>{children}</>;
}
