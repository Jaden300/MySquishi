/**
 * The landing page.
 *
 * Squishi is driven here from a preview stream rather than the live store, so
 * the character is doing its one memorable thing before the visitor has
 * connected anything.
 */

import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { SquishiMascot } from "../components/SquishiMascot";

export function LandingPage() {
  const preview = usePreviewContraction();

  return (
    <div className="mx-auto flex max-w-3xl flex-col items-center gap-8 py-10 text-center">
      <SquishiMascot value={preview} size={200} />

      <div className="flex flex-col gap-3">
        <h1 className="text-3xl text-squish-700">Grip strength, made visible</h1>
        <p className="text-ink/70">
          MySquishi turns the electrical activity of your forearm into
          something you can see, so you can tell whether today went well
          without guessing.
        </p>
      </div>

      <div className="flex flex-wrap justify-center gap-3">
        <Link
          to="/onboarding"
          className="rounded-card bg-squish-500 px-5 py-2.5 text-mist hover:bg-squish-700"
        >
          Get started
        </Link>
        <Link
          to="/session"
          className="rounded-card border border-squish-300 px-5 py-2.5 text-squish-700 hover:bg-squish-50"
        >
          Try a session
        </Link>
      </div>

      <p className="text-sm text-ink/60">
        Works with no hardware attached. The simulator is a permanent feature,
        not a fallback.
      </p>

    </div>
  );
}

/** A gentle looping contraction, so Squishi is alive on the landing page. */
function usePreviewContraction(): number {
  const [value, setValue] = useState(0);

  useEffect(() => {
    const started = Date.now();
    const timer = window.setInterval(() => {
      const t = ((Date.now() - started) / 1000) % 6;
      // Ramp, hold, release, rest.
      const shape =
        t < 1 ? t : t < 3 ? 1 : t < 4 ? 1 - (t - 3) : 0;
      setValue(shape * 70);
    }, 60);

    return () => window.clearInterval(timer);
  }, []);

  return value;
}
