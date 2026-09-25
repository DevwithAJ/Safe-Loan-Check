
from pathlib import Path
import json
import sys
import pandas as pd
import numpy as np

from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier, HistGradientBoostingClassifier
from sklearn.metrics import (
    precision_score, recall_score, f1_score, average_precision_score,
    confusion_matrix, classification_report
)

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "app_risk_training_real.csv"
OUT = ROOT / "models" / "real_model_comparison.json"

FEATURES = [
    "contacts_permission","call_logs_permission","sms_permission","media_permission",
    "named_regulated_lender","apr_disclosed","developer_website_present",
    "physical_address_present","company_email_domain","app_age_days","days_since_update",
    "installs_log10","rating","complaint_rate","name_similarity"
]

def metrics(y_true, prob, threshold=0.5):
    pred = (prob >= threshold).astype(int)
    return {
        "recall_risky": float(recall_score(y_true, pred, zero_division=0)),
        "precision_risky": float(precision_score(y_true, pred, zero_division=0)),
        "f1_risky": float(f1_score(y_true, pred, zero_division=0)),
        "pr_auc": float(average_precision_score(y_true, prob)),
        "confusion_matrix": confusion_matrix(y_true, pred).tolist(),
    }

def main():
    if not DATA.exists():
        raise SystemExit("Run scripts/build_real_training_data.py first.")

    df = pd.read_csv(DATA)
    if len(df) < 50:
        raise SystemExit("Need at least 50 completed real rows before comparison.")
    if df["label_risky"].nunique() < 2:
        raise SystemExit("Both Verified and Risky classes are required.")

    X = df[FEATURES].astype(float)
    y = df["label_risky"].astype(int)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.20, random_state=42, stratify=y
    )

    results = {}

    # Baseline from redesign guide: contact permission alone.
    base_pred = X_test["contacts_permission"].astype(int).values
    results["baseline_contacts_rule"] = {
        "recall_risky": float(recall_score(y_test, base_pred, zero_division=0)),
        "precision_risky": float(precision_score(y_test, base_pred, zero_division=0)),
        "f1_risky": float(f1_score(y_test, base_pred, zero_division=0)),
        "confusion_matrix": confusion_matrix(y_test, base_pred).tolist(),
    }

    models = {
        "logistic_regression": Pipeline([
            ("scaler", StandardScaler()),
            ("clf", LogisticRegression(class_weight="balanced", max_iter=3000, random_state=42))
        ]),
        "random_forest": RandomForestClassifier(
            n_estimators=400, class_weight="balanced", min_samples_leaf=2, random_state=42
        ),
        "hist_gradient_boosting": HistGradientBoostingClassifier(
            max_iter=250, learning_rate=0.06, max_leaf_nodes=15, random_state=42
        ),
    }

    for name, model in models.items():
        model.fit(X_train, y_train)
        prob = model.predict_proba(X_test)[:,1]
        results[name] = metrics(y_test.values, prob)

    payload = {
        "records": int(len(df)),
        "verified": int((y==0).sum()),
        "risky": int((y==1).sum()),
        "test_records": int(len(y_test)),
        "features": FEATURES,
        "results": results,
        "note": "Model selection must prioritise risky-class recall while maintaining acceptable precision. Do not select by accuracy alone."
    }
    OUT.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))

if __name__ == "__main__":
    main()
