
from pathlib import Path
import csv
import sys

ROOT = Path(__file__).resolve().parents[1]
REAL_DIR = ROOT / "data" / "real"
DLA = ROOT / "data" / "dla_directory_real.csv"

errors = []
warnings = []

def read_csv(path):
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))

if DLA.exists():
    rows = read_csv(DLA)
    if not rows:
        errors.append("dla_directory_real.csv exists but has no data rows.")
    for i, r in enumerate(rows, start=2):
        if not (r.get("app_name") or "").strip():
            errors.append(f"DLA row {i}: missing app_name")
        if not (r.get("source_date") or "").strip():
            errors.append(f"DLA row {i}: missing source_date")
        if not (r.get("source_url") or "").strip():
            errors.append(f"DLA row {i}: missing source_url")
        if str(r.get("is_demo","")).strip() not in {"0","0.0","False","false"}:
            errors.append(f"DLA row {i}: is_demo must be 0 for real data")
else:
    warnings.append("No data/dla_directory_real.csv yet. Import the dated RBI export first.")

label_path = REAL_DIR / "label_evidence.csv"
if label_path.exists():
    labels = read_csv(label_path)
    for i, r in enumerate(labels, start=2):
        label = (r.get("label") or "").strip().lower()
        if label and label not in {"verified","risky","excluded"}:
            errors.append(f"Label row {i}: label must be Verified, Risky, or Excluded")
        if label == "risky" and not (r.get("evidence_source") or "").strip():
            errors.append(f"Label row {i}: Risky label missing evidence_source")

listing_path = REAL_DIR / "app_listing_dataset.csv"
if listing_path.exists():
    header = read_csv(listing_path)
    # directory_status must not be a classifier feature column.
    with listing_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        cols = next(reader, [])
    if "directory_status" in cols:
        errors.append("app_listing_dataset.csv contains directory_status. Remove it to avoid leakage.")

print("REAL DATA VALIDATION")
print("=" * 60)
if errors:
    print("ERRORS:")
    for e in errors:
        print(" -", e)
else:
    print("No blocking errors found.")

if warnings:
    print("\nWARNINGS:")
    for w in warnings:
        print(" -", w)

if errors:
    sys.exit(1)
