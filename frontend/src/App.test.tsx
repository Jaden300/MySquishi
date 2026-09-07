// @vitest-environment node
// Reads the route table from disk rather than mounting the router, which would
// pull in every page and every chart for what is a table of strings.
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

/**
 * The eleven route era has to keep resolving.
 *
 * Someone's bookmark, a link in a demo script or a QR code on a poster all
 * outlive a refactor, and a dead link in front of an audience is worse than a
 * route nobody types any more.
 */

const source = readFileSync(
  fileURLToPath(new URL("./App.tsx", import.meta.url)),
  "utf8",
);

const LEGACY: [string, string][] = [
  ["onboarding", "/train?stage=profile"],
  ["calibrate", "/train?stage=calibrate"],
  ["session", "/train?stage=live"],
  ["insights", "/progress?tab=insights"],
  ["clinician", "/lab?tab=clinician"],
  ["connect", "/lab?tab=hardware"],
  ["settings", "/lab?tab=settings"],
  ["about", "/"],
];

describe("route table", () => {
  it.each(LEGACY)("redirects %s to %s", (from, to) => {
    const pattern = new RegExp(
      `path:\\s*"${from}"[^}]*to=\\{?["\`]${to.replace(/[?]/g, "\\?")}`,
    );
    expect(source).toMatch(pattern);
  });

  it("carries the session id across the summary redirect", () => {
    // Navigate cannot interpolate a param, so this one needs a component and
    // is the redirect most likely to be quietly dropped.
    expect(source).toMatch(/path:\s*"session\/:id\/summary"/);
    expect(source).toMatch(/to=\{`\/progress\/session\/\$\{id\}`\}/);
  });

  it("serves the four destinations", () => {
    for (const path of ["train", "progress", "lab"]) {
      expect(source).toMatch(new RegExp(`path:\\s*"${path}"`));
    }
    expect(source).toMatch(/index:\s*true/);
  });

  it("catches an unknown path rather than rendering an empty shell", () => {
    expect(source).toMatch(/path:\s*"\*"/);
  });

  it("marks every redirect as a replacement so back does not bounce", () => {
    // Without replace, the back button lands on the old URL, which redirects
    // forward again and traps the reader.
    const navigates = source.match(/<Navigate[^>]*>/g) ?? [];
    expect(navigates.length).toBeGreaterThanOrEqual(8);
    for (const tag of navigates) expect(tag).toContain("replace");
  });
});
