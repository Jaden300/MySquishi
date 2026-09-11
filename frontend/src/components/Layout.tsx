/**
 * The app shell: navigation, the standing disclaimer, and an error boundary.
 *
 * Four links. The app used to carry seven, which meant a menu on a phone and
 * a decision every time you wanted to get anywhere. Four fit in one row at
 * 390px once the wordmark drops to its mark, so there is no hamburger and no
 * hidden navigation anywhere in the product.
 */

import { Component, useEffect, useRef, useState, type ReactNode } from "react";
import {
  Link,
  NavLink,
  Outlet,
  useLocation,
  useRouteError,
} from "react-router-dom";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";

import { NotAMedicalDevice } from "./Honesty";
import { SquishiMark } from "./brand/SquishiMark";
import { PoseSpot } from "./brand/PoseSpot";
import { BODY_PATH } from "./brand/poses";
import { useDemoStore } from "../store/demo";
import { Wordmark } from "./brand/Wordmark";
import { Button } from "./ui/Button";

const NAV = [
  { to: "/", label: "Home", end: true },
  { to: "/train", label: "Train", end: false },
  { to: "/progress", label: "Progress", end: false },
  { to: "/lab", label: "Lab", end: false },
];

export function Layout() {
  const location = useLocation();
  const reduced = useReducedMotion();
  const stuck = useStuckHeader();

  return (
    <div className="brand-ground relative min-h-screen">
      <BackgroundBlobs />

      {/*
        A sentinel rather than a scroll listener: the header only needs to know
        whether the page has left the top, and an observer answers that without
        running a handler on every frame of every scroll.
      */}
      <div aria-hidden="true" data-header-sentinel className="h-0" />

      <header
        className={`sticky top-0 z-30 border-b transition-colors duration-200 ${
          stuck
            ? "border-squish-100 bg-mist/85 shadow-soft backdrop-blur-md"
            : "border-transparent bg-mist/60 backdrop-blur"
        }`}
      >
        <div className="mx-auto flex max-w-6xl items-center gap-3 px-4 py-3 sm:gap-6 sm:px-6">
          <Link to="/" className="shrink-0" aria-label="MySquishi home">
            {/* The lettering is dropped on the narrowest screens so the four
                navigation links keep their row. */}
            <span className="hidden sm:inline">
              <Wordmark size={22} />
            </span>
            <span className="sm:hidden">
              <SquishiMark size={30} title="MySquishi" />
            </span>
          </Link>

          <div className="flex flex-1 justify-end">
            <DemoToggle />
          </div>

          <nav className="flex items-center gap-1">
            {NAV.map((item) => (
              <NavLink key={item.to} to={item.to} end={item.end}>
                {({ isActive }) => (
                  <span
                    className={`relative inline-flex rounded-pill px-3 py-2 text-label transition-colors sm:px-4 ${
                      isActive ? "text-mist" : "text-ink/70 hover:text-squish-700"
                    }`}
                  >
                    {isActive ? (
                      <motion.span
                        layoutId="nav-indicator"
                        className="absolute inset-0 rounded-pill bg-squish-500"
                        transition={
                          reduced
                            ? { duration: 0 }
                            : { type: "spring", stiffness: 420, damping: 34 }
                        }
                      />
                    ) : null}
                    <span className="relative">{item.label}</span>
                  </span>
                )}
              </NavLink>
            ))}
          </nav>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-4 py-10 sm:px-6">
        {/*
          Keyed on the path so a route change crossfades. Deliberately short:
          long enough to register as a transition, short enough that it never
          reads as waiting for something.
        */}
        <AnimatePresence mode="wait" initial={false}>
          <motion.div
            key={location.pathname}
            initial={reduced ? false : { opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={reduced ? { opacity: 1 } : { opacity: 0, y: -6 }}
            transition={reduced ? { duration: 0 } : { duration: 0.18 }}
          >
            <Outlet />
          </motion.div>
        </AnimatePresence>
      </main>

      <footer className="mx-auto flex max-w-6xl items-center gap-3 px-4 pb-12 sm:px-6">
        <SquishiMark size={22} className="shrink-0 opacity-40" />
        <NotAMedicalDevice />
      </footer>
    </div>
  );
}

/**
 * The demo data control.
 *
 * Global state, so it sits in the shell rather than on a page. Deliberately
 * borrows SyntheticBadge's shape and its diamond so the two read as one
 * system: that component still marks individual records, and this one marks
 * the mode. Both stay, because a mixed list needs the per record badge even
 * while demo mode is on.
 *
 * The label carries a shape as well as a colour, which the accessibility
 * floor requires, and collapses to the diamond alone under sm where the four
 * navigation links already fill the row at 390px.
 */
function DemoToggle() {
  const demoMode = useDemoStore((s) => s.demoMode);
  const setDemoMode = useDemoStore((s) => s.setDemoMode);

  if (!demoMode) {
    return (
      <button
        type="button"
        onClick={() => setDemoMode(true)}
        className="rounded-pill px-3 py-1.5 text-label text-ink/60 transition-colors hover:text-squish-700"
        title="Show the seeded demo history again."
      >
        <span aria-hidden="true" className="sm:hidden">
          ◇
        </span>
        <span className="hidden sm:inline">Demo data</span>
        <span className="sr-only">Turn demo data on</span>
      </button>
    );
  }

  return (
    <span
      className="inline-flex items-center gap-2 rounded-pill border border-squish-300 bg-squish-100 py-1 pl-3 pr-1 text-label text-squish-700"
      title="You are looking at seeded demonstration data, not a real person's history."
    >
      <span aria-hidden="true">◇</span>
      <span className="hidden sm:inline">Demo data</span>

      <button
        type="button"
        onClick={() => setDemoMode(false)}
        className="rounded-pill bg-mist px-2.5 py-1 text-label text-squish-700 transition-colors hover:bg-squish-50"
      >
        Exit
        <span className="sr-only"> demo data</span>
      </button>
    </span>
  );
}

/**
 * The scattered mark field.
 *
 * Deterministic placements, never Math.random(): the arrangement must not
 * reshuffle on every render, and a fixed table can be reasoned about and
 * tested. Positions are in vw and vh so the field covers the viewport at
 * 390px without crowding the narrow column.
 *
 * Opacity runs 7 to 10 percent. Below that the field was invisible against
 * the near white ground and the page still read as flat, which was the whole
 * complaint. Still decoration: the cards these sit behind are opaque, so no
 * text is ever read against a mark.
 */
const SCATTER = Object.freeze([
  { left: 4, top: 7, size: 74, rotate: -14, opacity: 0.1, drift: "bob" },
  { left: 88, top: 4, size: 52, rotate: 18, opacity: 0.085, drift: "" },
  { left: 27, top: 15, size: 40, rotate: 8, opacity: 0.075, drift: "" },
  { left: 68, top: 19, size: 96, rotate: -21, opacity: 0.09, drift: "drift" },
  { left: 12, top: 31, size: 58, rotate: 12, opacity: 0.085, drift: "" },
  { left: 93, top: 36, size: 68, rotate: -8, opacity: 0.1, drift: "bob" },
  { left: 46, top: 42, size: 44, rotate: 22, opacity: 0.07, drift: "" },
  { left: 6, top: 54, size: 112, rotate: -17, opacity: 0.09, drift: "drift-slow" },
  { left: 77, top: 58, size: 50, rotate: 6, opacity: 0.085, drift: "" },
  { left: 33, top: 67, size: 82, rotate: -11, opacity: 0.1, drift: "bob" },
  { left: 90, top: 74, size: 62, rotate: 15, opacity: 0.075, drift: "" },
  { left: 16, top: 82, size: 46, rotate: -19, opacity: 0.085, drift: "" },
  { left: 58, top: 88, size: 128, rotate: 10, opacity: 0.09, drift: "drift" },
  { left: 81, top: 94, size: 56, rotate: -6, opacity: 0.07, drift: "" },
]);

/**
 * The soft shapes and the scattered marks behind the app.
 *
 * The complaint that started this revamp was that the site felt static. Most
 * of the answer is elsewhere, in transitions and reveals, but a page of
 * charts sitting on a flat colour reads as dead even when its contents move.
 * Three blurred blobs on a wash turned out to be close to flat anyway, so the
 * mark field carries the texture and the blobs carry the movement.
 *
 * Everything here is fixed, behind everything else, and hidden from assistive
 * technology. The CSS animations stop under reduced motion through the global
 * block in index.css.
 */
function BackgroundBlobs() {
  return (
    <div
      aria-hidden="true"
      className="pointer-events-none fixed inset-0 -z-10 overflow-hidden"
    >
      <span className="drift absolute -left-24 top-16 block h-72 w-72 rounded-full bg-squish-300/25 blur-3xl" />
      <span className="drift-slow absolute -right-20 top-1/3 block h-96 w-96 rounded-full bg-squish-100/40 blur-3xl" />
      <span className="drift absolute bottom-0 left-1/3 block h-80 w-80 rounded-full bg-squish-500/10 blur-3xl [animation-delay:-8s]" />

      {SCATTER.map((mark, i) => (
        <svg
          key={i}
          viewBox="0 0 200 200"
          width={mark.size}
          height={mark.size}
          className={`absolute block ${mark.drift}`}
          style={{
            left: `${mark.left}vw`,
            top: `${mark.top}vh`,
            opacity: mark.opacity,
            transform: `rotate(${mark.rotate}deg)`,
            /* Staggered so the field never pulses in unison. */
            animationDelay: `${-(i * 1.7).toFixed(1)}s`,
          }}
        >
          {/* The silhouette straight from the pose library, so the scatter
              cannot drift out of step with the character the way a second
              hand copy of the path would. */}
          <path d={BODY_PATH} fill="var(--squish-700)" />
        </svg>
      ))}
    </div>
  );
}

/** True once the page has scrolled away from the top. */
function useStuckHeader(): boolean {
  const [stuck, setStuck] = useState(false);
  const observed = useRef(false);

  useEffect(() => {
    const sentinel = document.querySelector("[data-header-sentinel]");
    if (!sentinel || typeof IntersectionObserver === "undefined") return;
    observed.current = true;

    const observer = new IntersectionObserver(
      ([entry]) => setStuck(!entry.isIntersecting),
      { threshold: 1 },
    );
    observer.observe(sentinel);
    return () => observer.disconnect();
  }, []);

  return stuck;
}

/** Route level error boundary, so one broken page does not blank the app. */
export function RouteError() {
  const error = useRouteError() as { message?: string; statusText?: string };

  return (
    <div className="mx-auto flex max-w-2xl flex-col items-center gap-6 px-6 py-20 text-center">
      <PoseSpot pose="confused" size={140} label="Squishi looks puzzled" />
      <h1 className="text-h1 text-squish-700">Something went wrong here</h1>
      <p className="text-body text-ink/70">
        {error?.message ?? error?.statusText ?? "This page could not be shown."}
      </p>
      <Button to="/" variant="secondary">
        Back to the start
      </Button>
    </div>
  );
}

interface BoundaryState {
  error: Error | null;
}

/**
 * Catches render errors inside a page, below the router's own boundary.
 *
 * Wrapped around each tab panel, so one model card that cannot render leaves
 * the rest of the page working rather than blanking the route.
 */
export class ErrorBoundary extends Component<
  { children: ReactNode },
  BoundaryState
> {
  state: BoundaryState = { error: null };

  static getDerivedStateFromError(error: Error): BoundaryState {
    return { error };
  }

  render() {
    if (this.state.error) {
      return (
        <div
          role="alert"
          className="flex items-center gap-4 rounded-panel border border-alert bg-mist p-6"
        >
          <PoseSpot pose="confused" size={56} />
          <p className="text-body text-ink">
            This section could not be shown. The rest of the page still works.
          </p>
        </div>
      );
    }
    return this.props.children;
  }
}
