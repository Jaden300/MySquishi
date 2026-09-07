/**
 * How much of what you are looking at is real.
 *
 * Replaces the "where the data comes from" paragraph, and is more honest than
 * the paragraph was: the prose said the demo account and the reference
 * population are synthetic, which is true but unquantified. This shows the
 * actual ratio, so a demo with two live sessions among thirty seeded ones
 * cannot read as a mostly real dataset.
 *
 * Each bar is labelled with its counts as well as its widths. Nothing here is
 * carried by colour alone: the synthetic segment is hatched as well as pale.
 */

interface DataSplitProps {
  liveSessions: number;
  syntheticSessions: number;
  cohortSize: number;
}

export function DataSplit({
  liveSessions,
  syntheticSessions,
  cohortSize,
}: DataSplitProps) {
  const sessions = liveSessions + syntheticSessions;

  return (
    <div className="flex flex-col gap-6">
      <SplitBar
        label="Your sessions"
        segments={[
          { label: "Recorded live", count: liveSessions, synthetic: false },
          { label: "Seeded for the demo", count: syntheticSessions, synthetic: true },
        ]}
        total={sessions}
        emptyMessage="No sessions recorded yet."
      />

      <SplitBar
        label="Reference population"
        segments={[
          { label: "Generated", count: cohortSize, synthetic: true },
        ]}
        total={cohortSize}
        emptyMessage="The reference cohort could not be loaded."
      />
    </div>
  );
}

interface Segment {
  label: string;
  count: number;
  synthetic: boolean;
}

function SplitBar({
  label,
  segments,
  total,
  emptyMessage,
}: {
  label: string;
  segments: Segment[];
  total: number;
  emptyMessage: string;
}) {
  const shown = segments.filter((s) => s.count > 0);

  return (
    <div className="flex flex-col gap-2">
      <span className="text-label text-ink/60">{label}</span>

      {total === 0 ? (
        <p className="text-body text-ink/70">{emptyMessage}</p>
      ) : (
        <>
          <div className="flex h-10 w-full overflow-hidden rounded-card border border-squish-100">
            {shown.map((segment) => (
              <div
                key={segment.label}
                title={`${segment.label}: ${segment.count} of ${total}`}
                style={{ width: `${(segment.count / total) * 100}%` }}
                className={
                  segment.synthetic
                    ? "h-full bg-squish-100 bg-[repeating-linear-gradient(45deg,transparent,transparent_5px,rgba(0,0,0,0.07)_5px,rgba(0,0,0,0.07)_10px)]"
                    : "h-full bg-squish-500"
                }
              />
            ))}
          </div>

          {/*
            The key is the honest part. Widths alone would let a reader guess
            wrong about which half is which, so every segment is named with its
            count next to a swatch that matches its fill, hatching included.
          */}
          <ul className="flex flex-wrap gap-x-5 gap-y-2">
            {shown.map((segment) => (
              <li
                key={segment.label}
                className="flex items-center gap-2 text-label text-ink/80"
              >
                <span
                  aria-hidden="true"
                  className={`h-3.5 w-3.5 shrink-0 rounded-sm border border-squish-300 ${
                    segment.synthetic
                      ? "bg-squish-100 bg-[repeating-linear-gradient(45deg,transparent,transparent_3px,rgba(0,0,0,0.12)_3px,rgba(0,0,0,0.12)_6px)]"
                      : "bg-squish-500"
                  }`}
                />
                {segment.label}: <span className="tabular">{segment.count}</span>
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}
