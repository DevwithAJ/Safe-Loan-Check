from pathlib import Path
import importlib
import json
import os

import sklearn

ROOT = Path(__file__).resolve().parents[1]
meta = json.loads((ROOT / "models" / "risk_model_meta.json").read_text(encoding="utf-8"))
EXPECTED_SKLEARN = str(meta.get("sklearn_version") or "1.8.0")

print(f"scikit-learn installed: {sklearn.__version__}")
print(f"expected for bundled model: {EXPECTED_SKLEARN}")
print(f"model: {meta.get('model_name')}")
if sklearn.__version__ != EXPECTED_SKLEARN:
    raise SystemExit(
        f"Version mismatch. Run: python -m pip install --upgrade scikit-learn=={EXPECTED_SKLEARN}"
    )

for module in ["flask", "rapidfuzz", "numpy_financial", "google_play_scraper"]:
    try:
        importlib.import_module(module)
        print(f"{module}: OK")
    except Exception as exc:
        raise SystemExit(f"Missing/broken dependency: {module} ({exc})")

app_env = os.getenv("APP_ENV", os.getenv("FLASK_ENV", "development")).lower()
secret = os.getenv("SECRET_KEY", "")
if app_env == "production" and secret in {"", "change-this-in-production", "CHANGE_ME_TO_A_LONG_RANDOM_SECRET"}:
    raise SystemExit("Production safety check failed: set a strong SECRET_KEY.")

alias_path = ROOT / "data" / "app_reference_aliases.csv"
if not alias_path.exists():
    raise SystemExit("Missing required data/app_reference_aliases.csv")
with alias_path.open("r", encoding="utf-8-sig") as fh:
    alias_rows = max(0, sum(1 for _ in fh) - 1)
print(f"website alias registry: OK ({alias_rows} row(s))")

print("Environment OK")
