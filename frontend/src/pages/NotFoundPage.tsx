/**
 * The catch all.
 *
 * A mistyped URL used to render an empty shell with a working navigation bar
 * and nothing in it, which reads as a broken app rather than a wrong address.
 */

import { PoseSpot } from "../components/brand/PoseSpot";
import { Button } from "../components/ui";

export function NotFoundPage() {
  return (
    <div className="mx-auto flex max-w-2xl flex-col items-center gap-6 py-16 text-center">
      <PoseSpot pose="confused" size={160} label="Squishi cannot find the page" />
      <h1 className="text-h1 text-squish-700">This page does not exist</h1>
      <div className="flex flex-wrap justify-center gap-3">
        <Button to="/">Back to the start</Button>
        <Button to="/train" variant="secondary">
          Start a session
        </Button>
      </div>
    </div>
  );
}
