/**
 * Squishi's pose library.
 *
 * Transcribed from the pose sheet artboard. Every pose shares one body path
 * and differs only in its arms, its face, and an optional squash transform,
 * which is what keeps the character recognisably the same across all twenty.
 *
 * Data rather than components, so poses can be enumerated, tested and picked
 * by id without rendering anything.
 */

/** The shared body silhouette, in the 200x200 pose viewBox. */
export const BODY_PATH =
  "M100,53 C142,53 162,77 162,103 C162,132 138,148 100,148 C62,148 38,132 38,103 C38,77 58,53 100,53 Z";

/** Stroke weights the artboard uses. Arms are heavier than the face. */
export const ARM_STROKE = 11;
export const FACE_STROKE = 5.5;

/** A dot eye. */
interface EyeDot {
  kind: "dot";
  cx: number;
  cy: number;
  r?: number;
}

/** An arced eye, used for closed, happy or exhausted expressions. */
interface EyeArc {
  kind: "arc";
  d: string;
}

export type Eye = EyeDot | EyeArc;

/** A stroked mouth curve. */
interface MouthStroke {
  kind: "stroke";
  d: string;
}

/** A filled mouth, for open or grinning shapes. */
interface MouthFill {
  kind: "fill";
  d: string;
}

/** An open O mouth. */
interface MouthEllipse {
  kind: "ellipse";
  cx: number;
  cy: number;
  rx: number;
  ry: number;
}

export type Mouth = MouthStroke | MouthFill | MouthEllipse;

export interface Pose {
  /** Stable identifier, used by the pose prop and by tests. */
  id: PoseId;
  /** Human readable name, matching the artboard caption. */
  label: string;
  /** Optional SVG transform applied to the body only, for squash and stretch. */
  bodyTransform?: string;
  /** Two stroked arm paths. */
  arms: [string, string];
  /** Eyes, usually a pair but a wink has one of each kind. */
  eyes: Eye[];
  mouth: Mouth;
  /** Sweat or effort dots, in the accent colour. */
  accents?: { cx: number; cy: number; r: number }[];
}

export type PoseId =
  | "idle"
  | "waving"
  | "cheering"
  | "flexing"
  | "midSqueeze"
  | "compressed"
  | "springingBack"
  | "sleeping"
  | "thumbsUp"
  | "thinking"
  | "confused"
  | "disappointed"
  | "exhausted"
  | "encouraging"
  | "celebrating"
  | "presenting"
  | "explaining"
  | "stretching"
  | "resting"
  | "winking";

/** A pair of dot eyes at the default size. */
function dots(
  leftX: number,
  rightX: number,
  y: number,
  r = 7,
): Eye[] {
  return [
    { kind: "dot", cx: leftX, cy: y, r },
    { kind: "dot", cx: rightX, cy: y, r },
  ];
}

export const POSES: Record<PoseId, Pose> = {
  idle: {
    id: "idle",
    label: "Idle",
    arms: ["M68,122 Q48,132 38,146", "M132,122 Q152,132 162,146"],
    eyes: dots(85, 115, 98),
    mouth: { kind: "stroke", d: "M89,118 Q100,128 111,118" },
  },

  waving: {
    id: "waving",
    label: "Waving",
    arms: ["M68,124 Q50,134 40,148", "M132,116 Q158,102 162,74"],
    eyes: dots(85, 115, 98),
    mouth: { kind: "stroke", d: "M88,117 Q100,130 112,117" },
  },

  cheering: {
    id: "cheering",
    label: "Cheering",
    arms: ["M70,116 Q46,96 40,66", "M130,116 Q154,96 160,66"],
    eyes: dots(85, 115, 98),
    mouth: { kind: "fill", d: "M86,115 Q100,133 114,115 Z" },
  },

  flexing: {
    id: "flexing",
    label: "Flexing",
    arms: ["M70,118 Q46,124 44,146", "M132,120 L168,106 L158,74"],
    eyes: dots(85, 115, 98),
    mouth: { kind: "stroke", d: "M89,118 Q100,127 111,116" },
  },

  midSqueeze: {
    id: "midSqueeze",
    label: "Mid-squeeze",
    bodyTransform: "translate(100,105) scale(1.07,0.93) translate(-100,-105)",
    arms: ["M72,118 Q36,110 26,84", "M128,118 Q164,110 174,84"],
    eyes: [
      { kind: "arc", d: "M77,95 L93,101" },
      { kind: "arc", d: "M107,101 L123,95" },
    ],
    mouth: { kind: "stroke", d: "M88,120 L112,120" },
  },

  compressed: {
    id: "compressed",
    label: "Compressed",
    bodyTransform: "translate(100,105) scale(1.34,0.7) translate(-100,-105)",
    arms: ["M70,118 Q42,128 16,132", "M130,118 Q158,128 184,132"],
    eyes: [
      { kind: "arc", d: "M75,94 L93,100" },
      { kind: "arc", d: "M107,100 L125,94" },
    ],
    mouth: { kind: "stroke", d: "M84,116 Q100,108 116,116" },
  },

  springingBack: {
    id: "springingBack",
    label: "Springing back",
    bodyTransform: "translate(100,105) scale(0.9,1.12) translate(-100,-105)",
    arms: ["M70,112 Q46,96 24,86", "M130,112 Q154,96 176,86"],
    eyes: dots(86, 114, 98),
    mouth: { kind: "stroke", d: "M88,117 Q100,131 112,117" },
  },

  sleeping: {
    id: "sleeping",
    label: "Sleeping",
    bodyTransform: "translate(100,105) scale(1.05,0.95) translate(-100,-105)",
    arms: ["M70,124 Q52,138 46,152", "M130,124 Q148,138 154,152"],
    eyes: [
      { kind: "arc", d: "M77,96 Q85,104 93,96" },
      { kind: "arc", d: "M107,96 Q115,104 123,96" },
    ],
    mouth: { kind: "stroke", d: "M92,120 Q100,126 108,120" },
  },

  thumbsUp: {
    id: "thumbsUp",
    label: "Thumbs up",
    arms: ["M68,124 Q48,134 38,148", "M132,120 L164,106 L162,80"],
    eyes: dots(85, 115, 98),
    mouth: { kind: "stroke", d: "M89,118 Q100,128 111,118" },
  },

  thinking: {
    id: "thinking",
    label: "Thinking",
    bodyTransform: "rotate(-7 100 105)",
    arms: ["M68,124 Q40,138 32,154", "M136,122 Q172,142 118,148"],
    eyes: dots(85, 115, 98),
    mouth: { kind: "stroke", d: "M90,122 Q100,117 110,122" },
  },

  confused: {
    id: "confused",
    label: "Confused",
    bodyTransform: "rotate(12 100 105)",
    arms: ["M68,126 Q48,138 36,150", "M130,118 Q162,126 180,108"],
    eyes: [
      { kind: "dot", cx: 86, cy: 97, r: 7 },
      { kind: "dot", cx: 116, cy: 100, r: 7 },
    ],
    mouth: { kind: "stroke", d: "M88,120 Q96,113 100,120 Q104,127 112,119" },
  },

  disappointed: {
    id: "disappointed",
    label: "Disappointed",
    bodyTransform:
      "translate(0,7) translate(100,105) scale(1.07,0.9) translate(-100,-105)",
    arms: ["M68,128 Q50,144 46,160", "M132,128 Q150,144 154,160"],
    eyes: dots(85, 115, 99),
    mouth: { kind: "stroke", d: "M89,126 Q100,116 111,126" },
  },

  exhausted: {
    id: "exhausted",
    label: "Exhausted",
    bodyTransform:
      "rotate(9 100 105) translate(100,105) scale(1.06,0.94) translate(-100,-105)",
    arms: ["M70,124 Q38,142 32,166", "M130,124 Q162,142 168,166"],
    eyes: [
      { kind: "arc", d: "M77,102 Q85,94 93,102" },
      { kind: "arc", d: "M107,102 Q115,94 123,102" },
    ],
    mouth: { kind: "ellipse", cx: 100, cy: 126, rx: 11, ry: 9 },
    accents: [
      { cx: 46, cy: 70, r: 6.5 },
      { cx: 156, cy: 62, r: 6.5 },
    ],
  },

  encouraging: {
    id: "encouraging",
    label: "Encouraging",
    arms: ["M70,116 L32,98 L46,64", "M130,116 L168,98 L154,64"],
    eyes: dots(85, 115, 98),
    mouth: { kind: "stroke", d: "M87,116 Q100,131 113,116" },
  },

  celebrating: {
    id: "celebrating",
    label: "Celebrating",
    bodyTransform: "translate(100,105) scale(1,1.04) translate(-100,-105)",
    arms: ["M70,114 L20,90", "M130,114 L180,90"],
    eyes: dots(85, 115, 98),
    mouth: { kind: "fill", d: "M85,115 Q100,135 115,115 Z" },
  },

  presenting: {
    id: "presenting",
    label: "Presenting",
    arms: ["M68,124 Q42,136 30,150", "M130,116 L172,116"],
    eyes: dots(89, 119, 98),
    mouth: { kind: "stroke", d: "M92,118 Q103,128 114,118" },
  },

  explaining: {
    id: "explaining",
    label: "Explaining",
    arms: ["M68,124 Q48,134 38,148", "M132,114 L172,64"],
    eyes: dots(86, 116, 98),
    mouth: { kind: "ellipse", cx: 100, cy: 120, rx: 6.5, ry: 6 },
  },

  stretching: {
    id: "stretching",
    label: "Stretching",
    bodyTransform:
      "translate(0,-4) translate(100,105) scale(0.92,1.14) translate(-100,-105)",
    arms: ["M72,110 Q30,52 88,26", "M128,110 Q170,52 112,26"],
    eyes: [
      { kind: "arc", d: "M77,96 Q85,104 93,96" },
      { kind: "arc", d: "M107,96 Q115,104 123,96" },
    ],
    mouth: { kind: "stroke", d: "M90,118 Q100,127 110,118" },
  },

  resting: {
    id: "resting",
    label: "Resting",
    bodyTransform:
      "translate(0,8) translate(100,105) scale(1.1,0.9) translate(-100,-105)",
    arms: ["M70,130 Q40,142 32,160", "M130,130 Q160,142 168,160"],
    eyes: dots(85, 115, 99),
    mouth: { kind: "stroke", d: "M90,122 Q100,130 110,122" },
  },

  winking: {
    id: "winking",
    label: "Winking",
    arms: ["M68,124 Q48,132 38,146", "M130,118 Q164,116 174,98"],
    eyes: [
      { kind: "dot", cx: 85, cy: 98, r: 7 },
      { kind: "arc", d: "M107,101 Q115,93 123,101" },
    ],
    mouth: { kind: "stroke", d: "M89,119 Q101,128 112,116" },
  },
};

/** Every pose id, in artboard order. Useful for a gallery or a test sweep. */
export const POSE_IDS = Object.keys(POSES) as PoseId[];
