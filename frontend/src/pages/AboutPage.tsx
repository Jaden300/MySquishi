/**
 * Responsible AI.
 *
 * States plainly what each model is, when it was trained and how well it
 * scored, reading the registry rather than a hand written list, so the page
 * cannot drift away from what is actually deployed.
 */

import { api } from "../lib/api";
import { useApi } from "../lib/useApi";
import { SyntheticBadge } from "../components/Honesty";
import { SquishiMark } from "../components/brand/SquishiMark";

export function AboutPage() {
  const models = useApi(() => api.models(), []);

  return (
    <div className="flex max-w-3xl flex-col gap-6">
      <header>
        <h1 className="text-h1 text-squish-700">How MySquishi works</h1>
      </header>

      <section className="flex flex-col gap-3 text-body text-ink/80">
        <p>
          MySquishi reads the electrical activity your forearm muscles produce
          when you grip, filters it, and measures a handful of things about
          each repetition: how quickly you built up force, how steadily you
          held it, and how the frequency content of the signal shifted as you
          tired.
        </p>
        <p>
          Grip force in kilograms is an estimate calibrated to a reference you
          reported yourself. It is not a dynamometer measurement, and it is
          labeled that way everywhere it appears.
        </p>
        <p>
          Every prediction is shown with an interval rather than a single
          number, because a point estimate with the uncertainty stripped off
          is the dishonest way to report a model.
        </p>
      </section>

      <section className="flex flex-col gap-3">
        <h2 className="text-label font-medium text-squish-700">
          Where the data comes from
        </h2>
        <div className="flex items-start gap-3 rounded-panel border border-squish-100 bg-mist p-4">
          <SyntheticBadge />
          <p className="text-body text-ink/80">
            The demo account and the reference population are synthetic. They
            were generated to demonstrate the app and do not describe real
            people. Anywhere synthetic data drives something you see, it
            carries this badge.
          </p>
        </div>
      </section>

      <section className="flex flex-col gap-3">
        <h2 className="text-label font-medium text-squish-700">The models</h2>

        {models.loading ? (
          <div role="status" className="flex items-center gap-2">
            <SquishiMark size={22} className="animate-pulse opacity-50" />
            <span className="sr-only">Loading model records</span>
          </div>
        ) : null}

        {models.error ? (
          <p role="alert" className="text-label text-ink">
            {models.error}
          </p>
        ) : null}

        {models.data?.length ? (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[36rem] text-left text-label">
              <thead>
                <tr className="border-b border-squish-100 text-label text-ink/60">
                  <th className="py-2">Model</th>
                  <th className="py-2">Trained</th>
                  <th className="py-2">Score</th>
                  <th className="py-2">Rows</th>
                </tr>
              </thead>
              <tbody>
                {models.data.map((record) => (
                  <tr key={record.model_id} className="border-b border-squish-50">
                    <td className="py-2 text-ink">{record.model_id}</td>
                    <td className="tabular py-2 text-ink/70">
                      {new Date(record.trained_at).toLocaleDateString()}
                    </td>
                    <td className="tabular py-2 text-ink/70">
                      {record.metric_name} {record.metric_value.toFixed(3)}
                    </td>
                    <td className="tabular py-2 text-ink/70">
                      {record.n_training_rows.toLocaleString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : !models.loading && !models.error ? (
          <p className="text-body text-ink/70">
            No trained models are on disk. The app falls back to transparent
            rule based scoring, and says so wherever that happens.
          </p>
        ) : null}
      </section>

      <section className="flex flex-col gap-3">
        <h2 className="text-label font-medium text-squish-700">Limitations</h2>
        <ul className="flex list-disc flex-col gap-2 pl-5 text-body text-ink/80">
          <li>
            Surface EMG is sensitive to electrode placement. Moving the
            electrodes changes the readings, which is why calibration belongs
            to a placement and not just to a person.
          </li>
          <li>
            The normative percentile reference is synthetic and approximate.
            It gives context, not a diagnosis.
          </li>
          <li>
            Forecasts assume you keep training roughly as you have been. They
            describe a trend, not a promise.
          </li>
          <li>
            The app does not diagnose anything, and it does not replace an
            assessment by a clinician.
          </li>
        </ul>
      </section>
    </div>
  );
}
