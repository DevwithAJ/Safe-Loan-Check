"""Safely refresh the local RBI DLA directory from a manually downloaded export.

Why manual download?
The RBI directory page is dynamic and production code should not depend on fragile,
uncontrolled scraping. Download the official export, then run this command so the app
keeps a dated, traceable local snapshot.

Examples:
    python scripts/refresh_rbi_directory.py "Digital Lending App.xlsx" --source-date 2026-09-25
    python scripts/refresh_rbi_directory.py cleaned.csv --source-date 2026-09-25
"""

from __future__ import annotations

from argparse import ArgumentParser
from datetime import date
from pathlib import Path
import csv
import hashlib
import json
import re
import shutil
import tempfile
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from services.validators import package_id_from_play_url
OUT = ROOT / "data" / "dla_directory_real.csv"
META = ROOT / "data" / "dla_directory_meta.json"
BACKUPS = ROOT / "data" / "backups"
DEFAULT_SOURCE_URL = "https://data.rbi.org.in/BOE/OpenDocument/opendoc/custom.jsp?iDocID=ARfEgy.WNSVIvFfvSIVmBCw&sIDType=CUID"



def normalize_public_url(value: str) -> str:
    """Return a stable package-bearing Play URL when one can be extracted."""
    text = str(value or "").strip()
    pkg = package_id_from_play_url(text)
    if pkg:
        return f"https://play.google.com/store/apps/details?id={pkg}"
    low = text.lower()
    if low.startswith("play.google.com/") or low.startswith("www.play.google.com/"):
        return "https://" + text
    if low.startswith("www."):
        return "https://" + text
    return text

def norm(value):
    value = str(value or "").strip().lower()
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return " ".join(value.split())


def detect_header_row(frame: pd.DataFrame) -> int:
    for idx, row in frame.head(30).iterrows():
        joined = " | ".join(norm(v) for v in row.tolist())
        if "name of the dla" in joined and ("entity name" in joined or "regulated entity" in joined):
            return int(idx)
    raise SystemExit("Could not detect the RBI DLA header row in the workbook.")


def find_col(columns, candidates):
    normalized = {norm(col): col for col in columns}
    for candidate in candidates:
        if norm(candidate) in normalized:
            return normalized[norm(candidate)]
    for ncol, raw in normalized.items():
        for candidate in candidates:
            nc = norm(candidate)
            if nc and (nc in ncol or ncol in nc):
                return raw
    return None


def read_source(path: Path) -> pd.DataFrame:
    if path.suffix.lower() in {".xlsx", ".xls"}:
        raw = pd.read_excel(path, sheet_name=0, header=None)
        header_row = detect_header_row(raw)
        header = raw.iloc[header_row].tolist()
        frame = raw.iloc[header_row + 1:].copy()
        frame.columns = header
        return frame
    if path.suffix.lower() == ".csv":
        return pd.read_csv(path, dtype=str)
    raise SystemExit("Supported source types: .xlsx, .xls, .csv")


def clean_rows(frame: pd.DataFrame, source_date: str, source_url: str):
    app_col = find_col(frame.columns, ["Name of the DLA", "DLA Name", "App Name", "name of dla"])
    entity_col = find_col(frame.columns, ["Entity Name", "Regulated Entity", "Name of RE", "RE Name"])
    owner_col = find_col(frame.columns, ["Name of the owner of DLA", "Owner of DLA", "Owner Name", "LSP"])
    platform_col = find_col(frame.columns, ["Available on", "Platform", "App Store"])
    url_col = find_col(frame.columns, ["Link to DLA", "DLA Link", "App URL", "URL"])
    sr_col = find_col(frame.columns, ["Sr. No", "Serial No", "S No", "S.No"])

    if not app_col:
        raise SystemExit(f"Could not find DLA/app name column. Columns: {list(frame.columns)}")

    if entity_col:
        frame[entity_col] = frame[entity_col].ffill()

    rows = []
    seen = set()
    for row_index, raw in frame.iterrows():
        app_name = str(raw.get(app_col) or "").strip()
        if not app_name or norm(app_name) in {"name of the dla", "dla name", "0", "nan", "none", "not available", "na", "n a"}:
            continue
        developer_name = str(raw.get(owner_col) or "").strip() if owner_col else ""
        regulated_entity = str(raw.get(entity_col) or "").strip() if entity_col else ""
        platform = str(raw.get(platform_col) or "").strip() if platform_col else ""
        raw_app_url = str(raw.get(url_col) or "").strip() if url_col else ""
        package_id = package_id_from_play_url(raw_app_url) or ""
        app_url = normalize_public_url(raw_app_url)
        source_record_no = str(raw.get(sr_col) or "").strip() if sr_col else str(row_index + 1)
        key = (norm(app_name), norm(developer_name), norm(regulated_entity), norm(platform), app_url.strip().lower(), package_id.lower())
        if key in seen:
            continue
        seen.add(key)
        rows.append({
            "app_name": app_name,
            "developer_name": developer_name,
            "regulated_entity": regulated_entity,
            "source_date": source_date,
            "source_url": source_url,
            "platform": platform,
            "app_url": app_url,
            "raw_app_url": raw_app_url,
            "package_id": package_id,
            "source_record_no": source_record_no,
            "is_demo": 0,
        })
    rows.sort(key=lambda r: (norm(r["app_name"]), norm(r["developer_name"]), norm(r["platform"])))
    return rows

def sha256_file(path: Path):
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main():
    parser = ArgumentParser()
    parser.add_argument("source", type=Path, help="Official RBI DLA export (.xlsx/.xls/.csv)")
    parser.add_argument("--source-date", default=date.today().isoformat(), help="Date the official export was downloaded")
    parser.add_argument("--source-url", default=DEFAULT_SOURCE_URL)
    parser.add_argument("--allow-small", action="store_true", help="Allow replacing the directory with fewer than 100 rows")
    args = parser.parse_args()

    if not args.source.exists():
        raise SystemExit(f"Source file not found: {args.source}")

    frame = read_source(args.source)
    rows = clean_rows(frame, args.source_date, args.source_url)
    if len(rows) < 100 and not args.allow_small:
        raise SystemExit(f"Safety stop: only {len(rows)} rows were produced. Use --allow-small only if intentional.")

    BACKUPS.mkdir(parents=True, exist_ok=True)
    if OUT.exists():
        backup = BACKUPS / f"dla_directory_real_before_{args.source_date}.csv"
        if not backup.exists():
            shutil.copy2(OUT, backup)

    fieldnames = [
        "app_name", "developer_name", "regulated_entity", "source_date",
        "source_url", "platform", "app_url", "raw_app_url", "package_id",
        "source_record_no", "is_demo",
    ]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", delete=False, newline="", encoding="utf-8", dir=OUT.parent, suffix=".tmp") as tmp:
        writer = csv.DictWriter(tmp, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
        tmp_path = Path(tmp.name)
    tmp_path.replace(OUT)

    metadata = {
        "source_file": str(args.source),
        "source_date": args.source_date,
        "source_url": args.source_url,
        "row_count": len(rows),
        "unique_app_names": len({norm(r["app_name"]) for r in rows}),
        "package_rows": sum(bool(r.get("package_id")) for r in rows),
        "unique_packages": len({r.get("package_id") for r in rows if r.get("package_id")}),
        "sha256": sha256_file(OUT),
        "generated_on": date.today().isoformat(),
    }
    META.write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"RBI directory refreshed: {len(rows)} rows -> {OUT}")
    print(f"Metadata: {META}")
    print("Restart the web process so its in-memory index reloads the new snapshot.")


if __name__ == "__main__":
    main()
