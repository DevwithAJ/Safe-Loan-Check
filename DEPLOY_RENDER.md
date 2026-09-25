# Safe Loan Check v2.6.3 — GitHub + Render Deployment

This package is already cleaned for GitHub and Render:
- `venv/` removed and ignored
- `.env` removed and ignored
- Python caches removed
- runtime SQLite cache removed
- local survey response export removed/ignored
- `render.yaml` configured for Render Free + Singapore
- Docker health check uses Render's dynamic `$PORT`

## 1) Push to GitHub

Repository:
`https://github.com/DevwithAJ/Safe-Loan-Check.git`

Open PowerShell inside this project folder and run:

```powershell
git init
git branch -M main
git remote remove origin 2>$null
git remote add origin https://github.com/DevwithAJ/Safe-Loan-Check.git
git add .
git status
git commit -m "Safe Loan Check v2.6.3 team roles Render ready"
git push -u origin main
```

If the remote repository already has commits and push is rejected, do not force-push blindly. Pull/reconcile the remote history first or confirm that replacing it is intended.

## 2) Deploy with Render Blueprint

1. Sign in to Render and connect GitHub.
2. Click **New > Blueprint**.
3. Select `DevwithAJ/Safe-Loan-Check`.
4. Keep Blueprint path as `render.yaml`.
5. Deploy the Blueprint.

The Blueprint creates:
- Web service: `safe-loan-check`
- Runtime: Docker
- Plan: Free
- Region: Singapore
- Health check: `/readyz`
- Auto deploy: each commit

## 3) Verify after deployment

Open:
- `https://YOUR-SERVICE.onrender.com/healthz`
- `https://YOUR-SERVICE.onrender.com/readyz`

`/readyz` should return HTTP 200 and `"status": "ready"`.
Then open the main site and verify the English/Hindi language selector.

## 4) First functional tests

Test at least:
- Bajaj Finance package: `org.altruist.BajajExperia`
- Kissht package: `com.fastbanking`
- RING package: `com.ideopay.user`

Known RBI-listed identities should resolve as listed when they exist in the bundled dated RBI directory snapshot.

## Free-tier note

Render Free web services can spin down after inactivity and their local filesystem is ephemeral. The SQLite metadata cache may reset after restart/redeploy. Core bundled RBI data and model files remain available because they are part of the deployed image.

## Team roles

Team roles are displayed on the public About page and language-selection screen. See `PROJECT_INFO.md`.
