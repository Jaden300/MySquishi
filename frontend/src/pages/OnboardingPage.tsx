/**
 * Onboarding: profile, injury context, goal, and consent.
 */

import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { api } from "../lib/api";
import { SquishiMascot } from "../components/SquishiMascot";

const AGE_BANDS = ["18-34", "35-49", "50-64", "65-79", "80+"];
const INJURY_TYPES = [
  "distal radius fracture",
  "post stroke hemiparesis",
  "carpal tunnel release",
  "flexor tendon repair",
  "age related sarcopenia",
  "other",
];

export function OnboardingPage() {
  const navigate = useNavigate();

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
      navigate("/calibrate");
    } else {
      setError(result.error);
    }
  }

  return (
    <div className="mx-auto flex max-w-xl flex-col gap-6">
      <header className="flex items-center gap-4">
        <SquishiMascot value={12} size={72} />
        <div>
          <h1 className="text-xl text-squish-700">Let us set things up</h1>
          <p className="text-sm text-ink/60">
            A few details so your readings mean something.
          </p>
        </div>
      </header>

      <form onSubmit={submit} className="flex flex-col gap-5">
        <Field label="What should we call you?">
          <input
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
            className="input"
            placeholder="Your name"
          />
        </Field>

        <div className="grid gap-5 sm:grid-cols-2">
          <Field label="Age band">
            <select value={ageBand} onChange={(e) => setAgeBand(e.target.value)} className="input">
              {AGE_BANDS.map((band) => (
                <option key={band} value={band}>
                  {band}
                </option>
              ))}
            </select>
          </Field>

          <Field label="Sex">
            <select value={sex} onChange={(e) => setSex(e.target.value)} className="input">
              <option value="female">Female</option>
              <option value="male">Male</option>
            </select>
          </Field>
        </div>

        <Field
          label="What are you recovering from?"
          hint="Used for context only. It does not change how your signal is measured."
        >
          <select
            value={injuryType}
            onChange={(e) => setInjuryType(e.target.value)}
            className="input"
          >
            {INJURY_TYPES.map((type) => (
              <option key={type} value={type}>
                {type}
              </option>
            ))}
          </select>
        </Field>

        <div className="grid gap-5 sm:grid-cols-2">
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

        <label className="flex items-start gap-3 rounded-card border border-squish-100 bg-mist p-4 text-sm">
          <input
            type="checkbox"
            checked={consent}
            onChange={(e) => setConsent(e.target.checked)}
            className="mt-0.5"
            required
          />
          <span className="text-ink/80">
            I understand that MySquishi is a training aid, not a medical
            device, and that it does not replace a clinician.
          </span>
        </label>

        {error ? (
          <p role="alert" className="text-sm text-alert">
            {error}
          </p>
        ) : null}

        <button
          type="submit"
          disabled={!consent || saving}
          className="rounded-card bg-squish-500 px-5 py-2.5 text-mist hover:bg-squish-700 disabled:opacity-50"
        >
          {saving ? "Saving..." : "Continue to calibration"}
        </button>
      </form>

    </div>
  );
}

function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <label className="flex flex-col gap-1.5">
      <span className="text-sm text-ink">{label}</span>
      {children}
      {hint ? <span className="text-xs text-ink/60">{hint}</span> : null}
    </label>
  );
}
