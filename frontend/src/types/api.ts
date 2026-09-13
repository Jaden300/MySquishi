/**
 * The shapes the backend returns.
 *
 * Mirrors backend/app/schemas.py and the websocket frame contract in
 * backend/app/api/live.py. The frame keys are asserted against the backend's
 * own list in a test, so a renamed field fails the suite rather than showing
 * up as undefined inside a chart.
 */

import type { Muscle } from "../lib/muscle";

export type { Muscle };

/** A prediction with its uncertainty. Never a bare number. */
export interface Interval {
  point: number;
  lower: number;
  upper: number;
  level: number;
  unit: string;
}

export interface Factor {
  name: string;
  contribution: number;
  direction: "increases" | "decreases" | "neutral";
  plain_text: string;
}

export interface Explanation {
  summary: string;
  factors: Factor[];
  method: string;
}

/** The envelope every model endpoint returns. */
export interface Prediction<T = unknown> {
  model_id: string;
  value: T;
  explanation: Explanation;
  is_synthetic: boolean;
  trained_at: string | null;
  /** True when a heuristic produced this because no trained model was found. */
  degraded: boolean;
}

export interface Patient {
  id: string;
  display_name: string;
  age_band: string | null;
  sex: string | null;
  injury_type: string | null;
  injury_date: string | null;
  dominant_hand: string | null;
  unaffected_kg: number | null;
  goal_kg: number | null;
  archetype: string | null;
  consent_accepted: boolean;
  is_synthetic: boolean;
}

export interface SessionSummary {
  id: number;
  patient_id: string;
  started_at: string;
  ended_at: string | null;
  source_id: string;
  is_live: boolean;
  is_synthetic: boolean;
  muscle: Muscle;

  borg: number | null;
  quickdash_score: number | null;
  quickdash_valid: boolean;

  rep_count: number | null;
  mean_mvc: number | null;
  peak_mvc: number | null;
  mean_rep_quality: number | null;
  hold_cv_mean: number | null;
  sqi_mean: number | null;
  total_impulse: number | null;
  duration_s: number | null;

  fatigue_slope: number | null;
  fatigue_r_squared: number | null;
  fatigue_p_value: number | null;

  /** Absent entirely on a non grip muscle, not null. The backend omits the
   *  key rather than sending an empty one, so a stale value cannot be
   *  rendered into it. See lib/muscle.ts. */
  strength_kg?: number | null;
  anomaly_score: number | null;
  anomaly_direction: string | null;
  adherence_gap_days: number | null;
}

export interface Rep {
  id: number;
  session_id: number;
  index: number;
  start_s: number;
  peak_s: number;
  end_s: number;

  peak_mvc: number;
  mean_mvc: number;
  time_to_peak_s: number;
  rfd: number;
  duration_s: number;
  relaxation_time_s: number;
  hold_cv: number;
  plateau_flatness: number;
  impulse: number;
  median_frequency: number;
  mean_frequency: number;
  dimitrov_index: number;

  quality: Interval | null;
  quality_top_factor: string | null;
  quality_feedback: string | null;
}

export interface SessionDetail {
  session: SessionSummary;
  reps: Rep[];
}

export interface Calibration {
  id: number;
  patient_id: string;
  created_at: string;
  mvc_reference_rms: number;
  reference_kg: number;
  r_squared: number;
  n_points: number;
  is_active: boolean;
  is_synthetic: boolean;
}

export interface Source {
  id: string;
  label: string;
  /** Drives the honesty chip. Comes from the source, never from page copy. */
  is_live: boolean;
  available: boolean;
  note: string;
}

export interface Goal {
  target_kg: number | null;
  target_date: string | null;
  current_kg: number | null;
  baseline_kg: number | null;
  progress_pct: number | null;
  achieved: boolean;
}

export interface ModelRecord {
  model_id: string;
  version: string;
  trained_at: string;
  metric_name: string;
  metric_value: number;
  cohort_version: string;
  n_training_rows: number;
  notes: string;
}

export interface Health {
  status: string;
  app: string;
  sample_rate: number;
  window_samples: number;
  frame_keys: string[];
}

/* -- the websocket contract ---------------------------------------------- */

export interface RepEvent {
  index: number;
  peak_mvc: number;
  quality: Interval;
  factor: string;
  feedback: string;
}

export interface Coach {
  phase: "ready" | "ramp" | "hold" | "release" | "rest";
  seconds_remaining: number;
  prompt: string;
  target_mvc_pct: number;
  reps_done: number;
}

export interface Frame {
  type: "frame";
  t: number;
  seq: number;
  fs: number;
  raw: number[];
  envelope: number[];
  /** Computed server side. The frontend never divides. */
  mvc_pct: number;
  /**
   * Raw amplitude of this window, before any normalization. Calibration reads
   * it to anchor on a measured maximum: mvc_pct is already divided by the
   * reference, so it cannot produce a new one.
   */
  window_rms: number;
  sqi: number;
  is_live: boolean;
  source_id: string;
  /** Which muscle is being trained. Gates the kilogram based claims. */
  muscle: Muscle;
  /** False when no calibration exists, so kilogram figures are uncalibrated. */
  calibrated: boolean;
  rep_event: RepEvent | null;
  coach: Coach;
}

export interface SummaryFrame {
  type: "summary";
  seq: number;
  session_id: number | null;
  rep_count: number;
  mean_mvc: number;
  peak_mvc: number;
  mean_rep_quality: number | null;
  sqi_mean: number | null;
  duration_s: number;
  total_impulse: number;
  fatigue: FatigueSummary | null;
  is_live: boolean;
  source_id: string;
  muscle: Muscle;
  calibrated: boolean;
  reps: Array<{
    index: number;
    peak_mvc: number;
    quality: Interval;
    feedback: string;
  }>;
}

export interface FatigueSummary {
  slope: Interval;
  r_squared: number;
  p_value: number;
  is_fatigued: boolean;
  [key: string]: unknown;
}

export interface ErrorFrame {
  type: "error";
  message: string;
}

export type LiveMessage = Frame | SummaryFrame | ErrorFrame;

/**
 * The keys every frame carries, mirroring FRAME_KEYS in
 * backend/app/api/live.py. Asserted against GET /api/health in a test.
 */
export const FRAME_KEYS = [
  "type",
  "t",
  "seq",
  "fs",
  "raw",
  "envelope",
  "mvc_pct",
  "window_rms",
  "sqi",
  "is_live",
  "source_id",
  "muscle",
  "calibrated",
  "rep_event",
  "coach",
] as const;

/**
 * The synthetic reference cohort.
 *
 * Both of these carry is_synthetic on the wire rather than relying on the UI
 * to remember. See backend/app/api/cohort.py.
 */
export interface CohortSummary {
  version: string;
  n_patients: number;
  archetypes: { id: string; label: string; count: number }[];
  is_synthetic: boolean;
  note: string;
}

export interface CohortPercentiles {
  reference_group: string;
  n_reference: number;
  /** True when the requested band was too small and the reference was widened. */
  pooled: boolean;
  ewgsop2_threshold: number;
  curve: { percentile: number; strength_kg: number }[];
  /** Pre binned by the backend, so the chart never rebins it differently. */
  histogram: { strength_kg: number; count: number }[];
  is_synthetic: boolean;
}

/** One point in the M12 archetype scatter. */
export interface CohortPoint {
  patient_id: string;
  x: number;
  y: number;
  archetype: string;
}
