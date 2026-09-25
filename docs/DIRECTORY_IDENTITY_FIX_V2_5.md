# Directory Identity Fix v2.5

This release fixes the broad failure mode where apps that are present in the RBI DLA export could still appear as **Not listed** because the source link was irregular or the current Google Play title/developer spelling differed from the RBI row.

## What changed

- Updated dated RBI DLA source: `RBI_DLA_Official_2026-09-25.xlsx`.
- Preserved 2,750 usable DLA rows from 2,758 source records; 8 rows contain only NA/NONE instead of an app name and are excluded.
- Added a normalized `package_id` column and retained `raw_app_url` + `source_record_no` for traceability.
- Package extraction now tolerates direct links, scheme-less links, labels before URLs, wrapped links, common URL typos, Google Play test paths, and Android-store links exposing the same dotted package id.
- Directory lookup now compares the Google Play developer against both the RBI DLA owner/LSP **and** the regulated entity.
- Strong title + owner/entity identity can verify rows where the RBI export provides only a Play search URL or website instead of a package-bearing Play URL.
- Exact DLA name with a developer mismatch becomes **Unclear**, not **Not listed**.
- A submitted package that conflicts with a known package for the same listed DLA becomes **Unclear** to avoid blessing a clone.

## Identity priority

1. Exact Android package id → `Listed`, 100/100.
2. Exact-equivalent DLA name + strong owner/entity match → `Listed`.
3. Strong current Play title + strong owner/entity match, when no official package is available → `Listed` with a non-100 confidence score.
4. Similar but conflicting identity → `Unclear`.
5. No sufficiently close identity → `Not listed`.

## Audit on the bundled 2026-09-25 snapshot

- Usable DLA rows: 2,750
- Unique normalized DLA names: 1,118
- Rows with extracted Android package ids: 939
- Unique Android package ids: 421
- Exact package self-audit: 421 / 421 unique packages resolved as `Listed`.
- Official-row self-audit: 2,750 / 2,750 usable rows resolved as `Listed` when checked with their source identity.

These audits prove lookup consistency against the loaded official snapshot. They do **not** mean every app on Google Play is safe, approved, or legal. Safe Loan Check remains an educational awareness tool.
