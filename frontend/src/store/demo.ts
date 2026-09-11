/**
 * Demo mode.
 *
 * The backend seeds a synthetic patient at startup and the app reads it under
 * a hardcoded id, so every visitor has always landed in a fully populated app
 * with no way to tell that the history was not theirs and no way out of it.
 * The per record synthetic badge was honest about each row, but it labelled
 * data nobody had asked for, and the carefully written empty states were
 * unreachable.
 *
 * This makes the state explicit and reversible. It is a client side filter on
 * the is_synthetic flag that already rides on every session, not a refetch and
 * not a backend change: seeding is untouched, and turning demo mode back on
 * restores the seeded history immediately because it was never deleted.
 *
 * Defaults to on, so a cold visit still opens onto a populated app and the
 * demo story is unchanged.
 */

import { create } from "zustand";

import type { SessionSummary } from "../types/api";

const STORAGE_KEY = "mysquishi.demoMode";

/**
 * Reads the stored preference.
 *
 * Wrapped because storage throws outright in some contexts rather than merely
 * returning null: a private window, or a browser set to block site data. A
 * failure here has to fall back to the default rather than take the app down.
 */
function readStored(): boolean {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw === null ? true : raw === "true";
  } catch {
    return true;
  }
}

function writeStored(on: boolean): void {
  try {
    localStorage.setItem(STORAGE_KEY, String(on));
  } catch {
    /* Preference is not persisted. The session still works. */
  }
}

interface DemoState {
  demoMode: boolean;
  setDemoMode: (on: boolean) => void;
}

export const useDemoStore = create<DemoState>((set) => ({
  demoMode: readStored(),
  setDemoMode: (on) => {
    writeStored(on);
    set({ demoMode: on });
  },
}));

/**
 * Filters a session list against the current mode.
 *
 * Kept as a plain function beside the store so it can be tested without
 * rendering, and called through the hook below in components.
 */
export function visibleSessions(
  sessions: SessionSummary[],
  demoMode: boolean,
): SessionSummary[] {
  return demoMode ? sessions : sessions.filter((s) => !s.is_synthetic);
}

/**
 * The session list a page should render, given the current mode.
 *
 * Takes null as well as undefined, because useApi holds null before a request
 * resolves and every call site would otherwise coalesce at the boundary.
 */
export function useVisibleSessions(
  sessions: SessionSummary[] | null | undefined,
): SessionSummary[] {
  const demoMode = useDemoStore((s) => s.demoMode);
  return visibleSessions(sessions ?? [], demoMode);
}
