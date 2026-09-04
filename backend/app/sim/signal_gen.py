"""Synthetic surface EMG generator.

Physiologically plausible rather than merely noisy. The pieces that matter:

- Interference pattern EMG is modeled as bandlimited Gaussian noise, which is
  what a real multi motor unit recording looks like.
- Amplitude follows a ramp, plateau, release envelope per repetition.
- Both amplitude and spectral content change with effort, mirroring motor
  unit recruitment and rate coding.
- The power spectrum shifts downward across repetitions. This is engineered
  deliberately, not hoped for, because M5 has to detect it and the demo makes
  a specific claim about it. See docs/ML.md.
- Artifacts (drift, mains hum, motion spikes, electrode pop) scale with a
  junkiness dial, which is what makes the signal quality model demonstrable.

Nothing here touches hardware. This is the Phase 1 stand in for the sensor.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field, replace

import numpy as np
from scipy import signal as sps

DEFAULT_FS = 1000

# Centre frequency of the simulated interference pattern at the start of a
# session, in Hz. Real sEMG median frequency sits somewhere around here.
BASE_CENTRE_HZ = 95.0

# How far the spectrum slides down per repetition. Fatigue is a real,
# measurable downward shift in median frequency, and this is the parameter
# that puts it there. Large enough to be statistically detectable at ten reps.
DEFAULT_FATIGUE_SHIFT_HZ_PER_REP = 2.2

# Amplitude compensation as fatigue sets in: firing rate drops but recruitment
# increases, so amplitude tends to creep up even as the spectrum falls.
DEFAULT_FATIGUE_AMPLITUDE_GAIN = 0.015


@dataclass(frozen=True)
class RepSpec:
    """One prescribed repetition."""

    target_mvc: float = 0.6
    ramp_s: float = 0.7
    hold_s: float = 4.0
    release_s: float = 0.8
    rest_s: float = 5.0


@dataclass(frozen=True)
class SessionProtocol:
    """A whole prescribed session."""

    reps: int = 10
    lead_in_s: float = 5.0
    rep: RepSpec = field(default_factory=RepSpec)

    def rep_specs(self) -> list[RepSpec]:
        return [self.rep] * self.reps


@dataclass(frozen=True)
class GroundTruthRep:
    """Where a repetition actually is, for testing the segmenter against."""

    index: int
    start_s: float
    peak_s: float
    end_s: float

    @property
    def duration_s(self) -> float:
        return self.end_s - self.start_s


@dataclass(frozen=True)
class GeneratedSession:
    """A synthetic trace plus the truth used to build it."""

    samples: np.ndarray
    sample_rate: int
    reps: list[GroundTruthRep]
    junkiness: float

    @property
    def duration_s(self) -> float:
        return self.samples.size / float(self.sample_rate)


def _effort_envelope(spec: RepSpec, fs: int) -> np.ndarray:
    """Ramp, plateau, release as a fraction of MVC.

    Ramp and release are raised cosine rather than linear: real force
    production has no instantaneous change in slope.
    """
    ramp_n = max(1, int(spec.ramp_s * fs))
    hold_n = max(1, int(spec.hold_s * fs))
    release_n = max(1, int(spec.release_s * fs))

    ramp = 0.5 * (1.0 - np.cos(np.linspace(0.0, np.pi, ramp_n)))
    hold = np.ones(hold_n)
    release = 0.5 * (1.0 + np.cos(np.linspace(0.0, np.pi, release_n)))

    return np.concatenate([ramp, hold, release]) * spec.target_mvc


def _shaped_noise(n: int, fs: int, centre_hz: float, rng: np.random.Generator) -> np.ndarray:
    """Bandlimited Gaussian noise standing in for the interference pattern.

    A bandpass centred on centre_hz gives the trace a definable median
    frequency, which is the quantity the fatigue model measures.
    """
    if n <= 0:
        return np.zeros(0)

    white = rng.normal(size=n)
    nyquist = fs / 2.0

    # Width scales with centre so the band stays plausible as it slides down.
    low = max(15.0, centre_hz * 0.45)
    high = min(nyquist * 0.95, centre_hz * 2.1)
    if low >= high:
        return white

    sos = sps.butter(3, [low / nyquist, high / nyquist], btype="bandpass", output="sos")
    shaped = sps.sosfilt(sos, white)

    rms = float(np.sqrt(np.mean(shaped**2)))
    return shaped / rms if rms > 1e-12 else shaped


class SyntheticEmgGenerator:
    """Generates synthetic sEMG, offline in one shot or as a live stream.

    Both paths share one code generator so the stream cannot drift away from
    what the offline tests validate.
    """

    def __init__(
        self,
        sample_rate: int = DEFAULT_FS,
        seed: int | None = None,
        junkiness: float = 0.0,
        *,
        baseline_rms: float = 0.012,
        mvc_rms: float = 1.0,
        fatigue_shift_hz_per_rep: float = DEFAULT_FATIGUE_SHIFT_HZ_PER_REP,
        fatigue_amplitude_gain: float = DEFAULT_FATIGUE_AMPLITUDE_GAIN,
    ) -> None:
        if sample_rate <= 0:
            raise ValueError(f"sample rate must be positive, got {sample_rate}")
        if not 0.0 <= junkiness <= 1.0:
            raise ValueError(f"junkiness must be within 0 to 1, got {junkiness}")

        self.sample_rate = sample_rate
        self.seed = seed
        self.junkiness = junkiness
        self.baseline_rms = baseline_rms
        self.mvc_rms = mvc_rms
        self.fatigue_shift_hz_per_rep = fatigue_shift_hz_per_rep
        self.fatigue_amplitude_gain = fatigue_amplitude_gain
        self._rng = np.random.default_rng(seed)

    def reset(self) -> None:
        """Restore the generator to its seeded starting state."""
        self._rng = np.random.default_rng(self.seed)

    # -- core construction -------------------------------------------------

    def _centre_for_rep(self, index: int) -> float:
        """Spectral centre for a repetition. Falls monotonically: fatigue."""
        centre = BASE_CENTRE_HZ - index * self.fatigue_shift_hz_per_rep
        # Never let fatigue push the band into implausible territory.
        return max(centre, 35.0)

    def _rest(self, n: int) -> np.ndarray:
        """Resting baseline. Low amplitude, broadband."""
        if n <= 0:
            return np.zeros(0)
        return _shaped_noise(n, self.sample_rate, 110.0, self._rng) * self.baseline_rms

    def _contraction(self, spec: RepSpec, index: int) -> np.ndarray:
        """One repetition: shaped noise amplitude modulated by the effort curve."""
        effort = _effort_envelope(spec, self.sample_rate)
        centre = self._centre_for_rep(index)
        carrier = _shaped_noise(effort.size, self.sample_rate, centre, self._rng)

        # Amplitude creeps up with fatigue even as the spectrum falls.
        gain = 1.0 + index * self.fatigue_amplitude_gain

        # Baseline is always present underneath the contraction.
        floor = _shaped_noise(effort.size, self.sample_rate, 110.0, self._rng)
        floor = floor * self.baseline_rms

        return carrier * effort * self.mvc_rms * gain + floor

    def build_session(self, protocol: SessionProtocol | None = None) -> GeneratedSession:
        """Generate a complete session, with ground truth rep boundaries."""
        proto = protocol or SessionProtocol()
        fs = self.sample_rate

        segments: list[np.ndarray] = []
        truth: list[GroundTruthRep] = []
        cursor = 0

        lead_in = int(proto.lead_in_s * fs)
        segments.append(self._rest(lead_in))
        cursor += lead_in

        for index, spec in enumerate(proto.rep_specs()):
            contraction = self._contraction(spec, index)
            start_n = cursor
            # The peak sits at the end of the ramp, where the plateau begins.
            peak_n = start_n + int(spec.ramp_s * fs)
            end_n = start_n + contraction.size

            segments.append(contraction)
            cursor = end_n

            truth.append(
                GroundTruthRep(
                    index=index,
                    start_s=start_n / fs,
                    peak_s=peak_n / fs,
                    end_s=end_n / fs,
                )
            )

            rest_n = int(spec.rest_s * fs)
            segments.append(self._rest(rest_n))
            cursor += rest_n

        clean = np.concatenate(segments) if segments else np.zeros(0)
        dirty = self._add_artifacts(clean)

        return GeneratedSession(
            samples=dirty,
            sample_rate=fs,
            reps=truth,
            junkiness=self.junkiness,
        )

    # -- artifacts ---------------------------------------------------------

    def _add_artifacts(self, x: np.ndarray) -> np.ndarray:
        """Layer on the realistic ways a cheap electrode setup goes wrong."""
        if x.size == 0 or self.junkiness <= 0.0:
            return x

        j = self.junkiness
        fs = self.sample_rate
        t = np.arange(x.size) / fs
        out = x.copy()

        # Baseline wander from electrode and cable movement, well below band.
        drift_hz = 0.35
        out = out + j * 0.55 * self.mvc_rms * np.sin(2 * np.pi * drift_hz * t + self._rng.uniform(0, 2 * np.pi))

        # Mains hum, plus a little of its third harmonic.
        out = out + j * 0.42 * self.mvc_rms * np.sin(2 * np.pi * 60.0 * t)
        out = out + j * 0.11 * self.mvc_rms * np.sin(2 * np.pi * 180.0 * t)

        # Motion spikes: short, large, low frequency excursions.
        n_spikes = self._rng.poisson(j * 5.0)
        for _ in range(int(n_spikes)):
            at = self._rng.integers(0, x.size)
            width = int(self._rng.uniform(0.02, 0.09) * fs)
            lo, hi = max(0, at - width), min(x.size, at + width)
            shape = np.hanning(hi - lo) if hi > lo else np.zeros(0)
            out[lo:hi] += self._rng.choice([-1.0, 1.0]) * j * 1.6 * self.mvc_rms * shape

        # Electrode pop: a step discontinuity that decays back to baseline.
        if self._rng.random() < j * 0.5:
            at = int(self._rng.integers(0, x.size))
            decay_n = min(x.size - at, int(0.4 * fs))
            if decay_n > 0:
                step = j * 1.9 * self.mvc_rms * self._rng.choice([-1.0, 1.0])
                out[at : at + decay_n] += step * np.exp(-np.linspace(0, 6, decay_n))

        # Wideband sensor noise floor rises with junkiness too.
        out = out + self._rng.normal(scale=j * 0.05 * self.mvc_rms, size=x.size)

        return out

    # -- the two public interfaces ----------------------------------------

    def generate_session(self, protocol: SessionProtocol | None = None) -> np.ndarray:
        """Offline: the whole trace at once."""
        return self.build_session(protocol).samples

    def stream(
        self,
        window_samples: int,
        protocol: SessionProtocol | None = None,
        *,
        loop: bool = True,
    ) -> Iterator[np.ndarray]:
        """Online: fixed size windows, for SimulatedSource to hand to the socket.

        Reads over a lazily regenerated buffer so the streaming path produces
        the same kind of signal the offline tests validate. With loop set, the
        session repeats indefinitely so a demo can run as long as it likes.
        """
        if window_samples <= 0:
            raise ValueError(f"window must be positive, got {window_samples}")

        proto = protocol or SessionProtocol()
        buffer = self.generate_session(proto)
        cursor = 0

        while True:
            if cursor + window_samples > buffer.size:
                if not loop:
                    remaining = buffer[cursor:]
                    if remaining.size:
                        yield remaining
                    return
                # Regenerate rather than replay, so a long demo keeps varying.
                buffer = self.generate_session(proto)
                cursor = 0

            yield buffer[cursor : cursor + window_samples]
            cursor += window_samples


def make_protocol(
    reps: int = 10,
    target_mvc: float = 0.6,
    hold_s: float = 4.0,
    rest_s: float = 5.0,
) -> SessionProtocol:
    """Convenience builder for the common uniform protocol."""
    return SessionProtocol(
        reps=reps,
        rep=replace(RepSpec(), target_mvc=target_mvc, hold_s=hold_s, rest_s=rest_s),
    )
