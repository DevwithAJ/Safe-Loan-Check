# Safe Loan Check — Production Status

**Version:** 2.6 Production Candidate — Bilingual User-Friendly UX + Directory Identity Fix

## v2.6 UX + language improvements
- First-visit language gate: English / हिंदी.
- Language preference persists and can be changed from the header.
- User-facing pages are bilingual.
- Result page is now user-first: plain-language verdict, four easy status cards, reason for the verdict, next actions, and a Green/Amber/Red color guide.
- Technical model/directory evidence is still available but collapsed by default.
- Amber is explicitly explained as caution, not rejection.

## v2.5 fixes
- Updated local RBI DLA snapshot from the supplied 25 Sep 2026 workbook.
- 2,750 usable DLA rows retained; 8 NA/NONE non-app rows excluded.
- 939 rows contain an extracted Android package ID, representing 421 unique packages.
- Package parsing now handles direct, scheme-less, embedded/wrapped, typo-formatted and Play-test URLs.
- Directory matching compares store developer identity with both the DLA owner/LSP and regulated entity.
- Strong title + identity matching supports RBI rows with only search/website links.
- Package conflicts for a copied app name are kept **Unclear** to reduce clone false-positives.
- Bajaj Finance `org.altruist.BajajExperia` → `Listed / 100`.
- Capital Now current Play title + Finxer developer → `Listed` via strong title/owner identity even though the RBI row uses a Play search URL.

## v2.2 fixes
- `click my loan` now exactly resolves to the dated RBI entry `ClickmyLoan` after compact spacing/punctuation normalization.
- `https://web.clickmyloan.com/` resolves locally to Google Play package `com.habile.cloudbankin.clickmyloan`.
- The resolved package is used for directory matching and, when enabled, Google Play public metadata.
- Arbitrary website URLs are not crawled. Unregistered website domains remain unresolved and neutral; this avoids SSRF and prevents invented mappings.
- Alias evidence is stored in `data/app_reference_aliases.csv` with a source URL and verification date.

## Ready now
- Real dated RBI directory lookup
- Package-first + exact-equivalent name matching
- Source-backed official-website → Play-package resolver
- In-memory directory indexing + freshness protection
- Experimental real-label ML v1
- Automatic public Google Play metadata from explicit/resolved links
- Transparent rule-based listing warnings
- True-cost/APR calculator
- Conservative Decision Layer
- CSRF, validation, rate limiting, security headers
- Health/readiness endpoints
- Docker/Gunicorn/Render deployment files
- Privacy and terms pages

## Not yet evidence-complete
- ML v2 trained on balanced listing features
- 100+ genuine campus survey analysis
- 30-person impact pilot
- External security/privacy review
- Shared rate limiting for multi-instance horizontal scaling

Do not describe the current ML component as a validated fraud/legality detector.

## Validation performed in build environment (25 Sep 2026)
- Python bytecode compilation: PASS
- Core/unit tests: **28 passed** in the base build environment (Flask-dependent tests remain skipped there)
- Flask integration tests: **9 included; skipped in the base build container before Flask dependencies are installed**
- Bundled RBI index: **2,750 usable rows**
- Unique normalized DLA names: **1,118**
- Package-bearing rows: **939**
- Unique extracted Android packages: **421**
- Package identity audit: **421 / 421 Listed**
- Official-row self-audit: **2,750 / 2,750 Listed** when checked with the official row identity
- Bajaj Finance package regression: PASS
- Kissht/RING package regressions: PASS
- Capital Now title/developer fallback regression: PASS

The package is a **production candidate for a small controlled deployment**, not a validated consumer fraud-detection service.


## v2.6.1 Author Credit

Project-team roles are visible in the user-facing language gate, About page and project docs: **Ajit Kumar — Team Leader & Full-Stack Integration Lead; Ajeet Kumar — Frontend & UI/UX Developer; Sonu Kumar — Machine Learning & Data Analysis Lead; Parnav Kr Mishra — Data Research, Testing & Documentation Lead**. GitHub maintainer: **DevwithAJ**.
