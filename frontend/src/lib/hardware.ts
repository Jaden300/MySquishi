/**
 * The hardware setup content, as data.
 *
 * Lifted out of the page so the same wiring chain can be drawn as a diagram in
 * two places at two lengths, and so the steps can be enumerated and tested
 * without rendering anything.
 *
 * docs/HARDWARE_CHECKLIST.md is the builder facing version with tiers and
 * failure modes. This is the shipped copy, written for a first time user.
 */

/**
 * Named glyphs the setup steps and figures draw.
 *
 * Kept as ids rather than components so this file stays data. The renderer
 * maps them; see components/figures/Glyph.tsx.
 */
export type GlyphId =
  | "switch"
  | "stack"
  | "wipe"
  | "electrode"
  | "usb"
  | "muscle"
  | "stopwatch"
  | "hand"
  | "wave"
  | "chip"
  | "gauge";

export interface SetupStep {
  title: string;
  body: string;
  glyph: GlyphId;
  /**
   * The output selector is the single setting most likely to be wrong, and
   * everything downstream depends on it, so it opens by default and is drawn
   * as a warning rather than as one step among eight.
   */
  critical?: boolean;
}

export const STEPS: SetupStep[] = [
  {
    title: "Set the output selector to RAW",
    glyph: "switch",
    critical: true,
    body:
      "The MyoWare 2.0 ships set to ENV. This pipeline needs RAW. It is the single " +
      "setting most likely to be wrong, and everything downstream depends on it, so " +
      "check it before anything else.",
  },
  {
    title: "Stack the hardware",
    glyph: "stack",
    body:
      "Snap the sensor onto the three electrodes, connect the Link Shield with the " +
      "3.5 mm cable, and seat the Arduino Shield on the Uno headers. No soldering. " +
      "Push the plug fully in until it clicks.",
  },
  {
    title: "Prepare the skin",
    glyph: "wipe",
    body:
      "Wash the area, wipe it with alcohol, and let it dry completely. A damp site " +
      "bridges the electrodes and flattens the reading.",
  },
  {
    title: "Place the electrodes",
    glyph: "electrode",
    body:
      "Two over the belly of the muscle, 2 cm apart and lined up with the muscle " +
      "fibres. The third goes on nearby bone as a reference. Placement decides " +
      "signal quality more than anything else in the chain.",
  },
  {
    title: "Plug in over USB",
    glyph: "usb",
    body:
      "Use a data cable, not a charge only one. Close the Arduino Serial Monitor if " +
      "it is open: it holds the port exclusively. Nano clones usually need the CH340 " +
      "driver.",
  },
  {
    title: "Pick the muscle",
    glyph: "muscle",
    body:
      "Choose it on the session page, so the app reports the measurements that are " +
      "valid for that muscle and withholds the ones that are not.",
  },
  {
    title: "Calibrate",
    glyph: "stopwatch",
    body:
      "Three maximal efforts, five seconds each, with thirty seconds of rest between. " +
      "The highest becomes your reference, and every later reading is a percentage of " +
      "it.",
  },
  {
    title: "Start a session",
    glyph: "hand",
    body: "Squeeze and hold when Squishi asks. Rest between repetitions.",
  },
];

export interface Failure {
  symptom: string;
  cause: string;
  glyph: GlyphId;
}

export const FAILURES: Failure[] = [
  {
    symptom: "No port listed",
    glyph: "usb",
    cause: "Almost always a charge only USB cable. Try a different one.",
  },
  {
    symptom: "Garbled characters",
    glyph: "chip",
    cause: "Baud mismatch. The sketch runs at 230400.",
  },
  {
    symptom: "Flat trace that never moves",
    glyph: "wave",
    cause: "Dead or dried out electrodes, or the selector is still on ENV.",
  },
  {
    symptom: "Erratic, drifting trace",
    glyph: "electrode",
    cause: "The reference electrode is on muscle instead of bone.",
  },
];

export interface ChainNode {
  label: string;
  glyph: GlyphId;
  /** The full description, carried on hover rather than printed. */
  detail?: string;
}

/**
 * The physical wiring chain, seven links.
 *
 * Drawn on the hardware tab. The labels are short enough to sit inside a node;
 * the detail rides on the node as a tooltip.
 */
export const WIRING_CHAIN: ChainNode[] = [
  { label: "Sensor", glyph: "chip", detail: "MyoWare 2.0 on the muscle, switch set to RAW" },
  { label: "Electrodes", glyph: "electrode", detail: "Two on the muscle belly, one on nearby bone" },
  { label: "Link Shield", glyph: "stack", detail: "Connected over the 3.5 mm cable" },
  { label: "Arduino Shield", glyph: "stack", detail: "Seated on the Uno headers" },
  { label: "Uno", glyph: "chip", detail: "Reading pin A0" },
  { label: "Computer", glyph: "usb", detail: "Over a USB data cable" },
  { label: "MySquishi", glyph: "gauge", detail: "Over serial at 230400 baud" },
];

/**
 * The signal chain, five stages.
 *
 * Drawn on the front page. Where the wiring chain is what you physically
 * connect, this is what happens to the measurement: it is the answer to what
 * the app actually does, which used to be a paragraph nobody read.
 */
export const SIGNAL_CHAIN: ChainNode[] = [
  { label: "Muscle", glyph: "muscle", detail: "Motor units fire as you contract" },
  { label: "Electrodes", glyph: "electrode", detail: "Surface electrodes pick up the voltage across the skin" },
  { label: "Envelope", glyph: "wave", detail: "The raw signal is rectified and smoothed into an effort envelope" },
  { label: "Features", glyph: "chip", detail: "Amplitude and frequency features are computed per repetition" },
  { label: "Percent MVC", glyph: "gauge", detail: "Effort as a share of your own calibrated maximum" },
];
