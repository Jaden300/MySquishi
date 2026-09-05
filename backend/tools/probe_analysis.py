"""Tier analysis for the Phase 2 hardware probe.

This module is deliberately **pure**: it takes an array of raw samples and
returns a verdict. It opens no serial port, reads no device, and holds no
application state. All of the judgement in the probe lives here, which is what
makes the judgement testable with no hardware attached.

It does import the app's own filter chain and feature extractor, and that is
on purpose. The probe has to report the numbers the app will *actually* see.
Reimplementing the filters here would let the two drift apart, and a tier
verdict computed from a different pipeline than the one that runs in
production is a fiction. `tools/probe.py` is the real boundary: it is the only
module that touches a serial port.

That split matters: on bring up day the builder gets one shot at a working
rig, and a bug in the verdict logic is the worst possible time to discover it.
Here it is covered by tests against synthetic signals whose tier is known in
advance, in `tools/tests/test_probe_analysis.py`.

## The tiers

The probe answers one question: **how good is this rig, really?** The answer
scales what Phase 3 is allowed to promise.

- **Tier A, clean.** Real contraction visible well above baseline, mains
  contamination low, no clipping. The full pipeline is justified: rep
  segmentation, force regression, spectral fatigue.
- **Tier B, usable.** Contraction clearly detectable but the signal is noisy
  or drifting. Amplitude features are trustworthy; spectral features are not.
  Fatigue estimates get suppressed rather than shown as fact.
- **Tier C, marginal.** Contraction only barely separable from rest. Nothing
  beyond a binary "gripping or not" indicator can be honestly displayed.
- **Tier D, unusable.** No detectable contraction, or the input is clipped or
  dead. The demo runs on Simulated and the hardware stays unplugged.

The point of grading rather than passing or failing is that a mediocre rig is
still worth something, but only if the app narrows its claims to match. A
Tier C rig presented as Tier A is exactly the dishonesty the rest of this
project is built to avoid.

## Why the output mode is checked before anything else

The MyoWare 2.0 has an output selector: ENV, RECT, and RAW. **ENV is the
factory default and it is the wrong one for this pipeline.** An envelope has
already been rectified and smoothed, so nearly all of its energy sits below
20 Hz, and `preprocess()` bandpasses 20-450 Hz. Measured on a synthetic
envelope, under 4 percent of the signal survives that filter, against 91
percent for a true raw trace.

The failure is quiet, which is what makes it dangerous. Enough noise survives
the bandpass that rest and contraction still differ, so a naive read produces
a plausible contrast number and a confident, wrong tier. So the probe
estimates how much power lives above the bandpass corner and refuses to grade
an envelope above Tier C, which is the honest ceiling for a signal that can
only answer "gripping or not".
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace

import numpy as np

from app.signal.features import window_features
from app.signal.filters import BAND_LOW_HZ, preprocess

# Window length used to walk the recording, in milliseconds. Matches the live
# pipeline's analysis window so the numbers the probe reports are the numbers
# the app will actually see.
WINDOW_MS = 200.0

# Thresholds separating the tiers.
#
# Contrast is the ratio of contraction amplitude to resting amplitude. It is
# the single most important number: below roughly 2x there is no reliable way
# to tell a grip from a twitch of the cable.
CONTRAST_CLEAN = 5.0
CONTRAST_USABLE = 3.0
CONTRAST_MARGINAL = 1.8

# Fraction of total band power sitting at mains. Above the clean bar the
# spectral features that M5 depends on stop meaning anything.
MAINS_CLEAN = 0.10
MAINS_USABLE = 0.30

# Fraction of samples pinned at an ADC rail. Any real clipping is
# disqualifying: a clipped peak is an unknown peak.
SATURATION_LIMIT = 0.02

# Baseline drift, normalized to RMS. Sustained drift means a loose electrode
# or a warming contact, and it corrupts amplitude comparisons across a session.
DRIFT_USABLE = 1.5

# Fraction of AC power sitting above the bandpass corner, used to tell a raw
# sEMG trace from an already smoothed envelope. Real sEMG puts most of its
# power in the 20-450 Hz band; an envelope puts almost none there. The gap
# between the two bars is wide on purpose: anything landing in the middle is
# reported as suspect rather than silently guessed at.
HF_RAW_FLOOR = 0.35
HF_ENV_CEILING = 0.10

# Fraction of expected samples missing from the serial link. Occasional
# dropouts are survivable; a link losing this many samples cannot support
# timing sensitive work like rate of force development.
DROPOUT_USABLE = 0.05

# How far below the configured rate the measured rate may fall before the
# spectral band is too truncated to trust.
RATE_TOLERANCE = 0.8

# Separability between adjacent effort levels, in pooled standard deviations.
# Below the usable bar, light and hard contractions overlap enough that a
# force regression would be fitting noise.
SEPARABILITY_CLEAN = 1.5
SEPARABILITY_USABLE = 0.8

# ADC codes for a 10 bit converter. Real clipping means samples pinned at a
# literal rail, which is a different question from the scale relative
# saturation that window_features reports.
ADC_MIN = 0
ADC_MAX = 1023

TIER_LABELS: dict[str, str] = {
    "A": "clean",
    "B": "usable",
    "C": "marginal",
    "D": "unusable",
}

# What Phase 3 may switch on at each tier. The probe prints this so the
# builder leaves bring up knowing what the rig actually supports.
TIER_CAPABILITIES: dict[str, tuple[str, ...]] = {
    "A": (
        "rep segmentation",
        "force regression in kg",
        "spectral fatigue",
        "rep quality scoring",
    ),
    "B": (
        "rep segmentation",
        "force regression in kg",
        "rep quality scoring",
    ),
    "C": ("live contraction indicator only",),
    "D": (),
}


@dataclass(frozen=True)
class ProbeMetrics:
    """The measured properties of a recording, before any judgement.

    Everything below `snr_estimate` is optional and defaults to a neutral
    value. Those fields need information only the acquisition shell has, such
    as arrival timestamps and unscaled ADC counts. Callers holding nothing but
    an array of samples still get a gradeable set of metrics, and the
    corresponding checks in `grade()` sit out rather than firing on a default.
    """

    n_samples: int
    duration_s: float
    sample_rate: int
    rest_rms: float
    active_rms: float
    contrast: float
    mains_ratio: float
    saturation_ratio: float
    baseline_drift: float
    snr_estimate: float

    # Link integrity, from the arrival timestamps. None when not measured.
    measured_sample_rate: float | None = None
    dropout_ratio: float = 0.0

    # True rail pinning, from unscaled ADC counts. None when not measured.
    adc_saturation_ratio: float | None = None

    # Output mode detection. See the module docstring.
    hf_ratio: float | None = None
    output_mode: str = "unknown"

    # Three way effort separation. Populated only by measure_phases().
    light_rms: float | None = None
    hard_rms: float | None = None
    separability: float | None = None

    def to_dict(self) -> dict[str, object]:
        out: dict[str, object] = {
            "n_samples": self.n_samples,
            "duration_s": round(self.duration_s, 2),
            "sample_rate": self.sample_rate,
            "rest_rms": round(self.rest_rms, 6),
            "active_rms": round(self.active_rms, 6),
            "contrast": round(self.contrast, 2),
            "mains_ratio": round(self.mains_ratio, 4),
            "saturation_ratio": round(self.saturation_ratio, 4),
            "baseline_drift": round(self.baseline_drift, 3),
            "snr_estimate": round(self.snr_estimate, 2),
            "dropout_ratio": round(self.dropout_ratio, 4),
            "output_mode": self.output_mode,
        }
        # Optional measurements are emitted only when actually measured, so a
        # consumer can tell "not checked" from "checked and fine".
        if self.measured_sample_rate is not None:
            out["measured_sample_rate"] = round(self.measured_sample_rate, 1)
        if self.adc_saturation_ratio is not None:
            out["adc_saturation_ratio"] = round(self.adc_saturation_ratio, 4)
        if self.hf_ratio is not None:
            out["hf_ratio"] = round(self.hf_ratio, 3)
        if self.light_rms is not None:
            out["light_rms"] = round(self.light_rms, 6)
        if self.hard_rms is not None:
            out["hard_rms"] = round(self.hard_rms, 6)
        if self.separability is not None:
            out["separability"] = round(self.separability, 2)
        return out


@dataclass(frozen=True)
class ProbeVerdict:
    """The tier, why it was assigned, and what it permits."""

    tier: str
    label: str
    metrics: ProbeMetrics
    reasons: list[str] = field(default_factory=list)
    capabilities: tuple[str, ...] = ()

    @property
    def is_usable(self) -> bool:
        """True when the rig can drive anything at all beyond simulation."""
        return self.tier in ("A", "B", "C")

    def to_dict(self) -> dict[str, object]:
        return {
            "tier": self.tier,
            "label": self.label,
            "is_usable": self.is_usable,
            "metrics": self.metrics.to_dict(),
            "reasons": list(self.reasons),
            "capabilities": list(self.capabilities),
        }


def _rms(x: np.ndarray) -> float:
    if x.size == 0:
        return 0.0
    return float(np.sqrt(np.mean(np.asarray(x, dtype=float) ** 2)))


def detect_output_mode(samples: np.ndarray, fs: int) -> tuple[str, float]:
    """Tell a raw sEMG trace from an already smoothed envelope.

    Returns the mode ("raw", "env", or "unknown") and the fraction of AC power
    sitting above the bandpass corner that decided it.

    The DC component is excluded before the ratio is taken. A MyoWare envelope
    rides on a large DC offset, and leaving it in would swamp the comparison
    and make every input look like an envelope.
    """
    arr = np.asarray(samples, dtype=float).ravel()
    if arr.size < 16:
        return "unknown", float("nan")

    detrended = arr - arr.mean()
    spectrum = np.abs(np.fft.rfft(detrended)) ** 2
    freqs = np.fft.rfftfreq(detrended.size, d=1.0 / fs)

    # Drop the DC bin: the offset is not signal, and it is huge on ENV output.
    total = float(spectrum[1:].sum())
    if total <= 0:
        return "unknown", float("nan")

    high = float(spectrum[freqs >= BAND_LOW_HZ].sum())
    ratio = high / total

    if ratio >= HF_RAW_FLOOR:
        return "raw", ratio
    if ratio <= HF_ENV_CEILING:
        return "env", ratio
    return "unknown", ratio


def adc_saturation(counts: np.ndarray) -> float:
    """Fraction of samples pinned at a literal ADC rail.

    This is the honest clipping measure, and it is deliberately not the same
    question as `window_features()["saturation_ratio"]`. That one flags samples
    near the *observed* extremes, which is the right definition for a scaled
    trace but reports a nonzero floor on any recording and cannot see the
    difference between a signal comfortably mid range and one hard against a
    rail. Clipping has to be judged against the converter, so it needs the
    unscaled integer counts that only the acquisition shell holds.
    """
    arr = np.asarray(counts, dtype=float).ravel()
    if arr.size == 0:
        return 0.0
    pinned = (arr <= ADC_MIN) | (arr >= ADC_MAX)
    return float(np.count_nonzero(pinned) / arr.size)


def measure_link(timestamps_ms: np.ndarray) -> tuple[float, float]:
    """Recover the achieved sample rate and dropout fraction from arrivals.

    The device clock is the only trustworthy witness to what the link actually
    delivered. A configured rate is an intention; this is the outcome.

    The median inter sample gap sets the nominal period, since a median rides
    out the occasional stall that a mean would smear across the whole
    recording. Each gap is then charged for the samples it swallowed, so one
    long stall and many short ones are weighted by how much data each actually
    cost rather than by how often they happened.
    """
    ts = np.asarray(timestamps_ms, dtype=float).ravel()
    if ts.size < 2:
        return float("nan"), 0.0

    deltas = np.diff(ts)
    deltas = deltas[deltas > 0]
    if deltas.size == 0:
        return float("nan"), 0.0

    period_ms = float(np.median(deltas))
    if period_ms <= 0:
        return float("nan"), 0.0

    rate = 1000.0 / period_ms

    # Count the samples the gaps swallowed, against what a clean run would
    # have delivered over the same span.
    missing = np.clip(np.round(deltas / period_ms) - 1.0, 0.0, None).sum()
    expected = (ts[-1] - ts[0]) / period_ms
    dropout = float(missing / expected) if expected > 0 else 0.0

    return rate, float(np.clip(dropout, 0.0, 1.0))


def _separability(a: np.ndarray, b: np.ndarray) -> float:
    """Normalized gap between two effort levels, in pooled deviations.

    A d-prime in spirit: the distance between the means over the pooled
    spread. Amplitude alone cannot answer whether a rig resolves effort,
    because a large gap between two very noisy levels is still not a gap you
    can act on.
    """
    if a.size == 0 or b.size == 0:
        return 0.0
    pooled = float(np.sqrt(a.var() + b.var()))
    if pooled <= 1e-12:
        # Identical and perfectly flat levels are not separable in any useful
        # sense, however far apart their means happen to sit.
        return 0.0
    return float(abs(b.mean() - a.mean()) / pooled)


def _prepare(samples: np.ndarray, fs: int) -> tuple[np.ndarray, int, int]:
    """Validate a recording and return it with its window geometry."""
    arr = np.asarray(samples, dtype=float).ravel()
    if arr.size == 0:
        raise ValueError("probe received no samples")

    window = max(1, int(fs * WINDOW_MS / 1000.0))
    n_windows = arr.size // window
    if n_windows < 5:
        raise ValueError(
            f"need at least 5 windows of {WINDOW_MS:.0f} ms to judge a rig, "
            f"got {n_windows}. Record for longer."
        )
    return arr, window, n_windows


def _build(
    arr: np.ndarray,
    fs: int,
    *,
    rest_rms: float,
    active_rms: float,
    extra: dict[str, object] | None = None,
) -> ProbeMetrics:
    """Assemble metrics shared by every measurement path."""
    contrast = active_rms / rest_rms if rest_rms > 1e-12 else 0.0

    # Integrity features come from the whole recording, since a single loose
    # moment is what the builder needs told about.
    whole = window_features(arr, fs)
    mode, hf_ratio = detect_output_mode(arr, fs)

    fields: dict[str, object] = {
        "n_samples": int(arr.size),
        "duration_s": arr.size / fs,
        "sample_rate": fs,
        "rest_rms": rest_rms,
        "active_rms": active_rms,
        "contrast": float(contrast),
        "mains_ratio": float(whole["mains_ratio"]),
        "saturation_ratio": float(whole["saturation_ratio"]),
        "baseline_drift": float(whole["baseline_drift"]),
        "snr_estimate": float(whole["snr_estimate"]),
        "hf_ratio": None if np.isnan(hf_ratio) else float(hf_ratio),
        "output_mode": mode,
    }
    fields.update(extra or {})
    return ProbeMetrics(**fields)  # type: ignore[arg-type]


def measure(samples: np.ndarray, fs: int) -> ProbeMetrics:
    """Reduce a raw recording to the numbers the tier decision needs.

    Rest and active levels are separated without needing the operator to mark
    when they gripped: windows are ranked by envelope amplitude, and the
    quietest and loudest quintiles are taken as rest and contraction. That
    works whether the builder gripped once or ten times, which matters because
    a bring up protocol nobody follows exactly is the normal case.

    `measure_phases()` does better when the protocol *was* followed. This
    stays as the fallback, and as the entry point for callers holding nothing
    but an array.
    """
    arr, window, n_windows = _prepare(samples, fs)

    filtered = preprocess(arr, fs)

    # Amplitudes are measured on the filtered trace, never the raw one. Real
    # MyoWare output rides on a large DC offset, and the RMS of a trace sitting
    # at 512 counts is about 512 whether the hand is squeezing or not. Taking
    # contrast on raw samples would report roughly 1.0x for every rig on
    # earth and grade a perfect signal as Tier D. The filtered trace is AC
    # coupled by the bandpass, and it is also what the app itself consumes.
    trimmed = filtered.filtered[: n_windows * window].reshape(n_windows, window)

    # Rank windows by envelope energy on the filtered trace, then split.
    env = filtered.envelope[: n_windows * window].reshape(n_windows, window)
    levels = env.mean(axis=1)
    order = np.argsort(levels)
    quintile = max(1, n_windows // 5)

    return _build(
        arr,
        fs,
        rest_rms=_rms(trimmed[order[:quintile]]),
        active_rms=_rms(trimmed[order[-quintile:]]),
    )


def measure_phases(
    samples: np.ndarray,
    fs: int,
    phases: dict[str, tuple[float, float]],
) -> ProbeMetrics:
    """Measure a recording whose effort phases are known, in seconds.

    `phases` maps a label to a (start, end) span in seconds. "rest", "light"
    and "hard" are the labels that matter; anything else is ignored.

    Knowing when the builder was resting and when they were gripping buys the
    one thing the quintile split cannot give: whether the rig resolves *three*
    effort levels rather than two. Force regression in kg is only honest on a
    rig that can tell a light squeeze from a hard one, and a two way contrast
    can look excellent on a rig that saturates the moment the hand closes.

    Falls back to `measure()` when the spans are missing or too short to
    support the comparison, so a protocol the builder fumbled still yields a
    verdict.
    """
    arr, _, _ = _prepare(samples, fs)
    filtered = preprocess(arr, fs)

    def span(label: str) -> np.ndarray:
        bounds = phases.get(label)
        if bounds is None:
            return np.asarray([], dtype=float)
        start = max(0, int(bounds[0] * fs))
        end = min(arr.size, int(bounds[1] * fs))
        if end - start < fs // 10:
            return np.asarray([], dtype=float)
        # The envelope, not the raw trace: see the note in measure() about the
        # DC offset. The envelope is also the right domain for comparing
        # effort levels, since it is amplitude over time with the interference
        # pattern already smoothed out.
        return filtered.envelope[start:end]

    rest, light, hard = span("rest"), span("light"), span("hard")
    if rest.size == 0 or light.size == 0 or hard.size == 0:
        return measure(samples, fs)

    # The weaker of the two adjacent gaps is the one that limits the rig:
    # resolving hard from rest is worthless if light and hard are a blur.
    separability = min(_separability(rest, light), _separability(light, hard))

    return _build(
        arr,
        fs,
        rest_rms=_rms(rest),
        active_rms=_rms(hard),
        extra={
            "light_rms": _rms(light),
            "hard_rms": _rms(hard),
            "separability": float(separability),
        },
    )


def grade(metrics: ProbeMetrics) -> ProbeVerdict:
    """Assign a tier from measured metrics, with the reasoning attached.

    Disqualifiers are checked before quality: a clipped or dead input is Tier
    D no matter how good the contrast looks, because the contrast itself is
    then meaningless.
    """
    reasons: list[str] = []

    # Disqualifiers first. ADC rail pinning leads: when it fires, every other
    # number in the recording was measured through a clipped signal.
    if metrics.adc_saturation_ratio is not None and (
        metrics.adc_saturation_ratio > SATURATION_LIMIT
    ):
        reasons.append(
            f"input is pinned at an ADC rail for {metrics.adc_saturation_ratio:.1%} "
            f"of samples (limit {SATURATION_LIMIT:.1%}). A clipped peak is an "
            "unknown peak. Turn the gain pot on the MyoWare down and re run."
        )
        return _verdict("D", metrics, reasons)

    if metrics.saturation_ratio > SATURATION_LIMIT:
        reasons.append(
            f"input is clipping ({metrics.saturation_ratio:.1%} of samples pinned "
            f"at a rail, limit {SATURATION_LIMIT:.1%}). A clipped peak is an "
            "unknown peak. Lower the gain on the MyoWare."
        )
        return _verdict("D", metrics, reasons)

    # Mode is checked before contrast, because on an envelope the contrast
    # number is an artifact of the bandpass rather than a property of the rig.
    # Reporting "no detectable contraction" here would send the builder to
    # re prep their skin when the actual fix is a selector switch.
    if metrics.output_mode == "env":
        reasons.append(
            "this looks like the MyoWare ENV output, not RAW: almost no power "
            f"above {BAND_LOW_HZ:.0f} Hz ({metrics.hf_ratio:.0%} of AC power). "
            "The filter chain expects a raw trace and removes nearly all of an "
            "envelope, so nothing measured here describes the rig. Move the "
            "output selector to RAW and re run before reading anything else."
        )
        return _verdict("D", metrics, reasons)

    if metrics.contrast < CONTRAST_MARGINAL:
        reasons.append(
            f"no detectable contraction: active signal is only "
            f"{metrics.contrast:.1f}x rest, below the {CONTRAST_MARGINAL}x floor. "
            "Check electrode placement, skin prep, and that the reference "
            "electrode is on bone."
        )
        return _verdict("D", metrics, reasons)

    # Quality grading.
    tier = "A"

    if metrics.contrast < CONTRAST_USABLE:
        tier = "C"
        reasons.append(
            f"contraction is only {metrics.contrast:.1f}x rest, which separates "
            "grip from rest but supports nothing quantitative."
        )
    elif metrics.contrast < CONTRAST_CLEAN:
        tier = "B"
        reasons.append(
            f"contraction is {metrics.contrast:.1f}x rest: clearly detectable, "
            "short of the clean bar."
        )
    else:
        reasons.append(
            f"strong contraction at {metrics.contrast:.1f}x rest."
        )

    # An envelope is already disqualified above, so anything reaching here has
    # spectral content worth reasoning about.
    if metrics.output_mode == "unknown" and metrics.hf_ratio is not None:
        tier = _worst(tier, "B")
        reasons.append(
            f"output mode is unclear: {metrics.hf_ratio:.0%} of AC power sits "
            f"above {BAND_LOW_HZ:.0f} Hz, between what a raw trace and an "
            "envelope look like. Confirm the selector is on RAW."
        )

    if metrics.mains_ratio > MAINS_USABLE:
        tier = _worst(tier, "C")
        reasons.append(
            f"heavy mains contamination ({metrics.mains_ratio:.1%} of band power). "
            "Unplug the laptop charger and move away from mains wiring."
        )
    elif metrics.mains_ratio > MAINS_CLEAN:
        tier = _worst(tier, "B")
        reasons.append(
            f"mains contamination at {metrics.mains_ratio:.1%} of band power: the "
            "notch filter will cope, but spectral fatigue estimates are not "
            "trustworthy on this rig."
        )

    if metrics.baseline_drift > DRIFT_USABLE:
        tier = _worst(tier, "B")
        reasons.append(
            f"baseline drifts by {metrics.baseline_drift:.1f}x RMS across the "
            "recording, which usually means a loose or drying electrode."
        )

    # Link integrity. A rig can have a beautiful signal and still be unusable
    # if the samples do not arrive.
    if metrics.dropout_ratio > DROPOUT_USABLE:
        tier = _worst(tier, "C")
        reasons.append(
            f"the serial link dropped {metrics.dropout_ratio:.1%} of samples. "
            "Timing sensitive measures like rate of force development cannot "
            "survive that. Try a direct USB port and a shorter cable."
        )

    if metrics.measured_sample_rate is not None and (
        metrics.measured_sample_rate < metrics.sample_rate * RATE_TOLERANCE
    ):
        tier = _worst(tier, "B")
        reasons.append(
            f"measured {metrics.measured_sample_rate:.0f} Hz against a configured "
            f"{metrics.sample_rate} Hz, so the usable band is narrower than the "
            "pipeline assumes and spectral fatigue is measured over a truncated "
            "spectrum."
        )

    # Three way effort separation, when the protocol was followed.
    if metrics.separability is not None:
        if metrics.separability < SEPARABILITY_USABLE:
            tier = _worst(tier, "C")
            reasons.append(
                f"light and hard contractions overlap (separability "
                f"{metrics.separability:.1f}). This rig detects a grip but "
                "cannot grade how hard it was, so a force estimate in kg would "
                "be fitting noise."
            )
        elif metrics.separability < SEPARABILITY_CLEAN:
            tier = _worst(tier, "B")
            reasons.append(
                f"effort levels are separable but not cleanly (separability "
                f"{metrics.separability:.1f}): usable for force regression, "
                "with wider intervals than a clean rig would earn."
            )
        else:
            reasons.append(
                f"rest, light, and hard are cleanly separable (separability "
                f"{metrics.separability:.1f})."
            )

    return _verdict(tier, metrics, reasons)


def _worst(current: str, candidate: str) -> str:
    """Return the lower of two tiers. Problems accumulate, never cancel."""
    return max(current, candidate)


def _verdict(tier: str, metrics: ProbeMetrics, reasons: list[str]) -> ProbeVerdict:
    return ProbeVerdict(
        tier=tier,
        label=TIER_LABELS[tier],
        metrics=metrics,
        reasons=reasons,
        capabilities=TIER_CAPABILITIES[tier],
    )


def analyze(
    samples: np.ndarray,
    fs: int,
    *,
    phases: dict[str, tuple[float, float]] | None = None,
    timestamps_ms: np.ndarray | None = None,
    counts: np.ndarray | None = None,
) -> ProbeVerdict:
    """Measure a recording and grade it. The probe's whole judgement.

    Everything past `fs` is optional and comes from the acquisition shell.
    Supplying more of it sharpens the verdict: `phases` unlocks three way
    separability, `timestamps_ms` unlocks rate and dropout detection, and
    `counts` unlocks true ADC rail clipping. With none of it, this degrades to
    the two way quintile split, which is still a verdict.
    """
    metrics = (
        measure_phases(samples, fs, phases) if phases else measure(samples, fs)
    )

    updates: dict[str, object] = {}
    if timestamps_ms is not None:
        rate, dropout = measure_link(timestamps_ms)
        if not np.isnan(rate):
            updates["measured_sample_rate"] = rate
        updates["dropout_ratio"] = dropout
    if counts is not None:
        updates["adc_saturation_ratio"] = adc_saturation(counts)

    if updates:
        metrics = replace(metrics, **updates)  # type: ignore[arg-type]

    return grade(metrics)


def format_report(verdict: ProbeVerdict) -> str:
    """Render a verdict as the text the builder reads in the terminal."""
    m = verdict.metrics
    lines = ["", "=" * 62]

    # The mode warning goes above the tier, not below it. A builder who reads
    # nothing else needs to see the one thing they can fix in ten seconds.
    if m.output_mode == "env":
        lines.extend(
            [
                "  WARNING: this looks like ENV output, not RAW.",
                "  Move the MyoWare 2.0 output selector to RAW and re run.",
                "=" * 62,
            ]
        )

    lines.extend([f"  TIER {verdict.tier}: {verdict.label.upper()}", "=" * 62, ""])

    rate = f"  Recording      {m.duration_s:.1f} s at {m.sample_rate} Hz configured"
    lines.append(rate)
    if m.measured_sample_rate is not None:
        lines.append(f"  Measured rate  {m.measured_sample_rate:.0f} Hz achieved")
    if m.dropout_ratio > 0:
        lines.append(f"  Dropouts       {m.dropout_ratio:.2%} of samples")

    lines.extend(
        [
            f"  Output mode    {m.output_mode}"
            + (f"  ({m.hf_ratio:.0%} of AC power above {BAND_LOW_HZ:.0f} Hz)"
               if m.hf_ratio is not None else ""),
            f"  Rest level     {m.rest_rms:.5f}",
        ]
    )
    if m.light_rms is not None:
        lines.append(f"  Light level    {m.light_rms:.5f}")
    lines.append(f"  Active level   {m.active_rms:.5f}")
    lines.append(f"  Contrast       {m.contrast:.1f}x  (rest to contraction)")
    if m.separability is not None:
        lines.append(
            f"  Separability   {m.separability:.1f}  (adjacent effort levels)"
        )

    # Spectral numbers are meaningless on an envelope, so they are withheld
    # rather than printed with a caveat nobody reads.
    if m.output_mode != "env":
        lines.append(f"  Mains          {m.mains_ratio:.1%} of band power")
    if m.adc_saturation_ratio is not None:
        lines.append(f"  ADC clipping   {m.adc_saturation_ratio:.2%} of samples")
    lines.append(f"  Baseline drift {m.baseline_drift:.2f}x RMS")
    lines.extend(["", "  What this means"])
    lines.extend(f"    - {reason}" for reason in verdict.reasons)
    lines.append("")

    if verdict.capabilities:
        lines.append("  Phase 3 may enable")
        lines.extend(f"    - {cap}" for cap in verdict.capabilities)
    else:
        lines.append("  Phase 3 enables nothing from this rig.")
        lines.append("  Run the demo on Simulated. This is a supported path,")
        lines.append("  not a failure: the app never required hardware.")

    lines.extend(["", "=" * 62, ""])
    return "\n".join(lines)
