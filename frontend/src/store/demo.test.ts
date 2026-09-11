/**
 * Demo mode.
 *
 * The filter is the whole feature: if it stops removing synthetic sessions,
 * exiting demo mode silently does nothing and the app is back to presenting
 * seeded history as the reader's own. That is the failure worth a test.
 */

import { describe, expect, it } from "vitest";

import { visibleSessions } from "./demo";
import type { SessionSummary } from "../types/api";

/** Only the two fields the filter reads. */
function session(id: number, isSynthetic: boolean): SessionSummary {
  return { id, is_synthetic: isSynthetic } as SessionSummary;
}

const SESSIONS = [
  session(1, true),
  session(2, false),
  session(3, true),
  session(4, false),
];

describe("visibleSessions", () => {
  it("keeps everything while demo mode is on", () => {
    expect(visibleSessions(SESSIONS, true)).toHaveLength(4);
  });

  it("drops the synthetic sessions once demo mode is off", () => {
    const visible = visibleSessions(SESSIONS, false);

    expect(visible.map((s) => s.id)).toEqual([2, 4]);
    expect(visible.every((s) => !s.is_synthetic)).toBe(true);
  });

  it("leaves the source list untouched", () => {
    visibleSessions(SESSIONS, false);

    // The seeded history is filtered, never deleted, which is what lets demo
    // mode be turned back on and restore it.
    expect(SESSIONS).toHaveLength(4);
  });

  it("returns nothing when every session is seeded", () => {
    // The case that makes the written empty states finally render.
    expect(visibleSessions([session(1, true)], false)).toEqual([]);
  });

  it("handles an empty list in both modes", () => {
    expect(visibleSessions([], true)).toEqual([]);
    expect(visibleSessions([], false)).toEqual([]);
  });
});
