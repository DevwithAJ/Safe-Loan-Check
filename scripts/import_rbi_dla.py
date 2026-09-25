
from pathlib import Path
import csv
import re
import sys
from datetime import date

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from services.validators import package_id_from_play_url
OUT = ROOT / "data" / "dla_directory_real.csv"

ALIASES = {
    "app_name": [
        "name of the dla", "dla name", "app name", "name of dla"
    ],
    "owner_name": [
        "name of the owner of dla", "owner of dla", "owner name", "lsp"
    ],
    "platform": [
        "available on", "platform", "app store"
    ],
    "app_url": [
        "link to dla", "dla link", "app url", "url"
    ],
    "regulated_entity": [
        "regulated entity", "name of re", "re name", "entity name"
    ],
    "source_date": [
        "source date", "download date", "collected on"
    ],
    "source_url": [
        "source url"
    ],
}


def normalize_public_url(value: str) -> str:
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

def norm(s):
    s = str(s or "").strip().lower()
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return " ".join(s.split())

def resolve(headers, aliases):
    norm_headers = {norm(h): h for h in headers}
    for a in aliases:
        na = norm(a)
        if na in norm_headers:
            return norm_headers[na]
    for nh, raw in norm_headers.items():
        for a in aliases:
            if norm(a) in nh or nh in norm(a):
                return raw
    return None

def main():
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python scripts/import_rbi_dla.py path\\to\\rbi_export.csv")

    src = Path(sys.argv[1])
    if not src.exists():
        raise SystemExit(f"File not found: {src}")

    with src.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            raise SystemExit("CSV has no header row.")
        headers = reader.fieldnames

        mapping = {key: resolve(headers, aliases) for key, aliases in ALIASES.items()}
        if not mapping["app_name"]:
            raise SystemExit(
                "Could not find the app/DLA name column. "
                f"Available headers: {headers}"
            )

        rows = []
        for r in reader:
            app = str(r.get(mapping["app_name"], "") or "").strip()
            if not app:
                continue

            raw_app_url = str(r.get(mapping["app_url"], "") or "").strip() if mapping["app_url"] else ""
            package_id = package_id_from_play_url(raw_app_url) or ""
            rows.append({
                "app_name": app,
                "developer_name": str(r.get(mapping["owner_name"], "") or "").strip() if mapping["owner_name"] else "",
                "regulated_entity": str(r.get(mapping["regulated_entity"], "") or "").strip() if mapping["regulated_entity"] else "",
                "source_date": str(r.get(mapping["source_date"], "") or "").strip() if mapping["source_date"] else date.today().isoformat(),
                "source_url": str(r.get(mapping["source_url"], "") or "").strip() if mapping["source_url"] else "https://data.rbi.org.in/BOE/OpenDocument/opendoc/custom.jsp?iDocID=ARfEgy.WNSVIvFfvSIVmBCw&sIDType=CUID",
                "platform": str(r.get(mapping["platform"], "") or "").strip() if mapping["platform"] else "",
                "app_url": normalize_public_url(raw_app_url),
                "raw_app_url": raw_app_url,
                "package_id": package_id,
                "source_record_no": "",
                "is_demo": 0,
            })

    rows.sort(key=lambda x: (x["app_name"].lower(), x["developer_name"].lower()))

    fieldnames = [
        "app_name","developer_name","regulated_entity","source_date",
        "source_url","platform","app_url","raw_app_url","package_id",
        "source_record_no","is_demo"
    ]
    with OUT.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)

    print(f"Imported {len(rows)} rows -> {OUT}")
    print("Next: python scripts/validate_real_data.py")

if __name__ == "__main__":
    main()
