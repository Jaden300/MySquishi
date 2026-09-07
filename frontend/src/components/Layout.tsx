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
    <div className="brand-ground min-h-screen">
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

          <nav className="flex flex-1 items-center justify-end gap-1">
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
