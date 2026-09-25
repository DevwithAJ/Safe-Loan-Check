# RBI DLA Directory — Data Card

**Source:** Reserve Bank of India — Digital Lending Apps Directory  
**Collection / download date:** 25 September 2026  
**Original file:** `data/real/RBI_DLA_Official_2026-09-25.xlsx`  
**Raw CSV copy:** `data/real/dla_directory_raw_2026-09-25.csv`  
**Official directory URL:** https://data.rbi.org.in/BOE/OpenDocument/opendoc/custom.jsp?iDocID=ARfEgy.WNSVIvFfvSIVmBCw&sIDType=CUID

## Size

- Source records: **2,758**
- Usable DLA rows: **2,750**
- Excluded non-app rows containing only NA/NONE: **8**
- Unique normalized DLA / app names: **1,118**
- Unique regulated entities represented: **442**
- Rows with an extracted Android package ID: **939**
- Unique extracted Android package IDs: **421**

## Fields used by Safe Loan Check

- App / DLA name
- DLA owner / LSP name
- Regulated entity
- Platform
- Canonical app link when possible
- Original/raw DLA link
- Android package ID when extractable
- RBI source record number
- Source date and source URL

## Cleaning and identity handling

1. Forward-filled `Entity Name` because the Excel report visually groups multiple DLA rows under one regulated entity.
2. Preserved the original RBI link and source serial number for traceability.
3. Extracted Android package IDs from direct links, scheme-less links, embedded/wrapped links, common URL typos, Google Play test paths, and compatible Android-store links that expose the same package ID.
4. Canonicalized package-bearing links to `https://play.google.com/store/apps/details?id=<package>` for stable matching.
5. Kept rows without a package ID. Those rows can still be matched using DLA title plus owner/regulated-entity identity.
6. Excluded only 8 rows where the DLA name itself is NA/NONE rather than guessing an app identity.

## Matching rule in v2.5

1. Exact Android package ID is the strongest identity signal.
2. Exact-equivalent app name + strong owner/regulated-entity identity is next.
3. Strong current Play title + owner/regulated-entity identity can confirm an official row that lacks a direct package-bearing Play link.
4. If a copied app name conflicts with a known official package/developer, the result is `Unclear`, not automatically `Listed`.

## Validation audit

- **421 / 421** unique extracted Android packages resolve as `Listed` at 100/100.
- **2,750 / 2,750** usable official rows resolve as `Listed` when checked using their own official identity.

These are lookup-consistency tests against the dated snapshot. They do not prove that an app is safe, legal, inexpensive, or RBI-approved.

## Leakage rule

`directory_status` and package-match status are not classifier features. Directory verification stays in Check 1 and the Decision Layer; ML v1 remains separate.
