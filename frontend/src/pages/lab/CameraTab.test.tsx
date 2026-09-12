/**
 * The camera panel.
 *
 * Two things are worth asserting here beyond "it renders". A browser that
 * cannot do this must be told why rather than handed a dead button, and the
 * panel must not print a clinical figure: a camera measures distance, so a
 * kilogram or a percentile appearing on this tab would be a claim the sensor
 * cannot support. See docs/CLINICAL.md.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import { CameraTab } from "./CameraTab";
import { useCameraStore } from "../../store/camera";

function renderTab() {
  return render(
    <MemoryRouter>
      <CameraTab />
    </MemoryRouter>,
  );
}

function stubWorkingCamera() {
  vi.stubGlobal("isSecureContext", true);
  Object.defineProperty(navigator, "mediaDevices", {
    configurable: true,
    value: { getUserMedia: vi.fn().mockResolvedValue({ getTracks: () => [] }) },
  });
}

/**
 * jsdom implements no canvas and logs a notice every time one is asked for a
 * context. Stubbing it with a recorder keeps the suite output clean and, more
 * usefully, means the overlay drawing actually runs here rather than being
 * skipped by the null guard.
 */
function stubCanvas() {
  const calls: string[] = [];
  const context = new Proxy(
    {},
    {
      get: (_target, property) => {
        if (property === "canvas") return undefined;
        return (...args: unknown[]) => {
          calls.push(`${String(property)}(${args.join(",")})`);
        };
      },
    },
  );

  vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue(
    context as unknown as CanvasRenderingContext2D,
  );

  return calls;
}

describe("the camera panel", () => {
  beforeEach(() => {
    useCameraStore.getState().reset();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    Object.defineProperty(navigator, "mediaDevices", {
      configurable: true,
      value: undefined,
    });
  });

  it("says the video stays in the browser", () => {
    /* The only sensor in the app that produces a picture of the user. The
       claim is required to be visible, not buried in a tooltip. */
    stubWorkingCamera();
    renderTab();

    expect(
      screen.getByText(/never leaves your browser/i),
    ).toBeInTheDocument();
  });

  it("says it is not attached to a session", () => {
    stubWorkingCamera();
    renderTab();

    expect(screen.getByText(/not attached to any session/i)).toBeInTheDocument();
  });

  it("explains an unusable browser instead of offering a dead button", () => {
    // jsdom has no mediaDevices, which is the old browser case exactly.
    renderTab();

    expect(screen.getByText(/no camera API/i)).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /start the camera/i }),
    ).not.toBeInTheDocument();
  });

  it("blames the address rather than the browser on plain http", () => {
    vi.stubGlobal("isSecureContext", false);
    renderTab();

    expect(screen.getByText(/only works over https/i)).toBeInTheDocument();
  });

  it("offers the control when the camera could work", () => {
    stubWorkingCamera();
    renderTab();

    expect(
      screen.getByRole("button", { name: /start the camera/i }),
    ).toBeInTheDocument();
  });

  it("shows the specific failure, not a generic one", () => {
    stubWorkingCamera();
    renderTab();
    // The store is driven from outside React here, the way the tracker drives
    // it, so the update has to be flushed before the panel is read.
    act(() => useCameraStore.getState().setStatus("error", "camera-in-use"));

    expect(screen.getByRole("alert")).toHaveTextContent(
      /another application is using the camera/i,
    );
  });

  it("reads a hand as open or closed in words, not by colour alone", () => {
    stubWorkingCamera();
    const drawn = stubCanvas();
    renderTab();

    const points = Array.from({ length: 21 }, () => ({ x: 0, y: 0, z: 0 }));
    points[0] = { x: 0.5, y: 0.5, z: 0 };
    points[9] = { x: 0.5, y: 0.3, z: 0 };
    points[4] = { x: 0.5, y: 0.5, z: 0 };
    points[8] = { x: 0.7, y: 0.5, z: 0 };

    act(() => {
      useCameraStore.getState().setStatus("running");
      useCameraStore.getState().setLandmarks(points);
    });

    expect(screen.getByText("Hand open")).toBeInTheDocument();

    // The bones as well as the joints: 21 arcs would still be a scatter of
    // dots rather than something that reads as a hand.
    expect(drawn.filter((call) => call.startsWith("arc"))).toHaveLength(21);
    expect(drawn.some((call) => call.startsWith("stroke"))).toBe(true);
  });

  it("prints no clinical figure anywhere on the panel", () => {
    /* The gate this tab has to pass. A camera measures kinematics, so any of
       these words appearing here would be a claim it cannot support, and the
       thumb to finger distance is never called grip. */
    stubWorkingCamera();
    const { container } = renderTab();
    act(() => useCameraStore.getState().setStatus("running"));

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
