# Design

Palette tokens, typography, Squishi, copy voice, accessibility floor.

## Palette

Soft violet, clean, calm, taken from the logo. This is a medical product for someone who is injured and possibly frustrated. It should feel airy and encouraging, not clinically cold and not childish.

| Token | Hex | Use |
|---|---|---|
| `--squish-50` | `#F7F5FE` | page background |
| `--squish-100` | `#E6E1FA` | card fills, chart bands, borders |
| `--squish-300` | `#AC9AF7` | secondary accents, logo gradient top |
| `--squish-500` | `#7A66DD` | primary action, live signal line, focus ring |
| `--squish-700` | `#4B3B96` | headings, emphasis, the wordmark |
| `--ink` | `#2A2320` | body text, a warm near black rather than pure black |
| `--mist` | `#FFFFFF` | card surfaces |
| `--alert` | `#EF5346` | fatigue and anomaly warnings only |
| `--good` | `#17A88F` | goal met, on track |

Use `--alert` sparingly. It should appear maybe twice on a whole screen. When it appears it means something.

`--good` is deliberately darker than the mint in the logo artwork, because it has to hold up as text and as a chart stroke on white, not only as a fill.

### Brand tokens

Squishi's own colours sit outside the UI ramp, so retinting the interface never retints the character:

| Token | Hex | Use |
|---|---|---|
| `--squishi-body` | `#FFB6A6` | the blob, coral against the violet interface |
| `--squishi-face` | `#4B3B96` | eyes, mouth, brows |
| `--squishi-accent` | `#46E0C6` | sweat and effort marks, decoration only |

### Token pipeline

`src/index.css` `:root` is the single source of truth and holds all nine ramp values as CSS custom properties. `tailwind.config.js` maps them through `var()`, so Tailwind classes and raw CSS resolve to the same variable. Recharts cannot consume `var()` in every prop, so `src/lib/tokens.ts` re-exports the literal hex values, and one test asserts the two lists agree. The brand tokens are not mirrored: nothing in Recharts draws the mascot.

## Brand mark

The logo is Squishi's face. Three components in `src/components/brand/`:

- `SquishiMark` is the bare blob face, the reusable still mark. It is decorative and hidden from assistive technology unless given a `title`.
- `Wordmark` is the primary lockup: `My` + the mark + `quishi`, the blob standing in for the S. The letters and mark are `aria-hidden` under one `aria-label`, so it is announced as a single name rather than as "My" then "quishi".
- `PoseArt` renders one pose from the library, shared by the animated mascot and every still placement, so the character is drawn in exactly one place.

`public/favicon.svg` and `public/logo.svg` carry the boxed app icon: the blob on the violet gradient.

### The watermark

The mark also appears as page furniture, and the rule is that it must never compete with content. `.brand-watermark` places one blob at four percent opacity in a panel's bottom right corner, behind the content and taking no pointer events. `.brand-watermark-sm` is the quieter variant for dense cards. `.brand-ground` washes the page with two soft radial gradients.

Apply the watermark deliberately to chosen panels. It is not sprayed randomly, and its placement is deterministic so the layout is stable across renders.

## Layout and form

Simplicist and minimal. Generous whitespace. One idea per card. Soft rounded corners at 12 to 16px. Very light shadows or none at all: prefer a 1px `--squish-100` border over a drop shadow. Charts drawn with thin lines and a lot of breathing room, not dense grids.

### No standing small text

Captions, hints, footnotes and explanatory sub-lines are not used. This is a deliberate reversal of the earlier "large numbers with small quiet labels" pattern: in practice the page filled with grey nine-pixel prose that nobody read and everybody had to look past.

What survives, and where it goes:

- A label that *names* a number stays visible. A sentence that *explains* one does not.
- Clinical notes that the honesty rules require are carried on the element they describe, as a `title` attribute plus an `.sr-only` span. Nothing is deleted, so a reader who wants the interval, the method or the kilogram caveat gets it on hover and assistive technology always announces it.
- Badges and chips stay: they are the text half of a colour-coded state, which the accessibility floor requires.

Before adding any new `text-xs` paragraph, put it in a tooltip instead.

## Typography

One family, two at most. Avoid all caps labels. Avoid accenting one word in a headline in a different color. Avoid arrows glued onto button text. Sentence case everywhere. Numbers are tabular figures so charts and tables do not jitter.

## Squishi

A small, round, soft coral blob with a violet face. Squishi squishes: it compresses in proportion to the patient's live contraction. That is the single memorable interaction in the whole product, since your effort deforms the character in real time. Spend the boldness here and keep everything else quiet.

Four expressions by contraction level: resting under 5 percent, working 5 to 40, straining 40 to 80, proud above 80. Proud also fires on rep completion.

Squishi appears in the session view, in empty and loading states, on the landing and onboarding pages, and through calibration. Not scattered further than that.

### The pose library

`src/components/brand/poses.ts` holds twenty poses as data, not as components, so they can be enumerated and picked by id without rendering anything. Every pose shares one body path and differs only in its arms, its face, and an optional squash transform, which is what keeps the character recognisably the same across all twenty.

The four expressions map onto four poses: resting to `idle`, working to `midSqueeze`, straining to `compressed`, proud to `cheering`. A `pose` prop pins any of the twenty for a still placement that illustrates rather than reports.

### Implementation

The component subscribes to exactly one store selector, the live percent MVC scalar, so mascot re-renders never drag the charts along. That scalar drives Framer Motion scale springs. An optional `value` prop overrides the store so the landing page can drive it from a preview stream.

Two rules the artwork forces:

- Poses carry their own authored squash. The animated branch suppresses it and lets the spring alone scale the character, because applying both compounds the two scales and flattens the blob into a line.
- The animated branch borrows `idle`'s arms. Poses authored at an extreme already fling the arms out flat, and squashing those again turns them into stubs.

Under `prefers-reduced-motion`, the spring is replaced by a discrete four state swap with no continuous animation and no idle bounce.

## Copy voice

Warm, plain, direct. "Squeeze and hold" rather than "Initiate isometric contraction protocol." Clinical terminology lives in the analytics layer where a clinician reads it. The patient layer stays human. Empty states invite action. Errors say what happened and what to do.

## Honesty affordances

These are components, not per page copy, so they cannot be forgotten:

- `SyntheticBadge` renders wherever a record has `is_synthetic` true. It stays visible.
- `IntervalReadout` is the only component allowed to render a prediction, and it requires lower and upper bounds as props. A bare point estimate is therefore a type error rather than a review catch. The bounds are still attached to every number, carried as a `title` and an `.sr-only` span rather than printed beneath it: the requirement is that the uncertainty travels with the estimate, not that it occupies a line of the layout.
- `ClinicalTooltip` reads its term map from `CLINICAL.md`.

The same treatment applies to `KG_ESTIMATE_NOTE`, `PERCENTILE_NOTE` and `NON_GRIP_NOTE`. The constants are unchanged and still render on the element they qualify. `NotAMedicalDevice` remains visible in the footer, because consent references it.

## Accessibility floor

Non-negotiable:

- responsive down to 390px width
- visible keyboard focus on every interactive element
- `prefers-reduced-motion` respected, Squishi stops animating
- AA contrast throughout
- no information conveyed by color alone, so every colored state carries a label or shape as well

## Chart conventions

Consistent axes, thin lines, the squish palette, always labeled units, always an empty state. Every chart component accepts loading, error, and empty props so the states pass is mechanical rather than bespoke per chart.
