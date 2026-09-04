# Design

Palette tokens, typography, Squishi, copy voice, accessibility floor.

## Palette

Light blue, clean, calm. This is a medical product for someone who is injured and possibly frustrated. It should feel airy and encouraging, not clinically cold and not childish.

| Token | Hex | Use |
|---|---|---|
| `--squish-50` | `#F2F9FE` | page background |
| `--squish-100` | `#DCEEFB` | card fills, chart bands |
| `--squish-300` | `#7DC5F0` | secondary accents, mascot |
| `--squish-500` | `#2E9BDB` | primary action, live signal line |
| `--squish-700` | `#1B6C9E` | headings, emphasis |
| `--ink` | `#132430` | body text, a real dark blue slate rather than tinted black |
| `--mist` | `#FFFFFF` | card surfaces |
| `--alert` | `#E8825A` | fatigue and anomaly warnings only |
| `--good` | `#4FBFA0` | goal met, on track |

Use `--alert` sparingly. It should appear maybe twice on a whole screen. When it appears it means something.

### Token pipeline

`src/index.css` `:root` is the single source of truth and holds all nine as CSS custom properties. `tailwind.config.js` maps them through `var()`, so Tailwind classes and raw CSS resolve to the same variable. Recharts cannot consume `var()` in every prop, so `src/lib/tokens.ts` re-exports the literal hex values, and one test asserts the two lists agree.

## Layout and form

Simplicist and minimal. Generous whitespace. One idea per card. Large numbers with small quiet labels. Soft rounded corners at 12 to 16px. Very light shadows or none at all: prefer a 1px `--squish-100` border over a drop shadow. Charts drawn with thin lines and a lot of breathing room, not dense grids.

## Typography

One family, two at most. Avoid all caps labels. Avoid accenting one word in a headline in a different color. Avoid arrows glued onto button text. Sentence case everywhere. Numbers are tabular figures so charts and tables do not jitter.

## Squishi

A small, round, soft blue blob. Squishi squishes: it compresses in proportion to the patient's live contraction. That is the single memorable interaction in the whole product, since your effort deforms the character in real time. Spend the boldness here and keep everything else quiet.

Four expressions by contraction level: resting under 5 percent, working 5 to 40, straining 40 to 80, proud above 80. Proud also fires on rep completion.

Squishi appears in the session view, in empty states, and in celebration moments. Nowhere else.

Implementation: the component subscribes to exactly one store selector, the live percent MVC scalar, so mascot re-renders never drag the charts along. That scalar drives Framer Motion scale springs. An optional `value` prop overrides the store so the landing page can drive it from a preview stream.

Under `prefers-reduced-motion`, the spring is replaced by a discrete four state swap with no continuous animation and no idle bounce.

## Copy voice

Warm, plain, direct. "Squeeze and hold" rather than "Initiate isometric contraction protocol." Clinical terminology lives in the analytics layer where a clinician reads it. The patient layer stays human. Empty states invite action. Errors say what happened and what to do.

## Honesty affordances

These are components, not per page copy, so they cannot be forgotten:

- `SyntheticBadge` renders wherever a record has `is_synthetic` true.
- `IntervalReadout` is the only component allowed to render a prediction, and it requires lower and upper bounds as props. A bare point estimate is therefore a type error rather than a review catch.
- `ClinicalTooltip` reads its term map from `CLINICAL.md`.

## Accessibility floor

Non-negotiable:

- responsive down to 390px width
- visible keyboard focus on every interactive element
- `prefers-reduced-motion` respected, Squishi stops animating
- AA contrast throughout
- no information conveyed by color alone, so every colored state carries a label or shape as well

## Chart conventions

Consistent axes, thin lines, the squish palette, always labeled units, always an empty state. Every chart component accepts loading, error, and empty props so the states pass is mechanical rather than bespoke per chart.
