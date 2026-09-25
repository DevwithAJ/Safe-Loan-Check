from pathlib import Path
import json
import sys
import re

import joblib
import numpy as np
import pandas as pd

from sklearn.ensemble import RandomForestClassifier, HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)
from sklearn.model_selection import StratifiedKFold, cross_val_predict, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from services.name_features import NameLexicalFeatures

DATA = ROOT / "data" / "real" / "feature_collection_worklist.csv"
MODEL = ROOT / "models" / "risk_model.joblib"
META = ROOT / "models" / "risk_model_meta.json"
REPORT = ROOT / "models" / "real_name_model_evaluation.json"
PREDICTIONS = ROOT / "models" / "real_name_model_holdout_predictions.csv"

RANDOM_STATE = 42
TARGET_RECALL = 0.75
TARGET_PRECISION = 0.30
TEST_SIZE = 0.20


def score_metrics(y_true, prob, threshold):
    pred = (np.asarray(prob) >= threshold).astype(int)
    return {
        "precision_risky": float(precision_score(y_true, pred, zero_division=0)),
        "recall_risky": float(recall_score(y_true, pred, zero_division=0)),
        "f1_risky": float(f1_score(y_true, pred, zero_division=0)),
        "pr_auc": float(average_precision_score(y_true, prob)),
        "confusion_matrix": confusion_matrix(y_true, pred).tolist(),
    }


def tune_threshold(y_true, prob):
    candidates = []
    for threshold in np.arange(0.10, 0.91, 0.01):
        m = score_metrics(y_true, prob, float(threshold))
        meets = (
            m["recall_risky"] >= TARGET_RECALL
            and m["precision_risky"] >= TARGET_PRECISION
        )
        candidates.append((meets, m["f1_risky"], m["precision_risky"], m["recall_risky"], float(threshold), m))

    eligible = [x for x in candidates if x[0]]
    pool = eligible if eligible else candidates
    best = max(pool, key=lambda x: (x[1], x[2], x[3]))
    return best[4], best[5], bool(best[0])


def keyword_baseline(names):
    # Same-input-modality baseline for this interim app-name model.
    # The redesign guide's preferred contacts-permission baseline cannot yet be
    # evaluated because risky examples do not have permission metadata.
    return np.asarray([
        1 if ("cash" in str(name).lower() or "loan" in str(name).lower()) else 0
        for name in names
    ], dtype=int)


def build_models():
    return {
        "lexical_random_forest": Pipeline([
            ("features", NameLexicalFeatures()),
            ("clf", RandomForestClassifier(
                n_estimators=600,
                class_weight="balanced",
                min_samples_leaf=2,
                max_features="sqrt",
                random_state=RANDOM_STATE,
            )),
        ]),
        "lexical_logistic_regression": Pipeline([
            ("features", NameLexicalFeatures()),
            ("scaler", StandardScaler()),
            ("clf", LogisticRegression(
                class_weight="balanced",
                max_iter=4000,
                random_state=RANDOM_STATE,
            )),
        ]),
        "lexical_hist_gradient_boosting": Pipeline([
            ("features", NameLexicalFeatures()),
            ("clf", HistGradientBoostingClassifier(
                max_iter=300,
                learning_rate=0.05,
                max_leaf_nodes=10,
                random_state=RANDOM_STATE,
            )),
        ]),
    }


def token_stats(df):
    base_rate = float((df["label_risky"] == 1).mean())
    stats = {}
    for token in NameLexicalFeatures.KEYWORDS:
        mask = df["app_name"].str.lower().str.contains(re.escape(token), regex=True)
        subset = df[mask]
        risky = int((subset["label_risky"] == 1).sum())
        verified = int((subset["label_risky"] == 0).sum())
        total = risky + verified
        rate = float(risky / total) if total else 0.0
        stats[token] = {
            "risky": risky,
            "verified": verified,
            "total": total,
            "risky_rate": round(rate, 4),
            "lift_vs_base": round(rate / base_rate, 3) if base_rate and total else 0.0,
        }
    return stats


def main():
    if not DATA.exists():
        raise SystemExit(f"Missing dataset: {DATA}")

    raw = pd.read_csv(DATA)
    df = raw[["app_name", "group_label", "source_url"]].copy()
    df["app_name"] = df["app_name"].fillna("").astype(str).str.strip()
    df["label_risky"] = df["group_label"].astype(str).str.lower().map({"verified": 0, "risky": 1})
    df = df[(df["app_name"] != "") & df["label_risky"].notna()].copy()
    df["label_risky"] = df["label_risky"].astype(int)

    if len(df) < 50 or df["label_risky"].nunique() < 2:
        raise SystemExit("Need at least 50 labelled rows and both classes.")

    X_train, X_test, y_train, y_test = train_test_split(
        df["app_name"],
        df["label_risky"],
        test_size=TEST_SIZE,
        random_state=RANDOM_STATE,
        stratify=df["label_risky"],
    )

    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=RANDOM_STATE)
    candidates = build_models()
    train_cv = {}

    for name, model in candidates.items():
        prob = cross_val_predict(model, X_train, y_train, cv=cv, method="predict_proba")[:, 1]
        threshold, metrics, met_target = tune_threshold(y_train.values, prob)
        train_cv[name] = {
            "threshold": threshold,
            "met_training_target": met_target,
            **metrics,
        }

    # Model selection uses training CV only. Held-out test is not consulted.
    selected_name = max(
        train_cv,
        key=lambda n: (
            train_cv[n]["met_training_target"],
            train_cv[n]["pr_auc"],
            train_cv[n]["f1_risky"],
        ),
    )
    selected_threshold = float(train_cv[selected_name]["threshold"])
    selected = candidates[selected_name]
    selected.fit(X_train, y_train)
    test_prob = selected.predict_proba(X_test)[:, 1]
    test_metrics = score_metrics(y_test.values, test_prob, selected_threshold)

    baseline_pred = keyword_baseline(X_test)
    baseline = {
        "rule": "Risky if app name contains substring 'cash' or 'loan'",
        "precision_risky": float(precision_score(y_test, baseline_pred, zero_division=0)),
        "recall_risky": float(recall_score(y_test, baseline_pred, zero_division=0)),
        "f1_risky": float(f1_score(y_test, baseline_pred, zero_division=0)),
        "confusion_matrix": confusion_matrix(y_test, baseline_pred).tolist(),
    }

    # Retrain the selected architecture on all real-labelled rows for deployment.
    deployed = build_models()[selected_name]
    deployed.fit(df["app_name"], df["label_risky"])
    joblib.dump(deployed, MODEL)

    # Global feature importances are useful for an auditable, simple explanation.
    feature_importance = []
    if selected_name == "lexical_random_forest":
        feature_names = list(deployed.named_steps["features"].get_feature_names_out())
        importances = deployed.named_steps["clf"].feature_importances_
        feature_importance = [
            {"feature": f, "importance": round(float(v), 6)}
            for f, v in sorted(zip(feature_names, importances), key=lambda x: x[1], reverse=True)
        ]

    tok_stats = token_stats(df)

    report = {
        "model_version": "real-label-name-signal-v1",
        "dataset": {
            "records": int(len(df)),
            "verified": int((df["label_risky"] == 0).sum()),
            "risky": int((df["label_risky"] == 1).sum()),
            "source_file": str(DATA.relative_to(ROOT)),
            "synthetic_rows": 0,
        },
        "validation": {
            "split": "stratified 80:20",
            "random_state": RANDOM_STATE,
            "train_records": int(len(X_train)),
            "test_records": int(len(X_test)),
            "training_target": {
                "recall_risky_min": TARGET_RECALL,
                "precision_risky_min": TARGET_PRECISION,
            },
            "selection_rule": "Select using training-only 5-fold CV: target met first, then PR-AUC, then F1. Test set touched after selection.",
        },
        "training_cv_results": train_cv,
        "selected_model": selected_name,
        "selected_threshold": selected_threshold,
        "held_out_test": test_metrics,
        "same_input_baseline": baseline,
        "feature_importance": feature_importance,
        "limitations": [
            "This v1 model uses only public app-name lexical features, because risky-labelled apps do not yet have balanced listing/permission metadata.",
            "It does not use directory_status or name_similarity, avoiding direct leakage from the RBI directory label definition.",
            "The preferred contacts-permission baseline from the project guide cannot yet be evaluated on the real risky set because permission metadata is missing.",
            "A later v2 should retrain on balanced public listing features and review complaint features when those are collected for both classes.",
            "The model is an educational risk-signal model, not a legality determination or financial advice.",
        ],
    }
    REPORT.write_text(json.dumps(report, indent=2), encoding="utf-8")

    holdout = pd.DataFrame({
        "app_name": X_test.values,
        "label_risky": y_test.values,
        "risk_probability": np.round(test_prob, 6),
        "predicted_risky": (test_prob >= selected_threshold).astype(int),
    })
    holdout.to_csv(PREDICTIONS, index=False)

    meta = {
        "model_version": "real-label-name-signal-v1",
        "model_name": "Random Forest — Real Label Name Signals" if selected_name == "lexical_random_forest" else selected_name,
        "model_type": selected_name,
        "training_data": "Real labels only: 200 Verified RBI-DLA examples + 33 Risky RBI enforcement-evidence examples",
        "training_records": int(len(df)),
        "verified_records": int((df["label_risky"] == 0).sum()),
        "risky_records": int((df["label_risky"] == 1).sum()),
        "is_synthetic": False,
        "high_risk_threshold": selected_threshold,
        "held_out_metrics": test_metrics,
        "baseline_metrics": baseline,
        "feature_names": list(NameLexicalFeatures.FEATURE_NAMES),
        "feature_importance": feature_importance,
        "token_stats": tok_stats,
        "model_scope": "App-name lexical risk signals only; directory status and directory similarity are excluded.",
        "data_note": "REAL-LABEL EXPERIMENTAL MODEL: trained on 233 labelled app names (200 Verified, 33 Risky). Current v1 risk probability uses app-name lexical signals only. Public listing fields are displayed as contextual warning/positive signals but are not yet learned by this model. Do not treat the score as a legality verdict.",
    }
    META.write_text(json.dumps(meta, indent=2), encoding="utf-8")

    print(json.dumps(report, indent=2))
    print(f"\nSaved deployed model: {MODEL}")
    print(f"Saved metadata:       {META}")
    print(f"Saved evaluation:     {REPORT}")
    print(f"Saved holdout rows:   {PREDICTIONS}")


if __name__ == "__main__":
    main()
