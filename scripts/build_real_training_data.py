
from pathlib import Path
import pandas as pd
import numpy as np
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "data" / "real" / "feature_collection_worklist.csv"
OUT = ROOT / "data" / "app_risk_training_real.csv"

FEATURES = [
    "contacts_permission",
    "call_logs_permission",
    "sms_permission",
    "media_permission",
    "named_regulated_lender",
    "apr_disclosed",
    "developer_website_present",
    "physical_address_present",
    "company_email_domain",
    "app_age_days",
    "days_since_update",
    "installs_log10",
    "rating",
    "complaint_rate",
    "name_similarity",
]

BINARY = [
    "contacts_permission","call_logs_permission","sms_permission","media_permission",
    "named_regulated_lender","apr_disclosed","developer_website_present",
    "physical_address_present","company_email_domain"
]

def main():
    if not SRC.exists():
        raise SystemExit(f"Missing {SRC}")

    df = pd.read_csv(SRC).fillna("")
    complete = df[df["collection_status"].astype(str).str.lower().eq("complete")].copy()

    if complete.empty:
        print("No strict-complete listing-feature rows yet.")
        print("Real ML v1 is already available via scripts/train_real_name_model.py.")
        print("This builder is reserved for future ML v2 after balanced listing features are collected for both classes.")
        return

    for c in BINARY:
        complete[c] = pd.to_numeric(complete[c], errors="coerce")
        bad = ~complete[c].isin([0,1])
        if bad.any():
            raise SystemExit(f"{c} must contain only 0/1 on completed rows.")

    numeric = ["app_age_days","days_since_update","installs","rating","complaint_rate","name_similarity"]
    for c in numeric:
        complete[c] = pd.to_numeric(complete[c], errors="coerce")

    if complete[numeric].isna().any().any():
        bad_cols = complete[numeric].columns[complete[numeric].isna().any()].tolist()
        raise SystemExit(f"Completed rows still have missing numeric fields: {bad_cols}")

    complete["installs_log10"] = np.log10(complete["installs"].clip(lower=0) + 1)
    complete["label_risky"] = complete["group_label"].astype(str).str.lower().map(
        {"verified":0, "risky":1}
    )

    if complete["label_risky"].isna().any():
        raise SystemExit("group_label must be Verified or Risky.")

    out = complete[
        ["app_name","developer_name"] + FEATURES + ["label_risky","source_url","feature_source_date","feature_source_note"]
    ].copy()
    out["is_synthetic"] = 0
    out.to_csv(OUT, index=False)

    print(f"Built {len(out)} real training rows -> {OUT}")
    print(out["label_risky"].value_counts().rename({0:"Verified",1:"Risky"}).to_string())

if __name__ == "__main__":
    main()
