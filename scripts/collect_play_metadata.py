"""
Safe Loan Check - Google Play metadata collector
Run on an internet-connected machine.

Install:
    pip install google-play-scraper rapidfuzz

Run from the Safe_Loan_Check project root:
    python scripts/collect_play_metadata.py

Rules:
- Does NOT invent permissions.
- Does NOT mark rows Complete unless all strict required fields exist.
- Uses current Play metadata for installs/rating/release/update/developer support/APR text.
- Complaint rate = fraction of sampled recent reviews rated <=2 stars, only when >=10 reviews are returned.
"""

from pathlib import Path
from datetime import datetime
from urllib.parse import urlparse, parse_qs
import csv, re, math

try:
    from google_play_scraper import app, reviews, Sort
except ImportError:
    raise SystemExit("Install dependency first: pip install google-play-scraper")

ROOT = Path(__file__).resolve().parents[1] if Path(__file__).parent.name == "scripts" else Path.cwd()
WORKLIST = ROOT / "data" / "real" / "feature_collection_worklist.csv"
BACKUP = ROOT / "data" / "real" / "feature_collection_worklist_before_play_collection.csv"
LOG = ROOT / "data" / "real" / "play_metadata_collection_log.csv"

TODAY = datetime.now().date()
FREE_EMAILS = {"gmail.com","yahoo.com","outlook.com","hotmail.com","rediffmail.com","icloud.com","protonmail.com"}

def package_id(url):
    if not url or "play.google.com" not in url:
        return None
    try:
        return parse_qs(urlparse(url).query).get("id", [None])[0]
    except Exception:
        return None

def bool01(v):
    return 1 if v else 0

def company_domain_flag(email):
    if not email or "@" not in email:
        return None
    domain = email.rsplit("@",1)[-1].lower().strip()
    return 0 if domain in FREE_EMAILS else 1

def parse_release_date(v):
    if not v:
        return None
    for fmt in ("%b %d, %Y","%d %b %Y","%Y-%m-%d"):
        try:
            return datetime.strptime(v, fmt).date()
        except Exception:
            pass
    return None

def parse_updated(v):
    if isinstance(v, (int,float)):
        try:
            return datetime.fromtimestamp(v).date()
        except Exception:
            return None
    return parse_release_date(str(v)) if v else None

def apr_flag(text):
    t = (text or "").lower()
    return 1 if re.search(r"\\bapr\\b|annual percentage rate", t) else 0

with WORKLIST.open("r", encoding="utf-8-sig", newline="") as f:
    reader = csv.DictReader(f)
    fields = reader.fieldnames
    rows = list(reader)

BACKUP.write_bytes(WORKLIST.read_bytes())
log = []

strict_required = [
    "contacts_permission","call_logs_permission","sms_permission","media_permission",
    "named_regulated_lender","apr_disclosed","developer_website_present",
    "physical_address_present","company_email_domain","app_age_days","days_since_update",
    "installs","rating","complaint_rate","name_similarity"
]

for n, row in enumerate(rows, start=1):
    pkg = package_id(row.get("app_url") or row.get("source_url"))
    if not pkg:
        continue
    try:
        info = app(pkg, lang="en", country="in")
        desc = info.get("description") or ""
        row["installs"] = info.get("minInstalls") or info.get("realInstalls") or row.get("installs")
        row["rating"] = info.get("score") if info.get("score") is not None else row.get("rating")
        row["developer_website_present"] = bool01(bool(info.get("developerWebsite")))
        row["physical_address_present"] = bool01(bool(info.get("developerAddress")))
        email_flag = company_domain_flag(info.get("developerEmail"))
        if email_flag is not None:
            row["company_email_domain"] = email_flag
        if desc:
            row["apr_disclosed"] = apr_flag(desc)

        released = parse_release_date(info.get("released"))
        if released:
            row["app_age_days"] = (TODAY - released).days
        updated = parse_updated(info.get("updated"))
        if updated:
            row["days_since_update"] = (TODAY - updated).days

        try:
            result, _ = reviews(pkg, lang="en", country="in", sort=Sort.NEWEST, count=100)
            scores = [x.get("score") for x in result if isinstance(x.get("score"), int)]
            if len(scores) >= 10:
                row["complaint_rate"] = round(sum(s <= 2 for s in scores) / len(scores), 4)
        except Exception:
            pass

        # Permissions are deliberately untouched: Play Data Safety != Android runtime permission manifest.
        missing = [c for c in strict_required if str(row.get(c) or "").strip() == ""]
        row["collection_status"] = "Complete" if not missing else "Pending"
        note = (row.get("feature_source_note") or "").strip()
        extra = f" Google Play collector ran {TODAY.isoformat()} for package {pkg}; permissions were not inferred."
        row["feature_source_note"] = (note + extra).strip()
        row["feature_source_date"] = TODAY.isoformat()
        log.append([n, row.get("app_name"), pkg, "OK", ",".join(missing)])
    except Exception as e:
        log.append([n, row.get("app_name"), pkg, "ERROR", str(e)[:300]])

with WORKLIST.open("w", encoding="utf-8-sig", newline="") as f:
    w = csv.DictWriter(f, fieldnames=fields)
    w.writeheader()
    w.writerows(rows)

with LOG.open("w", encoding="utf-8-sig", newline="") as f:
    w = csv.writer(f)
    w.writerow(["row","app_name","package_id","status","missing_or_error"])
    w.writerows(log)

print(f"Updated: {WORKLIST}")
print(f"Backup:  {BACKUP}")
print(f"Log:     {LOG}")
print("Important: permission fields remain blank unless separately verified.")
