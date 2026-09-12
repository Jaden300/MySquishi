/**
 * Camera: hand landmarks in the browser, on their own.
 *
 * TO REMOVE THIS FEATURE ENTIRELY: delete this file, src/lib/handTracker.ts,
 * src/store/camera.ts and their three test files, then remove the three lines
 * mentioning "camera" from src/pages/LabPage.tsx. Nothing else imports any of
 * it. No backend, no database, no dependency in package.json, no build config.
 *
 * What this is, and just as importantly what it is not. It previews the
 * webcam, draws MediaPipe's 21 hand landmarks over it and says whether the
 * hand reads as open or closed. It writes nothing to a session, sends no frame
 * anywhere and produces no clinical figure. The sEMG signal measures effort
 * and this measures motion; pairing the two is the interesting part and it is
 * deliberately not built here.
 *
 * The clinical rule that governs this file: a camera measures the distance
 * between points, so nothing here may print kilograms, a percentile, EWGSOP2,
 * an MCID, a percentage of maximum, or the unqualified word strength, and the
 * thumb to finger distance is never called grip. See docs/CLINICAL.md.
 */

import { useEffect, useRef, useState } from "react";

import {
  aperture,
  handTracker,
  HAND_CONNECTIONS,
  isOpen,
} from "../../lib/handTracker";
import { tokens } from "../../lib/tokens";
import {
  cameraAvailable,
  unavailableFault,
  useCameraStore,
  type CameraFault,
} from "../../store/camera";
import { Button, Card, SectionHeader } from "../../components/ui";

/**
 * One message per failure.
 *
 * A single "camera failed" is what makes a working feature look like broken
 * software. Each of these tells the reader what happened and, where there is
 * one, what they can do about it.
 */
const FAULT_COPY: Record<CameraFault, string> = {
  "insecure-context":
    "The camera only works over https or on localhost. This page is on neither, so the browser will not allow it.",
  "no-camera-api":
    "This browser has no camera API, so hand tracking cannot run here. Everything else in the app works normally.",
  "no-camera-found":
    "No camera was found on this device. Connect one and press start again.",
  "permission-denied":
    "The camera permission was not granted. If you dismissed the prompt, press start to see it again. If you denied it, allow the camera for this site in the browser settings and reload.",
  "camera-in-use":
    "Another application is using the camera. Close it and press start again.",
  "model-unreachable":
    "The hand tracking model could not be downloaded. This is the one part of the app that needs the network: everything else runs offline.",
  "model-failed":
    "The hand tracking model downloaded but would not start in this browser.",
  unknown: "The camera could not be started, and the browser gave no reason.",
};

export function CameraTab() {
  const videoRef = useRef<HTMLVideoElement>(null);
  const status = useCameraStore((s) => s.status);
  const fault = useCameraStore((s) => s.fault);
  const landmarks = useCameraStore((s) => s.landmarks);
  const [requested, setRequested] = useState(false);

  const available = cameraAvailable();
  const blocked = unavailableFault();

  // The camera belongs to this tab alone. Without the teardown the indicator
  // light stays on after the reader has moved to Settings, which is the most
  // alarming thing this feature could do.
  useEffect(() => () => handTracker.stop(), []);

  const start = () => {
    setRequested(true);
    if (videoRef.current) handTracker.start(videoRef.current);
  };

  const stop = () => {
    setRequested(false);
    handTracker.stop();
  };

  const open = landmarks ? aperture(landmarks) : null;

  return (
    <div className="flex flex-col gap-10">
      <section>
        <SectionHeader
          title="Camera hand tracking"
          note="Twenty one landmarks at video rate, tracked entirely in this browser."
        />

        {/* The privacy claim is the first thing on the panel rather than a
            footnote. This is the only sensor in the app that produces an image
            of the person using it, and a webcam page that does not say where
            the video goes has answered the reader's first question with
            silence. */}
        <Card tone="accent" className="flex flex-col gap-2">
          <p className="text-body text-ink">
            <span aria-hidden="true">◆</span> The video never leaves your
            browser. Nothing is uploaded, recorded or saved, and closing this
            tab releases the camera.
          </p>
          <p className="text-label text-ink/70">
            This is a motion preview, separate from the sEMG signal. It is not
            attached to any session and produces no clinical measurement.
          </p>
        </Card>
      </section>

      {available ? (
        <section className="flex flex-col gap-4">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <StatusLine status={status} landmarks={landmarks} />
            <Button
              variant={status === "running" ? "secondary" : "primary"}
              onClick={status === "running" || requested ? stop : start}
              disabled={status === "loading"}
            >
              {status === "loading"
                ? "Starting the camera"
                : status === "running" || requested
                  ? "Stop the camera"
                  : "Start the camera"}
            </Button>
          </div>

          <Stage videoRef={videoRef} landmarks={landmarks} />

          {status === "error" && fault ? (
            <Card tone="alert">
              <p role="alert" className="text-body text-ink">
                {FAULT_COPY[fault]}
              </p>
            </Card>
          ) : null}

          {status === "running" ? <Aperture value={open} /> : null}
        </section>
      ) : (
        <Card tone="alert">
          <p className="text-body text-ink">
            {FAULT_COPY[blocked ?? "unknown"]}
          </p>
        </Card>
      )}
    </div>
  );
}

/** Mirrors SourceChip's shape, so a live camera reads like a live sensor. */
function StatusLine({
  status,
  landmarks,
}: {
  status: string;
  landmarks: unknown;
}) {
  if (status !== "running") {
    return (
      <span className="text-label text-ink/70">
        {status === "loading"
          ? "Loading the model. The first run downloads it."
          : "The camera is off."}
      </span>
    );
  }

  return (
    <span className="flex flex-wrap items-center gap-3">
      <span className="inline-flex items-center gap-1.5 rounded-pill border border-good bg-good/15 px-3 py-1 text-label text-ink">
        <span aria-hidden="true">●</span>
        Camera
      </span>
      <span className="text-label text-ink/70">
        {landmarks ? "Hand in view" : "No hand in view"}
      </span>
    </span>
  );
}

/**
 * Open or closed, as a glyph and a word.
 *
 * A number between zero and one would look like a measurement and invite the
 * reader to treat it as one, which is exactly the false precision the clinical
 * rules forbid. The distance is real; what it means clinically is not
 * something a webcam can say.
 */
function Aperture({ value }: { value: number | null }) {
  if (value === null) {
    return (
      <p className="text-body text-ink/70">
        Hold one hand in the frame to see whether it reads as open or closed.
      </p>
    );
  }

  const isHandOpen = isOpen(value);

  return (
    <Card className="flex flex-wrap items-center gap-3">
      <span aria-hidden="true" className="text-h2 text-squish-700">
        {isHandOpen ? "◯" : "◉"}
      </span>
      <span className="text-h3 text-squish-700">
        {isHandOpen ? "Hand open" : "Hand closed"}
      </span>
      <span className="text-label text-ink/70">
        Thumb to finger distance, measured against the width of your own hand
        so that moving nearer the lens does not change it.
      </span>
    </Card>
  );
}

/**
 * The video and its overlay, in one square that scales down to a phone.
 *
 * The canvas is redrawn from the store rather than inside the detect loop, so
 * a rendering fault stays inside React where the tab's ErrorBoundary can catch
 * it instead of escaping into an animation callback.
 */
function Stage({
  videoRef,
  landmarks,
}: {
  videoRef: React.RefObject<HTMLVideoElement | null>;
  landmarks: { x: number; y: number }[] | null;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const context = canvas.getContext("2d");
    if (!context) return;

    const { width, height } = canvas;
    context.clearRect(0, 0, width, height);
    if (!landmarks) return;

    // squish300 is already held above the three to one contrast floor that
    // applies to graphical objects, because it is the colour the raw signal
    // trace is drawn in. See lib/contrast.test.ts.
    context.strokeStyle = tokens.squish300;
    context.fillStyle = tokens.squish500;
    context.lineWidth = 2;

    for (const [from, to] of HAND_CONNECTIONS) {
      const a = landmarks[from];
      const b = landmarks[to];
      if (!a || !b) continue;
      context.beginPath();
      context.moveTo(a.x * width, a.y * height);
      context.lineTo(b.x * width, b.y * height);
      context.stroke();
    }

    for (const point of landmarks) {
      context.beginPath();
      context.arc(point.x * width, point.y * height, 4, 0, Math.PI * 2);
      context.fill();
    }
  }, [landmarks]);

  return (
    <Card pad="none" className="overflow-hidden">
      <div className="relative aspect-[4/3] w-full bg-ink/5">
        {/* Mirrored, because an unmirrored preview of yourself is disorienting
            in a way that makes people think the tracking is wrong. */}
        <video
          ref={videoRef}
          playsInline
          muted
          className="h-full w-full -scale-x-100 object-cover"
        />
        <canvas
          ref={canvasRef}
          width={640}
          height={480}
          aria-hidden="true"
          className="pointer-events-none absolute inset-0 h-full w-full -scale-x-100"
        />
      </div>
    </Card>
  );
}
