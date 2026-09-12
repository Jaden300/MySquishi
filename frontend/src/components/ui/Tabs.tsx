/**
 * A tab strip.
 *
 * Carries the sections that used to be separate routes on Progress and Lab.
 * Implements the roving tabindex pattern: one stop in the tab order, arrow
 * keys move between tabs, so a keyboard user does not have to tab through
 * every section heading to reach the panel.
 */

import { useRef } from "react";
import { motion, useReducedMotion } from "framer-motion";

import { PoseSpot } from "../brand/PoseSpot";
import type { PoseId } from "../brand/poses";

export interface TabDef<T extends string> {
  id: T;
  label: string;
  pose?: PoseId;
}

interface TabsProps<T extends string> {
  tabs: TabDef<T>[];
  value: T;
  onChange: (id: T) => void;
  /** Distinguishes the layoutId when two strips share a page. */
  name: string;
  className?: string;
}

export function Tabs<T extends string>({
  tabs,
  value,
  onChange,
  name,
  className = "",
}: TabsProps<T>) {
  const reduced = useReducedMotion();
  const refs = useRef<(HTMLButtonElement | null)[]>([]);

  const move = (from: number, delta: number) => {
    const next = (from + delta + tabs.length) % tabs.length;
    onChange(tabs[next].id);
    refs.current[next]?.focus();
  };

  return (
    <div
      role="tablist"
      aria-label={name}
      className={`flex flex-wrap gap-1 rounded-pill border border-squish-100 bg-mist p-1.5 ${className}`}
    >
      {tabs.map((tab, i) => {
        const selected = tab.id === value;
        return (
          <button
            key={tab.id}
            ref={(el) => {
              refs.current[i] = el;
            }}
            role="tab"
            id={`${name}-tab-${tab.id}`}
            aria-selected={selected}
            aria-controls={`${name}-panel-${tab.id}`}
            tabIndex={selected ? 0 : -1}
            onClick={() => onChange(tab.id)}
            onKeyDown={(e) => {
              if (e.key === "ArrowRight" || e.key === "ArrowDown") {
                e.preventDefault();
                move(i, 1);
              } else if (e.key === "ArrowLeft" || e.key === "ArrowUp") {
                e.preventDefault();
                move(i, -1);
              } else if (e.key === "Home") {
                e.preventDefault();
                move(i, -i);
              } else if (e.key === "End") {
                e.preventDefault();
                move(i, tabs.length - 1 - i);
              }
            }}
            className={`relative inline-flex items-center gap-2 rounded-pill px-5 py-2 text-label transition-colors ${
              selected ? "text-mist" : "text-ink/70 hover:text-squish-700"
            }`}
          >
            {selected ? (
              <motion.span
                layoutId={`${name}-tab-indicator`}
                className="absolute inset-0 rounded-pill bg-squish-500"
                transition={
                  reduced
                    ? { duration: 0 }
                    : { type: "spring", stiffness: 420, damping: 34 }
                }
              />
            ) : null}
            {tab.pose ? (
              <PoseSpot pose={tab.pose} size={24} className="relative" />
            ) : null}
            <span className="relative">{tab.label}</span>
          </button>
        );
      })}
    </div>
  );
}

/** The panel a tab controls. Keeps the aria wiring in one place. */
export function TabPanel({
  name,
  id,
  children,
}: {
  name: string;
  id: string;
  children: React.ReactNode;
}) {
  return (
    // No tabIndex. The ARIA pattern gives a panel one only when it holds
    // nothing focusable, so a keyboard can still reach the content. Every
    // panel here holds links and buttons, so a tab stop on the wrapper is one
    // extra press before any of them, on every tab, with nothing to show.
    <div
      role="tabpanel"
      id={`${name}-panel-${id}`}
      aria-labelledby={`${name}-tab-${id}`}
    >
      {children}
    </div>
  );
}
