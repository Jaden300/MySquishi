/**
 * Hand pose geometry.
 *
 * Synthetic hands as plain arrays, the same approach the aperture tests next
 * door take: none of this needs a camera, a model or a browser, which is the
 * point of keeping the geometry pure.
 *
 * The poses are built in a deliberately dull coordinate frame. The wrist sits
 * at the origin of the hand and the fingers extend upward in decreasing y,
 * which is how MediaPipe reports an upright hand, and every distance is then
 * scaled by the wrist to middle base span.
 */

import { describe, expect, it } from "vitest";

import {
  classifyGesture,
  fingersExtended,
  GestureSmoother,
  readHand,
} from "./handPose";
import type { Landmark } from "../store/camera";

const FINGER_BASES = [5, 9, 13, 17];

/**
 * Build a hand.
 *
 * `fingers` is thumb first. An extended finger puts its tip well beyond its
 * middle knuckle; a curled one folds the tip back toward the wrist, which is
 * what a real curl does and what the reach test is looking for.
 *
 * `scale` multiplies every distance from the wrist, standing in for the hand
 * being nearer or further from the lens. `spread` is the thumb to index tip
 * distance, which only the aperture reads.
 */
function hand({
  fingers = [false, false, false, false, false],
  scale = 1,
  spread = 0.02,
}: {
  fingers?: boolean[];
  scale?: number;
  spread?: number;
} = {}): Landmark[] {
  const points: Landmark[] = Array.from({ length: 21 }, () => ({
    x: 0,
    y: 0,
    z: 0,
  }));

  const at = (x: number, y: number): Landmark => ({
    x: 0.5 + x * scale,
    y: 0.5 + y * scale,
    z: 0,
  });

  points[0] = at(0, 0);
  // Span is this distance: wrist to the base of the middle finger.
  points[9] = at(0, -0.2);

  const [thumb, ...rest] = fingers;

  rest.forEach((extended, index) => {
    const base = FINGER_BASES[index];
    const x = -0.06 + index * 0.05;

    points[base] = at(x, -0.18);
    if (extended) {
      points[base + 1] = at(x, -0.26);
      points[base + 2] = at(x, -0.32);
      points[base + 3] = at(x, -0.38);
    } else {
      // Curled: the tip folds back inside the knuckle.
      points[base + 1] = at(x, -0.24);
      points[base + 2] = at(x, -0.2);
      points[base + 3] = at(x, -0.15);
    }
  });

  // The thumb is built last, because where it goes depends on where the index
  // tip ended up: the aperture is the distance between those two points, and
  // the index tip is landmark 8, placed by the loop above.
  //
  // Two things have to hold at once, which is why this is a chain and not four
  // literal positions. The thumb's shape decides whether it reads as extended,
  // since that test measures the angle at its middle joint, so an extended
  // thumb needs its bones collinear and a folded one needs a sharp bend. Its
  // distance from the index tip separately decides the aperture. Writing the
  // tip on its own would satisfy one and quietly break the other.
  const target = {
    x: points[8].x + spread * scale,
    y: points[8].y + 0.05 * scale,
  };
  const along = (fraction: number): Landmark => ({
    x: points[0].x + (target.x - points[0].x) * fraction,
    y: points[0].y + (target.y - points[0].y) * fraction,
    z: 0,
  });

  points[1] = along(0.2);
  points[2] = along(0.35);
  if (thumb) {
    points[3] = along(0.67);
    points[4] = { ...target, z: 0 };
  } else {
    // Folded: the last bone turns hard away from the one before it.
    points[3] = along(0.67);
    const ux = (target.x - points[0].x) * 0.3;
    const uy = (target.y - points[0].y) * 0.3;
    points[4] = { x: points[3].x - uy, y: points[3].y + ux, z: 0 };
  }

  return points;
}

/** Rotate a whole hand about its wrist, to check nothing depends on a direction. */
function rotate(points: Landmark[], degrees: number): Landmark[] {
  const radians = (degrees * Math.PI) / 180;
  const cos = Math.cos(radians);
  const sin = Math.sin(radians);
  const origin = points[0];

  return points.map((point) => {
    const dx = point.x - origin.x;
    const dy = point.y - origin.y;
    return {
      x: origin.x + dx * cos - dy * sin,
      y: origin.y + dx * sin + dy * cos,
      z: point.z,
    };
  });
}

const ALL = [true, true, true, true, true];
const NONE = [false, false, false, false, false];

describe("which fingers are extended", () => {
  it("reads an open palm as five", () => {
    expect(fingersExtended(hand({ fingers: ALL }))).toEqual(ALL);
  });

  it("reads a fist as none, including the thumb", () => {
    /* The thumb regression test. A thumb abducts sideways instead of curling,
       so the reach test that works for the other four reports a fist as one
       finger extended, and a fist is the single most common pose anybody will
       make at this feature. */
    expect(fingersExtended(hand({ fingers: NONE }))).toEqual(NONE);
  });

  it("reads a thumbs up as the thumb alone", () => {
    /* The other direction of the same bug: a thumb test that always returned
       false would pass the fist case above and fail here. */
    const fingers = [true, false, false, false, false];
    expect(fingersExtended(hand({ fingers }))).toEqual(fingers);
  });

  it("reads one pointing finger", () => {
    const fingers = [false, true, false, false, false];
    expect(fingersExtended(hand({ fingers }))).toEqual(fingers);
  });

  it("reads two fingers", () => {
    const fingers = [false, true, true, false, false];
    expect(fingersExtended(hand({ fingers }))).toEqual(fingers);
  });

  it("gives the same answer near the lens and far from it", () => {
    const fingers = [false, true, true, false, false];
    expect(fingersExtended(hand({ fingers, scale: 0.4 }))).toEqual(
      fingersExtended(hand({ fingers, scale: 1.8 })),
    );
  });

  it("gives the same answer when the hand is turned", () => {
    const fingers = [false, true, false, false, false];
    const upright = hand({ fingers });
    expect(fingersExtended(rotate(upright, 30))).toEqual(
      fingersExtended(upright),
    );
    expect(fingersExtended(rotate(upright, -75))).toEqual(
      fingersExtended(upright),
    );
  });

  it("returns null on a partial hand rather than a wrong answer", () => {
    expect(fingersExtended([])).toBeNull();
  });

  it("returns null when the hand has no measurable span", () => {
    const collapsed: Landmark[] = Array.from({ length: 21 }, () => ({
      x: 0.5,
      y: 0.5,
      z: 0,
    }));
    expect(fingersExtended(collapsed)).toBeNull();
  });
});

describe("naming the pose", () => {
  it("names a fist", () => {
    expect(classifyGesture(NONE, 0.1)).toBe("fist");
  });

  it("names an open palm", () => {
    expect(classifyGesture(ALL, 1.2)).toBe("open palm");
  });

  it("names pointing", () => {
    expect(classifyGesture([false, true, false, false, false], 0.9)).toBe(
      "pointing",
    );
  });

  it("names two fingers", () => {
    expect(classifyGesture([false, true, true, false, false], 0.9)).toBe(
      "peace",
    );
  });

  it("names a thumbs up", () => {
    expect(classifyGesture([true, false, false, false, false], 0.9)).toBe(
      "thumbs up",
    );
  });

  it("separates a pinch from pointing by the gap, not the fingers", () => {
    /* Both fingers are geometrically straight either way. Only the distance
       between the tips tells the two poses apart. */
    const both = [true, true, false, false, false];
    expect(classifyGesture(both, 0.1)).toBe("pinch");
    expect(classifyGesture(both, 0.9)).not.toBe("pinch");
  });

  it("says nothing rather than guessing at a pose it does not know", () => {
    /* Index and ring out with the middle curled is not in the table. Forcing
       it into the nearest bucket is the failure this null exists to prevent,
       and it would be printed next to a calibrated reading. */
    expect(classifyGesture([false, true, false, true, false], 0.9)).toBeNull();
  });

  it("says nothing when there is no hand to read", () => {
    expect(classifyGesture(null, null)).toBeNull();
  });

  it("does not call a spread hand open without the aperture to back it", () => {
    expect(classifyGesture(ALL, null)).toBeNull();
  });
});

describe("reading one frame", () => {
  it("reports the count, the gesture and whether the hand is open", () => {
    const reading = readHand(hand({ fingers: ALL, spread: 0.25 }));

    expect(reading).not.toBeNull();
    expect(reading?.fingers).toBe(5);
    expect(reading?.open).toBe(true);
    expect(reading?.gesture).toBe("open palm");
  });

  it("counts a closed hand as no fingers", () => {
    const reading = readHand(hand({ fingers: NONE }));

    expect(reading?.fingers).toBe(0);
    expect(reading?.open).toBe(false);
    expect(reading?.gesture).toBe("fist");
  });

  it("returns null where there is no readable hand", () => {
    expect(readHand([])).toBeNull();
  });
});

describe("holding a label steady", () => {
  it("does not publish a label that has only been seen once", () => {
    const smoother = new GestureSmoother();

    expect(smoother.push("fist")).toBeNull();
    expect(smoother.push("fist")).toBeNull();
    expect(smoother.push("fist")).toBe("fist");
  });

  it("holds the last label through a single bad frame", () => {
    /* A genuine transition passes through poses that classify as something
       else on the way. At sixty frames a second that reads as a flickering
       word unless a new label has to earn its place. */
    const smoother = new GestureSmoother();
    smoother.push("fist");
    smoother.push("fist");
    smoother.push("fist");

    expect(smoother.push("peace")).toBe("fist");
  });

  it("promotes a label once it holds", () => {
    const smoother = new GestureSmoother();
    for (let i = 0; i < 3; i += 1) smoother.push("fist");

    smoother.push("peace");
    smoother.push("peace");
    expect(smoother.push("peace")).toBe("peace");
  });

  it("forgets everything when the camera stops", () => {
    const smoother = new GestureSmoother();
    for (let i = 0; i < 3; i += 1) smoother.push("fist");
    smoother.reset();

    expect(smoother.push("peace")).toBeNull();
  });
});
