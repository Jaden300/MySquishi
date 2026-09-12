import { useEffect, useState } from "react";

/**
 * True below Tailwind's sm breakpoint.
 *
 * Almost everything that has to adapt on a phone can do it in CSS, and should:
 * a responsive class costs nothing and never disagrees with what is painted.
 * This exists for the cases that cannot, which in practice means Recharts
 * props. A chart's margins and label placement are JavaScript values passed
 * into an SVG, so no media query reaches them.
 *
 * Matches `sm` in tailwind.config.js. If that moves, this moves with it.
 */
const NARROW = "(max-width: 639px)";

export function useNarrow(): boolean {
  const [narrow, setNarrow] = useState(() => {
    if (typeof window === "undefined" || !window.matchMedia) return false;
    return window.matchMedia(NARROW).matches;
  });

  useEffect(() => {
    if (typeof window === "undefined" || !window.matchMedia) return;

    const query = window.matchMedia(NARROW);
    const onChange = (event: MediaQueryListEvent) => setNarrow(event.matches);

    setNarrow(query.matches);
    query.addEventListener("change", onChange);
    return () => query.removeEventListener("change", onChange);
  }, []);

  return narrow;
}
