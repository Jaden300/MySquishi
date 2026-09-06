/**
 * The route table.
 */

import { createBrowserRouter, RouterProvider } from "react-router-dom";

import { Layout, RouteError } from "./components/Layout";
import { AboutPage } from "./pages/AboutPage";
import { ConnectPage } from "./pages/ConnectPage";
import { CalibratePage } from "./pages/CalibratePage";
import { ClinicianPage } from "./pages/ClinicianPage";
import { InsightsPage } from "./pages/InsightsPage";
import { LandingPage } from "./pages/LandingPage";
import { OnboardingPage } from "./pages/OnboardingPage";
import { ProgressPage } from "./pages/ProgressPage";
import { SessionPage } from "./pages/SessionPage";
import { SessionSummaryPage } from "./pages/SessionSummaryPage";
import { SettingsPage } from "./pages/SettingsPage";

const router = createBrowserRouter([
  {
    path: "/",
    element: <Layout />,
    errorElement: <RouteError />,
    children: [
      { index: true, element: <LandingPage /> },
      { path: "onboarding", element: <OnboardingPage /> },
      { path: "calibrate", element: <CalibratePage /> },
      { path: "session", element: <SessionPage /> },
      { path: "session/:id/summary", element: <SessionSummaryPage /> },
      { path: "progress", element: <ProgressPage /> },
      { path: "insights", element: <InsightsPage /> },
      { path: "clinician", element: <ClinicianPage /> },
      { path: "connect", element: <ConnectPage /> },
      { path: "settings", element: <SettingsPage /> },
      { path: "about", element: <AboutPage /> },
    ],
  },
]);

export default function App() {
  return <RouterProvider router={router} />;
}
