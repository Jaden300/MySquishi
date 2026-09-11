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
  htmlFor,
  children,
}: {
  label: string;
  hint?: string;
  /**
   * Set when the control is not a real form element. Select is a button and a
   * listbox, so wrapping it in a label would put a click target over a popup
   * and announce the label twice. Given this, the field renders a div with an
   * explicitly associated label instead.
   */
  htmlFor?: string;
  children: ReactNode;
}) {
  const text = <span className="text-label text-ink">{label}</span>;

  if (htmlFor) {
    return (
      <div className="flex flex-col gap-2" title={hint}>
        <label htmlFor={htmlFor}>{text}</label>
        {children}
        {hint ? <span className="sr-only">{hint}</span> : null}
      </div>
    );
  }

  return (
    <label className="flex flex-col gap-2" title={hint}>
      {text}
      {children}
      {hint ? <span className="sr-only">{hint}</span> : null}
    </label>
  );
}
