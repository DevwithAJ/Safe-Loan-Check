# Real ML v1 — App-Name Risk Signals

## What changed
The synthetic demo model has been replaced by an experimental model trained on **real labels only**:

- 200 `Verified` examples sampled from the dated RBI DLA directory used by the project.
- 33 `Risky` examples backed by the RBI enforcement evidence recorded in the project dataset.
- 0 synthetic training rows.

## Why v1 uses app-name lexical features
The current 233-row research pass does **not** contain balanced public listing metadata for both classes. In particular, the risky set has no reliable permissions, installs, rating, app age, update age or complaint-rate fields. Imputing those fields and training anyway would let the model learn the data-collection process rather than genuine risk patterns.

Therefore v1 uses only features available for every record at decision time and not derived from directory status:

- app-name length, word count, digit count, symbol count, uppercase ratio;
- presence of lexical terms such as `loan`, `cash`, `rupee`, `credit`, `borrow`, `lend`, `money`, `paisa`, `finance`, `instant`, `quick`, `easy`, `kredit`, `advance`, `emi`.

The model **does not use** `directory_status`, `name_similarity`, source URL or label evidence as inputs.

## Model comparison and validation
- Stratified 80:20 train/test split, random state 42.
- Model choice and threshold tuning are performed on the 80% training split using 5-fold stratified cross-validation.
- Target for threshold tuning in this build: risky recall >= 0.75 and risky precision >= 0.30 on training CV.
- Candidate models: Random Forest, Logistic Regression and HistGradientBoosting over the same lexical features.
- The held-out 20% test set is evaluated only after the model and threshold are selected from training CV.

See `models/real_name_model_evaluation.json` for exact metrics and `models/real_name_model_holdout_predictions.csv` for the held-out predictions.

## Important limitation
This is a **real-label experimental model**, not the final public-listing classifier envisioned by the redesign guide. The UI therefore separates:

1. ML app-name risk signal (the model probability), and
2. public listing warnings entered by the user (contextual signals, not currently learned by v1).

The next model version should be retrained only after comparable public listing features are collected for both Verified and Risky classes.
