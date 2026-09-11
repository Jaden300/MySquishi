/**
 * Profile, injury context, goal, and consent.
 *
 * The first stage of the training flow. It used to be its own route, which
 * meant the navigation bar offered you the setup form as a destination even
 * after you had filled it in.
 */

import { useState } from "react";

import { api } from "../../lib/api";
import { SquishiMascot } from "../../components/SquishiMascot";
import { Button, Card, Field, Select } from "../../components/ui";

const AGE_BANDS = ["18-34", "35-49", "50-64", "65-79", "80+"];
const INJURY_TYPES = [
  "distal radius fracture",
  "post stroke hemiparesis",
  "carpal tunnel release",
  "flexor tendon repair",
  "age related sarcopenia",
  "other",
];

export function ProfileStage({ onDone }: { onDone: () => void }) {
  const [displayName, setDisplayName] = useState("");
  const [ageBand, setAgeBand] = useState(AGE_BANDS[2]);
  const [sex, setSex] = useState("female");
  const [injuryType, setInjuryType] = useState(INJURY_TYPES[0]);
  const [unaffectedKg, setUnaffectedKg] = useState("");
  const [goalKg, setGoalKg] = useState("");
  const [consent, setConsent] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setSaving(true);
    setError(null);

    const result = await api.updatePatient("demo", {
      display_name: displayName || "You",
      age_band: ageBand,
      sex,
      injury_type: injuryType,
      unaffected_kg: unaffectedKg ? Number(unaffectedKg) : null,
      goal_kg: goalKg ? Number(goalKg) : null,
      consent_accepted: consent,
    });

    setSaving(false);
    if (result.ok) {
      onDone();
    } else {
      setError(result.error);
    }
  }

  return (
    <div className="mx-auto flex max-w-xl flex-col gap-8">
      <header className="flex items-center gap-4">
        <SquishiMascot value={12} size={96} pose="waving" />
        <h1 className="text-h1 text-squish-700">Let us set things up</h1>
      </header>

      <form onSubmit={submit} className="flex flex-col gap-6">
        <Field label="What should we call you?">
          <input
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
            className="input"
            placeholder="Your name"
          />
        </Field>

        <div className="grid gap-6 sm:grid-cols-2">
          <Field label="Age band" htmlFor="profile-age-band">
            <Select
              id="profile-age-band"
              value={ageBand}
              onChange={setAgeBand}
              options={AGE_BANDS.map((band) => ({ value: band, label: band }))}
            />
          </Field>

          <Field label="Sex" htmlFor="profile-sex">
            <Select
              id="profile-sex"
              value={sex}
              onChange={setSex}
              options={[
                { value: "female", label: "Female" },
                { value: "male", label: "Male" },
              ]}
            />
          </Field>
        </div>

        <Field
          label="What are you recovering from?"
          hint="Used for context only. It does not change how your signal is measured."
          htmlFor="profile-injury"
        >
          <Select
            id="profile-injury"
            value={injuryType}
            onChange={setInjuryType}
            options={INJURY_TYPES.map((type) => ({ value: type, label: type }))}
          />
        </Field>

        <div className="grid gap-6 sm:grid-cols-2">
          <Field
            label="Your other hand, in kg"
            hint="If you know it. Recovering to your own other hand is the honest target."
          >
            <input
              type="number"
              inputMode="decimal"
              value={unaffectedKg}
              onChange={(e) => setUnaffectedKg(e.target.value)}
              className="input tabular"
              placeholder="30"
            />
          </Field>

          <Field label="Your goal, in kg">
            <input
              type="number"
              inputMode="decimal"
              value={goalKg}
              onChange={(e) => setGoalKg(e.target.value)}
              className="input tabular"
              placeholder="27"
            />
          </Field>
        </div>

        <Card as="label" tone="accent" className="flex items-start gap-3">
          <input
            type="checkbox"
            checked={consent}
            onChange={(e) => setConsent(e.target.checked)}
            className="mt-1.5 h-5 w-5 shrink-0 accent-[var(--squish-500)]"
            required
          />
          <span className="text-body text-ink">
            I understand that MySquishi is a training aid, not a medical
            device, and that it does not replace a clinician.
          </span>
        </Card>

        {error ? (
          <p role="alert" className="text-body text-alert">
            {error}
          </p>
        ) : null}

        <Button type="submit" size="lg" disabled={!consent || saving}>
          {saving ? "Saving..." : "Continue to calibration"}
        </Button>
      </form>
    </div>
  );
}
