/**
 * The camera preview and its landmark overlay.
 *
 * Shared by the Lab tab and the live session so there is one copy of the
 * drawing rather than two that drift apart. Part of the camera extension: see
 * the removal procedure at the top of src/lib/handTracker.ts.
 *
 * Lines and dots on a 2D canvas, deliberately. Twenty one strokes for the
 * bones and twenty one filled circles for the joints is enough for the overlay
 * to read as a hand, and it costs no rendering library, no WebGL context and
 * no third dimension that the landmarks are too weakly conditioned to support.
 *
 * The canvas is redrawn from the store inside React rather than inside the
 * detect loop, so a rendering fault stays where an ErrorBoundary can catch it
 * instead of escaping into an animation callback.
 *
 * This is the one component allowed to subscribe to the raw landmark array,
 * which is rewritten sixty times a second. It can afford to because it only
 * writes to a canvas. Nothing that renders text may do the same: see
 * store/camera.ts.
 */

import { useEffect, useRef } from "react";

import { HAND_CONNECTIONS } from "../lib/handTracker";
import { tokens } from "../lib/tokens";
import { useCameraStore } from "../store/camera";
import { Card } from "./ui";

export function HandStage({
  videoRef,
  className = "aspect-[4/3] w-full",
}: {
  videoRef: React.RefObject<HTMLVideoElement | null>;
  /** The shape of the preview box. The session wants a much smaller one. */
  className?: string;
}) {
  const landmarks = useCameraStore((s) => s.landmarks);
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
      <div className={`relative bg-ink/5 ${className}`}>
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
