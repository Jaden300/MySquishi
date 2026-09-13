/**
 * The hand panel in the live session.
 *
 * Three things matter here beyond "it renders". The camera must stay off until
 * somebody asks for it, a camera that fails must not take the session with it,
 * and the panel must print no clinical figure: it sits beside a calibrated
 * force reading, which is the adjacency docs/CLINICAL.md exists to police.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, render, screen } from "@testing-library/react";

import { HandPanel } from "./HandPanel";
import { useCameraStore } from "../../store/camera";

function stubWorkingCamera() {
  vi.stubGlobal("isSecureContext", true);
  Object.defineProperty(navigator, "mediaDevices", {
    configurable: true,
    value: { getUserMedia: vi.fn().mockResolvedValue({ getTracks: () => [] }) },
  });
}

/** jsdom implements no canvas, and the overlay asks for a 2D context. */
function stubCanvas() {
  const context = new Proxy(
    {},
    {
      get: (_target, property) => {
        if (property === "canvas") return undefined;
        return () => {};
      },
    },
  );

  vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue(
    context as unknown as CanvasRenderingContext2D,
  );
}

describe("the hand panel", () => {
  beforeEach(() => {
    // The store is module global, so a reading left by one test would be read
    // by the next.
    useCameraStore.getState().reset();
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
    Object.defineProperty(navigator, "mediaDevices", {
      configurable: true,
      value: undefined,
    });
  });

  it("renders nothing where a camera could not work", () => {
    /* jsdom has no mediaDevices, which is the old browser case exactly. A dead
       control would be worse than no control. */
    const { container } = render(<HandPanel />);

    expect(container).toBeEmptyDOMElement();
  });

  it("starts switched off and touches no camera on mount", () => {
    /* Turning the webcam on unasked is the one thing this feature must never
       do, and a stored preference is not somebody asking. */
    stubWorkingCamera();
    render(<HandPanel />);

    const toggle = screen.getByRole("button", { name: /camera off/i });
    expect(toggle).toHaveAttribute("aria-pressed", "false");
    expect(navigator.mediaDevices.getUserMedia).not.toHaveBeenCalled();
  });

  it("shows no readout until the camera is running", () => {
    stubWorkingCamera();
    render(<HandPanel />);

    expect(screen.queryByText(/fingers extended/i)).not.toBeInTheDocument();
  });

  it("reports the count, the gesture and whether the hand is open", () => {
    stubWorkingCamera();
    stubCanvas();
    render(<HandPanel />);

    // Driven from outside React, the way the tracker drives it.
    act(() => {
      useCameraStore.getState().setStatus("running");
      useCameraStore.getState().setHandReading({
        gesture: "fist",
        fingers: 0,
        open: false,
      });
    });

    expect(screen.getByText(/no fingers extended/i)).toBeInTheDocument();
    expect(screen.getByText(/hand closed/i)).toBeInTheDocument();
    expect(screen.getByText(/gesture: fist/i)).toBeInTheDocument();
  });

  it("says a pose is not recognised rather than guessing", () => {
    stubWorkingCamera();
    stubCanvas();
    render(<HandPanel />);

    act(() => {
      useCameraStore.getState().setStatus("running");
      useCameraStore.getState().setHandReading({
        gesture: null,
        fingers: 3,
        open: true,
      });
    });

    expect(screen.getByText(/not recognised/i)).toBeInTheDocument();
    expect(screen.getByText(/three fingers extended/i)).toBeInTheDocument();
  });

  it("says when there is no hand in view", () => {
    stubWorkingCamera();
    stubCanvas();
    render(<HandPanel />);

    act(() => useCameraStore.getState().setStatus("running"));

    expect(screen.getByText(/no hand in view/i)).toBeInTheDocument();
  });

  it("shows the specific failure and keeps the rest of the panel", () => {
    /* The constraint that matters most: the camera is an enhancement layer, so
       a camera that fails must leave the session running and the control
       reachable. */
    stubWorkingCamera();
    render(<HandPanel />);

    act(() => useCameraStore.getState().setStatus("error", "camera-in-use"));

    expect(screen.getByRole("alert")).toHaveTextContent(
      /another application is using the camera/i,
    );
    expect(
      screen.getByRole("button", { name: /camera/i }),
    ).toBeInTheDocument();
  });

  it("says the video stays in the browser", () => {
    /* The session is where somebody actually sees the webcam come on, so the
       claim belongs here and not only on the Lab tab. */
    stubWorkingCamera();
    stubCanvas();
    render(<HandPanel />);

    act(() => useCameraStore.getState().setStatus("running"));

    expect(screen.getByText(/stays in this browser/i)).toBeInTheDocument();
  });

  it("prints no clinical figure anywhere on the panel", () => {
    /* The gate. A camera measures where points are, so any of these words
       appearing beside the effort trace would be a claim it cannot support.
       Scoped to this panel: the session legitimately prints percent MVC a few
       elements away. */
    stubWorkingCamera();
    stubCanvas();
    const { container } = render(<HandPanel />);

    act(() => {
      useCameraStore.getState().setStatus("running");
      useCameraStore.getState().setHandReading({
        gesture: "pinch",
        fingers: 2,
        open: false,
      });
    });

    const text = (container.textContent ?? "").toLowerCase();
    for (const term of [
      "kg",
      "kilogram",
      "percentile",
      "ewgsop",
      "mcid",
      "mvc",
      "strength",
      "grip",
    ]) {
      expect(text).not.toContain(term);
    }
  });
});
