/**
 * The page title block.
 *
 * Every page renders one, which is most of what makes four separate pages feel
 * like one product rather than four.
 *
 * There is no subtitle prop, and that is deliberate. docs/DESIGN.md allows a
 * label that names a thing and forbids a sentence that explains one, so what
 * exists here is kicker, which is a short label, and note, which is never
 * printed.
 */

import type { ReactNode } from "react";

import { PoseSpot } from "../brand/PoseSpot";
import type { PoseId } from "../brand/poses";

interface PageHeaderProps {
  title: string;
  /** A short label above the title. Names the context, never explains it. */
  kicker?: string;
  pose?: PoseId;
  /** Accessible name for the pose. Required for a pose that carries meaning. */
  poseLabel?: string;
  /** Context for the title. Carried on hover and to assistive technology. */
  note?: string;
  action?: ReactNode;
}

export function PageHeader({
  title,
  kicker,
  pose,
  poseLabel,
  note,
  action,
}: PageHeaderProps) {
  return (
    <header className="mb-8 flex flex-wrap items-end justify-between gap-x-6 gap-y-4">
      <div className="flex min-w-0 items-center gap-4">
        {pose ? <PoseSpot pose={pose} size={80} label={poseLabel} /> : null}
        <div className="min-w-0" title={note}>
          {kicker ? (
            <p className="text-label text-squish-500">{kicker}</p>
          ) : null}
          <h1 className="text-h1 text-squish-700">{title}</h1>
          {note ? <span className="sr-only">{note}</span> : null}
        </div>
      </div>
      {action ? <div className="flex items-center gap-3">{action}</div> : null}
    </header>
  );
}
