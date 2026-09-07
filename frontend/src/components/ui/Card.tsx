/**
 * The one surface.
 *
 * Replaces roughly twenty copies of the same border, radius and padding
 * string. ChartFrame and Figure both render their shell through this, so a
 * chart card and a content card cannot drift apart.
 */

import type { ElementType, ReactNode } from "react";

type Tone = "plain" | "raised" | "accent" | "alert";
type Pad = "none" | "sm" | "md" | "lg";

interface CardProps {
  as?: ElementType;
  tone?: Tone;
  /** Applies the brand blob at four percent behind the content. */
  watermark?: boolean | "sm";
  pad?: Pad;
  className?: string;
  children: ReactNode;
  title?: string;
}

const TONE: Record<Tone, string> = {
  plain: "border border-squish-100 bg-mist",
  // docs/DESIGN.md prefers a hairline to a shadow, so raised is deliberately
  // rare: the hero, the live panel, the sticky header.
  raised: "border border-squish-100 bg-mist shadow-soft",
  accent: "border border-squish-300 bg-squish-50",
  alert: "border-2 border-alert bg-mist",
};

const PAD: Record<Pad, string> = {
  none: "",
  sm: "p-4",
  md: "p-5",
  lg: "p-7 sm:p-9",
};

export function Card({
  as: Tag = "section",
  tone = "plain",
  watermark = false,
  pad = "md",
  className = "",
  children,
  title,
}: CardProps) {
  const mark =
    watermark === "sm"
      ? "brand-watermark brand-watermark-sm"
      : watermark
        ? "brand-watermark"
        : "";

  return (
    <Tag
      title={title}
      className={`rounded-panel ${TONE[tone]} ${PAD[pad]} ${mark} ${className}`}
    >
      {children}
    </Tag>
  );
}
