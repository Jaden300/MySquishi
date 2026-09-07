/**
 * Every deployed model, its score and how much it was trained on.
 *
 * Replaces the four column table on the about page. The table was accurate and
 * unreadable: four numbers per row in twelve pixel text, with no way to see
 * that one model was trained on forty times the rows of another.
 *
 * A card per model puts the score at stat size and draws the training set as a
 * bar against the largest, so relative provenance is visible rather than
 * requiring the reader to compare four figure numbers by eye.
 *
 * Reads the registry, so it cannot drift away from what is actually deployed.
 */

import type { ModelRecord } from "../../types/api";

interface ModelProvenanceProps {
  models: ModelRecord[];
}

export function ModelProvenance({ models }: ModelProvenanceProps) {
  // Bars are relative to the largest training set, so the comparison is
  // between models rather than against an arbitrary absolute scale.
  const largest = models.reduce((max, m) => Math.max(max, m.n_training_rows), 0);

  return (
    <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {models.map((record) => {
        const share = largest > 0 ? record.n_training_rows / largest : 0;
        const trained = new Date(record.trained_at).toLocaleDateString();
        const note =
          `${record.model_id}, ${record.metric_name} ${record.metric_value.toFixed(3)}, ` +
          `trained on ${record.n_training_rows.toLocaleString()} rows on ${trained}.`;

        return (
          <li
            key={record.model_id}
            title={note}
            className="flex flex-col gap-3 rounded-card border border-squish-100 bg-squish-50 p-4"
          >
            <div className="flex items-baseline justify-between gap-3">
              <span className="text-h3 text-squish-700">{record.model_id}</span>
              <span className="text-label text-ink/60">{record.metric_name}</span>
            </div>

            <span className="tabular text-stat text-squish-700">
              {record.metric_value.toFixed(2)}
            </span>

            {/*
              The bar is sized against the largest training set across all
              models, so a short bar means less evidence behind that model.
              The row count is printed beside it, because a bar with no number
              is a shape rather than a fact.
            */}
            <div className="flex flex-col gap-1.5">
              <div className="h-2.5 w-full overflow-hidden rounded-pill bg-squish-100">
                <div
                  className="h-full rounded-pill bg-squish-500"
                  style={{ width: `${Math.max(share * 100, 2)}%` }}
                />
              </div>
              <span className="tabular text-label text-ink/60">
                {record.n_training_rows.toLocaleString()} rows
              </span>
            </div>

            <span className="sr-only">{note}</span>
          </li>
        );
      })}
    </ul>
  );
}
