/**
 * A section title.
 *
 * Like PageHeader, this has no prop that can print a sentence beneath the
 * heading. note goes to the title attribute and to screen reader text, which
 * is the mechanic docs/DESIGN.md prescribes: nothing an honesty rule requires
 * is deleted, it simply stops being set in grey nine pixel type nobody reads.
 */

import type { ReactNode } from "react";

import { PoseSpot } from "../brand/PoseSpot";
import type { PoseId } from "../brand/poses";

interface SectionHeaderProps {
  title: string;
  pose?: PoseId;
  poseLabel?: string;
  /** Context for the section. Never printed. */
  note?: string;
  action?: ReactNode;
  id?: string;
}

export function SectionHeader({
  title,
  pose,
  poseLabel,
  note,
  action,
  id,
}: SectionHeaderProps) {
  return (
    <div className="mb-5 flex flex-wrap items-center justify-between gap-x-4 gap-y-2">
      <div className="flex items-center gap-3" title={note}>
        {pose ? <PoseSpot pose={pose} size={56} label={poseLabel} /> : null}
        <h2 id={id} className="text-h2 text-squish-700">
          {title}
        </h2>
        {note ? <span className="sr-only">{note}</span> : null}
      </div>
      {action ? <div className="flex items-center gap-3">{action}</div> : null}
    </div>
  );
}
