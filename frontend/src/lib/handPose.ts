/**
 * What the hand in front of the camera is doing.
 *
 * Pure geometry over the 21 landmarks MediaPipe reports. Landmarks in, plain
 * values out: nothing here imports the store, opens a camera or holds state,
 * which is what lets the whole file be tested with hand written arrays the way
 * aperture() already is.
 *
 * Everything is measured against the span from the wrist to the base of the
 * middle finger, the same scale aperture() uses, so moving nearer the lens
 * does not change an answer.
 *
 * Nothing here is a clinical measurement. A camera reports where points are,
 * not how hard somebody is squeezing, and docs/CLINICAL.md is explicit that
 * the two must not be dressed up as each other. A finger count is a count.
 *
 * Where this is unreliable, stated plainly because it is better known than
 * discovered during a demo:
 *
 * - The palm facing the lens and the back of the hand facing the lens are
 *   indistinguishable here. MediaPipe reports handedness, but the tracker runs
 *   at numHands 1 and does not carry it through, so a pointing hand reads the
 *   same either way round.
 * - A hand aimed down the optical axis foreshortens, and both tests below
 *   degrade together. The landmarks carry a z, but it is weakly conditioned
 *   and using it would buy noise rather than depth.
 * - Crossed or occluded fingers are inferred by the model rather than seen,
 *   and inferred landmarks can be confidently wrong.
 */

import type { Landmark } from "../store/camera";

const WRIST = 0;
const MIDDLE_BASE = 9;

/** Thumb joints: the two bones whose angle says whether it is straight. */
const THUMB_MCP = 2;
const THUMB_IP = 3;
const THUMB_TIP = 4;
const INDEX_TIP = 8;

/** Base landmark of each of the four fingers that curl along the palm. */
const FINGER_BASES = [5, 9, 13, 17] as const;

/**
 * How much further from the wrist a tip must sit than its own middle knuckle,
 * as a fraction of span, before the finger counts as extended.
 *
 * Zero would be the bare geometric answer and would flicker: a finger resting
 * exactly at the boundary crosses it on camera noise alone. This is the width
 * of the dead zone that stops that.
 */
const EXTEND_MARGIN = 0.12;

/**
 * Cosine of the largest bend at the thumb's interphalangeal joint that still
 * counts as straight. About 32 degrees.
 */
const THUMB_STRAIGHT = 0.85;

/**
 * Thumb to finger distance below which a hand with both of them out reads as a
 * pinch rather than as two extended fingers.
 *
 * Deliberately not OPEN_THRESHOLD. "Not open" is a much weaker claim than
 * "the tips are nearly touching", and reusing one number for both would call
 * every half closed hand a pinch.
 */
const PINCH_APERTURE = 0.35;

export type Gesture =
  | "fist"
  | "open palm"
  | "pointing"
  | "peace"
  | "thumbs up"
  | "pinch";

function distance(a: Landmark, b: Landmark): number {
  return Math.hypot(a.x - b.x, a.y - b.y);
}

/**
 * How far apart the thumb and index finger are, scaled by the size of the hand
 * itself so that moving toward or away from the lens does not change it.
 *
 * Deliberately called aperture and never "grip". This app defines grip against
 * a Jamar dynamometer in kilograms; a camera measures the distance between two
 * points and knows nothing about force. Naming this one grip would be the
 * decorative fake jargon docs/CLINICAL.md exists to forbid.
 *
 * Lives here rather than in handTracker.ts so the dependency runs one way,
 * from the tracker to this file. The tracker re-exports it, because it is the
 * import everything else already reaches for.
 */
export function aperture(landmarks: Landmark[]): number | null {
  const thumb = landmarks[THUMB_TIP];
  const index = landmarks[INDEX_TIP];
  const wrist = landmarks[WRIST];
  const middle = landmarks[MIDDLE_BASE];
  if (!thumb || !index || !wrist || !middle) return null;

  const span = distance(middle, wrist);
  if (span < 1e-6) return null;

  return distance(thumb, index) / span;
}

/** Where an open hand stops and a closed one starts, as a multiple of span. */
const OPEN_THRESHOLD = 0.75;

export function isOpen(value: number): boolean {
  return value >= OPEN_THRESHOLD;
}

/**
 * The size of the hand itself, used to divide out the distance to the lens.
 * Null when the points needed are missing or sit on top of each other.
 */
function handSpan(landmarks: Landmark[]): number | null {
  const wrist = landmarks[WRIST];
  const middle = landmarks[MIDDLE_BASE];
  if (!wrist || !middle) return null;

  const span = distance(wrist, middle);
  return span < 1e-6 ? null : span;
}

/**
 * Whether one of the four curling fingers is extended.
 *
 * A straight finger puts its tip further from the wrist than its own middle
 * knuckle. A curled one folds the tip back toward the palm and the difference
 * goes negative.
 *
 * Both distances are measured from the wrist rather than from the finger's own
 * base, and that is what makes the test survive rotation: they are two radii
 * about a single centre, so turning the whole hand in the image plane moves
 * both by the same amount and leaves the difference alone.
 */
function fingerExtended(
  landmarks: Landmark[],
  base: number,
  span: number,
): boolean | null {
  const wrist = landmarks[WRIST];
  const pip = landmarks[base + 1];
  const tip = landmarks[base + 3];
  if (!wrist || !pip || !tip) return null;

  const reach = distance(tip, wrist) - distance(pip, wrist);
  return reach / span > EXTEND_MARGIN;
}

/**
 * Whether the thumb is extended, which needs different geometry from the rest.
 *
 * The thumb swings sideways across the palm instead of curling along it, so
 * the reach test above reports a closed fist as one finger out: a folded thumb
 * can still leave its tip further from the wrist than its own joint. That is
 * the single most common pose anybody will make at this feature, so it gets
 * its own test rather than a fudged threshold.
 *
 * The question that does hold is whether the thumb is straight. Take its two
 * bones and compare their directions: collinear bones mean an extended thumb
 * whichever way it happens to point, and a folded one bends hard at the joint
 * between them. Being an angle between two vectors that rotate together, this
 * needs neither the span nor a reference direction.
 *
 * The one pose it cannot separate is a straight thumb tucked flat against the
 * palm, which reads as extended. That is the accepted trade: a tucked straight
 * thumb is rare and a thumbs up is not.
 */
function thumbExtended(landmarks: Landmark[]): boolean | null {
  const mcp = landmarks[THUMB_MCP];
  const ip = landmarks[THUMB_IP];
  const tip = landmarks[THUMB_TIP];
  if (!mcp || !ip || !tip) return null;

  const proximal = { x: ip.x - mcp.x, y: ip.y - mcp.y };
  const distal = { x: tip.x - ip.x, y: tip.y - ip.y };

  const proximalLength = Math.hypot(proximal.x, proximal.y);
  const distalLength = Math.hypot(distal.x, distal.y);
  if (proximalLength < 1e-6 || distalLength < 1e-6) return null;

  const dot = proximal.x * distal.x + proximal.y * distal.y;
  return dot / (proximalLength * distalLength) > THUMB_STRAIGHT;
}

/**
 * Which fingers are extended, thumb first, or null on a hand this cannot read.
 *
 * Null rather than a five false array on a partial hand: no hand and a closed
 * fist are different states, and collapsing them would print "fist" at an
 * empty frame.
 */
export function fingersExtended(landmarks: Landmark[]): boolean[] | null {
  const span = handSpan(landmarks);
  if (span === null) return null;

  const thumb = thumbExtended(landmarks);
  if (thumb === null) return null;

  const fingers = [thumb];
  for (const base of FINGER_BASES) {
    const extended = fingerExtended(landmarks, base, span);
    if (extended === null) return null;
    fingers.push(extended);
  }

  return fingers;
}

/**
 * A name for the pose, or null when it is not one of the poses below.
 *
 * The null is the point of this function rather than a gap in it. This sits
 * beside a calibrated force reading, where a label that is confidently wrong
 * costs more than no label at all, so anything outside the table falls through
 * to null and the panel says so.
 *
 * Pinch is tested first because in a pinch the thumb and index are both
 * geometrically straight, and the only thing separating it from pointing is
 * how far apart the tips are. That distance is exactly what aperture()
 * measures, which is the one place the existing helper earns its keep here.
 */
export function classifyGesture(
  extended: boolean[] | null,
  apertureValue: number | null,
): Gesture | null {
  if (!extended || extended.length !== 5) return null;

  const [thumb, index, middle, ring, little] = extended;
  const count = extended.filter(Boolean).length;

  if (
    thumb &&
    index &&
    apertureValue !== null &&
    apertureValue < PINCH_APERTURE
  ) {
    return "pinch";
  }

  if (count === 0) return "fist";

  if (count === 5) {
    return apertureValue !== null && isOpen(apertureValue) ? "open palm" : null;
  }

  if (index && !thumb && !middle && !ring && !little) return "pointing";
  if (index && middle && !thumb && !ring && !little) return "peace";
  if (thumb && !index && !middle && !ring && !little) return "thumbs up";

  return null;
}

/** Everything the panel shows, derived from one frame of landmarks. */
export interface HandReading {
  gesture: Gesture | null;
  fingers: number;
  open: boolean;
}

/**
 * Read one frame. Null when there is no hand, or none this can measure.
 *
 * The single entry point the tracker calls, so the order the pieces run in
 * lives here rather than being repeated at the call site.
 */
export function readHand(landmarks: Landmark[]): HandReading | null {
  const extended = fingersExtended(landmarks);
  if (!extended) return null;

  const apertureValue = aperture(landmarks);

  return {
    gesture: classifyGesture(extended, apertureValue),
    fingers: extended.filter(Boolean).length,
    open: apertureValue !== null && isOpen(apertureValue),
  };
}

/**
 * Holds a label steady across a frame or two of disagreement.
 *
 * Per finger dead zones kill most of the flicker, but a genuine transition
 * still passes through poses that classify as something else on the way, and
 * at sixty frames a second a two frame wobble is visible as a flickering word.
 * A new label has to win three of the last five frames before it is published,
 * which costs about fifty milliseconds and is not perceptible.
 *
 * A class rather than a function because the history is state, and it is owned
 * by the tracker: the smoothed gesture is a property of the stream, so two
 * components keeping their own buffers would disagree about the current pose.
 */
export class GestureSmoother {
  private readonly history: (Gesture | null)[] = [];
  private published: Gesture | null = null;

  private static readonly WINDOW = 5;
  private static readonly AGREEMENT = 3;

  /** Feed one frame's raw classification, get the label worth showing. */
  push(raw: Gesture | null): Gesture | null {
    this.history.push(raw);
    if (this.history.length > GestureSmoother.WINDOW) this.history.shift();

    const agreeing = this.history.filter((entry) => entry === raw).length;
    if (agreeing >= GestureSmoother.AGREEMENT) this.published = raw;

    return this.published;
  }

  reset(): void {
    this.history.length = 0;
    this.published = null;
  }
}
