
# Phase 1 — Real Data & Problem Evidence

Status: **In progress — RBI directory imported**

This phase replaces the runnable demo/synthetic setup with traceable project evidence.

## 1. Official RBI directory source

The RBI home page currently links **“DLA’s deployed by Regulated Entities”** under Citizen's Corner to a live report on `data.rbi.org.in`.

Official live directory:
https://data.rbi.org.in/BOE/OpenDocument/opendoc/custom.jsp?iDocID=ARfEgy.WNSVIvFfvSIVmBCw&sIDType=CUID

Official RBI press release explaining the directory:
https://rbi.org.in/scripts/BS_PressReleaseDisplay.aspx?prid=60403

Important interpretation:
- A directory match supports the claim that the DLA has been reported as associated with an RBI-regulated entity.
- RBI states that the directory is based on information submitted by regulated entities and is made available for the limited purpose of verifying claimed association.
- Do **not** write “RBI approved app”.
- Do **not** write “illegal app” merely because an app is missing.
- UI wording should remain: **Listed / Not listed / Unclear**.

## 2. What we need to save from the live directory

Save a dated copy for reproducibility.

Minimum fields:
- DLA / app name
- Owner / LSP name
- Platform
- DLA / app-store URL
- Regulated Entity
- Grievance officer details
- Regulated Entity website
- Date the copy was saved
- Source URL

Target for the project classifier: start with a manageable sample of **150–300 app listings**.

## 3. Labelling policy

### Verified group
An app appears in the dated RBI DLA directory copy.

### Risky group
Use only when:
1. the app is not found in the dated directory copy, **and**
2. at least one traceable negative source exists, such as:
   - official advisory,
   - credible news report,
   - app-store removal evidence,
   - clearly documented repeated harassment / hidden-fee complaints.

### Excluded
If the evidence is ambiguous, exclude the record. Do not guess.

## 4. Leakage rule

`directory_status` must **not** be a classifier feature.

The ML model may use public listing features such as:
- sensitive permissions,
- named lender disclosure,
- APR / fee disclosure,
- developer transparency,
- app age / update recency,
- installs / rating,
- complaint-rate features,
- name similarity.

Directory status remains a separate verification check and is combined only in the Decision Layer.

## 5. Files created for this phase

`data/real/dla_directory_raw.csv`
- Raw RBI directory export / transcription target.

`data/real/app_listing_dataset.csv`
- Public app-listing features.

`data/real/label_evidence.csv`
- Every class label must have a traceable evidence source.

`data/real/survey_responses.csv`
- Anonymous campus-survey results.

`data/real/source_registry.csv`
- Source log with collection/check dates.

## 6. Immediate tasks

1. Open the official RBI DLA directory.
2. Export/download it if the portal offers export; otherwise save a dated copy and transcribe/import required fields.
3. Put that file into `data/real/`.
4. Run:
   `python scripts/import_rbi_dla.py <downloaded_file.csv>`
5. Run:
   `python scripts/validate_real_data.py`
6. Launch the anonymous survey and collect at least 100 responses.
7. Only after the real labels and features exist, retrain and compare models.

## 7. Phase-completion criteria

Phase 1 is complete when:
- final problem statement is written using actual survey numbers,
- 100+ anonymous survey responses are available,
- a dated RBI DLA directory copy is saved,
- source registry is filled,
- no synthetic/US data is used as final evidence.

## RBI directory import refreshed — 25 September 2026

The latest supplied official Excel export has been imported into the v2.5 identity index.

- Source records: **2,758**
- Usable DLA rows: **2,750**
- Excluded NA/NONE non-app rows: **8**
- Unique normalized DLA/app names: **1,118**
- Unique regulated entities: **442**
- Package-bearing rows: **939**
- Unique extracted Android packages: **421**
- Output used by the Flask app: `data/dla_directory_real.csv`

The Flask configuration automatically prefers this real lookup file over the bundled demo directory. Package-first identity matching and title/owner fallbacks are documented in `DIRECTORY_IDENTITY_FIX_V2_5.md`.

Still pending in the evidence plan:
- 100+ genuine anonymous survey responses
- 30-participant impact pilot
- final report update with the completed survey/pilot results

