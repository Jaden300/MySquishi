/**
 * The voice rules, enforced against the source rather than trusted.
 *
 * docs/DESIGN.md states two of these. The habit this file follows is the one
 * chartMotion.test.ts describes: a rule that nothing fails on is a rule that
 * gets half applied, and the difference between a convention and a guarantee
 * is whether the suite goes red when it is broken.
 */

// @vitest-environment node

import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

const SRC = join(__dirname, "..");

/** The one module allowed to touch the speech API directly. */
const SPEECH_MODULE = join("lib", "speech.ts");

function sourceFiles(dir: string): string[] {
  const found: string[] = [];

  for (const entry of readdirSync(dir)) {
    const path = join(dir, entry);

    if (statSync(path).isDirectory()) {
      found.push(...sourceFiles(path));
      continue;
    }

    if (/\.tsx?$/.test(entry) && !/\.test\.tsx?$/.test(entry)) {
      found.push(path);
    }
  }

  return found;
}

describe("speech stays in one module", () => {
  it("is not spoken anywhere but lib/speech.ts", () => {
    /* One browser queue means one owner. A component calling speak() directly
       would talk over the controller's priority ordering with no way for it
       to know.

       Feature detection is not speaking: `"speechSynthesis" in window` is how
       a component hides a toggle that would otherwise do nothing, so this
       looks for member access and utterance construction rather than for the
       name on its own. */
    const speaks = /speechSynthesis\s*\.|new SpeechSynthesisUtterance/;

    const offenders = sourceFiles(SRC)
      .filter((path) => !path.endsWith(SPEECH_MODULE))
      .filter((path) => speaks.test(readFileSync(path, "utf8")))
      .map((path) => path.slice(SRC.length + 1));

    expect(offenders).toEqual([]);
  });
});

describe("voice does not collide with the live region channel", () => {
  it("the coach prompt is not also announced to a screen reader", () => {
    /* The rule in docs/DESIGN.md is about a string, not a file: a screen
       reader user with voice on would hear the announcement and the synthesis
       interleaved. The prompt is the string voice actually speaks, so this
       checks the component that renders it rather than every file that
       happens to import the controller. LiveStage, for instance, carries an
       unrelated error alert and is not a collision. */
    const charts = readFileSync(
      join(SRC, "components", "charts", "LiveCharts.tsx"),
      "utf8",
    );

    const prompt = charts.slice(charts.indexOf("export function CoachPrompt"));
    const body = prompt.slice(0, prompt.indexOf("\nexport function"));

    expect(body).not.toMatch(/aria-live|role="status"|role="alert"/);
  });
});

describe("the spoken copy is the copy on screen", () => {
  it("speaks the coach prompt rather than a second script", () => {
    /* Writing separate wording for the spoken version forks it from the
       visible prompt, and the two drift. */
    const speech = readFileSync(join(SRC, SPEECH_MODULE), "utf8");

    expect(speech).toMatch(/coach\??\.prompt/);
  });

  it("speaks no hardcoded clinical prompt of its own", () => {
    const speech = readFileSync(join(SRC, SPEECH_MODULE), "utf8");

    for (const written of ["Hold it steady", "Ease off slowly", "Squeeze"]) {
      expect(speech).not.toContain(written);
    }
  });
});
