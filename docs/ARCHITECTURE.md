# Architecture

System design, the `SignalSource` boundary, and the module layout.

## Shape

```
React + Vite + TypeScript + Tailwind (frontend)
Recharts . Framer Motion (Squishi only) . Zustand
                  |
                  |  REST (sessions, history, ML) + WebSocket (live stream)
                  |
FastAPI (Python) backend
  /signal    ingestion, filtering, feature extraction
  /ml        M1-M14 inference and training
  /sessions  CRUD, aggregation
  /export    CSV now, PDF in Phase 4
SQLite via SQLModel . scikit-learn . SciPy . NumPy
                  |
                  |  SignalSource interface  <- THE HARDWARE BOUNDARY
                  |
    SimulatedSource      SerialSource       ReplaySource
    (synthetic gen)      (real MyoWare)     (recorded csv)
    Phase 1              Phase 3            Phase 3
```

## The hardware boundary

`SignalSource` is the most important design decision in the project. It is a structural Protocol, declared in `backend/app/sources/base.py`:

```python
@runtime_checkable
class SignalSource(Protocol):
    def connect(self) -> bool: ...
    def read_window(self) -> np.ndarray: ...
    @property
    def sample_rate(self) -> int: ...
    @property
    def is_live(self) -> bool: ...
    def disconnect(self) -> None: ...
```

Because it is structural, Phase 3 added `SerialSource` and `ReplaySource` by registering them in the factory. No base class changes, no edits to any consumer. That is the whole payoff of the design: the hardware arrived and the boundary did not move.

Nothing in the codebase constructs a source directly. Everything goes through `get_source(source_id)` in the same module.

`is_live` is what drives the "Simulated" chip in the UI. The honesty label derives from the source object, never from page copy, so a source cannot be shown dishonestly.

**Serial code is confined to one module.** `backend/app/sources/serial_source.py` is the only file permitted to import pyserial, and four guard tests across `test_api.py` and `test_sources.py` fail the suite if `serial` appears anywhere else under `backend/app`. The import is deferred inside a function, so a missing driver surfaces when a live session is requested rather than breaking application import: the zero hardware demo path never depends on it.

## Streaming contract

**Sample rate is per source, not global.** The simulator runs 200 samples at 1000 Hz; the live sensor runs 100 at 500 Hz. Both are 200 ms, so the socket carries **5 frames per second** either way, and every consumer reads `fs` off the frame rather than assuming a constant. The DSP is parameterised by `fs` throughout and the bandpass clamps its upper edge below Nyquist automatically, so 500 Hz needs no special casing.

One consequence worth stating: at 500 Hz, Nyquist is 250 Hz, so the 250-450 Hz part of the sEMG band is unobserved and median frequency values are **not comparable to published figures**. The within session trend, which is what fatigue actually measures, holds regardless. The UI says so wherever fatigue is shown on a live session.

Endpoint: `ws://localhost:8000/api/signal/live?source=simulated&patient_id=demo&session_id=<id>&muscle=forearm_grip`

The client sends only `start`, `stop`, and `pause`. The server frame carries:

| Field | Meaning |
|---|---|
| `type` | `frame` or `summary` |
| `t`, `seq`, `fs` | seconds since start, frame counter, sample rate |
| `raw` | decimated to 100 points for transport |
| `envelope` | 20 points, one per 10 ms |
| `mvc_pct` | percent of maximum voluntary contraction |
| `sqi` | M1 signal quality, recomputed per frame |
| `is_live`, `source_id` | honesty metadata |
| `muscle` | which muscle is being trained, and so which claims are valid |
| `rep_event` | null, or index, peak, quality, factor on a newly closed rep |
| `coach` | phase, seconds remaining, prompt text |

`mvc_pct` is computed server side from the active calibration. The frontend never divides, so there is exactly one definition of percent MVC in the system.

Rep detection runs incrementally over a rolling envelope buffer and emits `rep_event` only on newly closed reps. M4 scores that rep synchronously, since it is a single tree predict, so timeline blocks color the instant they appear.

On `stop` the server persists the session and its reps, runs M3, M5 and M6, sends one `summary` frame, and closes. Everything else is REST. The socket carries frames, not queries.

## The clinical gate

`backend/app/clinical_gate.py` decides which claims are honest for which muscle, and it is a clinical requirement rather than a preference.

Phase 2 found that effort grading and fatigue are properties of motor unit recruitment, so they generalize to any skeletal muscle. Kilograms do not: `app/ml/force.py` fits a mapping specific to one muscle on one person, and the EWGSOP2 thresholds in `app/ml/percentile.py` are sarcopenia references validated on hand dynamometry. Reporting either against a biceps or a calf would be a false clinical claim.

| Claim | forearm_grip | Any other muscle |
|---|---|---|
| Force in kilograms | yes | **no** |
| EWGSOP2 status | yes | **no** |
| Population percentile | yes | **no** |
| Percent MVC | yes | yes |
| Fatigue, median frequency | yes | yes |
| Rep counts and timing | yes | yes |

Two implementation rules make this hold:

**Omit, do not null.** A null field still occupies the response, and a UI that rendered a stale value into it would be making the claim anyway. `SessionSummaryOut` drops `strength_kg` from its serialization entirely on a non grip muscle, so an absent key cannot be rendered at all.

**Gate before the prose is generated.** `percentile.py` embeds kilogram figures and EWGSOP2 wording inside `Explanation.summary`, which the UI renders verbatim. Gating structured fields alone would leak that text, so the percentile endpoint refuses before `assess()` is ever called. A test asserts no kilogram or EWGSOP2 wording reaches a non grip patient's insights feed.

Calibration is held one row per patient per muscle, since a maximum voluntary contraction belongs to the muscle as well as the person.

## Module layout

```
backend/app/
  main.py config.py db.py models.py schemas.py seed.py
  sources/   base.py simulated.py
  signal/    filters.py features.py segmentation.py
  sim/       signal_gen.py cohort_gen.py
  ml/        registry.py explain.py + one module per model family
  api/       signal.py sessions.py patients.py ml.py cohort.py export.py
  export/    report.py csv_export.py
  tests/
frontend/src/
  lib/ types/ store/ components/ pages/
```

Storage lives under `backend/data/`, all gitignored: `mysquishi.db`, `models/*.joblib` plus `manifest.json`, and `cohort/` plus its manifest.

## Toolchain

`python3` on PATH resolves to a conda environment that is **not** this project's. Build the virtual environment from the framework Python by absolute path:

```
/usr/local/bin/python3 -m venv backend/.venv
```

Then use absolute `backend/.venv/bin/python` and `backend/.venv/bin/pip` in every command. A bare `python` or `pip` silently installs into the conda environment and the venv will appear mysteriously broken.

## Design rules that constrain the code

- Every predictive endpoint returns an `Interval`, never a float. No bare point estimates.
- `is_synthetic` on a record drives a visible badge. Synthetic data is labeled in the UI.
- Session summary statistics are denormalized onto the `Session` row rather than recomputed from reps per request. That is what keeps the dashboard fast.
