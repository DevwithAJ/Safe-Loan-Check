# Production Candidate v2.2 — Change Log

## Implemented

### Security & operations
- Application factory and WSGI entry point
- Gunicorn + Docker production launch
- CSRF protection for browser POSTs
- Per-IP low-volume rate limiting
- Strict identity, URL, numeric and cost validation
- Request body size cap
- Secure cookie configuration
- CSP, X-Frame-Options, nosniff, Referrer-Policy, Permissions-Policy, optional HSTS
- Reverse proxy support only when configured
- Privacy/terms/status/error pages
- Request IDs
- Liveness/readiness endpoints

### Data freshness
- RBI directory loaded once into memory
- SHA-256 and row-count metadata
- Snapshot age and stale state
- Green results are suppressed when the directory is stale
- Safe CLI refresh from official RBI export with backup + atomic replace

### Public listing automation
- HTTPS Google Play / official website reference validation
- Source-backed local website-domain → Play-package resolver; arbitrary submitted websites are not crawled
- Exact-equivalent spacing/punctuation name normalization (`click my loan` = `ClickmyLoan`)
- Explicit Play Store package validation
- Optional Google Play public metadata provider
- SQLite cache
- Rating/install/update/release/developer transparency evidence
- Exact APR-text detection
- Optional capped complaint-keyword review summary
- Permission fields never inferred from generic Data Safety text

### Decision layer
- Experimental ML and rule-based listing evidence are displayed separately
- Strong public-listing warnings can prevent a Green result
- Model-unavailable and stale-directory states become Amber rather than silently passing
- Cost warning stays independent of identity/risk result

## Still required before claiming a validated public consumer-safety product

1. Collect balanced, traceable listing features for both Verified and Risky labels.
2. Train/evaluate ML v2 on listing features with held-out and later temporal data.
3. Review every false negative and calibrate thresholds.
4. Complete 100+ genuine survey responses and the planned 30-person pilot.
5. Test the APR calculator against at least five hand-worked offers.
6. Conduct dependency, penetration, privacy and abuse review before broad public exposure.
7. Establish an owner/cadence for RBI directory refreshes and incident handling.
8. If scaling beyond one Gunicorn worker/instance, move rate limiting to a shared backend such as Redis.

## Model honesty

Production Candidate v2 does **not** rename the current lexical model to “ML v2”. The active probability model remains Real ML v1. Public listing automation improves real-world evidence and the decision layer, but it is not used as learned features until the dataset supports that claim.
