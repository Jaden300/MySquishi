# Design

Palette tokens, typography, Squishi, copy voice, accessibility floor.

## Palette

Soft violet, clean, calm, taken from the logo. This is a medical product for someone who is injured and possibly frustrated. It should feel airy and encouraging, not clinically cold and not childish.

| Token | Hex | Use |
|---|---|---|
| `--squish-50` | `#F7F5FE` | page background |
| `--squish-100` | `#E6E1FA` | card fills, chart bands, borders |
| `--squish-300` | `#9A84F5` | secondary accents, logo gradient top, the raw trace |
| `--squish-500` | `#6350C4` | primary action, live signal line, focus ring |
| `--squish-700` | `#4B3B96` | headings, emphasis, the wordmark |
| `--ink` | `#2A2320` | body text, a warm near black rather than pure black |
| `--mist` | `#FFFFFF` | card surfaces |
| `--alert` | `#E72414` | fatigue and anomaly warnings only |
| `--good` | `#128572` | goal met, on track |

Use `--alert` sparingly. It should appear maybe twice on a whole screen. When it appears it means something.

### Why these exact values

Four of them were measured against white, the surface they are read on, and darkened until they cleared AA. The earlier values are worth recording, because every one of them looked fine:

| Token | Was | Measured | Now | Measures |
|---|---|---|---|---|
| `--squish-500` | `#7A66DD` | 4.40 | `#6350C4` | 6.04 |
| `--alert` | `#EF5346` | 3.50 | `#E72414` | 4.51 |
| `--good` | `#17A88F` | 2.99 | `#128572` | 4.54 |
| `--squish-300` | `#AC9AF7` | 2.41 | `#9A84F5` | 3.00 |

`--squish-500` is used in both directions, as a fill under white text and as text on white, so one token carried two failures. `--squish-300` draws the raw signal at one pixel wide, which is data rather than decoration, so it is held to the 3.0 floor for graphical objects rather than the 4.5 one for text.

This is enforced rather than described: `src/lib/contrast.test.ts` computes the ratios and fails the build if any of them drops back under its floor. Before that test existed, this section claimed `--good` had been darkened to pass as text, and it had not.

### Text at partial opacity

`text-ink/NN` looks like a shade of the body colour and behaves like a separate token. On white:

| Opacity | Ratio | Use |
|---|---|---|
| `/80` | 8.04 | readable |
| `/70` | 5.75 | readable, the floor |
| `/60` | 4.19 | decorative or `aria-hidden` only |
| `/50` | 3.13 | decorative or `aria-hidden` only |
| `/45`, `/40` | 2.73, 2.39 | decorative or `aria-hidden` only |

**Readable copy stops at `/70`.** Anything lighter is for marks a sighted reader is not meant to read, and those carry `aria-hidden` so a screen reader skips them too. Disabled controls are exempt under WCAG, but still read better at `/70` than below it.

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

- `SquishiMark` is the bare blob face, the reusable still mark. It is decorative and hidden from assistive technology unless given a `title`. It draws through `PoseArt pose="idle"` in a cropped viewBox rather than restating the body silhouette as its own path. It used to be a second copy of the character in a 620x520 box while `BODY_PATH` lived in 200x200, which is the drift `PoseArt` exists to prevent: the same character drawn twice at different proportions. Nobody noticed because the two never appeared together. At the sizes this design uses, they do.
- `Wordmark` is the primary lockup: `My` + the mark + `quishi`, the blob standing in for the S. The letters and mark are `aria-hidden` under one `aria-label`, so it is announced as a single name rather than as "My" then "quishi".
- `PoseArt` renders one pose from the library, shared by the animated mascot and every still placement, so the character is drawn in exactly one place.

`public/favicon.svg` and `public/logo.svg` carry the boxed app icon: the blob on the violet gradient.

### The watermark

The mark also appears as page furniture, and the rule is that it must never compete with content. `.brand-watermark` places one blob at four percent opacity in a panel's bottom right corner, behind the content and taking no pointer events. `.brand-watermark-sm` is the quieter variant for dense cards. `.brand-ground` washes the page with two soft radial gradients.

Apply the watermark deliberately to chosen panels. Its placement is deterministic so the layout is stable across renders.

### The scatter field

`BackgroundBlobs` in `src/components/Layout.tsx` also lays a field of fourteen marks behind the whole app. This is page texture rather than a per panel watermark, and the two do not overlap in purpose: the watermark belongs to a card, the scatter belongs to the page.

- Placements are a frozen module level table of literal positions, never `Math.random()`. The arrangement must not reshuffle between renders, and a fixed table can be reasoned about and tested.
- Positions are in `vw` and `vh`, so the field covers the viewport at 390px without crowding the narrow column.
- Opacity runs 7 to 10 percent. The first pass used 3 to 6, which measured as correct against the contrast floor and was invisible on the near white ground: the page still read as flat, which was the complaint the field exists to answer. The cards it sits behind are opaque, so no text is ever read against a mark.
- The silhouette comes from `BODY_PATH` in the pose library rather than a second copy of the shape, for the same reason `PoseArt` exists.
- A few marks carry `bob` or `drift` with staggered negative delays so the field never pulses in unison. These are CSS animations, so the global reduced motion block already stops them.

## Layout and form

Simplicist and minimal. Generous whitespace. One idea per card. Soft rounded corners at 12 to 16px. Very light shadows or none at all: prefer a 1px `--squish-100` border over a drop shadow. Charts drawn with thin lines and a lot of breathing room, not dense grids.

### No standing small text

Captions, hints, footnotes and explanatory sub-lines are not used. This is a deliberate reversal of the earlier "large numbers with small quiet labels" pattern: in practice the page filled with grey nine-pixel prose that nobody read and everybody had to look past.

What survives, and where it goes:

- A label that *names* a number stays visible. A sentence that *explains* one does not.
- Clinical notes that the honesty rules require are carried on the element they describe, as a `title` attribute plus an `.sr-only` span. Nothing is deleted, so a reader who wants the interval, the method or the kilogram caveat gets it on hover and assistive technology always announces it.
- Badges and chips stay: they are the text half of a colour-coded state, which the accessibility floor requires.

Before adding any new small paragraph, put it in a tooltip instead.

This rule was written before it was applied, and for a while the app carried 72 `text-sm` and 12 `text-xs` occurrences alongside it. It is now enforced three ways rather than remembered: the classes do not exist in the scale, `src/lib/typeScale.test.ts` fails on any that reappear, and the header primitives have no prop that can print a subtitle. `PageHeader` and `SectionHeader` take `note`, which goes to `title` and `.sr-only` and is never rendered visibly.

The replacement mechanic, applied throughout: the explanatory sentence moves onto the thing it explains, and a figure takes the space it occupied. The about page went from 135 lines of paragraphs to six figures and one sentence this way, and no sentence was deleted.

## Primitives

`src/components/ui/` holds everything that appears on more than one page as the same shape. Before it existed, the primary button's utility string was copy pasted fourteen times and the card's about twenty, which is how two pages end up with different hover colours.

- `Button` resolves to a router `Link`, an anchor or a real `button` depending on which of `to` and `href` is set, so a link never has to be dressed as a button by hand.
- `Card` is the one surface. `ChartFrame` and `Figure` both render their shell through it, so a chart card and a content card cannot drift.
- `PageHeader` and `SectionHeader` are described above. Every page renders a `PageHeader`, which is most of what makes four routes feel like one product.
- `StatTile` is one number, named. `size="hero"` is the one enormous number a page is allowed.
- `Figure` is `ChartFrame` for anything hand drawn: the same loading, error and empty discipline, and `source="synthetic"` renders the badge automatically, so a hand built figure cannot dodge the honesty rule the way a bare `div` could.
- `Tabs` implements roving tabindex with a Framer `layoutId` indicator.
- `Select` is the one dropdown. A native `select` cannot have its popup styled, so five controls were rendering the operating system's list, arrow and rows inside a violet page. This is the listbox pattern instead: a `combobox` trigger and a `listbox` popup, which means reimplementing by hand the keyboard behaviour the native control gave away for free. Arrows move, Enter and Space commit, Escape closes and restores focus, Home and End jump, typing a letter jumps, and disabled options are skipped rather than merely refused. That is the reason it is written once here rather than per call site, and the reason it carries its own test file.
- `Field` wraps a control in a `label`, or takes `htmlFor` and renders an associated one instead. `Select` needs the second form: it is a button and a popup, not a form element, so wrapping it would put a click target over the list and announce the label twice.
- `Reveal` fades its children in once when first scrolled to, and returns them untouched under reduced motion.
- `PoseSpot` is the single way a still pose reaches the page.
- `Glyph` and `GlyphTile` in `src/components/figures/` carry the small line drawings that let a step, a failure or a pipeline node be recognised without reading it. Drawn rather than pulled from an icon font, so they inherit the palette and hold one stroke weight with the rest of the brand.

Glyphs are duotone: a solid shape sits behind the stroke at 18 percent, both `currentColor`, so a glyph is one colour at two opacities and cannot drift off palette. They were outline only at 1.6px for a while, which at 24px in a flat tinted square read as a smudge rather than an object. The stroke is now 1.9.

`GlyphTile` is the tile itself, and the one way an icon reaches a card. Four call sites hand rolled the same square before it existed, which is how two of them ended up with a flat wash and the other two with no tile at all. Its gradient runs violet to a hint of the mascot's coral, which is what stops it reading as a grey shade. Tone is `brand` or `alert` and is a function of meaning, never of which glyph it holds.

## Typography

Two faces, both self-hosted through `@fontsource-variable/*` and imported in `src/main.tsx` above `index.css`. Not a Google Fonts link: the app has to stay fully demoable with no network, and `render.yaml` serves one origin.

| Role | Face | Where |
|---|---|---|
| Display | Fraunces Variable | `h1`, `h2`, `h3`, stat values, the wordmark |
| Body | Plus Jakarta Sans Variable | everything else |

Fraunces carries `font-variation-settings: "opsz" 48, "SOFT" 60, "WONK" 1`. The `SOFT` axis rounds the terminals, which is what makes the headings agree with the blob instead of sitting over it as a separate idea.

### The axis import, which is load bearing

Fraunces must be imported as `@fontsource-variable/fraunces/full.css`, not as the bare package. This is not a preference and it is easy to break silently:

- The bare `@fontsource-variable/fraunces` entry point ships the **`wght` only** axis build. The `SOFT` and `WONK` declaration above then has no axes to move, the browser drops it without an error, and every heading in the app renders at `SOFT` 0: a hard, sharp, high contrast serif, which is the opposite of the intent. The app shipped in exactly that state for a while and the CSS looked correct the whole time, because a `font-variation-settings` naming an axis the file does not carry is not a mistake a browser reports.
- `soft.css` plus `wonk.css` looks like the cheaper pick and is a trap. Each subset declares its own `@font-face` under the same family name and the same `unicode-range`, so the later import shadows the earlier one outright: that pairing downloads 98KB of Latin and ends up with `WONK` and no `SOFT`. One file carrying both axes is the only version that works.
- `opsz` is pinned rather than left to the font. Fraunces defaults it to 9, the caption grade, drawn thin and high contrast for text a few millimetres tall, which looks brittle at heading sizes. 48 is the display end.

The cost is a 121KB Latin woff2 against the 36KB `wght` only file. It is `font-display: swap` and off the critical path, and it is the price of the axes doing anything at all.

`Wordmark` sets the same three axes inline, because it is SVG adjacent markup that the `h1, h2, h3` element rule does not reach, and it sits inches from an `h1` in the header where a different optical size would read as a second typeface.

A bare `h1, h2, h3` element rule sets the display face, so a heading that forgets its class still gets the right one.

### The scale

`theme.fontSize` in `tailwind.config.js` is **replaced, not extended**. Nothing below 16px exists, so `text-xs` and `text-sm` no longer generate anything at all. That is the enforcement mechanism for the rule below: a deleted class cannot be reached for.

| Class | Size / line-height | Use |
|---|---|---|
| `text-label` | 16px / 1.4, weight 500 | the floor: form labels, table headers, chips, tile labels |
| `text-body` | 17px / 1.6 | default body |
| `text-lead` | 20px / 1.5 | intro line, coach prompt, insight summary |
| `text-h3` | 24px / 1.2 | card and chart titles |
| `text-h2` | 32px / 1.15 | section headings |
| `text-stat` | 40px / 1.0 | stat values, `IntervalReadout` point |
| `text-h1` | 44px / 1.05 | page titles |
| `text-hero` | clamp(40px, 7vw, 64px) | the Home headline, and nothing else |
| `text-mega` | clamp(56px, 12vw, 112px) | one hero number per page |

The `clamp()` steps are what keep 390px working without responsive variants.

Avoid all caps labels. Avoid accenting one word in a headline in a different color. Avoid arrows glued onto button text. Sentence case everywhere. Numbers are tabular figures so charts and tables do not jitter.

### The 13px exception

Chart axis ticks are 13px, set in `src/lib/chartText.ts`, and this is a decision rather than an oversight. A Y-axis tick is scale furniture, not a sentence: it is read against the line it labels, not on its own. Ticks at 16px eat enough of the plot area to make the chart worse, which is the opposite of what the type floor is for. Tailwind cannot reach a Recharts `fontSize` prop, so the module exists to keep the four chart text roles in one place, and a test asserts nothing under `components/charts/` or `components/figures/` sets a numeric `fontSize` below 13.

## Squishi

A small, round, soft coral blob with a violet face. Squishi squishes: it compresses in proportion to the patient's live contraction. That is the single memorable interaction in the whole product, since your effort deforms the character in real time. Spend the boldness here and keep everything else quiet.

Four expressions by contraction level: resting under 5 percent, working 5 to 40, straining 40 to 80, proud above 80. Proud also fires on rep completion.

### The pose library

`src/components/brand/poses.ts` holds twenty poses as data, not as components, so they can be enumerated and picked by id without rendering anything. Every pose shares one body path and differs only in its arms, its face, and an optional squash transform, which is what keeps the character recognisably the same across all twenty.

The four expressions map onto four poses: resting to `idle`, working to `midSqueeze`, straining to `compressed`, proud to `cheering`. A `pose` prop pins any of the twenty for a still placement that illustrates rather than reports.

### Placement

For a long time fourteen of the twenty were dead code: the library claimed a range of expression the app never used. `poses.coverage.test.ts` now fails if a pose is defined and not placed, so the library cannot drift back out of sync with what ships.

The rule that keeps twenty placements from looking sprayed: **at most one pose per screenful, always anchored to a heading, a state, or a datum, never floating in whitespace.** A pose reaches the page only through `PoseSpot`, which takes one of three roles: page or section header, figure anchor, or an empty, loading or error state.

| Pose | Page | Placement | Role |
|---|---|---|---|
| `waving` | Home, Train | hero beside the headline, profile stage header | greeting, labelled |
| `explaining` | Home, Train | pipeline section header, calibration instructions | section |
| `presenting` | Home, Progress | model grid section header, insights empty state | section, empty |
| `thinking` | Home, Progress | data split figure corner, insights loading state | figure anchor, loading |
| `winking` | Home | CTA corner, bobbing | decorative |
| `encouraging` | Train | calibration prompt | stage |
| `midSqueeze` | Train | live mascot, store driven | live |
| `compressed` | Train | live mascot above 80 percent | live |
| `cheering` | Train | live mascot proud, rep pulse | live |
| `resting` | Train | calibration rest countdown | stage |
| `celebrating` | Train | calibration done, and the session summary | stage |
| `sleeping` | Train | session idle before start, bobbing | empty |
| `flexing` | Progress | page header | page |
| `stretching` | Progress | adherence figure, bobbing | figure anchor |
| `thumbsUp` | Progress | goal ring at 100 percent | conditional, labelled |
| `exhausted` | Progress | fatigue figure | figure anchor |
| `disappointed` | Progress | plateau card when a changepoint exists | conditional, labelled |
| `springingBack` | Progress | insights tab header | section |
| `confused` | Lab, any | settings diagnostics failure, not found page | error, labelled |
| `idle` | Lab | wordmark, footer, watermark, Lab header | furniture |

Three placements are conditional: `thumbsUp`, `disappointed` and `confused`. That is deliberate. They carry meaning rather than decorating, so they take an accessible label instead of `aria-hidden`, and a demo can surface them by driving the data.

### Implementation

The component subscribes to exactly one store selector, the live percent MVC scalar, so mascot re-renders never drag the charts along. That scalar drives Framer Motion scale springs. An optional `value` prop overrides the store so the landing page can drive it from a preview stream.

Two rules the artwork forces:

- Poses carry their own authored squash. The animated branch suppresses it and lets the spring alone scale the character, because applying both compounds the two scales and flattens the blob into a line.
- The animated branch borrows `idle`'s arms. Poses authored at an extreme already fling the arms out flat, and squashing those again turns them into stubs.

Under `prefers-reduced-motion`, the spring is replaced by a discrete four state swap with no continuous animation and no idle bounce.

## Motion

The earlier rule scoped Framer Motion to the mascot alone. That conflated boldness with motion, and the result was a site that read as unfinished: nothing on it moved except one character, so every page felt like a static document with a toy on it.

The rule now:

> **Motion is chrome, never data.** Framer Motion covers the mascot spring, layout transitions between tabs and stages, and scroll reveals. Chart series keep `isAnimationActive={false}`. A chart that grows on load misrepresents its own values for as long as it is growing, and a rehabilitation patient watching a strength number climb from zero on every page load is being told something false for a moment. Squishi stays the only thing whose motion is driven by a live measurement.

What animates:

- the mascot spring, driven by live percent MVC (unchanged)
- 180ms page crossfades through `AnimatePresence`, keyed on the path
- the tab and stage `layoutId` indicators, which is what makes the four route structure legible
- one shot scroll reveals, staggered 60ms
- a mount only count up on `StatTile`
- the goal ring drawing on, ending at the value the data says
- the signal travelling along the pipeline connectors
- three background blobs drifting at unsynced periods
- `active:scale` on buttons, `bob` on decorative poses, and one coral pulse behind the mascot when a repetition closes

Reduced motion: CSS animations are covered by the global block in `index.css`. Framer driven items guard on `useReducedMotion()` and take an explicit `transition={{ duration: 0 }}` rather than relying on that backstop, because Framer animates inline transforms the CSS rule cannot reach.

## Copy voice

Warm, plain, direct. "Squeeze and hold" rather than "Initiate isometric contraction protocol." Clinical terminology lives in the analytics layer where a clinician reads it. The patient layer stays human. Empty states invite action. Errors say what happened and what to do.

## Honesty affordances

These are components, not per page copy, so they cannot be forgotten:

- `SyntheticBadge` renders wherever a record has `is_synthetic` true. It stays visible.
- The demo mode control in the header marks the same fact one level up. See below.
- `IntervalReadout` is the only component allowed to render a prediction, and it requires lower and upper bounds as props. A bare point estimate is therefore a type error rather than a review catch. The bounds are still attached to every number, carried as a `title` and an `.sr-only` span rather than printed beneath it: the requirement is that the uncertainty travels with the estimate, not that it occupies a line of the layout.
- `ClinicalTooltip` reads its term map from `CLINICAL.md`.

The same treatment applies to `KG_ESTIMATE_NOTE`, `PERCENTILE_NOTE` and `NON_GRIP_NOTE`. The constants are unchanged and still render on the element they qualify. `NotAMedicalDevice` remains visible in the footer, because consent references it.

### Demo mode

The backend seeds a synthetic patient at startup and the frontend reads it under a hardcoded id, so for a long time every visitor landed in a fully populated app with no way to tell the history was not theirs and no way out of it. The per record badge was honest about each row, but it labelled data nobody had asked for, and the empty states written for every panel were unreachable in practice.

`src/store/demo.ts` makes that state explicit and reversible:

- It is a client side filter on the `is_synthetic` flag that already rides on every session. Not a refetch, and not a backend change: seeding is untouched, the seeded rows are filtered rather than deleted, and turning demo mode back on restores them immediately.
- It defaults to on and persists to `localStorage`, wrapped in `try/catch` because storage throws outright in a private window rather than returning null. A failure falls back to the default.
- Pages derive from `useVisibleSessions` rather than from `sessions.data`, so one call site filters a whole page.
- Model outputs are computed server side across the seeded history and a client side filter cannot reach inside them, so they are suppressed entirely when demo mode is off and nothing real is left. A forecast fitted on data the reader has just chosen to hide is not their forecast, and showing it would be the exact confusion demo mode exists to remove.

The control sits in the header, borrows `SyntheticBadge`'s shape and diamond so the two read as one system, and collapses to the diamond alone under `sm`. Both stay: a mixed list still needs the per record badge while demo mode is on.

## Accessibility floor

Non-negotiable:

- responsive down to 390px width
- visible keyboard focus on every interactive element
- `prefers-reduced-motion` respected, Squishi stops animating
- AA contrast throughout
- no information conveyed by color alone, so every colored state carries a label or shape as well

### How each one is held

A floor written as a list is a hope. These are the mechanisms behind it.

**390px.** The `clamp()` steps on the type scale mean most of the app needs no responsive variant at all, and every `grid-cols-N` in the codebase already carries one. Two places could not be solved that way. The clinician session log is eight columns needing 46rem, so the four secondary ones drop below `sm` and Status folds into the reps cell rather than disappearing. `ChartFrame` heights `clamp()` down to 62 percent on a narrow screen, because a 340px chart otherwise eats most of a phone. Recharts props cannot read a media query, so `lib/useNarrow.ts` exists for the few values that have to be JavaScript: on `StrengthTrendChart` the Goal and MCID labels move inside the plot below `sm`, returning the 52px right margin that was a fifth of the chart.

**Focus.** One global `:focus-visible` rule, so no component has to remember. It paints a white gap between the ring and the element via `box-shadow`, because the ring is `--squish-500` and so is the fill on the active nav pill, the active tab and every primary button: without the gap, focus is invisible on exactly the controls a keyboard lands on most.

**Getting to the content.** A skip link is the first focusable element in `Layout`, hidden until focused. Without it, reaching the page means tabbing past the wordmark, the demo toggle and four nav links on every route. `Layout.test.tsx` asserts it is the first tab stop and that it points at a `main` that exists.

**Contrast.** `lib/contrast.test.ts`, described above.

**Not by color alone.** The anomaly dots carry "Standout" or "Off pattern" as text, the effort gauge states "On target" or "Below target", and a disabled option in `Select` is struck through as well as dimmed.

Touch targets are 44px: nav pills were about 40.

## Chart conventions

Consistent axes, thin lines, the squish palette, always labeled units, always an empty state. Every chart component accepts loading, error, and empty props so the states pass is mechanical rather than bespoke per chart.
