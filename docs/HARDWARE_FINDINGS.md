# Hardware findings

What the rig can actually do, measured on 2026-09-05. This is the Phase 2
deliverable: the honest answer to "what can this sensor do today", and the
scope it sets for Phase 3.

Every number here comes from traces in `backend/calibration/`. Nothing is
estimated. Re grade any of them offline with `--replay`, no hardware needed.

## The verdict in one paragraph

The rig resolves **how hard a muscle is working** and cannot resolve **which
motion produced it**. Effort separates cleanly across three levels. Individual
fingers do not separate at all. Because effort is what survives, and effort is
not specific to the hand, the same sensor and the same analysis generalize to
any skeletal muscle you can place electrodes over: forearm, biceps, calf.

That is the product: a strength and fatigue trainer for **any muscle**, not a
grip specific device and not a gesture recognizer.

## Signal quality

From `probe_20260905_212517.csv`, a 13 s free run.

| Measure | Value | Reading |
|---|---|---|
| Tier | **A, clean** | Top grade |
| Resting baseline | 510.7 ADC counts, sd 0.45 | Mid rail on a 10 bit ADC, as it should be |
| Contrast, rest to contraction | **33.8x** | Tier A needs 5x |
| Output mode | raw, 98% of AC power above 20 Hz | Confirms the selector is on RAW, not ENV |
| ADC clipping | 0.00% | Peak 562 against a 1023 ceiling, ample headroom |
| Baseline drift | 0.00x RMS | Electrodes fresh and well adhered |
| Mains contamination | 4.8% of band power | Charger unplugged. Rises to ~8% when plugged in |
| Dropouts | 4.69% | Acceptable, under the 5% threshold |

Do not touch the gain pot. Headroom is healthy and raising gain only risks
clipping on a harder contraction.

## Effort levels: the numbers

From `probe_20260905_214205.csv`, the gesture survey. Values are the mean
rectified envelope after the standard 20-450 Hz bandpass, in the same units
`tools/probe.py` reports. **These are envelope units, not volts and not
kilograms.**

| State | Envelope level | Multiple of rest |
|---|---|---|
| **Rest** | **0.34** | 1.0x |
| **Light, ~25% effort** | **0.49** | **1.4x** |
| **Medium, ~50% effort** | **0.98** | **2.9x** |
| **Hard, maximal** | **4.89** | **14.4x** |

The response is strongly non linear. Going from rest to a quarter effort moves
the number very little (0.34 to 0.49), while the last step from half to maximal
nearly quintuples it (0.98 to 4.89). This matters for UI design: a linear bar
driven by raw envelope will look dead through the entire low effort range,
which is exactly the range a rehab patient works in. **Map effort to display on
a log or square root scale, or calibrate per user against their own maximum.**

Separability between levels, as Cohen's d over the pooled spread:

| Pair | d | Reading |
|---|---|---|
| light vs medium | **1.54** | Usable, the tightest real pair |
| medium vs hard | **3.56** | Clean |
| light vs hard | 4.13 | Clean |

Below 1.0 two levels overlap and no classifier separates them. The worst
adjacent pair is 1.54, so **three effort levels are defensible**. Do not claim
finer gradation than three without evidence: nothing here supports ten levels.

## What does not work

**Individual fingers do not decode.** All four finger curls produced real
signal against rest (d = 4.59 to 6.21), so the poses were performed correctly.
They simply are not distinguishable from each other:

| Pair | d | Reading |
|---|---|---|
| **middle vs ring** | **0.03** | Statistically identical |
| index vs middle | 1.38 | Amplitude difference, not identity |
| index vs ring | 1.50 | Amplitude difference, not identity |

Levels sit at index 1.33, middle 1.77, ring 1.78, little 0.63. What varies
across these poses is how hard the finger was pressed, not which finger moved.

The cause is physical, not a tuning problem. The finger compartments of flexor
digitorum superficialis sum into a single differential electrode pair. Decoding
per finger needs an **8 to 16 channel array** around the forearm plus a trained
classifier. It is not reachable by improving placement or filtering on one
channel. **Do not build per finger features.**

**Hard grip and wrist flexion are the same event**: d = 0.12, levels 4.89 and
4.73. Wrist flexion recruits the same flexor mass. One channel cannot tell a
grip from a wrist curl, so do not offer a UI that claims to.

**Pinch is distinguishable from a hard grip** (d = 3.14, level 1.51), but only
because it is weaker, not because the channel recognizes the gesture. It sits
between medium and hard effort and any equally moderate contraction looks the
same.

## Generalizing to other muscles

The MyoWare documentation supports placement on other muscle groups, and
nothing in this signal chain is hand specific. The two findings that survive,
**effort grading** and **fatigue**, are properties of motor unit recruitment
and apply to any skeletal muscle.

Expect biceps and calf to read **better** than the forearm did. Both are larger
muscles with more motor units under the electrode, so contrast should meet or
exceed the 33.8x measured here. Re run `tools/probe.py` on each new site to
confirm rather than assuming.

Placement rules carry over unchanged: two electrodes over the muscle belly
**2 cm apart, aligned along the fibre direction**, and the reference on nearby
bone. For biceps the fibres run along the upper arm and the reference goes on
the elbow or acromion; for calf the fibres run down the gastrocnemius and the
reference goes on the ankle bone. See `@docs/HARDWARE_CHECKLIST.md`.

### The clinical constraint, and it is a hard one

**Kilograms and population percentiles are valid for grip only.**

`app/ml/percentile.py` carries the EWGSOP2 low grip strength thresholds
(27.0 kg male, 16.0 kg female). Those are sarcopenia screening references
validated on **hand dynamometry**. They are meaningless on a biceps or a calf.
`app/ml/force.py` maps sEMG amplitude to kilograms, and that mapping is
specific to both the muscle and the person.

So on any non grip muscle, the app must not display kilograms, EWGSOP2 status,
or population percentile. Doing so would breach the clinical accuracy rule in
`CLAUDE.md`.

What **is** honest on any muscle:

- **Percent of that person's own maximum (%MVC)**, the standard normalization
  in surface EMG, and it sidesteps the calibration problem entirely
- **Fatigue via median frequency decline**, muscle independent and supported at
  Tier A
- **Effort consistency across reps**, and **time under tension**
- **Rep counts and rep timing**

## What Phase 3 may build

Tier A on signal quality, with effort confirmed separable at three levels:

- Rep segmentation
- Force regression in kg, **grip only**, gated on the selected muscle
- Spectral fatigue via median frequency shift
- Rep quality scoring
- Three level effort targeting, light / medium / hard
- %MVC for every muscle, after a per muscle calibration

Explicitly out of scope, because the data does not support it:

- Per finger decoding, at any tier
- Distinguishing grip from wrist flexion
- More than three effort levels
- Kilograms or EWGSOP2 status on any muscle other than grip

## Note on the two Tier C runs

`probe_20260905_212734.csv` and `probe_20260905_212947.csv` both graded **Tier
C** with separability 0.8 and 0.5, which would have forbidden force regression.
Both were protocol artifacts, not hardware limits.

The graded protocol prints each prompt and begins timing in the same instant,
so the seconds spent reading land inside the measured window. On a 5 s window
that is a large fraction. Inspecting the traces showed contractions starting
1-2 s late and, in the light phase, lasting about 1 s inside a 5 s window. The
grader averaged mostly rest and correctly concluded the levels overlapped. A
third factor: maximal grip fell 10.99 to 6.43 to 4.07 across three runs in four
minutes, which is ordinary fatigue.

`tools/gestures.py` fixes this with a countdown before each window, 8 s holds,
and 1.5 s trimmed from each end. Under that protocol the same rig separated
effort cleanly. **When a bring up result disagrees with a free run on the same
hardware, suspect the protocol before the sensor.**

The recorded tier for signal quality is **A**. The Tier C runs are retained in
`backend/calibration/` as evidence rather than deleted.
