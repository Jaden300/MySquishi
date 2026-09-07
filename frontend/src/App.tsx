/**
 * The route table.
 *
 * Four destinations. The app used to have eleven, which is more places than it
 * has tasks: onboarding, calibration and a session are one flow, and the
 * clinician view, the hardware guide and the settings are one workbench.
 *
 * Every old path still resolves. The redirects are three lines each and a dead
 * link during a demo is worse than a route nobody types any more.
 */

import {
  createBrowserRouter,
  Navigate,
  RouterProvider,
  useParams,
} from "react-router-dom";

import { Layout, RouteError } from "./components/Layout";
import { HomePage } from "./pages/HomePage";
import { LabPage } from "./pages/LabPage";
import { NotFoundPage } from "./pages/NotFoundPage";
import { ProgressPage } from "./pages/ProgressPage";
import { SessionSummaryPage } from "./pages/SessionSummaryPage";
import { TrainPage } from "./pages/TrainPage";

/** Navigate cannot interpolate a route param, so this carries the id across. */
function LegacySessionSummaryRedirect() {
  const { id } = useParams();
  return <Navigate to={`/progress/session/${id}`} replace />;
}

const router = createBrowserRouter([
  {
    path: "/",
    element: <Layout />,
    errorElement: <RouteError />,
    children: [
      { index: true, element: <HomePage /> },
      { path: "train", element: <TrainPage /> },
      { path: "progress", element: <ProgressPage /> },
      { path: "progress/session/:id", element: <SessionSummaryPage /> },
      { path: "lab", element: <LabPage /> },

      // The eleven route era, preserved.
      { path: "onboarding", element: <Navigate to="/train?stage=profile" replace /> },
      { path: "calibrate", element: <Navigate to="/train?stage=calibrate" replace /> },
      { path: "session", element: <Navigate to="/train?stage=live" replace /> },
      { path: "session/:id/summary", element: <LegacySessionSummaryRedirect /> },
      { path: "insights", element: <Navigate to="/progress?tab=insights" replace /> },
      { path: "clinician", element: <Navigate to="/lab?tab=clinician" replace /> },
      { path: "connect", element: <Navigate to="/lab?tab=hardware" replace /> },
      { path: "settings", element: <Navigate to="/lab?tab=settings" replace /> },
      { path: "about", element: <Navigate to="/" replace /> },

      { path: "*", element: <NotFoundPage /> },
    ],
  },
]);

export default function App() {
  return <RouterProvider router={router} />;
}
