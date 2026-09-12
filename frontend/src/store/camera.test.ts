/**
 * The camera preference and the capability probe.
 *
 * Mirrors voice.test.ts, including the storage throws case. The probe carries
 * more weight here than speechAvailable does: it decides between three
 * different explanations the panel can give, and getting it wrong means
 * telling somebody their browser is too old when the real problem is that the
 * page is being served over plain http.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  CAMERA_STORAGE_KEY,
  cameraAvailable,
  unavailableFault,
  useCameraStore,
} from "./camera";

/** jsdom provides no mediaDevices, so a working browser has to be faked. */
function stubWorkingCamera() {
  vi.stubGlobal("isSecureContext", true);
  Object.defineProperty(navigator, "mediaDevices", {
    configurable: true,
    value: { getUserMedia: vi.fn() },
  });
}

function removeMediaDevices() {
  Object.defineProperty(navigator, "mediaDevices", {
    configurable: true,
    value: undefined,
  });
}

describe("the camera preference", () => {
  beforeEach(() => {
    localStorage.clear();
    useCameraStore.setState({ cameraOn: false });
  });

  it("defaults to off", () => {
    // Stronger than a convention. Nothing may acquire a webcam unasked.
    expect(useCameraStore.getState().cameraOn).toBe(false);
  });

  it("persists a change", () => {
    useCameraStore.getState().setCameraOn(true);

    expect(useCameraStore.getState().cameraOn).toBe(true);
    expect(localStorage.getItem(CAMERA_STORAGE_KEY)).toBe("true");
  });

  it("turns back off", () => {
    useCameraStore.getState().setCameraOn(true);
    useCameraStore.getState().setCameraOn(false);

    expect(useCameraStore.getState().cameraOn).toBe(false);
    expect(localStorage.getItem(CAMERA_STORAGE_KEY)).toBe("false");
  });

  it("survives storage that throws on write", () => {
    const spy = vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("site data blocked");
    });

    expect(() => useCameraStore.getState().setCameraOn(true)).not.toThrow();
    expect(useCameraStore.getState().cameraOn).toBe(true);

    spy.mockRestore();
  });
});

describe("the tracking state", () => {
  beforeEach(() => {
    useCameraStore.getState().reset();
  });

  it("starts idle with no fault", () => {
    expect(useCameraStore.getState().status).toBe("idle");
    expect(useCameraStore.getState().fault).toBeNull();
  });

  it("clears a stale fault when the status moves on", () => {
    useCameraStore.getState().setStatus("error", "permission-denied");
    useCameraStore.getState().setStatus("loading");

    expect(useCameraStore.getState().fault).toBeNull();
  });

  it("drops the landmarks on reset", () => {
    useCameraStore.getState().setLandmarks([{ x: 0.5, y: 0.5, z: 0 }]);
    useCameraStore.getState().reset();

    expect(useCameraStore.getState().landmarks).toBeNull();
  });
});

describe("whether a camera could work here", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    removeMediaDevices();
  });

  it("is false in jsdom, which has no camera api", () => {
    expect(cameraAvailable()).toBe(false);
  });

  it("names the missing api when the browser is too old", () => {
    vi.stubGlobal("isSecureContext", true);
    removeMediaDevices();

    expect(unavailableFault()).toBe("no-camera-api");
  });

  it("names the insecure context before the missing api", () => {
    /* A current browser on plain http exposes no mediaDevices at all, so
       checking the api first would tell somebody their browser is the problem
       when the address bar is. */
    vi.stubGlobal("isSecureContext", false);
    removeMediaDevices();

    expect(unavailableFault()).toBe("insecure-context");
  });

  it("is true once a secure context and the api are both present", () => {
    stubWorkingCamera();

    expect(unavailableFault()).toBeNull();
    expect(cameraAvailable()).toBe(true);
  });
});
