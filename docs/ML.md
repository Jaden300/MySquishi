# ML stack

M1 to M14: inputs, outputs, explainability, and fit timing. This file is the contract each model slice is checked against.

Stack: scikit-learn, SciPy, NumPy, Pandas. Models stay small and fast, and the whole set trains in under a minute on the synthetic cohort.

## Summary table

| ID | Name | Estimator | Output | Explanation from | Fit timing | Depends on |
|---|---|---|---|---|---|---|
| M1 | Signal quality index | LogisticRegression | Interval 0-100 | coefficients | build time | signal_gen |
| M2 | Rep segmentation | Bonato dual threshold | list of reps | thresholds reported verbatim | deterministic | filters |
| M3 | EMG to force | Ridge | kg Interval | coefficients | per user at calibration | features |
| M4 | Rep quality | HistGradientBoosting | 0-100 plus factor | permutation importance | build time | M2 |
| M5 | Spectral fatigue | linregress | slope Interval, R2 | slope sign, R2, n reps | per session | M2 |
| M6 | Session anomaly | IsolationForest | score plus direction | leave one feature out delta | build time | M2, M5, cohort |
| M7 | Perceived vs actual | Ridge | Borg Interval plus residual | coefficients | build time | cohort |
| M8 | Session prescriber | rules | targets plus reasons | the rules themselves | request time | M4, M5, M6, M13 |
| M9 | Recovery trajectory | best of linear, exponential plateau, GP | median path plus 80 percent band | winning model, CV MAE table | per patient, memoized | sessions |
| M10 | Time to goal | posterior crossing | weeks median plus 10th and 90th | inherits M9 | request time | M9 |
| M11 | Plateau detection | CUSUM | changepoints plus verdict | threshold, drift magnitude | request time | sessions |
| M12 | Recovery archetype | KMeans(4) plus PCA(2) | archetype plus coordinates | two most separating features | build time | cohort |
| M13 | Adherence risk | LogisticRegression | probability Interval | coefficients | build time | cohort |
| M14 | Cohort percentile | empirical percentiles | percentile Interval | reference and n | build time | cohort, M3 |
| M15 | Weekly rollup | ISO week aggregation | per week Intervals plus cross week change | week counts, misses, quiet weeks | request time, memoized | sessions |

## Dependency gates

```
signal_gen -> filters -> features -> M2 -> {M4, M5} -> M6 -> M8
cohort_gen -> {M6, M7, M12, M13, M14}
sessions -> M9 -> M10
```

**M2 and cohort_gen are the two gates.** Everything else parallelizes once they land. M2 is the single point of failure: a subtly wrong segmentation is worse than a broken one, because it fails silently through M4, M5, M6, and M8. No downstream model slice starts until M2 recovers exact rep counts against generator ground truth.

## Signal layer

**M1 signal quality index.** Logistic regression over windowed features: baseline drift, relative power at 60 Hz, saturation ratio, and an SNR estimate. Produces a 0 to 100 score driving a permanent, honest quality badge. Training data comes from sweeping the generator's junkiness dial, so M1 needs no cohort. This model is the project's integrity feature: it tells the user when not to trust the reading.

**M2 rep segmentation.** Adaptive dual threshold on the RMS envelope, Bonato style. Baseline mean and standard deviation come from a rest window. Onset threshold is `mu + k_on * sigma`, offset threshold is `mu + k_off * sigma` with `k_off < k_on`, and that gap is the hysteresis that suppresses chatter. The envelope must stay above onset for a minimum duration before a rep is declared, and below offset for a minimum duration before it closes. Output is a list of reps with start, peak, end, and duration.

**M3 EMG to force.** Ridge regression from normalized amplitude features to estimated grip force in kilograms, fitted per user during calibration and stored on the calibration row. Honest framing: this is an estimate calibrated to a self reported reference, not a dynamometer reading, and the interval comes from the fit residuals.

**M4 rep quality.** Gradient boosted regressor over per rep features: RFD, hold CV, plateau flatness, relaxation completeness, and peak accuracy against target. Produces a 0 to 100 score plus the top contributing factor as feedback text, for example "your hold was steady, but you released too quickly."

**M5 spectral fatigue.** Per rep FFT to median frequency, then linear regression of MDF against rep index. A negative slope beyond a threshold triggers a fatigue flag and a rest recommendation. Reports slope with its confidence interval, R squared, p value, and the Thorstensson and Dimitrov indices alongside.

The fatigue claim must be engineered rather than hoped for. The generator's per rep spectral decrement is an explicit parameter, defaulted large enough to be statistically significant at ten reps, and the p value is asserted in a test.

## Session layer

**M6 session anomaly.** Isolation Forest over a session feature vector: mean percent MVC, rep count, fatigue slope, CV, adherence gap, and SQI. Flags sessions that do not fit the patient's own pattern. **Direction matters**: an anomaly is classified as positive or negative by comparing against the patient's own rolling mean, so an exceptional session is not reported as a problem.

**M7 perceived versus actual effort.** Ridge predicting Borg CR10 from session features. A large residual, where the patient feels wrecked but produced little or the reverse, is clinically interesting and is surfaced as an insight card.

**M8 adaptive session prescriber.** Rule engine over recent performance, fatigue trend, anomalies, and adherence, setting the next session's target percent MVC, rep count, hold duration, and rest interval. It emits a list of plain text reasons alongside the numbers. Never a black box number.

## Longitudinal layer

**M9 recovery trajectory.** The centerpiece. Three candidates are fitted to the patient's strength history and selected by cross validated error:

- linear trend as the baseline,
- exponential plateau `y = a + (b - a) * (1 - exp(-k * t))`, the physiologically realistic shape for rehabilitation and the one that usually wins,
- Gaussian process regression with an RBF plus linear kernel, which gives a principled uncertainty band.

Selection uses **expanding window time series cross validation**. Shuffled cross validation leaks the future into the past and flatters the linear model, so it is never used here. The 80 percent band comes from the GP posterior directly, or from residual bootstrap for the parametric winners, so the fan chart exists whichever model wins.

**M10 time to goal.** Samples M9's posterior and finds the first crossing of the goal per draw. Reports median weeks plus the 10th and 90th percentiles, and explicitly reports the share of draws that never cross within the horizon rather than silently dropping them. Never a bare point estimate: the uncertainty is the honest part.

**M11 plateau detection.** Two sided CUSUM over the detrended strength series, returning candidate changepoints with the mean slope before and after, and a plateau verdict when the post changepoint slope confidence interval includes zero. Distinguishes a true plateau from short term noise and triggers a protocol change recommendation.

**M12 recovery archetype clustering.** KMeans with k of 4 over per patient trajectory shape features: initial slope, final to initial ratio, time to 80 percent of final, plateau index, and variability. Produces named archetypes: fast responder, steady climber, late bloomer, plateaued. A PCA to two dimensions is persisted alongside so the cohort scatter has stable coordinates.

**KMeans label order is not stable across refits.** Cluster 0 is not reliably the fast responder next time. Archetype names are therefore mapped from centroid ordering at fit time and that map is persisted inside the artifact, never hardcoded to a cluster index.

**M13 adherence and dropout risk.** Logistic regression on session cadence, days since last session, completion rate, recent trend, and weeks elapsed, predicting probability of disengagement within 14 days. Drives gentle nudges. The surfaced copy is encouraging and never shaming.

**M14 cohort percentile normalization.** Empirical percentile curves by age band and sex, plus the EWGSOP2 thresholds as reference lines. Places an absolute number in context. The reference is approximate and synthetic, and carries a flag the UI must display.

**M15 weekly rollup.** Sessions bucketed into ISO weeks off `started_at`, which is the unit a patient and a clinician actually talk in. Weeks with no sessions are emitted rather than skipped, because a silence is the most informative thing a rollup can show, and a prescribed session that was never completed counts toward adherence and toward nothing else. The current week is flagged partial and excluded from every trend, since comparing a two day week against whole ones manufactures a decline.

The uncertainty is two quantities and they are treated differently. Within a week the interval is the observed spread of the sessions themselves, matching the clinician report, because those sessions are the population rather than a sample from one. Across weeks the change genuinely is an estimate, so it carries a bootstrap interval. The kilogram figure narrows to the grip sessions in each week, per the clinical gate.

## Explainability

Every model output shown to a user is accompanied by what drove it. Tree models use permutation importance, linear models use coefficient inspection. Every model returns the same `Explanation` shape: a summary, a list of factors with name, contribution, direction, and plain text, and the method used.

A "why am I seeing this" affordance appears on every insight card.

## Interval discipline

Every predictive model returns an `Interval` with point, lower, upper, and level, never a bare float. This is enforced structurally: the frontend's `IntervalReadout` requires lower and upper props, so a bare point estimate is a type error, and a parameterized test asserts `lower <= point <= upper` across every interval returning model.

## Build time versus request time

Cohort trained and cached to joblib: M1, M4, M6, M7, M12, M13, M14. Written by `ml/train_all.py` along with a manifest recording version, seed, timestamp, and per model cross validation metrics.

Fitted per session or per request: M2 (deterministic), M3 (per user at calibration, persisted on the calibration row), M5, M8, M9, M10, M11, M15. M9 is the only request time fit heavy enough to notice, and with sixty or fewer observations a GP fit is milliseconds, but it is memoized on patient and session count anyway. M15 is memoized too, on session count and on the calendar week, because its answer moves when the week turns over even with no new session.
