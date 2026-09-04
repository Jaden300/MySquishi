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

Because it is structural, Phase 3 adds `SerialSource` by registering it in the factory. No base class changes, no edits to any consumer.

Nothing in the codebase constructs a source directly. Everything goes through `get_source(source_id)` in the same module.

`is_live` is what drives the "Simulated" chip in the UI. The honesty label derives from the source object, never from page copy, so a source cannot be shown dishonestly.

**Phase 1 rule: no serial-port code exists.** `backend/app/tests/test_api.py::test_no_serial_imports` fails the suite if `serial` appears anywhere under `backend/app`. This makes the Phase 2 hard stop enforced rather than remembered.

## Streaming contract

Sample rate is 1000 Hz. The analysis window is 200 samples (200 ms), non-overlapping, so the socket carries **5 frames per second**.

Endpoint: `ws://localhost:8000/api/signal/live?source=simulated&patient_id=demo&session_id=<id>`

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
| `rep_event` | null, or index, peak, quality, factor on a newly closed rep |
| `coach` | phase, seconds remaining, prompt text |

`mvc_pct` is computed server side from the active calibration. The frontend never divides, so there is exactly one definition of percent MVC in the system.

Rep detection runs incrementally over a rolling envelope buffer and emits `rep_event` only on newly closed reps. M4 scores that rep synchronously, since it is a single tree predict, so timeline blocks color the instant they appear.

On `stop` the server persists the session and its reps, runs M5 and M6, sends one `summary` frame, and closes. Everything else is REST. The socket carries frames, not queries.

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
