/**
 * The workbench: clinician view, hardware setup, settings.
 *
 * Three pages that were each a destination in the navigation bar and none of
 * which a patient needs during a session. They are one place you go when you
 * want to look under the hood, so they are one page with three tabs.
 */

import { useSearchParams } from "react-router-dom";

import { ErrorBoundary } from "../components/Layout";
import { PageHeader, TabPanel, Tabs, type TabDef } from "../components/ui";
import { CameraTab } from "./lab/CameraTab";
import { ClinicianTab } from "./lab/ClinicianTab";
import { HardwareTab } from "./lab/HardwareTab";
import { SettingsTab } from "./lab/SettingsTab";

type LabTab = "clinician" | "hardware" | "camera" | "settings";

const TABS: TabDef<LabTab>[] = [
  { id: "clinician", label: "Clinician" },
  { id: "hardware", label: "Hardware" },
  { id: "camera", label: "Camera" },
  { id: "settings", label: "Settings" },
];

export function LabPage() {
  const [params, setParams] = useSearchParams();
  const raw = params.get("tab");
  const tab: LabTab = TABS.some((t) => t.id === raw)
    ? (raw as LabTab)
    : "clinician";

  const setTab = (next: LabTab) => {
    const updated = new URLSearchParams(params);
    updated.set("tab", next);
    setParams(updated, { replace: true });
  };

  return (
    <>
      <PageHeader
        title="Lab"
        pose="idle"
        note="The clinical view, the hardware setup and your settings."
        action={<Tabs tabs={TABS} value={tab} onChange={setTab} name="lab" />}
      />

      {/* Each panel is boundaried, so one section that cannot render leaves
          the other two working rather than blanking the route. */}
      <TabPanel name="lab" id={tab}>
        <ErrorBoundary key={tab}>
          {tab === "clinician" ? <ClinicianTab /> : null}
          {tab === "hardware" ? <HardwareTab /> : null}
          {tab === "camera" ? <CameraTab /> : null}
          {tab === "settings" ? <SettingsTab /> : null}
        </ErrorBoundary>
      </TabPanel>
    </>
  );
}
