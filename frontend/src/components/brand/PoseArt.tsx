/**
 * Renders one pose from the library into the 200x200 pose viewBox.
 *
 * Shared by the animated mascot and by the static brand placements, so the
 * character is drawn in exactly one place and cannot drift between them.
 */

import {
  ARM_STROKE,
  BODY_PATH,
  FACE_STROKE,
  POSES,
  type Eye,
  type Mouth,
  type PoseId,
} from "./poses";

interface PoseArtProps {
  pose: PoseId;
  /**
   * Overrides the pose's own body transform. The animated mascot passes its
   * live squash here so the two are never multiplied together.
   */
  bodyTransform?: string | null;
  /**
   * Takes the arms from a different pose than the face.
   *
   * The live mascot squashes the whole character with a spring. Poses authored
   * at an extreme, compressed above all, already carry arms flung out flat, and
   * squashing those again flattens them into stubs. So the animated branch
   * keeps the expressive face and borrows idle's neutral arms, which deform
   * legibly under any amount of squash.
   */
  armsFrom?: PoseId;
  /** Set for decorative placements that should not carry the arms. */
  bodyOnly?: boolean;
}

export function PoseArt({
  pose,
  bodyTransform,
  armsFrom,
  bodyOnly = false,
}: PoseArtProps) {
  const art = POSES[pose];
  const arms = POSES[armsFrom ?? pose].arms;
  const transform =
    bodyTransform === null ? undefined : (bodyTransform ?? art.bodyTransform);

  return (
    <>
      <g transform={transform}>
        <path d={BODY_PATH} fill="var(--squishi-body)" />
      </g>

      {bodyOnly ? null : (
        <g
          fill="none"
          stroke="var(--squishi-body)"
          strokeWidth={ARM_STROKE}
          strokeLinecap="round"
        >
          <path d={arms[0]} />
          <path d={arms[1]} />
        </g>
      )}

      {art.eyes.map((eye, i) => (
        <EyeShape key={i} eye={eye} />
      ))}

      <MouthShape mouth={art.mouth} />

      {art.accents?.map((accent, i) => (
        <circle
          key={i}
          cx={accent.cx}
          cy={accent.cy}
          r={accent.r}
          fill="var(--squishi-accent)"
        />
      ))}
    </>
  );
}

function EyeShape({ eye }: { eye: Eye }) {
  if (eye.kind === "dot") {
    return (
      <circle
        cx={eye.cx}
        cy={eye.cy}
        r={eye.r ?? 7}
        fill="var(--squishi-face)"
      />
    );
  }

  return (
    <path
      d={eye.d}
      fill="none"
      stroke="var(--squishi-face)"
      strokeWidth={FACE_STROKE}
      strokeLinecap="round"
    />
  );
}

function MouthShape({ mouth }: { mouth: Mouth }) {
  if (mouth.kind === "ellipse") {
    return (
      <ellipse
        cx={mouth.cx}
        cy={mouth.cy}
        rx={mouth.rx}
        ry={mouth.ry}
        fill="var(--squishi-face)"
      />
    );
  }

  if (mouth.kind === "fill") {
    return (
      <path
        d={mouth.d}
        fill="var(--squishi-face)"
        stroke="var(--squishi-face)"
        strokeWidth={FACE_STROKE}
        strokeLinejoin="round"
      />
    );
  }

  return (
    <path
      d={mouth.d}
      fill="none"
      stroke="var(--squishi-face)"
      strokeWidth={FACE_STROKE}
      strokeLinecap="round"
    />
  );
}
