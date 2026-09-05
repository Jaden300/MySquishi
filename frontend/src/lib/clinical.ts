/**
 * Clinical term definitions.
 *
 * Transcribed from docs/CLINICAL.md, which is the source text: every term is
 * real and each definition is what the user reads on hover. Decorative
 * jargon is worse than none, so nothing is added here that is not in that
 * file, and nothing is reworded to sound more impressive than it is.
 */

export const CLINICAL_TERMS: Record<string, string> = {
  // Measurement and physiology
  sEMG:
    "Surface electromyography. Electrodes on the skin record the electrical activity of the muscle underneath.",
  MVC:
    "Maximum Voluntary Contraction. Your own strongest effort, measured during a calibration trial.",
  "percent MVC":
    "Effort expressed as a percentage of your own maximum. This is what makes readings comparable across sessions and between people, and it is the single most important normalization in the app.",
  "RMS envelope":
    "Root mean square over a sliding window. The standard way to smooth a raw EMG trace into the effort line the models actually read.",
  "Isometric contraction":
    "Muscle tension without joint movement. A grip hold is exactly this.",
  "Flexor digitorum superficialis":
    "A forearm muscle that flexes the fingers. One of the muscles the electrodes sit over.",
  "Flexor carpi radialis":
    "A forearm muscle that flexes and abducts the wrist. The other main muscle under the electrodes.",
  RFD:
    "Rate of Force Development. How quickly you ramp up to your peak. A meaningful rehabilitation metric in its own right, since strength and speed of force production recover differently.",
  "Time to peak contraction":
    "How long it takes to reach maximum effort within a single repetition.",
  "Contraction duration":
    "How long a single repetition lasts from onset to release.",
  "Relaxation time":
    "How long it takes to return to rest after a hold. Slow relaxation can indicate fatigue.",
  "Force time integral":
    "Also called impulse. The area under the contraction curve, representing the total work done.",
  "CV of force":
    "Coefficient of variation during a hold. Measures steadiness and neuromuscular control. A lower value means a smoother hold.",

  // Fatigue
  "Median frequency":
    "The frequency that divides the EMG power spectrum into two equal halves. As a muscle fatigues, the spectrum shifts downward, so MDF falls.",
  MDF:
    "The frequency that divides the EMG power spectrum into two equal halves. As a muscle fatigues, the spectrum shifts downward, so MDF falls.",
  "MDF slope":
    "Median frequency regressed against repetition index. A negative slope is objective evidence of fatigue rather than a subjective impression.",
  "Dimitrov spectral fatigue index":
    "An alternative spectral fatigue metric, weighted toward low frequency content. Reported as a secondary readout.",
  "Thorstensson fatigue index":
    "The decline from your peak repetition to your final repetition, as a percentage.",

  // Clinical context and outcomes
  "Jamar dynamometer":
    "The clinical gold standard instrument for measuring grip strength. MySquishi approximates it from muscle activity, and is not validated against it.",
  "EWGSOP2 thresholds":
    "European Working Group on Sarcopenia in Older People, second consensus. Defines low grip strength as under 27 kg for men and under 16 kg for women. Used here as a screening reference line, not a diagnosis.",
  MCID:
    "Minimal Clinically Important Difference. The smallest change that is actually meaningful to a patient rather than measurement noise. For grip strength it is roughly 5 to 6 kg.",
  "Borg CR10":
    "A 0 to 10 scale for perceived exertion, collected after a session. Comparing it against measured output is itself informative.",
  QuickDASH:
    "An 11 item patient reported questionnaire on arm, shoulder, and hand disability. Scored 0 to 100, where higher means more difficulty.",
  "Adherence rate":
    "Sessions completed against sessions prescribed. One of the strongest predictors of rehabilitation outcome.",

  // Signal quality, surfaced on the live badge.
  SQI:
    "Signal quality index. How trustworthy the current reading is, judged from baseline drift, mains interference, clipping and signal to noise ratio.",
};

/**
 * Grip force in kilograms is a calibrated estimate from EMG amplitude, not a
 * dynamometer measurement. docs/CLINICAL.md requires this to be said wherever
 * a kilogram figure appears.
 */
export const KG_ESTIMATE_NOTE =
  "Estimated from muscle activity and calibrated to your own reported reference. Not a dynamometer measurement.";

/** The normative reference is approximate and synthetic. */
export const PERCENTILE_NOTE =
  "The reference population is synthetic and approximate. Used for context, not for diagnosis.";

/** EWGSOP2 low grip strength thresholds, in kilograms. */
export const EWGSOP2_THRESHOLDS = { male: 27, female: 16 } as const;

/** Minimal clinically important difference for grip strength, in kilograms. */
export const MCID_KG = 5.5;
