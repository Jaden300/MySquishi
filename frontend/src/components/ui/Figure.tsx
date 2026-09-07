/**
 * The card a non chart figure lives in.
 *
 * ChartFrame does this for Recharts. This does it for everything hand drawn:
 * the signal pipeline, the provenance grid, the data split bar. The point is
 * that a hand built figure gets the same loading, error and empty discipline a
 * chart gets, and cannot dodge the synthetic badge the way a bare div could.
 */

import type { ReactNode } from "react";

import { SyntheticBadge } from "../Honesty";
import { SquishiMark } from "../brand/SquishiMark";
import { PoseSpot } from "../brand/PoseSpot";
import type { PoseId } from "../brand/poses";
import { Card } from "./Card";

interface FigureProps {
  title: string;
  /**
   * Where the numbers came from. synthetic renders the badge automatically,
   * which is why a figure declares its provenance rather than remembering to
   * render an affordance.
   */
  source?: "measured" | "synthetic" | "model";
  /** Context for the figure. Carried on hover, never printed. */
  note?: string;
  pose?: PoseId;
  poseLabel?: string;

  loading?: boolean;
  error?: string | null;
  isEmpty?: boolean;
  emptyMessage?: string;
  onRetry?: () => void;

  action?: ReactNode;
  children: ReactNode;
  className?: string;
}

export function Figure({
  title,
  source = "measured",
  note,
  pose,
  poseLabel,
  loading = false,
  error = null,
  isEmpty = false,
  emptyMessage,
  onRetry,
  action,
  children,
  className = "",
}: FigureProps) {
  return (
    <Card
      as="figure"
      watermark="sm"
      className={`relative m-0 ${className}`}
    >
      <figcaption className="mb-5 flex flex-wrap items-start justify-between gap-3">
        <h3 className="min-w-0 text-h3 text-squish-700" title={note}>
          {title}
          {note ? <span className="sr-only">. {note}</span> : null}
        </h3>
        <div className="flex shrink-0 items-center gap-2">
          {source === "synthetic" ? <SyntheticBadge /> : null}
          {action}
        </div>
      </figcaption>

      <FigureBody
        loading={loading}
        error={error}
        isEmpty={isEmpty}
        emptyMessage={emptyMessage}
        onRetry={onRetry}
      >
        {children}
      </FigureBody>

      {pose && !loading && !error && !isEmpty ? (
        <PoseSpot
          pose={pose}
          size={64}
          placement="corner-br"
          label={poseLabel}
          motion={poseLabel ? "none" : "bob"}
        />
      ) : null}
    </Card>
  );
}

function FigureBody({
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
      <div role="status" aria-label="Loading" className="min-h-[160px]">
        <div className="h-40 w-full animate-pulse rounded-card bg-squish-50" />
        <span className="sr-only">Loading</span>
      </div>
    );
  }

  if (error) {
    // Errors say what happened and what to do, per docs/DESIGN.md.
    return (
      <div
        role="alert"
        className="flex min-h-[160px] flex-col items-center justify-center gap-3 text-center"
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
      <div className="flex min-h-[160px] flex-col items-center justify-center gap-3 text-center">
        <SquishiMark size={52} className="opacity-30" />
        <p className="text-body text-ink/70">
          {emptyMessage ?? "Nothing here yet."}
        </p>
      </div>
    );
  }

  return <>{children}</>;
}
