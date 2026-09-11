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
import { Select } from "./ui/Select";

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
      <label htmlFor="source-select" className="text-label text-ink/80">
        Signal source
      </label>

      <div className="flex items-center gap-2">
        <Select
          id="source-select"
          className="flex-1"
          value={value}
          disabled={disabled || sources.loading}
          title={selected?.note}
          onChange={onChange}
          placeholder={sources.loading ? "Loading sources" : "Select a source"}
          options={(sources.data ?? []).map((source) => ({
            value: source.id,
            label: source.available
              ? source.label
              : `${source.label} (not available)`,
            disabled: !source.available,
          }))}
        />

        {selected ? <SourceChip isLive={selected.is_live} /> : null}
      </div>

      {sources.error ? (
        <p role="alert" className="text-label text-ink">
          Could not load the source list. Simulation still works.
        </p>
      ) : null}
    </div>
  );
}
