/**
 * The REST client.
 *
 * Every call returns a result rather than throwing, so a failed request is a
 * state a component renders instead of an exception that unmounts a page. That
 * is what makes the error states in ChartFrame mechanical: a chart is handed
 * an error and draws it, the same way it draws data.
 */

import { DEFAULT_MUSCLE, type Muscle } from "./muscle";
import type {
  Calibration,
  CohortPercentiles,
  CohortSummary,
  Goal,
  Health,
  ModelRecord,
  Patient,
  Prediction,
  Rep,
  SessionDetail,
  SessionSummary,
  Source,
} from "../types/api";

export type Result<T> =
  | { ok: true; data: T }
  | { ok: false; error: string };

const BASE = "/api";

async function request<T>(
  path: string,
  init?: RequestInit,
): Promise<Result<T>> {
  try {
    const response = await fetch(`${BASE}${path}`, {
      headers: { "Content-Type": "application/json" },
      ...init,
    });

    if (!response.ok) {
      // FastAPI puts the human readable reason in detail. Prefer it over a
      // bare status code, because it is written to be read.
      let detail = `Request failed with status ${response.status}`;
      try {
        const body = await response.json();
        if (typeof body?.detail === "string") detail = body.detail;
      } catch {
        // No JSON body. The status line is what we have.
      }
      return { ok: false, error: detail };
    }

    if (response.status === 204) {
      return { ok: true, data: undefined as T };
    }

    return { ok: true, data: (await response.json()) as T };
  } catch {
    return {
      ok: false,
      error: "Could not reach the server. Check that the backend is running.",
    };
  }
}

function post<T>(path: string, body: unknown): Promise<Result<T>> {
  return request<T>(path, { method: "POST", body: JSON.stringify(body) });
}

export const api = {
  health: () => request<Health>("/health"),

  // Patients
  getPatient: (id: string) => request<Patient>(`/patients/${id}`),
  createPatient: (payload: Partial<Patient>) =>
    post<Patient>("/patients", payload),
  updatePatient: (id: string, payload: Partial<Patient>) =>
    request<Patient>(`/patients/${id}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
  getGoal: (id: string) => request<Goal>(`/patients/${id}/goal`),
  deletePatientData: (id: string) =>
    request<void>(`/patients/${id}/data`, { method: "DELETE" }),

  // Sessions
  listSessions: (patientId: string, limit = 100) =>
    request<SessionSummary[]>(
      `/sessions?patient_id=${encodeURIComponent(patientId)}&limit=${limit}`,
    ),
  getSession: (id: number) => request<SessionDetail>(`/sessions/${id}`),
  getReps: (id: number) => request<Rep[]>(`/sessions/${id}/reps`),
  setBorg: (id: number, borg: number) =>
    post<SessionSummary>(`/sessions/${id}/borg`, { borg }),
  setQuickDash: (id: number, score: number, itemsAnswered: number) =>
    post<{ valid: boolean; note: string }>(`/sessions/${id}/quickdash`, {
      score,
      items_answered: itemsAnswered,
    }),

  // Signal
  listSources: () => request<Source[]>("/signal/sources"),
  getCalibration: (patientId: string, muscle: Muscle = DEFAULT_MUSCLE) =>
    request<Calibration | null>(
      `/signal/calibration?patient_id=${encodeURIComponent(patientId)}` +
        `&muscle=${encodeURIComponent(muscle)}`,
    ),
  calibrate: (payload: {
    patient_id: string;
    feature_rows: Array<Record<string, number>>;
    reference_kg: number;
    mvc_reference_rms: number;
    /** A maximum voluntary contraction belongs to a muscle as well as a
     *  person, so calibrations are held one per patient per muscle. */
    muscle?: Muscle;
  }) => post<Calibration>("/signal/calibrate", payload),

  // Models. Each returns the same envelope, so the UI treats them uniformly.
  forecast: (id: string) => request<Prediction>(`/ml/forecast/${id}`),
  plateau: (id: string) => request<Prediction>(`/ml/plateau/${id}`),
  archetype: (id: string) => request<Prediction>(`/ml/archetype/${id}`),
  adherence: (id: string) => request<Prediction>(`/ml/adherence/${id}`),
  percentile: (id: string) => request<Prediction>(`/ml/percentile/${id}`),
  perceived: (id: string) => request<Prediction>(`/ml/perceived/${id}`),
  anomalies: (id: string) => request<Prediction>(`/ml/anomalies/${id}`),
  prescription: (id: string) => request<Prediction>(`/ml/prescription/${id}`),
  insights: (id: string) => request<Prediction[]>(`/ml/insights/${id}`),
  models: () => request<ModelRecord[]>("/ml/models"),

  // Cohort. Both are synthetic and say so on the wire, so anything drawn from
  // them carries the badge.
  cohortSummary: () => request<CohortSummary>("/cohort/summary"),
  /**
   * The reference distribution for one age band and sex.
   *
   * Returns the histogram already binned, so the chart draws what the model
   * computed rather than rebinning it in the browser and risking a different
   * answer to the one the percentile endpoint gives.
   */
  cohortPercentiles: (ageBand: string, sex: string) =>
    request<CohortPercentiles>(
      `/cohort/percentiles?age_band=${encodeURIComponent(ageBand)}&sex=${encodeURIComponent(sex)}`,
    ),
};

export { request };
