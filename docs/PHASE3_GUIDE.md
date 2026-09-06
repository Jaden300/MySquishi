# Phase 3 implementation guide

How to connect the hardware, scoped to what Phase 2 actually measured. Read
`@docs/HARDWARE_FINDINGS.md` first: it sets the boundaries, and this document
assumes them.

Written so an agent picking this up cold can start without rediscovering
anything.

> **Phase 3 is now built.** This document is kept as the reasoning behind the
> implementation rather than as a plan. Four things in it were wrong and are
> corrected inline below: there were four guard tests rather than two, several
> line numbers had drifted, `probe.py` lives at `backend/tools/`, and there is
> no `POST /api/sessions` at all. See `@docs/TASKS.md` for what shipped.

## Where you are starting from

Phase 1 built the whole app against `SimulatedSource`. Phase 2 graded the rig
at **Tier A** for signal quality and confirmed **three separable effort
levels**, with per finger decoding ruled out.

The hardware boundary already exists and needs no redesign.
`app/sources/base.py` defines `SignalSource` as a structural `Protocol` with
five members: `connect()`, `read_window()`, `sample_rate`, `is_live`,
`disconnect()`. Every consumer depends on that shape alone. `get_source()` at
`base.py:106` is the single construction point in the application.

So Phase 3 is: write two classes, register them in that factory, gate the grip
only clinical claims, and add the muscle selector. Nothing else changes.

## Step 1: SerialSource

New file `app/sources/serial_source.py`, satisfying the Protocol.

Note the guards first. **There are four, not two.** This section originally
said both lived in `app/tests/test_api.py`; two more sit in
`app/tests/test_sources.py`, and all four fail the moment this file is written:

- `test_no_serial_imports` (`test_api.py:32`) scans every `.py` under `app/`
  for a line starting `import serial` or `from serial`
- `test_pyserial_is_not_a_dependency` (`test_api.py:48`) asserts `pyserial` is
  absent from `backend/requirements.txt`
- `test_no_serial_imports_anywhere_in_the_app` (`test_sources.py:149`), a regex
  variant that skips `tests/`
- `test_pyserial_is_not_a_dependency` (`test_sources.py:164`), a near duplicate

Three further tests **invert** rather than simply failing, and need rewriting
rather than narrowing: `test_api.py:207` asserts `"Phase 3"` appears in the
serial error, `test_sources.py:39` asserts `NotImplementedError`, and
`test_sources.py:47` asserts only `simulated` is available.

**Update them, do not delete them.** Narrow the import scan to exclude
`app/sources/serial_source.py` so it still protects the rest of the package,
and replace the dependency assertion with one that pins pyserial deliberately.
The point of both is that hardware code cannot leak in unnoticed, and that
remains worth enforcing after Phase 3 opens the one door it needs.

pyserial is currently a probe only dependency, declared in
`tools/requirements-probe.txt` rather than `requirements.txt`. Phase 3 promotes
it to a real dependency of the app.

```python
class SerialSource:
    def __init__(self, port: str | None = None, baud: int = 230400): ...
    def connect(self) -> bool: ...
    def read_window(self) -> np.ndarray: ...
    @property
    def sample_rate(self) -> int: return 500
    @property
    def is_live(self) -> bool: return True
    def disconnect(self) -> None: ...
```

Constants that must match `firmware/mysquishi_probe.ino`, and a mismatch
produces plausible garbage rather than an error:

- **Baud 230400**, not 115200
- **Sample rate 500 Hz**, not the 1000 Hz the simulated pipeline uses
- Line format `millis,adc_counts`, ASCII, one sample per line
- Lines beginning `#` are the boot header, collect them and skip

`backend/tools/probe.py` already solves every hard part of this (note the path:
`backend/tools/`, not a top level `tools/`). Its `record()` (`probe.py:164`)
handles port opening, buffer reset, header lines, and partial line recovery.
`discover_port()` (`probe.py:115`) auto detects across board types with a
denylist for the permanent macOS ports. **Reuse that logic rather than
rewriting it.**

One caveat on that reuse: `discover_port` prompts on stdin when the answer is
ambiguous and calls `SystemExit` on failure, neither of which can happen inside
a websocket handler. Only the filter and hint logic transfers; the shipped
`list_candidate_ports()` returns candidates and lets the UI ask.

Two things `probe.py` does not do, which `SerialSource` must:

- **Read continuously in a background thread**, buffering into a ring, because
  `read_window()` has to return promptly without blocking on serial
- **Survive unplugging.** A disconnected sensor must degrade visibly through
  the SQI badge rather than crashing the session

Note the sample rate difference. The signal pipeline is parameterised by `fs`
throughout, and the bandpass clamps its upper edge below Nyquist automatically,
so 500 Hz needs no special casing. But **spectral fatigue at 500 Hz observes a
truncated spectrum**: Nyquist is 250 Hz, so the 250-450 Hz portion of the sEMG
band is unobserved and median frequency values are not comparable to textbook
figures. Say so in the UI wherever fatigue is shown.

## Step 2: ReplaySource

Demo insurance, and the reason it matters is that hardware fails during demos.

Reads a CSV from `backend/calibration/` and replays it at wall clock speed
through the identical interface. `is_live` returns **False**, so the honesty
chip correctly shows it is not a live session.

`probe.py:326` already has `load()`, which parses these CSVs including the
`#` header block and the `millis,adc_counts` columns. Reuse it, minus its
`_fail` path: that calls `SystemExit`, which would take down the server rather
than the request.

There are already four real traces in `backend/calibration/` to replay. Record
a clean session while the hardware works and keep it as the demo trace.

## Step 3: The muscle selector

This is the pivot from a grip device to a general strength and fatigue trainer,
and Phase 2 supports it: effort grading and fatigue are not hand specific.

Add a muscle field to the session model: `forearm_grip`, `biceps`, `calf`,
`other`. Default `forearm_grip`, which is also correct for every row recorded
before the selector existed.

**There is no `POST /api/sessions`.** Sessions are created entirely inside the
websocket handler, at `app/api/signal.py:143`, so the muscle threads through
the socket query params rather than a REST body: `signal.py` to
`LiveSessionRunner` to the `Session(...)` construction.

**The gating rule, and it is a clinical requirement rather than a preference:**

| Feature | forearm_grip | Any other muscle |
|---|---|---|
| Force in kg | Yes | **No** |
| EWGSOP2 status | Yes | **No** |
| Population percentile | Yes | **No** |
| %MVC | Yes | Yes |
| Fatigue, median frequency | Yes | Yes |
| Rep counts and timing | Yes | Yes |
| Effort consistency | Yes | Yes |

`app/ml/percentile.py:39` holds the EWGSOP2 thresholds (27.0 kg male, 16.0 kg
female). Those are sarcopenia references validated on **hand dynamometry** and
are meaningless on a biceps or calf. `app/ml/force.py` maps amplitude to
kilograms and that mapping is muscle and person specific. Surfacing either on a
non grip muscle would breach the clinical accuracy rule in `CLAUDE.md`.

Implement the gate in the API layer so it cannot be bypassed by a frontend bug,
and have the response omit the field rather than sending null, so a UI mistake
cannot render a stale value.

**Gating the structured fields is not sufficient on its own.**
`percentile.py:198-206` and `:239-242` embed kilogram figures and EWGSOP2
wording directly into `Explanation.summary`, which the UI renders verbatim at
`ProgressPage.tsx:453` and `InsightsPage.tsx:66`. The shipped gate closes this
by refusing at the endpoint, before `assess()` is ever called, so the prose is
never generated for a non grip muscle. A test asserts no kilogram or EWGSOP2
wording reaches a biceps patient's insights feed.

## Step 4: Per muscle calibration and %MVC

%MVC is what makes the multi muscle pivot honest, and it needs a calibration
step per muscle per user.

Record a maximum voluntary contraction: three maximal efforts, five seconds
each, thirty seconds rest between, take the highest. Store it against the user
and muscle. Every subsequent reading reports as a percentage of it.

Two things this needs that are easy to miss. `Calibration` has **no muscle
column**, and the deactivation logic at `signal.py:91-98` retires *all* active
rows for a patient, so calibrating a biceps would silently clobber the grip
calibration a kilogram estimate depends on. Both are fixed: the column exists
and the deactivation is scoped by muscle.

Also note `Session.strength_kg` was **never written by the live path** before
Phase 3. The only writer was `app/seed.py:278`, and `ForceModel.predict` was
never called in a request path at all, so the percentile endpoints worked only
on seeded demo data. M3 now runs when the session closes, for grip only,
anchored on the hardest window of the session.

**Use the measured effort curve when designing the UI.** From
`@docs/HARDWARE_FINDINGS.md`, the envelope response is strongly non linear:

| Effort | Envelope | Multiple of rest |
|---|---|---|
| Rest | 0.34 | 1.0x |
| ~25% | 0.49 | 1.4x |
| ~50% | 0.98 | 2.9x |
| Maximal | 4.89 | 14.4x |

A linear bar driven by the raw envelope is nearly motionless through the entire
low effort range, which is exactly where a rehab patient works. **Map to
display on a log or square root scale.** This is the single most likely way to
ship something that technically works and feels broken.

Effort targeting is limited to **three levels**. The tightest adjacent pair,
light versus medium, separates at d = 1.54. Ten levels are not supported.

## Step 5: Tune the pipeline, and what not to build

Tier A permits rep segmentation, force regression (grip only), spectral
fatigue, and rep quality scoring.

Do not build, because the measurements rule them out:

- **Per finger decoding.** middle vs ring separated at d = 0.03. Physical
  limit of one differential pair, not a tuning problem
- **Grip versus wrist flexion.** d = 0.12, the same event on this channel
- **More than three effort levels**
- **Kilograms or EWGSOP2 on any non grip muscle**

## Step 6: Register and verify

Add both classes to `get_source()` in `app/sources/base.py:106` and flip
`available` to `True` for `serial` and `replay` in `SOURCE_CATALOGUE`
(`base.py:77`). The settings dropdown picks them up with no further changes.

Then verify the non negotiable still holds: **the app must be fully demoable
with zero hardware attached.** Unplug everything and confirm the whole demo
path runs on Simulated. That constraint outranks every feature in this
document.

## Connecting the sensor: the end user walkthrough

For the instruction page. `@docs/HARDWARE_CHECKLIST.md` is the builder facing
version with tiers and failure modes; this is the shape the shipped page needs,
written for someone who has never seen the kit.

**What connects to what:**

```
  MyoWare 2.0 sensor          (on the muscle, switch set to RAW)
        |
        v  snap connectors
  3 electrodes                (2 on the muscle belly, 1 on nearby bone)
        |
        v  Link Shield
  3.5 mm TRS cable
        |
        v
  Arduino Shield              (seats on the Uno headers, no soldering)
        |
        v  pin A0
  Arduino Uno
        |
        v  USB data cable, not a charge only cable
  Computer
        |
        v  serial, 230400 baud
  MySquishi                   (Settings > Source > Live sensor)
```

The page should walk these steps in order:

1. **Set the output selector to RAW.** ENV is the factory default and it is
   wrong for this pipeline. Highest risk setting on the board, so put it first
   and make it visually prominent
2. **Stack the hardware** in the order above. Push the TRS plug fully in until
   it clicks
3. **Prepare the skin.** Wash, wipe with alcohol, let it dry completely. A damp
   site bridges the electrodes and flattens the reading
4. **Place the electrodes.** Two over the muscle belly **2 cm apart, aligned
   along the fibre direction**, one on nearby bone as reference. Include a
   diagram per supported muscle, since placement decides signal quality more
   than anything else in the chain
5. **Plug in over USB** and select the port. Nano clones usually need the CH340
   driver
6. **Pick the muscle** in the app, so the correct metrics are shown
7. **Calibrate**, three maximal efforts, to establish %MVC
8. **Start a session**

Design notes for that page:

- **A live signal preview during setup** is the highest value element. Someone
  who can see the trace move when they squeeze knows immediately that it works,
  and no amount of prose substitutes
- Surface the failure table from `@docs/HARDWARE_CHECKLIST.md` inline: no port
  listed means a charge only cable, garbage characters mean a baud mismatch, a
  flat trace means dead electrodes, erratic and drifting means the reference is
  on muscle instead of bone
- Say plainly that **the app works fully without any hardware.** Simulation
  Mode is a first class feature, not a fallback, and that is a selling point
  rather than an apology
