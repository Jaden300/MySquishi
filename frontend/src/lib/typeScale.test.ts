// @vitest-environment node
// Reads the source tree from disk rather than rendering anything, so it opts
// out of the jsdom environment the component tests need.
import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

/**
 * The type floor, enforced.
 *
 * docs/DESIGN.md bans standing small text. tailwind.config.js makes that hard
 * to break by deleting the classes, so text-xs now generates nothing at all,
 * but a dead class is invisible: the element simply inherits and nobody
 * notices the intent was to shrink it. These tests catch that case, and catch
 * the chart type that Tailwind cannot reach.
 */

const srcDir = fileURLToPath(new URL("..", import.meta.url));

function sourceFiles(dir: string): string[] {
  return readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const path = join(dir, entry.name);
    if (entry.isDirectory()) return sourceFiles(path);
    if (!/\.tsx?$/.test(entry.name)) return [];
    if (entry.name.includes(".test.")) return [];
    return [path];
  });
}

const files = sourceFiles(srcDir);

describe("type scale", () => {
  it("finds source files to check", () => {
    // Guards the tests below against silently passing on an empty list.
    expect(files.length).toBeGreaterThan(20);
  });

  it("uses no class below the sixteen pixel floor", () => {
    // text-xs, text-sm and arbitrary pixel sizes under 16. These no longer
    // exist in the Tailwind scale, so any survivor is a silent no-op.
    const banned = /\btext-(?:xs|sm)\b|\btext-\[(?:[0-9]|1[0-5])px\]/;
    const offenders = files
      .filter((file) => banned.test(readFileSync(file, "utf8")))
      .map((file) => file.replace(srcDir, ""));

    expect(offenders).toEqual([]);
  });

  it("keeps chart type at or above thirteen pixels", () => {
    /*
      Recharts sets type through props, so the Tailwind scale cannot reach it
      and these have to be checked separately. 13px is a deliberate exception
      to the app's 16px floor: an axis tick is scale furniture read against
      the mark it labels, not prose, and larger ticks take space from the plot.
      See src/lib/chartText.ts.
    */
    const offenders: string[] = [];
    for (const file of files) {
      if (file.endsWith("chartText.ts")) continue;
      const source = readFileSync(file, "utf8");
      for (const match of source.matchAll(/fontSize:\s*(\d+)/g)) {
        if (Number(match[1]) < 13) {
          offenders.push(`${file.replace(srcDir, "")}: ${match[0]}`);
        }
      }
    }

    expect(offenders).toEqual([]);
  });

  it("routes chart type through the shared module rather than literals", () => {
    // A chart that sets its own fontSize is how the floor drifts back down one
    // axis at a time, so charts declare their type by importing it.
    const chartFiles = files.filter((file) => /components[/\\]charts[/\\]/.test(file));
    expect(chartFiles.length).toBeGreaterThan(0);

    const offenders = chartFiles
      .filter((file) => /fontSize:\s*\d+/.test(readFileSync(file, "utf8")))
      .map((file) => file.replace(srcDir, ""));

    expect(offenders).toEqual([]);
  });
});
