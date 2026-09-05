/**
 * Test environment setup.
 *
 * Two browser APIs that jsdom does not implement have to be stubbed, and both
 * failures are opaque without them:
 *
 * matchMedia is what Framer Motion's useReducedMotion reads, so every test
 * touching Squishi throws without it.
 *
 * ResizeObserver is what Recharts' ResponsiveContainer uses to size itself, so
 * every chart test throws without it.
 */

import "@testing-library/jest-dom/vitest";
import { afterEach, vi } from "vitest";
import { cleanup } from "@testing-library/react";

afterEach(() => {
  cleanup();
});

// Setup runs for every test file, including the few that opt into the node
// environment to read files from disk. Those have no DOM to patch.
if (typeof window !== "undefined") {
  // Defaults to "no preference", so components render their animated branch
  // unless a test explicitly asks for reduced motion.
  Object.defineProperty(window, "matchMedia", {
    writable: true,
    value: vi.fn().mockImplementation((query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  });

  class ResizeObserverStub {
    observe() {}
    unobserve() {}
    disconnect() {}
  }

  globalThis.ResizeObserver =
    ResizeObserverStub as unknown as typeof ResizeObserver;

  // Recharts measures its container and renders nothing at zero size, which
  // would make every chart assertion fail against an empty SVG. Giving the
  // stub a real box makes charts render under test.
  Object.defineProperty(HTMLElement.prototype, "clientWidth", {
    configurable: true,
    value: 800,
  });
  Object.defineProperty(HTMLElement.prototype, "clientHeight", {
    configurable: true,
    value: 400,
  });
}
