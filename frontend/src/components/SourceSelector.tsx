/**
 * Where the signal comes from.
 *
 * Reads the catalogue from the backend rather than hardcoding a list, so the
 * set of sources has exactly one definition. `is_live` on each entry is what
 * drives the honesty chip: the label derives from the source object and never
 * from page copy, so a simulated session cannot be presented as a live one.
 *
 * Simulation is a permanent first class feature rather than a fallback, and
 * the copy here says so rather than apologising for it.
 */

import { api } from "../lib/api";
import { useApi } from "../lib/useApi";
import { SourceChip } from "./Honesty";

interface SourceSelectorProps {
  value: string;
  onChange: (sourceId: string) => void;
  disabled?: boolean;
}

export function SourceSelector({
  value,
  onChange,
  disabled = false,
}: SourceSelectorProps) {
  const sources = useApi(() => api.listSources(), []);
  const selected = sources.data?.find((source) => source.id === value);

  return (
    <div className="flex flex-col gap-2">
      <label htmlFor="source-select" className="text-sm text-ink/80">
        Signal source
      </label>

      <div className="flex items-center gap-2">
        <select
          id="source-select"
          value={value}
          disabled={disabled || sources.loading}
          title={selected?.note}
          onChange={(event) => onChange(event.target.value)}
          className="flex-1 rounded-xl border border-squish-100 bg-mist px-3 py-2 text-sm text-ink focus:outline-none focus:ring-2 focus:ring-squish-500 disabled:opacity-60"
        >
          {(sources.data ?? []).map((source) => (
            <option key={source.id} value={source.id} disabled={!source.available}>
              {source.label}
              {source.available ? "" : " (not available)"}
            </option>
          ))}
        </select>

        {selected ? <SourceChip isLive={selected.is_live} /> : null}
      </div>

      {sources.error ? (
        <p role="alert" className="text-sm text-ink">
          Could not load the source list. Simulation still works.
        </p>
      ) : null}
    </div>
  );
}
