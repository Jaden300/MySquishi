/**
 * Live session state, updated five times a second.
 *
 * Split from the session store on purpose. Squishi subscribes to exactly one
 * scalar here, so a contraction re-renders the mascot and nothing else. If
 * mvcPct lived inside a frame object, every subscriber to that object would
 * re-render on every frame and the charts would be dragged along by the
 * mascot. See docs/DESIGN.md.
 */

import { create } from "zustand";

import type { Coach, Frame, RepEvent, SummaryFrame } from "../types/api";

/** How many envelope points the oscilloscope keeps on screen. */
const TRACE_LENGTH = 600;

export type LiveStatus = "idle" | "connecting" | "running" | "paused" | "ended";

interface LiveState {
  status: LiveStatus;

  /**
   * Percent of maximum voluntary contraction, computed server side.
   * Squishi's only subscription. Kept flat and primitive so the selector can
   * bail out on an unchanged value.
   */
  mvcPct: number;

  /** When the most recent repetition closed, so Squishi can look proud. */
  repCompletedAt: number;

  /**
   * The strongest effort seen this connection. Tracked here rather than in a
   * component: it is derived from the frames as they arrive, and the
   * calibration trial only needs to read it.
   */
  peakMvcPct: number;

  sqi: number;
  isLive: boolean;
  sourceId: string;
  calibrated: boolean;

  raw: number[];
  envelope: number[];
  coach: Coach | null;
  reps: RepEvent[];
  elapsed: number;

  summary: SummaryFrame | null;
  error: string | null;

  setStatus: (status: LiveStatus) => void;
  applyFrame: (frame: Frame) => void;
  applySummary: (summary: SummaryFrame) => void;
  setError: (message: string | null) => void;
  reset: () => void;
}

const initial = {
  status: "idle" as LiveStatus,
  mvcPct: 0,
  repCompletedAt: 0,
  peakMvcPct: 0,
  sqi: 100,
  isLive: false,
  sourceId: "simulated",
  calibrated: false,
  raw: [] as number[],
  envelope: [] as number[],
  coach: null,
  reps: [] as RepEvent[],
  elapsed: 0,
  summary: null,
  error: null,
};

export const useLiveStore = create<LiveState>((set) => ({
  ...initial,

  setStatus: (status) => set({ status }),

  applyFrame: (frame) =>
    set((state) => {
      const raw = [...state.raw, ...frame.raw].slice(-TRACE_LENGTH);
      const envelope = [...state.envelope, ...frame.envelope].slice(
        -TRACE_LENGTH,
      );

      return {
        mvcPct: frame.mvc_pct,
        peakMvcPct: Math.max(state.peakMvcPct, frame.mvc_pct),
        sqi: frame.sqi,
        isLive: frame.is_live,
        sourceId: frame.source_id,
        calibrated: frame.calibrated,
        raw,
        envelope,
        coach: frame.coach,
        elapsed: frame.t,
        reps: frame.rep_event ? [...state.reps, frame.rep_event] : state.reps,
        repCompletedAt: frame.rep_event ? Date.now() : state.repCompletedAt,
      };
    }),

  applySummary: (summary) => set({ summary, status: "ended", mvcPct: 0 }),

  setError: (error) => set({ error, status: "idle" }),

  reset: () => set({ ...initial }),
}));

/** Squishi's selector. Exported so there is exactly one of it. */
export const selectMvcPct = (state: LiveState) => state.mvcPct;
