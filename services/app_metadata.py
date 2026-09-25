from __future__ import annotations

from datetime import datetime, timezone, date
from email.utils import parseaddr
import re
from urllib.parse import urlparse

from .metadata_cache import MetadataCache
from .validators import package_id_from_play_url

FREE_EMAIL_DOMAINS = {
    "gmail.com", "googlemail.com", "yahoo.com", "outlook.com", "hotmail.com",
    "icloud.com", "proton.me", "protonmail.com", "rediffmail.com",
}

COMPLAINT_PATTERN = re.compile(
    r"\b(harass(?:ment|ed|ing)?|threat(?:en|ened|ening|s)?|blackmail|"
    r"hidden\s+(?:fee|charge|charges)|extra\s+charge|fraud|scam|abusive?|"
    r"contact\s+list|called\s+my\s+contacts|privacy\s+violation)\b",
    re.IGNORECASE,
)
APR_PATTERN = re.compile(r"\bAPR\b|annual\s+percentage\s+rate", re.IGNORECASE)


def _safe_date_from_release(value) -> date | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value.date()
    text = str(value).strip()
    for fmt in ("%b %d, %Y", "%d %b %Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            pass
    return None


def _safe_date_from_updated(value) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(value, tz=timezone.utc).date()
        except (ValueError, OSError, OverflowError):
            return None
    return _safe_date_from_release(value)


def _company_email_flag(email: str | None):
    if not email:
        return None
    _, parsed = parseaddr(email)
    if "@" not in parsed:
        return None
    domain = parsed.rsplit("@", 1)[-1].lower().strip()
    return 0 if domain in FREE_EMAIL_DOMAINS else 1


def _contains_phrase(text: str, phrase: str) -> bool:
    phrase = " ".join(str(phrase or "").lower().split())
    if len(phrase) < 4:
        return False
    normalized = " ".join(str(text or "").lower().split())
    return phrase in normalized


class AppMetadataService:
    """Fetches a small public metadata snapshot for an explicit Google Play URL.

    This uses the third-party `google-play-scraper` package. The integration is
    optional and failure-safe: if the provider is unavailable, directory lookup,
    ML scoring, and cost calculation still work. Only derived public metadata is
    cached; user financial input is never stored here.
    """

    def __init__(
        self,
        *,
        cache_db,
        enabled: bool,
        cache_ttl_seconds: int,
        error_cache_ttl_seconds: int,
        review_analysis_enabled: bool,
        review_sample_size: int,
    ):
        self.enabled = bool(enabled)
        self.cache_ttl_seconds = int(cache_ttl_seconds)
        self.error_cache_ttl_seconds = int(error_cache_ttl_seconds)
        self.review_analysis_enabled = bool(review_analysis_enabled)
        self.review_sample_size = int(review_sample_size)
        self.cache = MetadataCache(cache_db)

    @staticmethod
    def provider_available() -> bool:
        try:
            import google_play_scraper  # noqa: F401
            return True
        except Exception:
            return False

    def fetch(self, play_store_url: str) -> dict:
        package_id = package_id_from_play_url(play_store_url)
        if not play_store_url:
            return {"status": "not_requested", "attempted": False, "package_id": None}
        if not package_id:
            return {
                "status": "invalid_url",
                "attempted": False,
                "package_id": None,
                "reason": "A Google Play package id could not be read from the URL.",
            }
        if not self.enabled:
            return {
                "status": "disabled",
                "attempted": False,
                "package_id": package_id,
                "reason": "Automatic public-listing lookup is disabled by server configuration.",
            }

        cached = self.cache.get(package_id)
        stale_success = None
        if cached:
            ttl = self.cache_ttl_seconds if cached.get("status") == "ok" else self.error_cache_ttl_seconds
            if int(cached.get("cache_age_seconds", ttl + 1)) <= ttl:
                return cached
            if cached.get("status") == "ok":
                stale_success = dict(cached)

        if not self.provider_available():
            if stale_success:
                stale_success["stale_cache"] = True
                stale_success["reason"] = "Public provider is unavailable; using an older cached public-listing snapshot."
                return stale_success
            payload = {
                "status": "unavailable",
                "attempted": True,
                "package_id": package_id,
                "reason": "Public listing provider is not installed on this server.",
            }
            self.cache.put(package_id, payload["status"], payload)
            return payload

        try:
            from google_play_scraper import app as gp_app
            info = gp_app(package_id, lang="en", country="in")
            payload = self._build_payload(package_id, play_store_url, info)
            self._add_permission_summary(payload, package_id)
            if self.review_analysis_enabled:
                self._add_review_summary(payload, package_id)
            self.cache.put(package_id, payload["status"], payload)
            return payload
        except Exception as exc:
            if stale_success:
                stale_success["stale_cache"] = True
                stale_success["reason"] = "Fresh public metadata failed; using an older cached public-listing snapshot."
                stale_success["provider_error_type"] = exc.__class__.__name__
                return stale_success
            payload = {
                "status": "error",
                "attempted": True,
                "package_id": package_id,
                "reason": "Public listing could not be fetched right now.",
                "provider_error_type": exc.__class__.__name__,
            }
            self.cache.put(package_id, payload["status"], payload)
            return payload

    def _build_payload(self, package_id: str, play_store_url: str, info: dict) -> dict:
        today = datetime.now(timezone.utc).date()
        released = _safe_date_from_release(info.get("released"))
        updated = _safe_date_from_updated(info.get("updated"))
        description = str(info.get("description") or "")[:30000]
        email = info.get("developerEmail")
        min_installs = info.get("minInstalls")
        rating = info.get("score")

        public_features = {
            # Permissions are intentionally not inferred from Play Data Safety text.
            "contacts_permission": None,
            "call_logs_permission": None,
            "sms_permission": None,
            "media_permission": None,
            "named_regulated_lender": None,
            # Auto-scan only creates a positive APR signal. Absence in a store
            # description is treated as Unknown, not proof that the lender failed to disclose it elsewhere.
            "apr_disclosed": 1 if APR_PATTERN.search(description) else None,
            "developer_website_present": 1 if info.get("developerWebsite") else 0,
            "physical_address_present": 1 if info.get("developerAddress") else 0,
            "company_email_domain": _company_email_flag(email),
            "app_age_days": (today - released).days if released else None,
            "days_since_update": (today - updated).days if updated else None,
            "installs": int(min_installs) if isinstance(min_installs, (int, float)) else None,
            "rating": round(float(rating), 2) if isinstance(rating, (int, float)) else None,
            "complaint_rate": None,
            "name_similarity": None,
        }

        return {
            "status": "ok",
            "attempted": True,
            "provider": "google-play-scraper",
            "package_id": package_id,
            "source_url": play_store_url,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "title": str(info.get("title") or "").strip(),
            "developer": str(info.get("developer") or "").strip(),
            "developer_email": str(email or "").strip(),
            "developer_website": str(info.get("developerWebsite") or "").strip(),
            "developer_address": str(info.get("developerAddress") or "").strip(),
            "released": released.isoformat() if released else None,
            "updated": updated.isoformat() if updated else None,
            "installs_display": str(info.get("installs") or "").strip(),
            "description": description,
            "apr_text_detected": bool(APR_PATTERN.search(description)),
            "public_features": public_features,
            "cache_hit": False,
        }


    @staticmethod
    def _permission_feature_flags(raw_permissions) -> tuple[dict, dict]:
        """Convert Play permission text into positive-only sensitive-permission signals.

        google-play-scraper exposes human-readable permission groups/text. This helper
        intentionally records only supported *positive* evidence. If a permission is not
        observed, the feature remains None rather than becoming 0, because absence from
        the scraped response is not strong enough evidence that the installed app never
        requests it.
        """
        flags = {
            "contacts_permission": None,
            "call_logs_permission": None,
            "sms_permission": None,
            "media_permission": None,
        }
        categories = []
        flattened = []
        if isinstance(raw_permissions, dict):
            items = raw_permissions.items()
        elif isinstance(raw_permissions, (list, tuple)):
            items = [("Other", raw_permissions)]
        else:
            items = []

        for category, values in items:
            cat = str(category or "").strip()
            if cat:
                categories.append(cat)
            if isinstance(values, (list, tuple, set)):
                vals = list(values)
            elif values is None:
                vals = []
            else:
                vals = [values]
            for value in vals:
                text = str(value or "").strip()
                if text:
                    flattened.append(f"{cat}: {text}" if cat else text)

        joined = " | ".join(flattened).lower()
        category_text = " | ".join(categories).lower()

        # Require explicit contact-list wording; account discovery alone is not treated
        # as contact access.
        if re.search(r"(?:read|modify|write|access|view).*\bcontacts?\b|\bcontacts?\b.*(?:read|modify|write|access|view)", joined):
            flags["contacts_permission"] = 1

        if "call log" in joined or "call history" in joined:
            flags["call_logs_permission"] = 1

        if (
            re.search(r"\bsms\b|text messages?", joined)
            or re.search(r"(?:^|[| ])sms(?:$|[| ])", category_text)
        ):
            flags["sms_permission"] = 1

        # Media/storage access is counted only when the permission response itself
        # exposes a media/storage group with at least one permission string.
        media_categories = [
            c for c in categories
            if any(token in c.lower() for token in ("photos", "media", "files", "storage"))
        ]
        if media_categories and flattened:
            flags["media_permission"] = 1

        summary = {
            "available": bool(categories or flattened),
            "categories": sorted(set(categories)),
            "positive_flags": [key for key, value in flags.items() if value == 1],
            "method": "Positive-only detection from public Google Play permission text; non-detection remains Unknown.",
        }
        return flags, summary

    def _add_permission_summary(self, payload: dict, package_id: str):
        try:
            from google_play_scraper import permissions as gp_permissions
            raw = gp_permissions(package_id, lang="en", country="in")
            flags, summary = self._permission_feature_flags(raw)
            for key, value in flags.items():
                if value == 1:
                    payload.setdefault("public_features", {})[key] = 1
            payload["permission_summary"] = summary
        except Exception as exc:
            payload["permission_summary"] = {
                "available": False,
                "positive_flags": [],
                "method": "Permission evidence unavailable; all permission fields remain Unknown unless manually verified.",
                "error_type": exc.__class__.__name__,
            }

    def _add_review_summary(self, payload: dict, package_id: str):
        try:
            from google_play_scraper import reviews, Sort
            items, _ = reviews(
                package_id,
                lang="en",
                country="in",
                sort=Sort.NEWEST,
                count=self.review_sample_size,
            )
            texts = [str(item.get("content") or "") for item in items if item.get("content")]
            if len(texts) < 10:
                return
            complaint_count = sum(bool(COMPLAINT_PATTERN.search(text)) for text in texts)
            rate = round(complaint_count / len(texts), 4)
            payload["public_features"]["complaint_rate"] = rate
            payload["review_summary"] = {
                "sample_size": len(texts),
                "complaint_keyword_matches": complaint_count,
                "complaint_rate": rate,
                "method": "Keyword share in a capped newest-review sample; review text is not stored.",
            }
        except Exception:
            payload["review_summary"] = {
                "status": "unavailable",
                "method": "Review analysis failed without affecting the rest of the check.",
            }

    @staticmethod
    def enrich_with_directory(metadata: dict, directory: dict) -> dict:
        """Derive a positive 'named lender' signal only when public text supports it.

        Absence is left Unknown instead of being converted to a negative signal.
        """
        if not metadata or metadata.get("status") != "ok" or directory.get("status") != "Listed":
            return metadata
        description = metadata.get("description") or ""
        candidates = list(directory.get("regulated_entities") or []) + list(directory.get("matched_developers") or [])
        candidates.extend([directory.get("regulated_entity"), directory.get("matched_developer")])
        if any(_contains_phrase(description, item) for item in candidates if item):
            metadata.setdefault("public_features", {})["named_regulated_lender"] = 1
        return metadata
