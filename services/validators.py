from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse, parse_qs
import ipaddress
import math
import re


class ValidationError(ValueError):
    pass


def clean_text(value, *, field: str, max_length: int, required: bool = False) -> str:
    text = " ".join(str(value or "").strip().split())
    if required and not text:
        raise ValidationError(f"{field} is required.")
    if len(text) > max_length:
        raise ValidationError(f"{field} is too long (max {max_length} characters).")
    return text


def validate_play_store_url(value: str) -> str:
    value = str(value or "").strip()
    if not value:
        return ""
    if len(value) > 600:
        raise ValidationError("Play Store URL is too long.")
    try:
        parsed = urlparse(value)
    except Exception as exc:
        raise ValidationError("Play Store URL is invalid.") from exc
    if parsed.scheme != "https" or parsed.netloc.lower() not in {"play.google.com", "www.play.google.com"}:
        raise ValidationError("Only an https://play.google.com Store URL is supported.")
    package_id = parse_qs(parsed.query).get("id", [""])[0].strip()
    if (
        not package_id
        or len(package_id) > 200
        or not re.fullmatch(r"[A-Za-z0-9_]+(?:\.[A-Za-z0-9_]+)+", package_id)
    ):
        raise ValidationError("Play Store URL must contain a valid Android package id.")
    return value




def validate_app_reference_url(value: str) -> str:
    """Accept an HTTPS Google Play or public official website URL.

    Arbitrary website URLs are never fetched by the server. They are only used by
    the local, source-backed website alias resolver. This validation also rejects
    local/private IP literals, credentials and non-HTTPS schemes.
    """
    value = str(value or "").strip()
    if not value:
        return ""
    if len(value) > 600:
        raise ValidationError("App URL is too long.")
    try:
        parsed = urlparse(value)
    except Exception as exc:
        raise ValidationError("App URL is invalid.") from exc
    if parsed.scheme != "https" or not parsed.hostname:
        raise ValidationError("Use an https:// Google Play or official website URL.")
    if parsed.username or parsed.password:
        raise ValidationError("App URL must not contain embedded credentials.")
    try:
        port = parsed.port
    except ValueError as exc:
        raise ValidationError("App URL contains an invalid port.") from exc
    if port not in (None, 443):
        raise ValidationError("Only the standard HTTPS port is supported.")

    host = parsed.hostname.lower().rstrip(".")
    if host in {"localhost", "localhost.localdomain"} or host.endswith(".local"):
        raise ValidationError("Local/private website URLs are not supported.")
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        ip = None
    if ip is not None and (ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved):
        raise ValidationError("Local/private website URLs are not supported.")

    if host in {"play.google.com", "www.play.google.com"}:
        # Reuse strict package-id validation for Play URLs.
        validate_play_store_url(value)
    return value


def package_id_from_play_url(value: str) -> str | None:
    """Extract an Android package id from messy stored app-link text.

    User-submitted Google Play URLs are validated separately. RBI/source exports can
    contain scheme-less links, labels before the URL, HTML-escaped query strings,
    wrapped security URLs, minor URL typos, or Android test links. This parser is
    intentionally tolerant *only for stored/reference data* so directory identity
    matching does not fail because of source formatting.
    """
    from html import unescape
    from urllib.parse import unquote

    raw = unescape(str(value or "").strip())
    if not raw:
        return None
    raw = unquote(raw)

    # Normalize common source-export typos without changing user input validation.
    cleaned = raw.replace("\\u200b", "").replace("\\ufeff", "")
    cleaned = re.sub(r"(?i)https?//(?=(?:www\.)?play\.google\.com/)", "https://", cleaned)
    cleaned = re.sub(r"(?i)play\.google\.com\.store/", "play.google.com/store/", cleaned)

    package_pattern = r"[A-Za-z0-9_]+(?:\.[A-Za-z0-9_]+)+"

    # 1) Direct/details links, including links embedded inside labels/wrappers.
    m = re.search(
        rf"(?i)(?:https?://)?(?:www\\.)?play\\.google\\.com/store/apps/details\\?[^\\s<>\"']*?(?:^|[?&])id=({package_pattern})",
        cleaned,
    )
    if m:
        return m.group(1)

    # Some exports contain details?id=... but with malformed separators or wrappers.
    if "play.google" in cleaned.lower():
        m = re.search(rf"(?i)(?:[?&]|\bid=)({package_pattern})", cleaned)
        if m:
            return m.group(1)

    # 2) Google Play internal/test URLs: /apps/test/<package>/<track>.
    m = re.search(rf"(?i)play\.google\.com/apps/test/({package_pattern})(?:/|$)", cleaned)
    if m:
        return m.group(1)

    # 3) Other Android-store links sometimes expose the same package as ?id=<pkg>.
    # Numeric Apple IDs do not match this dotted-package pattern.
    m = re.search(rf"(?i)(?:[?&]|\bid=)({package_pattern})(?:[&#\s]|$)", cleaned)
    if m:
        return m.group(1)

    return None

def tri_state_value(value):
    raw = str(value or "unknown").strip().lower()
    if raw in {"yes", "1", "true", "on"}:
        return 1
    if raw in {"no", "0", "false", "off"}:
        return 0
    return None


def optional_float(value, *, field: str, minimum: float | None = None, maximum: float | None = None) -> float | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"{field} must be a number.") from exc
    if not math.isfinite(number):
        raise ValidationError(f"{field} must be a finite number.")
    if minimum is not None and number < minimum:
        raise ValidationError(f"{field} must be at least {minimum}.")
    if maximum is not None and number > maximum:
        raise ValidationError(f"{field} must be at most {maximum}.")
    return number


def required_float(value, *, field: str, minimum: float | None = None, maximum: float | None = None) -> float:
    number = optional_float(value, field=field, minimum=minimum, maximum=maximum)
    if number is None:
        raise ValidationError(f"{field} is required when cost calculation is enabled.")
    return number


def required_int(value, *, field: str, minimum: int | None = None, maximum: int | None = None) -> int:
    number = required_float(value, field=field, minimum=minimum, maximum=maximum)
    if not float(number).is_integer():
        raise ValidationError(f"{field} must be a whole number.")
    return int(number)


LISTING_FIELDS = (
    "contacts_permission",
    "call_logs_permission",
    "sms_permission",
    "media_permission",
    "named_regulated_lender",
    "apr_disclosed",
    "developer_website_present",
    "physical_address_present",
    "company_email_domain",
)


def parse_manual_listing_features(mapping) -> dict:
    installs = optional_float(mapping.get("installs"), field="Installs", minimum=0, maximum=10_000_000_000)
    installs_log10 = math.log10(installs + 1) if installs is not None else None
    result = {field: tri_state_value(mapping.get(field)) for field in LISTING_FIELDS}
    result.update({
        "app_age_days": optional_float(mapping.get("app_age_days"), field="App age", minimum=0, maximum=36500),
        "days_since_update": optional_float(mapping.get("days_since_update"), field="Days since update", minimum=0, maximum=36500),
        "installs_log10": installs_log10,
        "rating": optional_float(mapping.get("rating"), field="Rating", minimum=0, maximum=5),
        "complaint_rate": optional_float(mapping.get("complaint_rate"), field="Complaint rate", minimum=0, maximum=1),
        "name_similarity": optional_float(mapping.get("name_similarity"), field="Name similarity", minimum=0, maximum=100),
    })
    return result


def validate_identity(mapping) -> dict:
    app_name = clean_text(mapping.get("app_name"), field="App name", max_length=120, required=False)
    developer_name = clean_text(mapping.get("developer_name"), field="Developer/company", max_length=160, required=False)
    # app_reference_url is the v2.2 field. play_store_url remains accepted for API/backward compatibility.
    raw_url = mapping.get("app_reference_url") or mapping.get("play_store_url", "")
    app_reference_url = validate_app_reference_url(raw_url)
    play_store_url = app_reference_url if package_id_from_play_url(app_reference_url) else ""
    if not app_name and not app_reference_url:
        raise ValidationError("Enter an app name, Google Play URL, or official website URL.")
    return {
        "app_name": app_name,
        "developer_name": developer_name,
        "app_reference_url": app_reference_url,
        "play_store_url": play_store_url,
    }


def validate_cost(mapping) -> dict | None:
    enabled_raw = str(mapping.get("calculate_cost") or "").lower()
    enabled = enabled_raw in {"on", "1", "true", "yes"}
    if not enabled:
        return None

    loan_amount = required_float(mapping.get("loan_amount"), field="Loan amount", minimum=1, maximum=10_000_000)
    processing_fee = required_float(mapping.get("processing_fee"), field="Processing fee", minimum=0, maximum=10_000_000)
    other_fees = required_float(mapping.get("other_upfront_fees"), field="Other upfront fees", minimum=0, maximum=10_000_000)
    emi = required_float(mapping.get("emi"), field="EMI", minimum=1, maximum=10_000_000)
    tenure = required_int(mapping.get("tenure_months"), field="Tenure", minimum=1, maximum=360)
    income = optional_float(mapping.get("monthly_income"), field="Monthly income/allowance", minimum=0, maximum=100_000_000)
    if processing_fee + other_fees >= loan_amount:
        raise ValidationError("Upfront fees must be lower than the loan amount.")
    return {
        "loan_amount": loan_amount,
        "processing_fee": processing_fee,
        "other_upfront_fees": other_fees,
        "emi": emi,
        "tenure_months": tenure,
        "monthly_income": income or 0,
    }
