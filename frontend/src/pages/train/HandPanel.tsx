/**
 * What the hand is doing, beside the effort trace.
 *
 * Part of the camera extension: see the removal procedure at the top of
 * src/lib/handTracker.ts.
 *
 * Off until asked, like the voice toggle next to it and for a stronger reason.
 * An app that turns the webcam on unprompted is a different category of wrong
 * from one that talks unprompted, so nothing here acquires a camera without a
 * press, and a stored preference is not a press.
 *
 * The clinical rule that governs this file, and it matters more here than it
 * did in the Lab because this panel sits beside a calibrated force reading: a
 * camera measures where points are, not how hard somebody is squeezing. So
 * nothing here prints kilograms, a percentile, EWGSOP2, an MCID, a percentage
 * of maximum, the unqualified word strength, or the word for what the sEMG
 * signal measures. A count of fingers is a count. See docs/CLINICAL.md.
 *
 * Nothing this panel shows is recorded. The readings are rendered and
 * discarded: no camera value joins the session, reaches the backend or is
 * written to the database.
 */

import { useEffect, useRef, useState } from "react";

import { HandStage } from "../../components/HandStage";
import { Card } from "../../components/ui";
import { handTracker } from "../../lib/handTracker";
import {
  cameraAvailable,
  useCameraStore,
  type CameraFault,
} from "../../store/camera";

/**
 * Shorter than the Lab's copy on purpose. This sits in a narrow column during
 * a session, where a paragraph would push the repetition count off the screen.
 * The Lab tab carries the long form.
 */
const FAULT_COPY: Record<CameraFault, string> = {
  "insecure-context": "The camera needs https or localhost.",
  "no-camera-api": "This browser has no camera API.",
  "no-camera-found": "No camera was found on this device.",
  "permission-denied":
    "The camera permission was not granted. Press again to see the prompt.",
  "camera-in-use": "Another application is using the camera.",
  "model-unreachable":
    "The tracking model could not be downloaded. This is the one part of the app that needs the network.",
  "model-failed": "The tracking model would not start in this browser.",
  unknown: "The camera could not be started.",
};

const COUNT_WORD = ["No", "One", "Two", "Three", "Four", "Five"] as const;

export function HandPanel() {
  const videoRef = useRef<HTMLVideoElement>(null);
  const status = useCameraStore((s) => s.status);
  const fault = useCameraStore((s) => s.fault);
  const [requested, setRequested] = useState(false);

  // Flat and primitive, one selector each, so an unchanged value re-renders
  // nothing. Subscribing to the raw landmark array here instead would re-render
  // this panel sixty times a second beside the charts. See store/camera.ts.
  const gesture = useCameraStore((s) => s.handReading?.gesture ?? null);
  const fingers = useCameraStore((s) => s.handReading?.fingers ?? null);
  const open = useCameraStore((s) => s.handReading?.open ?? false);

  // Started here rather than in the click, because the video element the
  // tracker needs does not exist at the moment of the press: the preview is
  // only rendered once `on` is true, so `videoRef.current` is still null
  // inside the handler and the start was silently skipped. The panel then
  // said "Camera on" over an empty box with nothing running behind it.
  //
  // By the time an effect runs the re-render has happened and the element is
  // mounted. Keyed on `requested` alone, so this fires on the press and not
  // on the sixty status changes a second that follow it.
  //
  // Above the availability check below, because a hook after an early return
  // is called conditionally and breaks the order React relies on.
  useEffect(() => {
    if (!requested) return;
    if (videoRef.current) handTracker.start(videoRef.current);
  }, [requested]);

  // A browser that cannot do this gets no control rather than a dead one, the
  // same way the voice toggle hides itself where there is no speech.
  if (!cameraAvailable()) return null;

  const running = status === "running";
  const on = running || requested;

  const toggle = () => {
    if (on) {
      setRequested(false);
      handTracker.stop();
      return;
    }
    setRequested(true);
  };

  return (
    <div className="flex w-full flex-col items-center gap-3">
      <button
        type="button"
        aria-pressed={on}
        onClick={toggle}
        disabled={status === "loading"}
        className="rounded-pill border border-squish-300 px-3 py-1.5 text-label text-squish-700 transition-colors hover:bg-squish-50 disabled:opacity-60"
        title="Watch what your hand is doing. The video stays in this browser."
      >
        <span aria-hidden="true">{on ? "◉" : "◌"}</span>{" "}
        {status === "loading"
          ? "Starting the camera"
          : on
            ? "Camera on"
            : "Camera off"}
      </button>

      {/* The preview only exists while it is running, so the column keeps its
          resting height for everybody who never turns it on. Small: the
          mascot and the coaching prompt above it are what somebody actually
          watches while contracting. */}
      {on ? (
        <HandStage videoRef={videoRef} className="aspect-[4/3] w-40" />
      ) : null}

      {running ? (
        <div className="flex flex-col items-center gap-1 text-center">
          {fingers === null ? (
            <p className="text-label text-ink/70">No hand in view</p>
          ) : (
            <>
              <p className="text-body text-squish-700">
                {COUNT_WORD[fingers]}{" "}
                {fingers === 1 ? "finger" : "fingers"} extended
              </p>
              <p className="text-label text-ink/70">
                <span aria-hidden="true">{open ? "◯" : "◉"}</span>{" "}
                {open ? "Hand open" : "Hand closed"}
              </p>
              {/* Not recognised rather than the nearest guess. A label that is
                  confidently wrong beside a real measurement costs more than
                  no label. */}
              <p className="text-label text-ink/70">
                {gesture ? `Gesture: ${gesture}` : "Gesture: not recognised"}
              </p>
            </>
          )}
          <p className="text-label text-ink/60">
            Motion only, and separate from the sensor trace. The video stays in
            this browser.
          </p>
        </div>
      ) : null}

      {status === "error" && fault ? (
        <Card tone="alert" pad="sm">
          <p role="alert" className="text-label text-ink">
            {FAULT_COPY[fault]}
          </p>
        </Card>
      ) : null}
    </div>
  );
}
