# Safe Loan Check — UX & Logic Fixes v1.1

## 1. Unknown is not No
The old form used checkboxes, so an unchecked transparency signal could be interpreted as absent. v1.1 uses `Yes / No / Unknown`. Only an explicit `No` can create an absence warning. `Unknown` is neutral.

## 2. Advanced listing evidence
Public listing fields are optional and collapsed by default. Real ML v1 uses app-name lexical signals; the optional listing fields are shown only as contextual evidence.

## 3. Cost Attention is separate from identity/risk
The Decision Layer still follows the project rules for Directory + ML risk + affordability. Effective APR is shown separately. If APR is at or above the configurable `COST_ATTENTION_APR` display threshold, the UI shows a `Cost Attention` badge. The threshold is a project UX aid, not a legal limit or recommendation.

## 4. Safer defaults
Loan-cost calculation is opt-in and no sample loan values are pre-filled. Listing metric fields default to blank/Unknown.
