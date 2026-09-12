# Tasks

Checkbox board. Update as work completes. Grouped by build phase - phases are ordered and **must not be reordered**.

## Phase 0: Scaffolding

- [x] Create `docs/` structure and workflow conventions
- [x] `.gitignore` (plan file kept private)
- [x] `git init` + first commit
- [x] FastAPI backend skeleton + SQLite via SQLModel
- [x] React + Vite + TS + Tailwind frontend skeleton
- [x] Design tokens wired into Tailwind config

## Phase 1: Everything in software, no hardware

**Exit criterion: a stranger can open the app and run a complete session with nothing plugged in.**

### Signal layer
- [x] `SignalSource` Protocol defined (the hardware boundary)
- [x] `SimulatedSource` - synthetic EMG generator (`sim/signal_gen.py`)
- [x] `sim/cohort_gen.py` - 200-400 synthetic patients, 6-14 weeks each
- [x] `signal/filters.py` - bandpass, notch, rectification, RMS envelope
- [x] `signal/features.py` - time- and frequency-domain features

### ML stack (M1-M14: see `@docs/ML.md`)
- [x] M1 Signal Quality Index
- [x] M2 Rep segmentation (everything downstream depends on this)
- [x] M3 EMG → force regression
- [x] M4 Rep quality scorer
- [x] M5 Spectral fatigue estimator
- [x] M6 Session anomaly detection
- [x] M7 Perceived vs. actual effort
- [x] M8 Adaptive session prescriber
- [x] M9 Recovery trajectory forecasting (headline)
- [x] M10 Time-to-goal estimator
- [x] M11 Plateau / changepoint detection
- [x] M12 Recovery archetype clustering
- [x] M13 Adherence / dropout risk
- [x] M14 Cohort percentile normalization
- [x] Explainability layer - every surfaced output has a "why"

### Frontend
- [x] `SquishiMascot` - contraction-driven, reduced-motion aware
- [x] Live session view (charts 1-7)
- [x] Session summary (charts 8-12)
- [x] Progress dashboard (charts 13-21)
- [x] Clinician view (charts 22-23)
- [x] Insights page with `WhyThis` drawers
- [x] Onboarding + calibration flows
- [x] Settings (source selector, diagnostics, export/delete)
- [x] Responsible AI / About page
- [x] Empty, loading, and error states everywhere

## Phase 2: 🛑 HARD STOP: hardware bring-up with the builder

**Do not proceed past this line autonomously.**

- [x] `firmware/mysquishi_probe.ino` - analog read + serial print only
- [x] `tools/probe.py` - standalone 60s diagnostic, prints tier verdict A/B/C/D
- [x] `docs/HARDWARE_CHECKLIST.md` - placement, prep, wiring, failure modes, test protocol
- [x] `tools/gestures.py` - structured pose survey, held windows with countdowns
- [x] **Builder runs the probe and reports the observed tier: A**
- [x] `docs/HARDWARE_FINDINGS.md` - measured numbers and what they rule in and out

## Phase 3: Connect hardware, scaled to the observed tier

Tier A. Full scope and step by step in `@docs/PHASE3_GUIDE.md`.

- [x] `SerialSource` behind the same interface (500 Hz, 230400 baud, background reader)
- [x] Update the Phase 2 guard tests, do not delete them. There were **four**, not two: two in `app/tests/test_api.py` and two more in `app/tests/test_sources.py`. All four narrowed to permit `app/sources/serial_source.py` alone
- [x] `ReplaySource`, replaying the four Phase 2 traces in `backend/calibration/`. `probe_20260905_214205.csv` is committed as the demo trace so replay works on a fresh clone
- [x] Signal pipeline tuned to Tier A: rep segmentation, force regression, spectral fatigue, rep quality
- [x] Graceful, *visible* degradation via the SQI badge. An unplugged sensor pads to a flat window rather than raising, so the badge collapses instead of the session
- [x] **Muscle selector** (forearm_grip / biceps / calf / other) on the session model
- [x] **Gate kg, EWGSOP2 and percentile to forearm_grip only**, enforced in the API layer. Fields are omitted rather than nulled, and the percentile prose is gated at its source so no kilogram figure reaches a non grip muscle
- [x] Per muscle MVC calibration, and %MVC reporting for every muscle
- [x] Effort mapped to display on a sqrt scale, three levels only (`frontend/src/lib/effort.ts`)
- [x] **Instruction page**: how to connect the sensor, with a live signal preview. Was `/connect`; now the Hardware tab of `/lab` after the frontend revamp collapsed eleven routes to four

Two things Phase 3 fixed that were not on this list:

- [x] `Session.strength_kg` was never written by the live path, only by the seeder. M3 now runs on close, for grip only
- [x] Session duration used the global window size rather than the source's own, so a 500 Hz session reported double its real length

Still open, needs the sensor attached:

- [ ] Record a fresh demo trace while the hardware is connected. The Phase 2 traces work, but a purpose recorded clean session is better insurance
- [ ] Re run `tools/probe.py` on biceps and calf to confirm the tier there, rather than assuming it carries over from the forearm

## Phase 4: Polish, stretch, submission

- [x] Seeded demo account - app looks lived-in on first click. Existed already,
      but anchored its date shift to the last *prescribed* session, so a
      programme ending on misses opened on a patient who looked lapsed. Now
      anchored to the last completed session, with patient selection preferring
      gaps spread through the programme, and the newest three sessions carry
      real repetitions
- [x] PDF + CSV clinician report export. The clinical gate is applied per
      session, so kg never appears against a non grip muscle. `muscle` and
      `quality_top_factor` added to the CSV columns
- [x] Mobile layout, keyboard nav, AA contrast pass. Four palette tokens were
      under AA and are darkened, enforced now by `lib/contrast.test.ts`. Skip
      link added, focus ring made visible on filled controls, and the header
      overflowed 390px by 51px until the demo toggle and nav pills were
      tightened
- [x] README with architecture diagram + screenshots. Mermaid diagram, four
      captures, regenerated by `backend/tools/screenshots.py`
- [ ] 90-second demo path rehearsed twice, including the hardware-fails path

### Stretch (only if 1-3 are genuinely finished)
- [ ] Clinician share link (read-only token)
- [ ] Session replay scrubber
- [ ] Bilateral comparison
- [ ] Voice coaching
- [ ] LLM weekly summary, grounded strictly in computed metrics
- [ ] Squishi grip-driven game mode

## Extensions (independent, none required)

See §15 of `MySquishi_Plan.md`.

- [ ] Mascot: animated Squishi driven by the live signal, frontend only
- [ ] AI/ML layer beyond M1-M14, capability to be scoped before building
- [ ] Camera detector: MediaPipe Hands, 21 landmarks at 30fps, browser only
