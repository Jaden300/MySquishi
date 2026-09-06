/**
 * The app shell: navigation, the standing disclaimer, and an error boundary.
 */

import { Component, type ReactNode } from "react";
import { Link, NavLink, Outlet, useRouteError } from "react-router-dom";

import { NotAMedicalDevice } from "./Honesty";

const NAV = [
  { to: "/session", label: "Session" },
  { to: "/progress", label: "Progress" },
  { to: "/insights", label: "Insights" },
  { to: "/clinician", label: "Clinician" },
  { to: "/connect", label: "Connect" },
  { to: "/settings", label: "Settings" },
  { to: "/about", label: "About" },
];

export function Layout() {
  return (
    <div className="min-h-screen bg-squish-50">
      <header className="border-b border-squish-100 bg-mist">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-6 gap-y-2 px-4 py-3 sm:px-6">
          <Link to="/" className="text-lg text-squish-700">
            MySquishi
          </Link>
          <nav className="flex flex-wrap gap-x-4 gap-y-1 text-sm">
            {NAV.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) =>
                  isActive
                    ? "text-squish-700 underline underline-offset-4"
                    : "text-ink/70 hover:text-squish-700"
                }
              >
                {item.label}
              </NavLink>
            ))}
          </nav>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-4 py-8 sm:px-6">
        <Outlet />
      </main>

      <footer className="mx-auto max-w-6xl px-4 pb-10 sm:px-6">
        <NotAMedicalDevice />
      </footer>
    </div>
  );
}

/** Route level error boundary, so one broken page does not blank the app. */
export function RouteError() {
  const error = useRouteError() as { message?: string; statusText?: string };

  return (
    <div className="mx-auto max-w-2xl px-6 py-16 text-center">
      <h1 className="text-xl text-squish-700">Something went wrong here</h1>
      <p className="mt-2 text-sm text-ink/70">
        {error?.message ?? error?.statusText ?? "This page could not be shown."}
      </p>
      <Link
        to="/"
        className="mt-6 inline-block rounded-card border border-squish-300 px-4 py-2 text-sm text-squish-700 hover:bg-squish-50"
      >
        Back to the start
      </Link>
    </div>
  );
}

interface BoundaryState {
  error: Error | null;
}

/** Catches render errors inside a page, below the router's own boundary. */
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
        <div role="alert" className="rounded-panel border border-alert bg-mist p-6">
          <p className="text-sm text-ink">
            This section could not be shown. The rest of the page still works.
          </p>
        </div>
      );
    }
    return this.props.children;
  }
}
