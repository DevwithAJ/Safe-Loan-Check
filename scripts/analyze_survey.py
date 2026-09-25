
from pathlib import Path
import json
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "data" / "real" / "survey_responses.csv"
OUT = ROOT / "data" / "real" / "survey_summary.json"

def pct(series, value):
    valid = series.dropna().astype(str).str.strip()
    if len(valid) == 0:
        return None
    return round((valid.str.lower() == value.lower()).mean() * 100, 1)

def main():
    df = pd.read_csv(SRC).fillna("")
    if df.empty:
        print("Survey file has no response rows yet.")
        return

    usefulness = pd.to_numeric(df["tool_usefulness_1_to_5"], errors="coerce")
    summary = {
        "responses": int(len(df)),
        "seen_instant_loan_ads_yes_pct": pct(df["seen_instant_loan_ads"], "Yes"),
        "used_or_known_user_yes_pct": pct(df["used_or_known_user"], "Yes"),
        "heard_rbi_dla_directory_yes_pct": pct(df["heard_rbi_dla_directory"], "Yes"),
        "knows_apr_or_kfs_yes_pct": pct(df["knows_apr_or_kfs"], "Yes"),
        "heard_threatening_calls_yes_pct": pct(df["heard_threatening_calls"], "Yes"),
        "tool_usefulness_mean": round(float(usefulness.mean()), 2) if usefulness.notna().any() else None,
        "target_met_100_responses": bool(len(df) >= 100),
    }
    OUT.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))

if __name__ == "__main__":
    main()
