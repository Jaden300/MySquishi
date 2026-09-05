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
