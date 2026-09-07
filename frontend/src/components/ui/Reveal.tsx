/**
 * Fades and lifts its children in the first time they are scrolled to.
 *
 * Once only: the observer disconnects after firing, so scrolling back up does
 * not replay the animation, which is the difference between a page that feels
 * alive and one that feels twitchy.
 *
 * Renders children with no wrapper behaviour at all under reduced motion.
 */

import { useEffect, useRef, useState, type ReactNode } from "react";
import { useReducedMotion } from "framer-motion";

interface RevealProps {
  children: ReactNode;
  /** 0 to 6, mapping onto the rise-delay utilities in index.css. */
  delay?: 0 | 1 | 2 | 3 | 4 | 5 | 6;
  className?: string;
}

export function Reveal({ children, delay = 0, className = "" }: RevealProps) {
  const ref = useRef<HTMLDivElement | null>(null);
  const reduced = useReducedMotion();
  // No IntersectionObserver in the test environment, and no reason to hide
  // content from a browser that lacks it either, so those start shown rather
  // than waiting for an observation that will never arrive.
  const [shown, setShown] = useState(
    () => typeof IntersectionObserver === "undefined",
  );

  useEffect(() => {
    const node = ref.current;
    if (!node) return;
    if (typeof IntersectionObserver === "undefined") return;

    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) {
          setShown(true);
          observer.disconnect();
        }
      },
      { rootMargin: "0px 0px -12% 0px" },
    );

    observer.observe(node);
    return () => observer.disconnect();
  }, []);

  /*
    Reduced motion returns the children untouched rather than starting them
    transparent. The global reduced motion block zeroes animation duration, so
    an element parked at opacity 0 waiting for a keyframe to raise it would
    simply never appear.
  */
  if (reduced) {
    return <div className={className}>{children}</div>;
  }

  return (
    <div
      ref={ref}
      className={`${shown ? `rise ${delay ? `rise-delay-${delay}` : ""}` : "opacity-0"} ${className}`}
    >
      {children}
    </div>
  );
}
