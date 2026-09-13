/**
 * Hand landmark tracking, in the browser and nowhere else.
 *
 * TO REMOVE THIS FEATURE ENTIRELY: delete this file, src/lib/handPose.ts,
 * src/store/camera.ts, src/components/HandStage.tsx,
 * src/pages/lab/CameraTab.tsx, src/pages/train/HandPanel.tsx and their test
 * files, then remove the three lines mentioning "camera" from
 * src/pages/LabPage.tsx and the two mentioning HandPanel from
 * src/pages/train/LiveStage.tsx, along with the handTracker.stop() teardown
 * there. There is no backend, no database column, no dependency in
 * package.json and no build configuration to back out.
 *
 * A module level singleton rather than a component, the same shape and for the
 * same reason as lib/speech.ts: a component remounts on a route change and
 * under StrictMode, and each mount reruns its effect. With speech that
 * announces a repetition twice. With a camera it acquires the device twice and
 * leaks a MediaStreamTrack, which leaves the hardware indicator light on after
 * the user has left the page. That is the most alarming bug this feature can
 * have, so there is exactly one owner of the stream.
 *
 * MediaPipe is fetched from a CDN at the moment it is first needed, by a
 * dynamic import that Vite is told to leave alone. Two consequences, both
 * wanted. The bundle is completely unchanged for anyone who never opens the
 * tab, and the roughly 19.5MB of wasm and model weights are never installed
 * into the repository. The cost is that this one feature needs the network on
 * first use, and says so plainly when it does not have it.
 */

import {
  useCameraStore,
  unavailableFault,
  type CameraFault,
  type Landmark,
} from "../store/camera";
import { GestureSmoother, readHand } from "./handPose";

/**
 * Pinned exactly, never a range.
 *
 * A floating version on a CDN means the demo can break between a rehearsal and
 * the room, with no commit in between to explain it.
 */
const VERSION = "1.0.1";
const BASE = `https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@${VERSION}`;
const WASM_PATH = `${BASE}/wasm`;
const MODEL_URL =
  "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task";

/** Detection below this is treated as no hand rather than a bad guess. */
const MIN_CONFIDENCE = 0.5;

/**
 * The 21 point topology, as MediaPipe indexes it: wrist, then thumb through
 * little finger, four points each from base to tip. Drawing the bones rather
 * than only the joints is what makes the overlay read as a hand.
 */
export const HAND_CONNECTIONS: ReadonlyArray<readonly [number, number]> = [
  [0, 1], [1, 2], [2, 3], [3, 4],
  [0, 5], [5, 6], [6, 7], [7, 8],
  [5, 9], [9, 10], [10, 11], [11, 12],
  [9, 13], [13, 14], [14, 15], [15, 16],
  [13, 17], [17, 18], [18, 19], [19, 20],
  [0, 17],
];

/**
 * The pose measures live in handPose.ts and are re-exported here.
 *
 * They moved so the dependency runs one way: this file reads the geometry,
 * and the geometry knows nothing about cameras. A cycle between the two broke
 * on module evaluation order, because constructing the singleton below reached
 * for a class the half evaluated other module had not defined yet.
 */
export { aperture, isOpen } from "./handPose";

/** Maps a getUserMedia rejection onto copy the panel can show. */
function faultFromMediaError(error: unknown): CameraFault {
  const name =
    typeof error === "object" && error !== null && "name" in error
      ? String((error as { name: unknown }).name)
      : "";

  switch (name) {
    case "NotFoundError":
    case "OverconstrainedError":
      return "no-camera-found";
    // Chrome and Firefox both report a dismissed prompt and an explicit denial
    // as NotAllowedError, with nothing to tell them apart. Rather than print a
    // guess, both land here and the copy covers the two cases.
    case "NotAllowedError":
    case "SecurityError":
      return "permission-denied";
    case "NotReadableError":
    case "AbortError":
      return "camera-in-use";
    default:
      return "unknown";
  }
}

interface Landmarker {
  detectForVideo(
    video: HTMLVideoElement,
    timestamp: number,
  ): { landmarks?: Landmark[][] };
  close(): void;
}

class HandTracker {
  private stream: MediaStream | null = null;
  private landmarker: Landmarker | null = null;
  private video: HTMLVideoElement | null = null;
  private frame: number | null = null;
  private running = false;
  /** Guards against a second start() while the first is still awaiting. */
  private starting = false;
  private lastTimestamp = -1;
  private onVisibility: (() => void) | null = null;
  /**
   * Owned here because a smoothed gesture is a property of the stream rather
   * than of any view. Two panels keeping their own history would disagree
   * about the current pose.
   */
  private readonly smoother = new GestureSmoother();

  /**
   * Acquire the camera, load the model and begin detecting. Safe to call
   * twice: the second call returns immediately rather than opening a second
   * stream.
   */
  async start(video: HTMLVideoElement): Promise<void> {
    if (this.running || this.starting) return;

    const blocked = unavailableFault();
    if (blocked) {
      this.fail(blocked);
      return;
    }

    this.starting = true;
    this.video = video;
    const store = useCameraStore.getState();
    store.setStatus("loading");

    try {
      this.stream = await navigator.mediaDevices.getUserMedia({
        video: { width: { ideal: 640 }, height: { ideal: 480 } },
        audio: false,
      });
    } catch (error) {
      this.starting = false;
      this.fail(faultFromMediaError(error));
      return;
    }

    // stop() can be called while the await above is still pending, when
    // somebody leaves the tab during the permission prompt. The stream that
    // arrives after that has to be released rather than left running.
    if (!this.starting) {
      this.releaseStream();
      return;
    }

    try {
      video.srcObject = this.stream;
      await video.play();
    } catch {
      /* Autoplay policies can refuse this. Detection still runs against the
         element, and the preview is the only thing lost, so it is not fatal. */
    }

    try {
      this.landmarker = await this.loadLandmarker();
    } catch (error) {
      this.starting = false;
      this.releaseStream();
      this.fail(
        error instanceof ModelLoadError ? "model-unreachable" : "model-failed",
      );
      return;
    }

    if (!this.starting) {
      this.releaseStream();
      this.closeLandmarker();
      return;
    }

    this.starting = false;
    this.running = true;
    this.watchVisibility();
    useCameraStore.getState().setStatus("running");
    this.loop();
  }

  /**
   * Release everything, in an order that holds even if start() failed halfway.
   *
   * Every branch of this has to run: a cancelled frame with a live track still
   * leaves the camera light on, and a closed landmarker with a live loop
   * throws on the next tick.
   */
  stop(): void {
    this.starting = false;
    this.running = false;

    if (this.frame !== null) {
      cancelAnimationFrame(this.frame);
      this.frame = null;
    }

    if (this.onVisibility) {
      document.removeEventListener("visibilitychange", this.onVisibility);
      this.onVisibility = null;
    }

    this.releaseStream();
    this.closeLandmarker();

    if (this.video) {
      try {
        this.video.srcObject = null;
      } catch {
        /* The element may already be detached. */
      }
      this.video = null;
    }

    this.lastTimestamp = -1;
    this.smoother.reset();
    useCameraStore.getState().reset();
  }

  private releaseStream(): void {
    try {
      for (const track of this.stream?.getTracks() ?? []) track.stop();
    } catch {
      /* Nothing usable to stop. */
    }
    this.stream = null;
  }

  private closeLandmarker(): void {
    try {
      this.landmarker?.close();
    } catch {
      /* Already closed, or wasm torn down under it. */
    }
    this.landmarker = null;
  }

  private fail(fault: CameraFault): void {
    useCameraStore.getState().setStatus("error", fault);
  }

  /**
   * Fetch MediaPipe and build the landmarker.
   *
   * The @vite-ignore is what keeps this out of the bundle: without it Vite
   * resolves the specifier at build time and the CDN URL becomes a build
   * dependency, which is the opposite of what this feature wants.
   */
  private async loadLandmarker(): Promise<Landmarker> {
    let vision: {
      FilesetResolver: {
        forVisionTasks(path: string): Promise<unknown>;
      };
      HandLandmarker: {
        createFromOptions(files: unknown, options: unknown): Promise<Landmarker>;
      };
    };

    try {
      vision = await import(/* @vite-ignore */ `${BASE}/vision_bundle.mjs`);
    } catch {
      throw new ModelLoadError();
    }

    let files: unknown;
    try {
      files = await vision.FilesetResolver.forVisionTasks(WASM_PATH);
    } catch {
      throw new ModelLoadError();
    }

    // A failure past this point is wasm or the model itself rather than the
    // network, so it is not remapped to unreachable.
    return vision.HandLandmarker.createFromOptions(files, {
      baseOptions: { modelAssetPath: MODEL_URL, delegate: "GPU" },
      runningMode: "VIDEO",
      numHands: 1,
      minHandDetectionConfidence: MIN_CONFIDENCE,
      minTrackingConfidence: MIN_CONFIDENCE,
    });
  }

  /**
   * Stop detecting while the tab is in the background.
   *
   * requestAnimationFrame is throttled rather than stopped there, and running
   * inference against a hidden video is heat and battery for frames nobody
   * sees. The camera stays acquired: releasing it would drop the indicator
   * light and then reacquire on return, which looks like the page reaching for
   * the camera on its own.
   */
  private watchVisibility(): void {
    this.onVisibility = () => {
      if (document.hidden) {
        if (this.frame !== null) {
          cancelAnimationFrame(this.frame);
          this.frame = null;
        }
      } else if (this.running && this.frame === null) {
        this.loop();
      }
    };
    document.addEventListener("visibilitychange", this.onVisibility);
  }

  private loop = (): void => {
    if (!this.running || !this.video || !this.landmarker) return;

    try {
      // MediaPipe rejects a timestamp that does not advance, which happens
      // whenever rAF fires twice inside one video frame.
      const timestamp = performance.now();
      if (timestamp > this.lastTimestamp) {
        this.lastTimestamp = timestamp;
        const result = this.landmarker.detectForVideo(this.video, timestamp);
        const hand = result?.landmarks?.[0] ?? null;

        const store = useCameraStore.getState();
        store.setLandmarks(hand);

        // Derived here, at the one place that already runs per frame and
        // already holds the landmarks. Publishing a small flat reading rather
        // than making every panel recompute from the raw array is what keeps
        // the session's re-render count down. See store/camera.ts.
        const reading = hand ? readHand(hand) : null;
        store.setHandReading(
          reading
            ? { ...reading, gesture: this.smoother.push(reading.gesture) }
            : null,
        );

        if (!reading) this.smoother.reset();
      }
    } catch {
      /* One bad frame is not worth ending the session over, and a throw here
         would escape into the animation callback where React cannot catch it.
         The next frame usually succeeds. */
    }

    this.frame = requestAnimationFrame(this.loop);
  };
}

/** Distinguishes "could not fetch it" from "fetched it and it would not run". */
class ModelLoadError extends Error {}

export const handTracker = new HandTracker();
