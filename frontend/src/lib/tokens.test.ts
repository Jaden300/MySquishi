// @vitest-environment node
// This test reads index.css from disk rather than rendering anything, so it
// opts out of the jsdom environment the component tests need.
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

import { cssVarNames, tokens, type TokenName } from "./tokens";

/**
 * index.css is the source of truth for the palette. tokens.ts mirrors the
 * literals for Recharts. If someone edits one and not the other, the charts
 * and the rest of the UI drift apart silently, so assert they agree.
 */

const cssPath = fileURLToPath(new URL("../index.css", import.meta.url));
const css = readFileSync(cssPath, "utf8");

function readCssVar(name: string): string | undefined {
  const match = css.match(new RegExp(`${name}\\s*:\\s*(#[0-9A-Fa-f]{3,8})\\s*;`));
  return match?.[1];
}

describe("design tokens", () => {
  it("declares every token in index.css", () => {
    for (const name of Object.values(cssVarNames)) {
      expect(readCssVar(name), `${name} missing from index.css`).toBeDefined();
    }
  });

  it("matches index.css for every value", () => {
    for (const key of Object.keys(tokens) as TokenName[]) {
      const fromCss = readCssVar(cssVarNames[key])?.toUpperCase();
      expect(fromCss, `${key} drifted from index.css`).toBe(tokens[key].toUpperCase());
    }
  });
});
