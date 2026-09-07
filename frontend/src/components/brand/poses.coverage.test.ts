// @vitest-environment node
// Reads the source tree from disk rather than rendering anything, so it opts
// out of the jsdom environment the component tests need.
import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

import { POSE_IDS } from "./poses";

/**
 * Every pose is placed.
 *
 * Twenty poses were transcribed into poses.ts and six of them rendered. The
 * other fourteen were dead code that looked like a feature: the library
 * claimed a range of expression the app never used.
 *
 * This test is what stops that happening again. A pose added to POSES and not
 * placed on a page fails here, so the library cannot drift back out of sync
 * with what ships. It matches on the pose name appearing as a prop value,
 * which is loose, but the alternative is rendering every route and asserting
 * on data-pose, and a name in a pose= prop is the thing that actually puts a
 * pose on screen.
 */

const srcDir = fileURLToPath(new URL("../..", import.meta.url));

function sourceFiles(dir: string): string[] {
  return readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const path = join(dir, entry.name);
    if (entry.isDirectory()) return sourceFiles(path);
    if (!/\.tsx?$/.test(entry.name)) return [];
    if (entry.name.includes(".test.")) return [];
    // The library itself defines every id, so counting it would make this
    // test pass unconditionally.
    if (entry.name === "poses.ts") return [];
    return [path];
  });
}

const sources = sourceFiles(srcDir).map((file) => readFileSync(file, "utf8"));

describe("pose coverage", () => {
  it("finds source files to check", () => {
    expect(sources.length).toBeGreaterThan(20);
  });

  it("defines twenty poses", () => {
    // The count is asserted so that deleting a pose to make the coverage test
    // pass shows up as a deliberate change rather than a quiet one.
    expect(POSE_IDS).toHaveLength(20);
  });

  it("places every pose somewhere in the app", () => {
    const unplaced = POSE_IDS.filter((id) => {
      // pose="waving", pose: "waving", or "waving" in a pose list.
      const used = new RegExp(`pose=["']${id}["']|["']${id}["']`);
      return !sources.some((source) => used.test(source));
    });

    expect(unplaced).toEqual([]);
  });
});
