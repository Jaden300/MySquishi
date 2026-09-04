# Clinical reference

Every term here is real. Use each one only where it genuinely applies, and define it in a tooltip where it is surfaced. Decorative fake jargon is worse than none: judges include people who will know.

This file is the source text for `ClinicalTooltip`. The `definition` column is what the user reads on hover.

## Measurement and physiology

| Term | Definition (tooltip text) |
|---|---|
| sEMG | Surface electromyography. Electrodes on the skin record the electrical activity of the muscle underneath. |
| MVC | Maximum Voluntary Contraction. Your own strongest effort, measured during a calibration trial. |
| percent MVC | Effort expressed as a percentage of your own maximum. This is what makes readings comparable across sessions and between people, and it is the single most important normalization in the app. |
| RMS envelope | Root mean square over a sliding window. The standard way to smooth a raw EMG trace into the effort line the models actually read. |
| Isometric contraction | Muscle tension without joint movement. A grip hold is exactly this. |
| Flexor digitorum superficialis | A forearm muscle that flexes the fingers. One of the muscles the electrodes sit over. |
| Flexor carpi radialis | A forearm muscle that flexes and abducts the wrist. The other main muscle under the electrodes. |
| RFD | Rate of Force Development. How quickly you ramp up to your peak. A meaningful rehabilitation metric in its own right, since strength and speed of force production recover differently. |
| Time to peak contraction | How long it takes to reach maximum effort within a single repetition. |
| Contraction duration | How long a single repetition lasts from onset to release. |
| Relaxation time | How long it takes to return to rest after a hold. Slow relaxation can indicate fatigue. |
| Force time integral | Also called impulse. The area under the contraction curve, representing the total work done. |
| CV of force | Coefficient of variation during a hold. Measures steadiness and neuromuscular control. A lower value means a smoother hold. |

## Fatigue

| Term | Definition (tooltip text) |
|---|---|
| Median frequency (MDF) | The frequency that divides the EMG power spectrum into two equal halves. As a muscle fatigues, the spectrum shifts downward, so MDF falls. |
| MDF slope | Median frequency regressed against repetition index. A negative slope is objective evidence of fatigue rather than a subjective impression. |
| Dimitrov spectral fatigue index | An alternative spectral fatigue metric, weighted toward low frequency content. Reported as a secondary readout. |
| Thorstensson fatigue index | The decline from your peak repetition to your final repetition, as a percentage. |

The MDF shift is a real, defensible, textbook technique, and it is one of the strongest technical talking points in the project. It is computed per repetition via FFT and then regressed against repetition index.

## Clinical context and outcomes

| Term | Definition (tooltip text) |
|---|---|
| Jamar dynamometer | The clinical gold standard instrument for measuring grip strength. MySquishi approximates it from muscle activity, and is not validated against it. |
| EWGSOP2 thresholds | European Working Group on Sarcopenia in Older People, second consensus. Defines low grip strength as under 27 kg for men and under 16 kg for women. Used here as a screening reference line, not a diagnosis. |
| MCID | Minimal Clinically Important Difference. The smallest change that is actually meaningful to a patient rather than measurement noise. For grip strength it is roughly 5 to 6 kg. |
| Borg CR10 | A 0 to 10 scale for perceived exertion, collected after a session. Comparing it against measured output is itself informative. |
| QuickDASH | An 11 item patient reported questionnaire on arm, shoulder, and hand disability. Scored 0 to 100, where higher means more difficulty. |
| Adherence rate | Sessions completed against sessions prescribed. One of the strongest predictors of rehabilitation outcome. |

### QuickDASH scoring

Score is `((sum of responses / number answered) - 1) * 25`, giving 0 to 100. The score is **not valid if more than one item is unanswered**, so the number of items answered is stored alongside it and the UI says so when the score cannot be computed.

## Honesty requirements attached to these terms

- Grip force in kilograms is a **calibrated estimate** derived from EMG amplitude, not a dynamometer measurement. Wherever a kg figure appears, the UI says so.
- The normative percentile reference is **approximate and drawn from a synthetic cohort**. It is labeled as such wherever it appears.
- EWGSOP2 thresholds are a screening reference. The app does not diagnose sarcopenia or anything else.
- MySquishi is a training aid, not a medical device, and does not replace a clinician.
