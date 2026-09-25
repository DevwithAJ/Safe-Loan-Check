from pathlib import Path
import json
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config import Config
from services.app_metadata import AppMetadataService
from services.app_reference import AppReferenceResolver
from services.cost_calculator import calculate_cost
from services.decision_layer import decide
from services.dla_lookup import DirectoryIndex
from services.risk_model import RiskModel
from services.validators import ValidationError, validate_app_reference_url, validate_play_store_url, package_id_from_play_url


def test_cost_calculator():
    result = calculate_cost(10000, 500, 0, 1900, 6, 15000)
    assert result["valid"]
    assert result["net_received"] == 9500.0
    assert result["total_repayable"] == 11400.0
    assert result["apr_percent"] is not None


def test_red_decision_for_not_listed_high_ml():
    result = decide("Not listed", 0.9, None, 0.65, 0.30)
    assert result["verdict"] == "Red"


def test_red_decision_for_not_listed_high_listing_signal():
    result = decide(
        "Not listed", 0.1, None, 0.65, 0.30,
        listing_signal_level="High",
    )
    assert result["verdict"] == "Red"


def test_green_decision_when_current_listed_low_risk():
    cost = {"valid": True, "emi_income_ratio": 0.20}
    result = decide("Listed", 0.10, cost, 0.65, 0.30, directory_stale=False, model_ready=True)
    assert result["verdict"] == "Green"


def test_stale_directory_downgrades_green_to_amber():
    cost = {"valid": True, "emi_income_ratio": 0.20}
    result = decide("Listed", 0.10, cost, 0.65, 0.30, directory_stale=True, model_ready=True)
    assert result["verdict"] == "Amber"


def test_real_name_model_loads_and_scores():
    model = RiskModel(Config.MODEL_PATH, Config.MODEL_META)
    assert model.ready
    result = model.score("QuickCash", {})
    assert result["ready"]
    assert 0 <= result["risk_probability"] <= 1
    assert result["threshold"] > 0


def test_directory_status_not_in_model_features():
    meta = json.loads(Config.MODEL_META.read_text(encoding="utf-8"))
    names = meta.get("feature_names", [])
    assert "directory_status" not in names
    assert "name_similarity" not in names
    assert meta.get("sklearn_version") == "1.8.0"


def test_unknown_listing_fields_are_neutral():
    model = RiskModel(Config.MODEL_PATH, Config.MODEL_META)
    result = model.score("GeM Sahay", {
        "named_regulated_lender": None,
        "apr_disclosed": None,
        "developer_website_present": None,
        "physical_address_present": None,
        "company_email_domain": None,
    })
    assert result["ready"]
    assert result["contextual_signals"] == []
    assert result["listing_signal_level"] == "Insufficient"


def test_strong_listing_warnings_get_high_rule_level():
    model = RiskModel(Config.MODEL_PATH, Config.MODEL_META)
    result = model.score("Example App", {
        "contacts_permission": 1,
        "call_logs_permission": 1,
        "apr_disclosed": 0,
        "named_regulated_lender": 0,
    })
    assert result["listing_signal_level"] == "High"
    assert len(result["contextual_signals"]) >= 3


def test_directory_index_loaded_once_and_reports_freshness():
    index = DirectoryIndex(Config.DLA_CSV, stale_after_days=45)
    assert index.meta["available"]
    assert index.meta["row_count"] > 100
    result = index.lookup("GeM Sahay", "")
    assert result["status"] == "Listed"
    assert result["snapshot"]["row_count"] == index.meta["row_count"]



def test_package_parser_accepts_scheme_less_google_play_url_from_stored_directory():
    assert package_id_from_play_url(
        "play.google.com/store/apps/details?id=org.altruist.BajajExperia&shortlink=4n"
    ) == "org.altruist.BajajExperia"


def test_bajaj_finance_matches_exact_google_play_package_id():
    index = DirectoryIndex(Config.DLA_CSV, stale_after_days=45)
    result = index.lookup(
        "Bajaj Finance : UPI & Loan App",
        "Bajaj Finance Limited",
        "https://play.google.com/store/apps/details?id=org.altruist.BajajExperia&hl=en_IN",
    )
    assert result["status"] == "Listed"
    assert result["match_score"] == 100
    assert result["matched_app"] == "Bajaj Finance App"
    assert any("BAJAJ FINANCE" in entity.upper() for entity in result["regulated_entities"])
    assert "package-id match" in result["reason"].lower()


def test_kissht_matches_by_google_play_package_id():
    index = DirectoryIndex(Config.DLA_CSV, stale_after_days=45)
    result = index.lookup(
        "Kissht Quick Personal Loan App",
        "OnEMI Technology Solutions Limited.",
        "https://play.google.com/store/apps/details?id=com.fastbanking&hl=en_IN",
    )
    assert result["status"] == "Listed"
    assert result["match_score"] == 100
    assert result["match_count"] >= 1
    assert any("FINANC" in entity.upper() or "CAPITAL" in entity.upper() for entity in result["regulated_entities"])
    assert "package-id match" in result["reason"].lower()


def test_kissht_long_store_title_matches_brand_and_normalized_developer_without_url():
    index = DirectoryIndex(Config.DLA_CSV, stale_after_days=45)
    result = index.lookup(
        "Kissht Quick Personal Loan App",
        "OnEMI Technology Solutions Limited.",
    )
    assert result["status"] == "Listed"
    assert result["match_score"] >= 95



def test_clickmyloan_spacing_normalization_is_exact_equivalent():
    index = DirectoryIndex(Config.DLA_CSV, stale_after_days=45)
    result = index.lookup("click my loan", "")
    assert result["status"] == "Listed"
    assert result["match_score"] == 100
    assert result["matched_app"].lower() == "clickmyloan"
    assert "spacing and punctuation" in result["reason"].lower()


def test_clickmyloan_website_resolves_to_google_play_package():
    resolver = AppReferenceResolver(Config.APP_REFERENCE_ALIAS_CSV)
    result = resolver.resolve("https://web.clickmyloan.com/")
    assert result["status"] == "resolved"
    assert result["package_id"] == "com.habile.cloudbankin.clickmyloan"
    assert "play.google.com" in result["play_store_url"]
    assert result["canonical_app_name"].lower().startswith("clickmyloan")


def test_app_reference_url_validation_accepts_public_https_and_rejects_private():
    assert validate_app_reference_url("https://web.clickmyloan.com/") == "https://web.clickmyloan.com/"
    assert validate_app_reference_url("https://play.google.com/store/apps/details?id=com.example.app")
    with pytest.raises(ValidationError):
        validate_app_reference_url("http://clickmyloan.com/")
    with pytest.raises(ValidationError):
        validate_app_reference_url("https://127.0.0.1/app")


def test_play_url_validation():
    good = "https://play.google.com/store/apps/details?id=com.example.app"
    assert validate_play_store_url(good) == good
    with pytest.raises(ValidationError):
        validate_play_store_url("https://evil.example/app?id=com.example")


def test_metadata_feature_derivation(tmp_path):
    service = AppMetadataService(
        cache_db=tmp_path / "cache.sqlite3",
        enabled=False,
        cache_ttl_seconds=3600,
        error_cache_ttl_seconds=60,
        review_analysis_enabled=False,
        review_sample_size=20,
    )
    payload = service._build_payload(
        "com.example.loan",
        "https://play.google.com/store/apps/details?id=com.example.loan",
        {
            "title": "Example Loan",
            "developer": "Example Finance Pvt Ltd",
            "description": "APR is 24% and the annual percentage rate is shown before borrowing.",
            "developerEmail": "support@examplefinance.in",
            "developerWebsite": "https://examplefinance.in",
            "developerAddress": "Mumbai, India",
            "released": "Jan 1, 2025",
            "updated": None,
            "minInstalls": 10000,
            "score": 4.2,
            "installs": "10,000+",
        },
    )
    f = payload["public_features"]
    assert f["apr_disclosed"] == 1
    assert f["developer_website_present"] == 1
    assert f["physical_address_present"] == 1
    assert f["company_email_domain"] == 1
    assert f["contacts_permission"] is None


def test_auto_metadata_does_not_turn_missing_apr_text_into_negative(tmp_path):
    service = AppMetadataService(
        cache_db=tmp_path / "cache2.sqlite3",
        enabled=False,
        cache_ttl_seconds=3600,
        error_cache_ttl_seconds=60,
        review_analysis_enabled=False,
        review_sample_size=20,
    )
    payload = service._build_payload(
        "com.example.app",
        "https://play.google.com/store/apps/details?id=com.example.app",
        {
            "title": "Example",
            "developer": "Example Pvt Ltd",
            "description": "Instant credit information is available in the app.",
            "developerEmail": "support@example.in",
            "developerWebsite": "https://example.in",
            "developerAddress": "India",
            "released": "Jan 1, 2025",
            "updated": None,
            "minInstalls": 1000,
            "score": 4.0,
            "installs": "1,000+",
        },
    )
    assert payload["apr_text_detected"] is False
    assert payload["public_features"]["apr_disclosed"] is None


def test_listed_moderate_listing_signal_is_amber():
    result = decide(
        "Listed", 0.1, None, 0.65, 0.30,
        listing_signal_level="Moderate",
        directory_stale=False,
        model_ready=True,
    )
    assert result["verdict"] == "Amber"


@pytest.fixture()
def web_app(tmp_path):
    pytest.importorskip("flask")
    from app import create_app

    class TestConfig(Config):
        TESTING = True
        SECRET_KEY = "test-secret-key"
        APP_ENV = "testing"
        IS_PRODUCTION = False
        DEBUG = False
        AUTO_METADATA_ENABLED = False
        METADATA_CACHE_DB = tmp_path / "metadata.sqlite3"
        CHECK_RATE_LIMIT_PER_MINUTE = 100
        API_RATE_LIMIT_PER_MINUTE = 100
        TRUST_PROXY = False
        FORCE_HSTS = False

    return create_app(TestConfig)


def _csrf(client):
    response = client.get("/check")
    assert response.status_code == 200
    with client.session_transaction() as session:
        token = session.get("_csrf_token")
    assert token
    return token


def test_check_form_has_csrf_and_cost_disabled(web_app):
    client = web_app.test_client()
    response = client.get("/check")
    assert response.status_code == 200
    assert b'name="_csrf_token"' in response.data
    assert b"data-cost-fields disabled" in response.data
    assert b"Advanced / Optional Public Listing Evidence" in response.data
    assert b'name="app_reference_url"' in response.data


def test_post_rejects_missing_csrf(web_app):
    client = web_app.test_client()
    response = client.post("/check", data={"app_name": "GeM Sahay"})
    assert response.status_code == 400


def test_minimal_post_runs_without_inventing_cost(web_app):
    client = web_app.test_client()
    token = _csrf(client)
    response = client.post("/check", data={"_csrf_token": token, "app_name": "GeM Sahay"})
    assert response.status_code == 200
    assert b"Identity Verification" in response.data
    assert b"Cost calculation was skipped" in response.data
    assert b"Public listing" in response.data


def test_clickmyloan_official_website_flow_resolves_and_lists(web_app):
    client = web_app.test_client()
    token = _csrf(client)
    response = client.post("/check", data={
        "_csrf_token": token,
        "app_name": "click my loan",
        "app_reference_url": "https://web.clickmyloan.com/",
    })
    assert response.status_code == 200
    assert b"Website resolved" in response.data
    assert b"com.habile.cloudbankin.clickmyloan" in response.data
    assert b">Listed<" in response.data


def test_high_apr_gets_separate_cost_attention_badge(web_app):
    client = web_app.test_client()
    token = _csrf(client)
    response = client.post("/check", data={
        "_csrf_token": token,
        "app_name": "GeM Sahay",
        "calculate_cost": "on",
        "loan_amount": "10000",
        "processing_fee": "500",
        "other_upfront_fees": "0",
        "emi": "1900",
        "tenure_months": "6",
        "monthly_income": "15000",
    })
    assert response.status_code == 200
    assert b"Cost Attention" in response.data
    assert b"project attention threshold" in response.data


def test_api_and_security_headers(web_app):
    client = web_app.test_client()
    response = client.post("/api/v1/check", json={"app_name": "GeM Sahay"})
    assert response.status_code == 200
    payload = response.get_json()
    assert "directory" in payload and "decision" in payload
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert "Content-Security-Policy" in response.headers


def test_readiness_endpoint(web_app):
    client = web_app.test_client()
    response = client.get("/readyz")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "ready"



def test_language_gate_and_hindi_switch(web_app):
    client = web_app.test_client()
    response = client.get("/")
    assert response.status_code == 200
    assert b"language-gate" in response.data

    response = client.get("/language/hi?next=/check", follow_redirects=True)
    assert response.status_code == 200
    assert "Safe Loan Check चलाएँ".encode("utf-8") in response.data
    assert b"language-gate" not in response.data

    response = client.get("/language/en?next=/check", follow_redirects=True)
    assert response.status_code == 200
    assert b"Run Safe Loan Check" in response.data


def test_result_has_user_first_summary(web_app):
    client = web_app.test_client()
    client.get("/language/en?next=/check")
    token = _csrf(client)
    response = client.post("/check", data={"_csrf_token": token, "app_name": "GeM Sahay"})
    assert response.status_code == 200
    assert b"What does this result mean?" in response.data
    assert b"View technical details" in response.data
    assert b"Color guide" in response.data

def test_permission_parser_is_positive_only():
    flags, summary = AppMetadataService._permission_feature_flags({
        "Contacts": ["read your contacts"],
        "SMS": ["read your text messages (SMS or MMS)"],
        "Photos/Media/Files": ["read the contents of your USB storage"],
        "Phone": ["read phone status and identity"],
    })
    assert flags["contacts_permission"] == 1
    assert flags["sms_permission"] == 1
    assert flags["media_permission"] == 1
    # Phone-state permission is not the same as call-log access.
    assert flags["call_logs_permission"] is None
    assert summary["available"] is True


def test_permission_parser_does_not_convert_absence_to_zero():
    flags, summary = AppMetadataService._permission_feature_flags({
        "Location": ["precise location (GPS and network-based)"],
    })
    assert all(value is None for value in flags.values())
    assert summary["positive_flags"] == []


def test_development_directory_is_real_when_snapshot_present():
    # The packaged project carries a dated real snapshot; development should prefer it.
    assert Path(Config.DLA_CSV).name == "dla_directory_real.csv"


def test_package_parser_handles_common_rbi_export_variants():
    samples = {
        "Android App URL: https://play.google.com/store/apps/details?id=com.one360.lending": "com.one360.lending",
        "https//play.google.com/store/apps/details?id=in.bajajfinservmarkets.app": "in.bajajfinservmarkets.app",
        "https://play.google.com.store/apps/details?id=com.paisabazaar": "com.paisabazaar",
        "https://protect.checkpoint.com/v2/r05/___https://play.google.com/store/apps/details?id=com.msf.angelmobile&hl=en_IN___": "com.msf.angelmobile",
        "https://play.google.com/apps/test/com.nextcapital/1": "com.nextcapital",
        "https://www.indusappstore.com/apps/finance/jhatpat-loans/com.habile.cloudbankin.achiievers/?page=details&id=com.habile.cloudbankin.achiievers": "com.habile.cloudbankin.achiievers",
    }
    for raw, expected in samples.items():
        assert package_id_from_play_url(raw) == expected


def test_capital_now_strong_title_and_owner_match_when_official_row_has_no_direct_package():
    index = DirectoryIndex(Config.DLA_CSV, stale_after_days=45)
    result = index.lookup(
        "Capital Now: Personal Loan App",
        "FINXER TECHNOLOGIES PRIVATE LIMITED",
        "https://play.google.com/store/apps/details?id=com.capitalnowapp.mobile&hl=en-IN",
    )
    assert result["status"] == "Listed"
    assert result["match_score"] >= 90
    assert result["matched_app"].lower().startswith("capital now")
    assert "GOLDLINE FINANCE" in " ".join(result["regulated_entities"]).upper()
    assert result["match_method"] == "strong_title_identity"


def test_exact_listed_name_with_wrong_developer_is_unclear_not_not_listed():
    index = DirectoryIndex(Config.DLA_CSV, stale_after_days=45)
    result = index.lookup("GeM Sahay", "Definitely Different Developer")
    assert result["status"] == "Unclear"
    assert result["match_method"] == "exact_name_identity_unclear"


def test_every_bundled_official_package_resolves_listed():
    index = DirectoryIndex(Config.DLA_CSV, stale_after_days=45)
    assert index.meta["unique_packages"] >= 400
    for package_id in index.by_package:
        result = index.lookup(
            "Store title may have changed",
            "Store developer may have changed",
            f"https://play.google.com/store/apps/details?id={package_id}",
        )
        assert result["status"] == "Listed", package_id
        assert result["match_score"] == 100, package_id
