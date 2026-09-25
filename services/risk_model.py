from __future__ import annotations

from pathlib import Path
import json
import logging

import joblib

logger = logging.getLogger(__name__)


class RiskModel:
    def __init__(self, model_path: Path, meta_path: Path):
        self.model_path = Path(model_path)
        self.meta_path = Path(meta_path)
        self.pipeline = None
        self.meta = {}
        self.load_error = None
        self.load()

    def load(self):
        self.pipeline = None
        self.meta = {}
        self.load_error = None
        if self.meta_path.exists():
            try:
                self.meta = json.loads(self.meta_path.read_text(encoding="utf-8"))
            except Exception as exc:
                self.load_error = f"Model metadata could not be read: {exc.__class__.__name__}"
                logger.exception("Could not load model metadata")
        if self.model_path.exists():
            try:
                self.pipeline = joblib.load(self.model_path)
            except Exception as exc:
                self.load_error = f"Model artifact could not be loaded: {exc.__class__.__name__}"
                logger.exception("Could not load model artifact")

    @property
    def ready(self):
        return self.pipeline is not None

    @property
    def health(self):
        return {
            "ready": self.ready,
            "model_name": self.meta.get("model_name"),
            "model_version": self.meta.get("model_version"),
            "error": self.load_error,
        }

    def score(self, app_name: str, features: dict | None = None) -> dict:
        features = features or {}
        app_name = (app_name or "").strip()
        listing = self._listing_signal_summary(features)

        base = {
            "contextual_signals": listing["warnings"],
            "positive_signals": self._positive_signals(features),
            "unknown_listing_fields": self._unknown_fields(features),
            "listing_signal_level": listing["level"],
            "listing_signal_score": listing["score"],
            "listing_evidence_count": listing["known_count"],
            "listing_evidence_total": listing["total_count"],
            "listing_evidence_pct": listing["coverage_pct"],
        }

        if not self.ready:
            return {
                **base,
                "ready": False,
                "risk_probability": None,
                "risk_score": None,
                "threshold": float(self.meta.get("high_risk_threshold", 0.5)),
                "model_reasons": [self.load_error or "Risk model is unavailable."],
                "model_name": self.meta.get("model_name", "Risk model"),
                "model_version": self.meta.get("model_version", ""),
                "model_scope": self.meta.get("model_scope", ""),
                "data_note": self.meta.get("data_note", ""),
            }

        if not app_name:
            return {
                **base,
                "ready": False,
                "risk_probability": None,
                "risk_score": None,
                "threshold": float(self.meta.get("high_risk_threshold", 0.5)),
                "model_reasons": ["An app name is required to run the ML risk model."],
                "model_name": self.meta.get("model_name", "Risk model"),
                "model_version": self.meta.get("model_version", ""),
                "model_scope": self.meta.get("model_scope", ""),
                "data_note": self.meta.get("data_note", ""),
            }

        try:
            prob = float(self.pipeline.predict_proba([app_name])[0, 1])
        except Exception as exc:
            logger.exception("Risk model scoring failed")
            return {
                **base,
                "ready": False,
                "risk_probability": None,
                "risk_score": None,
                "threshold": float(self.meta.get("high_risk_threshold", 0.5)),
                "model_reasons": [f"Risk model could not score this request ({exc.__class__.__name__})."],
                "model_name": self.meta.get("model_name", "Risk model"),
                "model_version": self.meta.get("model_version", ""),
                "model_scope": self.meta.get("model_scope", ""),
                "data_note": self.meta.get("data_note", ""),
            }

        threshold = float(self.meta.get("high_risk_threshold", 0.5))
        return {
            **base,
            "ready": True,
            "risk_probability": round(prob, 4),
            "risk_score": round(prob * 100, 1),
            "threshold": threshold,
            "model_reasons": self._name_model_reasons(app_name, prob, threshold),
            "model_name": self.meta.get("model_name", "Real-label ML model"),
            "model_version": self.meta.get("model_version", ""),
            "model_scope": self.meta.get("model_scope", ""),
            "data_note": self.meta.get("data_note", ""),
        }

    def _name_model_reasons(self, app_name: str, prob: float, threshold: float):
        lower = app_name.lower()
        token_stats = self.meta.get("token_stats", {})
        present = []
        for token, stat in token_stats.items():
            if token in lower and stat.get("total", 0) >= 2 and stat.get("lift_vs_base", 0) > 1.15:
                present.append((float(stat.get("lift_vs_base", 0)), token, stat))
        present.sort(reverse=True)

        reasons = []
        if prob >= threshold:
            for _, token, _ in present[:2]:
                reasons.append(
                    f"App name contains '{token}', a pattern more common in the risky-labelled training set."
                )
            if not reasons:
                reasons.append("The app-name pattern is similar to patterns learned from risky-labelled examples.")
        else:
            reasons.append("The app-name pattern stayed below the model's high-risk threshold.")
        return reasons[:3]

    @staticmethod
    def _number(row: dict, name: str):
        value = row.get(name)
        if value is None or value == "":
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _listing_signal_summary(self, row: dict):
        val = lambda name: self._number(row, name)
        weighted = []

        def add(weight, condition, message):
            if condition:
                weighted.append((weight, message))

        contacts = val("contacts_permission")
        calls = val("call_logs_permission")
        sms = val("sms_permission")
        media = val("media_permission")
        lender = val("named_regulated_lender")
        apr = val("apr_disclosed")
        website = val("developer_website_present")
        address = val("physical_address_present")
        company_email = val("company_email_domain")
        age = val("app_age_days")
        since_update = val("days_since_update")
        installs_log10 = val("installs_log10")
        rating = val("rating")
        complaints = val("complaint_rate")

        add(3.0, contacts == 1, "Requests contact-list access")
        add(3.0, calls == 1, "Requests call-log access")
        add(2.4, sms == 1, "Requests SMS access")
        add(1.2, media == 1, "Requests media/files access")
        add(3.0, lender == 0, "Regulated lender is marked as not clearly named")
        add(2.4, apr == 0, "APR/fees are marked as not disclosed")
        add(1.2, website == 0, "Developer website is marked as absent")
        add(0.8, address == 0, "Physical address is marked as absent")
        add(0.9, company_email == 0, "Company-domain email is marked as absent")
        add(1.8, age is not None and 0 < age < 120, "App appears very new from the observed age")
        add(0.9, since_update is not None and since_update > 365, "App has not been updated for a long time")
        add(0.8, installs_log10 is not None and 0 < installs_log10 < 3, "Install history is very small")
        add(1.2, rating is not None and 0 < rating < 3.0, "Public rating is low")
        add(2.8, complaints is not None and complaints >= 0.35, "High complaint-keyword rate in the sampled reviews")
        add(1.5, complaints is not None and 0.15 <= complaints < 0.35, "Noticeable complaint-keyword rate in the sampled reviews")

        fields = [
            "contacts_permission", "call_logs_permission", "sms_permission", "media_permission",
            "named_regulated_lender", "apr_disclosed", "developer_website_present",
            "physical_address_present", "company_email_domain", "app_age_days",
            "days_since_update", "installs_log10", "rating", "complaint_rate",
        ]
        known = sum(row.get(name) is not None and row.get(name) != "" for name in fields)
        total = len(fields)
        score = round(sum(weight for weight, _ in weighted), 2)
        weighted.sort(key=lambda x: x[0], reverse=True)

        if score >= 5.0:
            level = "High"
        elif score >= 2.5:
            level = "Moderate"
        elif known >= 3:
            level = "Low"
        else:
            level = "Insufficient"

        return {
            "warnings": [message for _, message in weighted[:5]],
            "score": score,
            "level": level,
            "known_count": known,
            "total_count": total,
            "coverage_pct": round((known / total) * 100, 1),
        }

    def _positive_signals(self, row: dict):
        val = lambda name: self._number(row, name)
        positives = []
        if val("named_regulated_lender") == 1:
            positives.append("Regulated lender is clearly named in the observed public evidence")
        if val("apr_disclosed") == 1:
            positives.append("APR is disclosed in the observed public evidence")
        if val("developer_website_present") == 1:
            positives.append("Developer website is present")
        if val("physical_address_present") == 1:
            positives.append("Physical address is present")
        if val("company_email_domain") == 1:
            positives.append("Company-domain email is present")
        return positives[:5]

    def _unknown_fields(self, row: dict):
        labels = {
            "contacts_permission": "Contacts permission",
            "call_logs_permission": "Call-log permission",
            "sms_permission": "SMS permission",
            "media_permission": "Media/files permission",
            "named_regulated_lender": "Named regulated lender",
            "apr_disclosed": "APR disclosure",
            "developer_website_present": "Developer website",
            "physical_address_present": "Physical address",
            "company_email_domain": "Company-domain email",
            "app_age_days": "App age",
            "days_since_update": "Update recency",
            "installs_log10": "Installs",
            "rating": "Rating",
            "complaint_rate": "Complaint-keyword rate",
            "name_similarity": "Name similarity",
        }
        return [label for key, label in labels.items() if row.get(key) is None or row.get(key) == ""]
