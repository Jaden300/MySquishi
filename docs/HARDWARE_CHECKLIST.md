# Hardware checklist

Phase 2 bring up: wiring, electrode placement, and the test protocol.

The goal of bring up is to answer one question honestly: **what can this
sensor actually do today?** The probe answers it with a tier, A through D, and
that tier scopes what Phase 3 is allowed to build. A Tier C rig presented as
Tier A is exactly the dishonesty the rest of this project is built to avoid.

Work through this page in order. It takes about fifteen minutes.

## Before you touch anything

> **Set the MyoWare 2.0 output selector to RAW.**

This is the single highest risk setting on the board, and ENV is the factory
default. The analysis chain bandpasses 20-450 Hz, and the ENV output has
already been rectified and smoothed, so nearly all of its energy sits below
20 Hz. Measured through the real filter chain, **under 4 percent of an
envelope survives, against 91 percent of a raw trace.**

The failure is quiet rather than loud. Enough noise survives the bandpass that
rest and contraction still look different, so a naive reading produces a
plausible contrast number and a confident, wrong tier. `tools/probe.py`
detects this and refuses to grade, but finding out costs you a 60 second
recording with electrodes already on your arm. Check the switch first.

## Bill of materials

- MyoWare 2.0 Muscle Sensor
- MyoWare Link Shield, 3.5 mm TRS cable, and Arduino Shield
- Arduino Uno or Nano (ATmega328P, 10 bit ADC)
- 3 disposable Ag/AgCl snap electrodes, **fresh**
- USB data cable, not a charge only one
- Alcohol wipe

Dried out electrodes are the most common cause of a bad first reading. If the
pack has been open for months, that is the first thing to rule out.

## Wiring

```
  MyoWare 2.0  -->  Link Shield  -->  3.5 mm TRS  -->  Arduino Shield  -->  A0
   (RAW mode)                            cable
```

The Arduino Shield seats directly on the Uno headers. Nothing needs soldering
and nothing needs a breadboard. Power the sensor side from a battery if you
can: it removes the mains loop through the USB ground entirely, and it is
often worth a full tier on its own.

## Skin preparation

Signal quality is decided here, more than anywhere else in the chain.

1. Wash the forearm with soap and water. Skip lotion and moisturizer.
2. Wipe the three electrode sites with alcohol.
3. **Let the alcohol dry completely.** Applying electrodes to a damp site
   bridges them electrically and flattens the reading.
4. If the area is hairy, shaving improves contact substantially.

## Electrode placement

The muscles that close the hand are the finger and wrist flexors, on the
palmar side of the forearm: **flexor digitorum superficialis** and **flexor
carpi radialis**. They sit in the upper third of the forearm, roughly a third
of the way from the elbow crease toward the wrist.

Find the belly first. Rest your forearm palm up, then squeeze your hand into a
fist. The muscle that bulges under your fingers about 5 cm below the elbow
crease is the target. Keep a finger there while you place the electrodes.

```
   palm up, left forearm

   ELBOW                                                  WRIST
     |                                                      |
     v                                                      v
    ___________________________________________________________
   /                                                           \
  |     [ E1 ]   [ E2 ]                                  [ REF ] |
  |        \       /                                        |    |
  |         \     /                                         |    |
  |    muscle belly, 2 cm apart,                      ulnar styloid
  |    in line with the fibres                        (the bony lump)
   \___________________________________________________________/

      <-- about 1/3 of the way down from the elbow -->
```

- **E1 and E2** go over the muscle belly, **2 cm apart**, aligned **along** the
  direction of the muscle fibres, which run lengthwise down the forearm. Two
  electrodes placed across the fibres see nearly the same signal and cancel
  most of it out.
- **REF** is the reference and it goes on **bone**, not muscle. The ulnar
  styloid, the bony lump on the pinky side of the wrist, is ideal. Bone is
  electrically quiet, which is the whole point of a reference.

A reference on muscle is the second most common bring up failure after dead
electrodes, and it looks like unstable, drifting garbage rather than an
obvious error.

## Flash the firmware

1. Install the Arduino IDE.
2. Open `firmware/mysquishi_probe.ino`.
3. Tools > Board > Arduino Uno. For a Nano clone that refuses to upload, try
   Processor > ATmega328P (Old Bootloader).
4. Tools > Port, select the board.
5. Upload.
6. Optional sanity check: open the Serial Monitor at **230400** baud. You
   should see a few `#` header lines, then two columns of numbers. Squeeze and
   the right hand column should visibly move.

> **Close the Serial Monitor before running the probe.** It holds the port
> exclusively and the probe will not be able to open it.

## Run the probe

```
cd backend
.venv/bin/pip install -r tools/requirements-probe.txt
.venv/bin/python -m tools.probe
```

Unplug the laptop charger and run on battery. This one step frequently moves
the mains contamination number by a full tier.

The probe talks you through a 60 second protocol:

| Phase | Duration | What you do |
|---|---|---|
| Rest | 10 s | Relax completely, arm supported |
| Light | 5 s | Squeeze at about a quarter effort |
| Rest | 10 s | Relax |
| Hard | 5 s | Squeeze as hard as is comfortable |
| Rest | 10 s | Relax |
| Pulses | 15 s | Three short hard squeezes with releases between |

Follow it as closely as you can, but do not restart if you drift. The three
labelled spans are what unlock the light-versus-hard separability score, and
if the timing is off the probe falls back to a two way split and still
produces a verdict.

The trace is saved to `backend/calibration/probe_<timestamp>.csv` as raw ADC
counts. Keep these. They re grade offline with `--replay`, and they are the
seed corpus for the Phase 3 replay source.

## Reading the verdict

| Tier | Meaning | What Phase 3 may build |
|---|---|---|
| **A** clean | Contraction well above baseline, low mains, no clipping | Rep segmentation, force in kg, spectral fatigue, rep quality |
| **B** usable | Clearly detectable but noisy or drifting | Rep segmentation, force in kg, rep quality. Fatigue is suppressed rather than shown as fact |
| **C** marginal | Barely separable from rest | A live "gripping or not" indicator, nothing quantitative |
| **D** unusable | No detectable contraction, or clipped or dead | Nothing. Run on Simulated |

**Tier D is a supported outcome, not a failure.** The app was built so that
hardware is an enhancement layer and never a dependency, and Simulation Mode
is a permanent first class feature. A demo on Simulated is a demo, not a
fallback.

## Failure modes

| Symptom | Likely cause | Fix |
|---|---|---|
| No serial port listed | Charge only cable, or missing driver | Use a data cable. Nano clones usually need the CH340 driver |
| Port will not open | Serial Monitor still running | Close it |
| Garbage characters in the monitor | Baud mismatch | Set the monitor to 230400 |
| Probe says ENV, not RAW | Output selector in the wrong position | Move it to RAW and re run |
| Tier D, flat trace | Dead or dried electrode, sensor unpowered | Fresh electrodes, check the TRS plug is fully seated |
| Tier D, rail pinned | Gain too high | Turn the gain pot down and re run |
| Heavy mains contamination | Charger plugged in, or mains wiring nearby | Run on battery, move away from power supplies |
| Baseline drifts | Loose or drying electrode | Re seat, or replace |
| Erratic and unstable | Reference on muscle instead of bone | Move REF to the ulnar styloid |
| Achieved rate well below 500 Hz | Serial link struggling | Lower `SAMPLE_HZ` in the sketch to 250. The bandpass clamps automatically |
| Many dropouts | USB hub or long cable | Plug directly into the machine |

## A note on sample rate

The firmware runs at **500 Hz**, not the 1000 Hz the simulated pipeline uses.
A `millis,value` line is 10 to 12 bytes, and at 8N1 framing 115200 baud
carries only about 960 to 1150 lines per second: at or below 1000 Hz with no
headroom, which turns every scheduling hiccup into a dropped sample. Running
at 500 Hz and 230400 baud leaves roughly 4x headroom, so a dropout in the
recording indicates a real problem rather than an arithmetic certainty.

The cost is real and worth stating plainly: Nyquist falls to 250 Hz, so the
250-450 Hz portion of the sEMG band is not observed, and spectral fatigue is
measured over a truncated spectrum. The Python bandpass clamps its upper edge
just below Nyquist automatically, so nothing breaks, but median frequency
estimates from this rig are not directly comparable to textbook values.
