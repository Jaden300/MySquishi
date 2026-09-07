// @vitest-environment node
// Reads the source tree from disk rather than rendering anything, so it opts
// out of the jsdom environment the component tests need.
import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

/**
 * Motion is chrome, never data.
 *
 * A Recharts series animates on mount by default, growing from zero to its
 * value. For the length of that animation the chart is showing numbers that
 * are not the numbers, and a rehabilitation patient watching their strength
 * climb from zero on every page load is being told something false, briefly,
 * about the thing they came to the page to check.
 *
 * docs/DESIGN.md states the rule. This is what keeps it true: the no small
 * text rule spent months written down and half applied, and the difference
 * was that nothing failed when it was broken.
 */

const srcDir = fileURLToPath(new URL("..", import.meta.url));

/** Recharts components that plot data, as opposed to drawing furniture. */
const SERIES = ["Line", "Area", "Bar", "Scatter", "Pie", "Radar", "RadialBar"];

function sourceFiles(dir: string): string[] {
  return readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const path = join(dir, entry.name);
    if (entry.isDirectory()) return sourceFiles(path);
    if (!/\.tsx$/.test(entry.name)) return [];
    if (entry.name.includes(".test.")) return [];
    return [path];
  });
}

/**
 * The opening tag starting at `from`, brackets in props balanced.
 *
 * A naive scan to the first ">" stops inside props like radius={[4, 4, 0, 0]}
 * and reports a series that does carry the flag, so the depth counter is what
 * makes this test trustworthy rather than noisy.
 */
function openingTag(source: string, from: number): string {
  let depth = 0;
  for (let i = from; i < source.length; i += 1) {
    const char = source[i];
    if (char === "{" || char === "[") depth += 1;
    else if (char === "}" || char === "]") depth -= 1;
    else if (char === ">" && depth === 0) return source.slice(from, i + 1);
  }
  return source.slice(from);
}

const files = sourceFiles(srcDir);

describe("chart motion", () => {
  it("finds source files to check", () => {
    expect(files.length).toBeGreaterThan(10);
  });

  it("never animates a data series", () => {
    const pattern = new RegExp(`<(${SERIES.join("|")})[\\s>]`, "g");
    const offenders: string[] = [];

    for (const file of files) {
      const source = readFileSync(file, "utf8");
      for (const match of source.matchAll(pattern)) {
        const tag = openingTag(source, match.index);
        if (!tag.includes("isAnimationActive={false}")) {
          const line = source.slice(0, match.index).split("\n").length;
          offenders.push(`${file.replace(srcDir, "")}:${line} ${match[1]}`);
        }
      }
    }

    expect(offenders).toEqual([]);
  });
});
