/**
 * Camera preference and hand tracking state.
 *
 * Mirrors store/voice.ts, including the try/catch on both sides of storage:
 * localStorage throws outright in a private window rather than returning null,
 * and a preference read that throws would take the page down on load.
 *
 * Defaults **off**, for a stronger reason than voice. An app that starts
 * talking unasked is a bad first impression; an app that turns the webcam on
 * unasked is a different category of wrong. Nothing here acquires a camera
 * until somebody presses the button.
 *
 * This is the whole state surface for the camera extension. No frame reaches
 * the backend, and no value here is written to the database or joined to a
 * session: the readings below are read by the live session panel and rendered,
 * never recorded. See lib/handTracker.ts for the deletion procedure.
 */

import { create } from "zustand";

import type { HandReading } from "../lib/handPose";

const STORAGE_KEY = "mysquishi.camera";

/**
 * Why tracking is not running.
 *
 * One member per failure rather than a single "error", because a page that
 * says only "camera failed" reads as broken software. A reader who is told the
 * permission was denied knows what to do next; a reader told nothing assumes
 * the feature does not work. The copy for each lives in CameraTab.
 */
export type CameraFault =
  | "insecure-context"
  | "no-camera-api"
  | "no-camera-found"
  | "permission-denied"
  | "camera-in-use"
  | "model-unreachable"
  | "model-failed"
  | "unknown";

export type CameraStatus = "idle" | "loading" | "running" | "error";

/** A single normalized landmark, as MediaPipe reports it: 0 to 1 per axis. */
export interface Landmark {
  x: number;
  y: number;
  z: number;
}

interface CameraState {
  /** The persisted preference. Survives a reload; does not itself start anything. */
  cameraOn: boolean;
  setCameraOn: (on: boolean) => void;

  status: CameraStatus;
  fault: CameraFault | null;
  /** Set together, so a status change cannot leave a stale fault behind it. */
  setStatus: (status: CameraStatus, fault?: CameraFault | null) => void;

  /** The most recent frame's 21 points, or null when no hand is in view. */
  landmarks: Landmark[] | null;
  setLandmarks: (landmarks: Landmark[] | null) => void;

  /**
   * What the hand is doing, derived from the landmarks by the tracker.
   *
   * Kept flat and primitive next to the raw array for the reason store/live.ts
   * gives: landmarks are rewritten sixty times a second, so anything that
   * subscribes to them re-renders sixty times a second. A panel reading this
   * field instead re-renders only when the answer actually changes, which
   * while somebody holds a pose is never. The bail out that makes that true
   * lives in setHandReading.
   */
  handReading: HandReading | null;
  setHandReading: (reading: HandReading | null) => void;

  reset: () => void;
}

/** True when two readings would render identically, so the write can be skipped. */
function sameReading(a: HandReading | null, b: HandReading | null): boolean {
  if (a === null || b === null) return a === b;
  return (
    a.gesture === b.gesture && a.fingers === b.fingers && a.open === b.open
  );
}

function readStored(): boolean {
  try {
    return localStorage.getItem(STORAGE_KEY) === "true";
  } catch {
    return false;
  }
}

function writeStored(on: boolean): void {
  try {
    localStorage.setItem(STORAGE_KEY, String(on));
  } catch {
    /* Preference is not persisted. The tab still works this visit. */
  }
}

export const useCameraStore = create<CameraState>((set) => ({
  cameraOn: readStored(),
  setCameraOn: (on) => {
    writeStored(on);
    set({ cameraOn: on });
  },

  status: "idle",
  fault: null,
  setStatus: (status, fault = null) => set({ status, fault }),

  landmarks: null,
  setLandmarks: (landmarks) => set({ landmarks }),

  handReading: null,
  // Compared before writing rather than after. Zustand notifies every
  // subscriber on each set() whatever the contents, so a selector cannot bail
  // out on a value that was republished unchanged: the skip has to happen
  // here, at the write.
  setHandReading: (reading) =>
    set((state) =>
      sameReading(state.handReading, reading) ? state : { handReading: reading },
    ),

  reset: () =>
    set({ status: "idle", fault: null, landmarks: null, handReading: null }),
}));

/**
 * Whether a camera could work here at all.
 *
 * Kept as a plain function, the same as speechAvailable, so the panel can
 * explain rather than offer a control that cannot do anything. Two separate
 * reasons are folded together here and split apart by `unavailableFault`: an
 * old browser with no API, and a modern one served over plain http, where
 * getUserMedia exists but is guaranteed to reject.
 *
 * jsdom has no mediaDevices, so this is false under test unless stubbed.
 */
export function cameraAvailable(): boolean {
  return unavailableFault() === null;
}

/** Which of the two unavailable cases applies, or null when neither does. */
export function unavailableFault(): CameraFault | null {
  if (typeof window === "undefined") return "no-camera-api";

  // Checked before the API, because http://example.com in a current browser
  // has no navigator.mediaDevices at all and "this browser has no camera API"
  // would be a misleading thing to tell someone whose browser is fine.
  if (window.isSecureContext === false) return "insecure-context";

  if (typeof navigator === "undefined") return "no-camera-api";
  if (typeof navigator.mediaDevices?.getUserMedia !== "function") {
    return "no-camera-api";
  }

  return null;
}

export { STORAGE_KEY as CAMERA_STORAGE_KEY };
