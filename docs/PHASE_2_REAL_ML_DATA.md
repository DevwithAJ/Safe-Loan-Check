
# Phase 2 — Real ML Dataset Preparation

Status: **Started**

## What is already prepared

### Verified candidates
`data/real/verified_candidate_apps_200.csv`

A reproducible sample of **200 apps** was selected from the imported RBI DLA directory.
These are candidates for the Verified class, but public listing features still have to be collected.

### Risky evidence seed
`data/real/risky_evidence_seed_rbi.csv`

**33 apps** are seeded from an official RBI enforcement press release dated 29 April 2024.
The press release names the apps as services/mobile apps used in the digital-lending operations of Acemoney (India) Limited. RBI cancelled the NBFC's Certificate of Registration and cited violations including digital-lending outsourcing/code-of-conduct issues, excessive interest and customer confidentiality.

One name, `RupeeGo`, was not labelled Risky because an exact-name match exists in the current imported RBI directory. It should be manually reviewed instead of forcing a label.

## Feature collection file

Use:
`data/real/feature_collection_worklist.csv`

For each row, collect only public, reproducible information and fill:

- contacts_permission: 0/1
- call_logs_permission: 0/1
- sms_permission: 0/1
- media_permission: 0/1
- named_regulated_lender: 0/1
- apr_disclosed: 0/1
- developer_website_present: 0/1
- physical_address_present: 0/1
- company_email_domain: 0/1
- app_age_days
- days_since_update
- installs
- rating
- complaint_rate
- name_similarity
- feature_source_date
- feature_source_note

Then set:
`collection_status = Complete`

## Important rules

1. Do not use `directory_status` as an ML feature.
2. Do not guess permissions, complaints, or disclosures.
3. If an app listing cannot be found, leave it Pending/Excluded rather than inventing values.
4. Every risky label must keep its evidence source.
5. Use the current RBI directory only as a separate verification layer and for constructing the Verified group.
6. Do not call a missing app “illegal”.

## After feature collection

Build the real ML table:

```powershell
python scripts\build_real_training_data.py
```

Compare baseline + three models:

```powershell
python scripts\compare_real_models.py
```

The comparison includes:
- contact-permission baseline,
- Logistic Regression,
- Random Forest,
- HistGradientBoosting.

Select a final model only after checking risky-class Recall, Precision, F1 and PR-AUC.

## Survey

After exporting Google Form responses into:
`data/real/survey_responses.csv`

run:

```powershell
python scripts\analyze_survey.py
```

Do not finalise the campus problem statement until at least 100 valid anonymous responses are collected.
