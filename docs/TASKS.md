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
- [ ] `SignalSource` Protocol defined (the hardware boundary)
- [ ] `SimulatedSource` - synthetic EMG generator (`sim/signal_gen.py`)
- [ ] `sim/cohort_gen.py` - 200-400 synthetic patients, 6-14 weeks each
- [ ] `signal/filters.py` - bandpass, notch, rectification, RMS envelope
- [ ] `signal/features.py` - time- and frequency-domain features

### ML stack (M1-M14: see `@docs/ML.md`)
- [ ] M1 Signal Quality Index
- [ ] M2 Rep segmentation (everything downstream depends on this)
- [ ] M3 EMG → force regression
- [ ] M4 Rep quality scorer
- [ ] M5 Spectral fatigue estimator
- [ ] M6 Session anomaly detection
- [ ] M7 Perceived vs. actual effort
- [ ] M8 Adaptive session prescriber
- [ ] M9 Recovery trajectory forecasting (headline)
- [ ] M10 Time-to-goal estimator
- [ ] M11 Plateau / changepoint detection
- [ ] M12 Recovery archetype clustering
- [ ] M13 Adherence / dropout risk
- [ ] M14 Cohort percentile normalization
- [ ] Explainability layer - every surfaced output has a "why"

### Frontend
- [ ] `SquishiMascot` - contraction-driven, reduced-motion aware
- [ ] Live session view (charts 1-7)
- [ ] Session summary (charts 8-12)
- [ ] Progress dashboard (charts 13-21)
- [ ] Clinician view (charts 22-23)
- [ ] Insights page with `WhyThis` drawers
- [ ] Onboarding + calibration flows
- [ ] Settings (source selector, diagnostics, export/delete)
- [ ] Responsible AI / About page
- [ ] Empty, loading, and error states everywhere

## Phase 2: 🛑 HARD STOP: hardware bring-up with the builder

**Do not proceed past this line autonomously.**

- [ ] `firmware/mysquishi_probe.ino` - analog read + serial print only
- [ ] `tools/probe.py` - standalone 60s diagnostic, prints tier verdict A/B/C/D
- [ ] `docs/HARDWARE_CHECKLIST.md` - placement, prep, wiring, failure modes, test protocol
- [ ] **Builder runs the probe and reports the observed tier**

## Phase 3: Connect hardware, scaled to the observed tier

- [ ] `SerialSource` behind the same interface
- [ ] Signal pipeline tuned to the observed tier
- [ ] Graceful, *visible* degradation via the SQI badge
- [ ] `ReplaySource` + **record a good real session while hardware works** (demo insurance)

## Phase 4: Polish, stretch, submission

- [ ] Seeded demo account - app looks lived-in on first click
- [ ] PDF + CSV clinician report export
- [ ] Mobile layout, keyboard nav, AA contrast pass
- [ ] README with architecture diagram + screenshots
- [ ] 90-second demo path rehearsed twice, including the hardware-fails path

### Stretch (only if 1-3 are genuinely finished)
- [ ] Clinician share link (read-only token)
- [ ] Session replay scrubber
- [ ] Bilateral comparison
- [ ] Voice coaching
- [ ] LLM weekly summary, grounded strictly in computed metrics
- [ ] Squishi grip-driven game mode
