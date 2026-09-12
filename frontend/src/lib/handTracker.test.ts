/**
 * Hand tracking.
 *
 * jsdom has no getUserMedia, no requestAnimationFrame worth the name and no
 * way to load MediaPipe, so all three are stubbed here rather than in
 * test/setup.ts: setup stubs what every file needs, and this is the only file
 * that opens a camera.
 *
 * The cases below are the bugs this singleton can actually have. Two streams
 * opened by a double mount under StrictMode, a track left running after the
 * reader leaves the tab, and a failure that reaches the panel as "something
 * went wrong" instead of as the specific thing that went wrong.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { aperture, handTracker, isOpen } from "./handTracker";
import { useCameraStore } from "../store/camera";

let tracks: { stop: ReturnType<typeof vi.fn>; kind: string }[] = [];
let getUserMedia: ReturnType<typeof vi.fn>;

function stubCamera() {
  tracks = [
    { stop: vi.fn(), kind: "video" },
    { stop: vi.fn(), kind: "audio" },
  ];

  getUserMedia = vi.fn().mockResolvedValue({ getTracks: () => tracks });

  vi.stubGlobal("isSecureContext", true);
  Object.defineProperty(navigator, "mediaDevices", {
    configurable: true,
    value: { getUserMedia },
  });

  vi.stubGlobal(
    "requestAnimationFrame",
    vi.fn(() => 1),
  );
  vi.stubGlobal("cancelAnimationFrame", vi.fn());
}

/** A video element that does not need a real media pipeline behind it. */
function fakeVideo(): HTMLVideoElement {
  const video = document.createElement("video");
  video.play = vi.fn().mockResolvedValue(undefined);
  return video;
}

describe("the hand tracker", () => {
  beforeEach(() => {
    stubCamera();
    useCameraStore.getState().reset();
  });

  afterEach(() => {
    handTracker.stop();
    vi.unstubAllGlobals();
    Object.defineProperty(navigator, "mediaDevices", {
      configurable: true,
      value: undefined,
    });
  });

  it("refuses to start in an insecure context, without touching the camera", () => {
    vi.stubGlobal("isSecureContext", false);

    handTracker.start(fakeVideo());

    expect(getUserMedia).not.toHaveBeenCalled();
    expect(useCameraStore.getState().fault).toBe("insecure-context");
  });

  it("opens one stream even when started twice", async () => {
    /* StrictMode mounts an effect twice. Two streams means two indicator
       lights and one of them never gets released. */
    const video = fakeVideo();
    await Promise.all([handTracker.start(video), handTracker.start(video)]);

    expect(getUserMedia).toHaveBeenCalledTimes(1);
  });

  it("stops every track when it is torn down", async () => {
    await handTracker.start(fakeVideo());
    handTracker.stop();

    for (const track of tracks) {
      expect(track.stop).toHaveBeenCalled();
    }
  });

  it("releases a stream that arrives after it was stopped", async () => {
    /* Somebody leaves the tab while the permission prompt is still open. The
       stream resolves into a tracker nobody is watching any more. */
    let resolve: (value: unknown) => void = () => {};
    getUserMedia.mockReturnValue(
      new Promise((r) => {
        resolve = r;
      }),
    );

    const starting = handTracker.start(fakeVideo());
    handTracker.stop();
    resolve({ getTracks: () => tracks });
    await starting;

    expect(tracks[0].stop).toHaveBeenCalled();
  });

  it("returns to a clean state after stopping", async () => {
    await handTracker.start(fakeVideo());
    handTracker.stop();

    expect(useCameraStore.getState().status).toBe("idle");
    expect(useCameraStore.getState().landmarks).toBeNull();
  });

  describe("reports each camera failure as itself", () => {
    const cases = [
      ["NotFoundError", "no-camera-found"],
      ["NotAllowedError", "permission-denied"],
      ["SecurityError", "permission-denied"],
      ["NotReadableError", "camera-in-use"],
      ["OverconstrainedError", "no-camera-found"],
      ["WhateverError", "unknown"],
    ] as const;

    for (const [name, fault] of cases) {
      it(`maps ${name} to ${fault}`, async () => {
        const error = new Error("denied");
        error.name = name;
        getUserMedia.mockRejectedValue(error);

        await handTracker.start(fakeVideo());

        expect(useCameraStore.getState().status).toBe("error");
        expect(useCameraStore.getState().fault).toBe(fault);
      });
    }
  });

  it("says the model is unreachable rather than throwing, with no network", async () => {
    /* The dynamic import cannot resolve under vitest, which is the same
       failure a demo machine with no network has. It has to land in the store
       as a stated reason, not as an unhandled rejection. */
    await handTracker.start(fakeVideo());

    expect(useCameraStore.getState().status).toBe("error");
    expect(useCameraStore.getState().fault).toBe("model-unreachable");
  });

  it("releases the camera when the model cannot be loaded", async () => {
    /* Otherwise a failed load leaves the light on with nothing to turn it off. */
    await handTracker.start(fakeVideo());

    expect(tracks[0].stop).toHaveBeenCalled();
  });
});

describe("the aperture measure", () => {
  /** A hand spanning 0.2 of the frame, with the pinch distance varied. */
  function hand(gap: number) {
    const points = Array.from({ length: 21 }, () => ({ x: 0, y: 0, z: 0 }));
    points[0] = { x: 0.5, y: 0.5, z: 0 };
    points[9] = { x: 0.5, y: 0.3, z: 0 };
    points[4] = { x: 0.5, y: 0.5, z: 0 };
    points[8] = { x: 0.5 + gap, y: 0.5, z: 0 };
    return points;
  }

  it("is scaled by the size of the hand, not the frame", () => {
    // The same pose at two distances from the lens reads the same.
    const near = aperture(hand(0.2));
    expect(near).toBeCloseTo(1);
  });

  it("reads a spread hand as open and a pinched one as closed", () => {
    expect(isOpen(aperture(hand(0.2))!)).toBe(true);
    expect(isOpen(aperture(hand(0.02))!)).toBe(false);
  });

  it("returns null rather than a wrong number on a partial hand", () => {
    expect(aperture([])).toBeNull();
  });

  it("returns null when the hand has no measurable span", () => {
    const collapsed = Array.from({ length: 21 }, () => ({ x: 0.5, y: 0.5, z: 0 }));
    expect(aperture(collapsed)).toBeNull();
  });
});
