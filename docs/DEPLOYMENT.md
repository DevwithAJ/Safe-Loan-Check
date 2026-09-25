# Deployment Guide

## 1. Pre-deployment checks

```bash
python scripts/check_environment.py
python scripts/validate_real_data.py
python scripts/production_smoke.py
python -m pytest -q
```

Confirm `/status` shows:
- RBI directory available and within freshness window
- ML model ready
- metadata provider installed if auto metadata is enabled

## 2. Required production settings

Set a long random `SECRET_KEY` and use `APP_ENV=production`.

Recommended behind an HTTPS reverse proxy:

```text
APP_ENV=production
TRUST_PROXY=1
FORCE_HSTS=1
AUTO_METADATA_ENABLED=1
REVIEW_ANALYSIS_ENABLED=0
```

## 3. Start

```bash
gunicorn -c gunicorn.conf.py wsgi:app
```

The included Gunicorn config deliberately uses one process and four threads so the built-in process-local rate limiter remains coherent. For multiple workers/containers, replace it with a shared Redis-backed limiter.

## 4. Health checks

- Liveness: `/healthz`
- Readiness: `/readyz`

Use `/healthz` for platform process health. Use `/readyz` in operational monitoring to detect missing model/directory assets.

## 5. RBI directory operations

Download a new official export, then:

```bash
python scripts/refresh_rbi_directory.py /path/to/export.xlsx --source-date YYYY-MM-DD
python scripts/validate_real_data.py
```

Restart the application so the in-memory index uses the new snapshot.

## 6. Persistent cache

`instance/metadata_cache.sqlite3` contains only cached public app metadata and derived review aggregates. On an ephemeral platform it is safe to lose; losing it only causes future metadata lookups to be fetched again.
