# ML Model Status — Production Candidate v2.5

**Active probability model:** Random Forest — Real Label Name Signals  
**Model version:** `real-label-name-signal-v1`  
**Runtime scikit-learn:** 1.8.0  
**Training records:** 233 real-labelled app names  
**Classes:** 200 Verified / 33 Risky  
**Synthetic training rows:** 0  
**High-risk threshold:** 0.42

## Held-out test
- Risky recall: 1.00
- Risky precision: 0.50
- F1: 0.667
- PR-AUC: 0.578
- Confusion matrix: `[[33, 7], [0, 7]]`

## Baseline on same held-out test
Rule: app name contains `cash` or `loan`.
- Recall: 0.714
- Precision: 0.263
- F1: 0.385

## Leakage controls
The ML model does not use:
- RBI directory status
- RBI directory fuzzy-match score / `name_similarity`
- source URL
- enforcement evidence fields

## v2 runtime change
Production Candidate v2.5 can automatically collect public Play listing evidence from an explicit Play URL. These fields are used by a **separate transparent rule layer** and are displayed separately from the ML probability. They are not misrepresented as learned ML features.

## Why the active model is still called v1
The Risky class does not yet have balanced, traceable permissions/rating/installs/review metadata comparable to the Verified class. Training a listing-feature model now would require imputing/guessing too much evidence or introducing dataset bias. The production candidate therefore keeps the honest v1 model and adds safer public-evidence automation around it.

## Next ML milestone
Train `ML v2` only after enough rows in both classes have verified public-listing features. Evaluate Logistic Regression + tree model(s) using stratified training-side CV, then a held-out set and later temporal holdout. Prioritize Risky recall while enforcing a minimum precision target.
