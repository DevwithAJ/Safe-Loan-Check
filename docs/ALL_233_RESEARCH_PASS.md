# All 233 Apps — Research & Evidence Pass

Snapshot date: 2026-09-24

## What this pass does

- Processes all 233 candidate rows (200 Verified + 33 Risky seed rows).
- Keeps label evidence traceable to the RBI DLA directory or RBI enforcement source.
- Computes `name_similarity` reproducibly against the current project RBI DLA directory.
- Adds detailed public metadata for rows that were directly verified during research.
- Leaves unsupported values blank instead of converting unknown values to `0`.
- Keeps `collection_status=Pending` until every strict field required by the current builder is present.

## Important interpretation

A blank value means **not verified**, not “No”. This distinction is essential for permissions, disclosure and developer-transparency fields.

`directory_status` is label/evidence context and must **not** be used as an ML feature.

The 33 Risky seed labels are backed by RBI's 29-Apr-2024 enforcement release naming those apps among Acemoney (India) Limited digital lending services. This is evidence for the academic seed label; the project should not independently describe an app as illegal.

## Bulk Google Play metadata collector

Run on an internet-connected system:

```bash
pip install google-play-scraper rapidfuzz
python scripts/collect_play_metadata.py
```

The collector can populate store metadata such as installs, rating, release/update dates, developer website/address/email and APR-text detection for Google Play rows. It deliberately does not infer Android runtime permissions from Play Data Safety categories.

## Why strict model-ready is still low

The current `build_real_training_data.py` requires every one of the 15 feature fields to be non-missing. Public sources do not expose all permission/app-age/review-derived fields for every app, especially removed or older apps. Do not fabricate these values just to make a row Complete. A later modeling step should either collect consistent manifest/review evidence or formally redesign the feature set and missing-data strategy before training.
