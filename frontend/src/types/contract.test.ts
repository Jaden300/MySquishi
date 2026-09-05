// @vitest-environment node
/**
 * The websocket frame contract.
 *
 * The frame is not described by OpenAPI, so this is what keeps the TypeScript
 * type and the server's frame in agreement. FRAME_KEYS is exported from
 * backend/app/api/live.py and served on GET /api/health precisely so this
 * check is possible.
 *
 * The assertion runs against the backend source rather than a running server,
 * so it works in CI with nothing started.
 */

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

import { FRAME_KEYS } from "./api";

const LIVE_PY = fileURLToPath(
  new URL("../../../backend/app/api/live.py", import.meta.url),
);

function backendFrameKeys(): string[] {
  const source = readFileSync(LIVE_PY, "utf8");
  const block = source.match(/FRAME_KEYS[^=]*=\s*\(([^)]*)\)/);
  if (!block) throw new Error("FRAME_KEYS not found in backend/app/api/live.py");

  return [...block[1].matchAll(/"([^"]+)"/g)].map((m) => m[1]);
}

describe("websocket frame contract", () => {
  it("matches the backend's FRAME_KEYS exactly", () => {
    expect(FRAME_KEYS.slice()).toEqual(backendFrameKeys());
  });

  it("carries the honesty fields the UI depends on", () => {
    // is_live drives the Simulated chip and calibrated gates the kg figures.
    // Losing either silently would let the UI overstate what it knows.
    expect(FRAME_KEYS).toContain("is_live");
    expect(FRAME_KEYS).toContain("calibrated");
    expect(FRAME_KEYS).toContain("sqi");
  });

  it("carries mvc_pct, which is computed server side", () => {
    expect(FRAME_KEYS).toContain("mvc_pct");
  });
});
