/**
 * A labelled form control.
 *
 * Lifted out of the onboarding page, which already had the right shape: the
 * hint rides on the label as a tooltip plus screen reader text rather than
 * printing beneath the field, so a form carries no standing explanatory prose.
 */

import type { ReactNode } from "react";

export function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: ReactNode;
}) {
  return (
    <label className="flex flex-col gap-2" title={hint}>
      <span className="text-label text-ink">{label}</span>
      {children}
      {hint ? <span className="sr-only">{hint}</span> : null}
    </label>
  );
}
