import { tokens, cssVarNames, type TokenName } from "./lib/tokens";

/**
 * Scaffolding check for the token pipeline. Each swatch is painted by a
 * Tailwind class (which resolves through var()) while the caption prints the
 * literal from tokens.ts. If the two ever drift, the swatch and its label
 * will visibly disagree.
 *
 * This page is replaced by the router in the next slice.
 */

const swatches: { name: TokenName; className: string; usage: string }[] = [
  { name: "squish50", className: "bg-squish-50", usage: "page background" },
  { name: "squish100", className: "bg-squish-100", usage: "card fills, chart bands" },
  { name: "squish300", className: "bg-squish-300", usage: "secondary accents, mascot" },
  { name: "squish500", className: "bg-squish-500", usage: "primary action, signal line" },
  { name: "squish700", className: "bg-squish-700", usage: "headings, emphasis" },
  { name: "ink", className: "bg-ink", usage: "body text" },
  { name: "mist", className: "bg-mist", usage: "card surfaces" },
  { name: "alert", className: "bg-alert", usage: "fatigue and anomaly warnings only" },
  { name: "good", className: "bg-good", usage: "goal met, on track" },
];

export default function App() {
  return (
    <main className="mx-auto max-w-3xl px-6 py-12">
      <h1 className="text-2xl text-squish-700">MySquishi design tokens</h1>
      <p className="mt-2 text-sm text-ink/70">
        Swatch fill comes from Tailwind through a CSS custom property. The hex
        beside it comes from tokens.ts. They should match.
      </p>

      <ul className="mt-8 space-y-3">
        {swatches.map((s) => (
          <li
            key={s.name}
            className="flex items-center gap-4 rounded-card border border-squish-100 bg-mist p-3"
          >
            <span
              className={`${s.className} h-10 w-10 shrink-0 rounded-card border border-squish-100`}
              aria-hidden="true"
            />
            <span className="w-32 text-sm text-ink">{cssVarNames[s.name]}</span>
            <span className="tabular w-24 text-sm text-ink/70">{tokens[s.name]}</span>
            <span className="text-sm text-ink/60">{s.usage}</span>
          </li>
        ))}
      </ul>
    </main>
  );
}
