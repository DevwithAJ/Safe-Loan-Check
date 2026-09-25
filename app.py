from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import hmac
import json
import logging
import math
import secrets
import uuid

from dotenv import load_dotenv
from flask import Flask, abort, g, jsonify, redirect, render_template, request, session
from werkzeug.middleware.proxy_fix import ProxyFix

load_dotenv()

from config import Config
from translations import TRANSLATIONS
from services.app_metadata import AppMetadataService
from services.app_reference import AppReferenceResolver
from services.cost_calculator import calculate_cost
from services.decision_layer import decide
from services.dla_lookup import DirectoryIndex
from services.rate_limit import FixedWindowRateLimiter
from services.risk_model import RiskModel
from services.validators import (
    ValidationError,
    parse_manual_listing_features,
    validate_cost,
    validate_identity,
)

logger = logging.getLogger("safe_loan_check")


def _configure_logging(app: Flask):
    level = logging.DEBUG if app.debug else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


def _client_ip() -> str:
    return request.remote_addr or "unknown"


def _csrf_token() -> str:
    token = session.get("_csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["_csrf_token"] = token
    return token


def _check_csrf():
    expected = session.get("_csrf_token", "")
    supplied = request.form.get("_csrf_token", "")
    if not expected or not supplied or not hmac.compare_digest(str(expected), str(supplied)):
        abort(400, description="The form session expired or the CSRF token was invalid. Reload the form and try again.")


def _merge_features(manual: dict, automatic: dict | None) -> tuple[dict, dict]:
    automatic = automatic or {}
    merged = {}
    sources = {}
    keys = set(manual) | set(automatic)
    for key in keys:
        manual_value = manual.get(key)
        auto_value = automatic.get(key)
        if manual_value is not None and manual_value != "":
            merged[key] = manual_value
            sources[key] = "manual"
        else:
            merged[key] = auto_value
            sources[key] = "public_listing" if auto_value is not None and auto_value != "" else "unknown"

    installs = automatic.get("installs")
    if manual.get("installs_log10") is None and installs is not None:
        try:
            merged["installs_log10"] = math.log10(float(installs) + 1)
            sources["installs_log10"] = "public_listing"
        except (TypeError, ValueError):
            pass
    return merged, sources


def _translate(key: str, lang: str = "en", **kwargs) -> str:
    language = lang if lang in TRANSLATIONS else "en"
    text = TRANSLATIONS.get(language, {}).get(key)
    if text is None:
        text = TRANSLATIONS.get("en", {}).get(key, key)
    try:
        return str(text).format(**kwargs)
    except Exception:
        return str(text)


def _safe_next_url(value: str | None) -> str:
    value = (value or "").strip()
    if not value.startswith("/") or value.startswith("//"):
        return "/"
    return value


def _public_metadata_view(metadata: dict) -> dict:
    """Remove verbose provider text before returning metadata to UI/API."""
    if not metadata:
        return {}
    allowed = {
        "status", "attempted", "provider", "package_id", "source_url", "fetched_at",
        "title", "developer", "developer_email", "developer_website", "developer_address",
        "apr_text_detected",
        "released", "updated", "installs_display", "public_features", "permission_summary", "review_summary",
        "cache_hit", "cache_age_seconds", "stale_cache", "reason", "provider_error_type",
    }
    return {k: v for k, v in metadata.items() if k in allowed}


def create_app(config_object=Config) -> Flask:
    app = Flask(__name__, instance_relative_config=False)
    app.config.from_object(config_object)

    validation_problems = config_object.validate()
    if validation_problems:
        message = " ".join(validation_problems)
        if app.config.get("IS_PRODUCTION"):
            raise RuntimeError(message)
        logger.warning("Configuration warning: %s", message)

    Path(app.root_path, "instance").mkdir(parents=True, exist_ok=True)
    _configure_logging(app)

    if app.config.get("TRUST_PROXY"):
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1)

    directory_index = DirectoryIndex(
        app.config["DLA_CSV"],
        stale_after_days=app.config["DIRECTORY_STALE_AFTER_DAYS"],
    )
    risk_model = RiskModel(app.config["MODEL_PATH"], app.config["MODEL_META"])
    metadata_service = AppMetadataService(
        cache_db=app.config["METADATA_CACHE_DB"],
        enabled=app.config["AUTO_METADATA_ENABLED"],
        cache_ttl_seconds=app.config["METADATA_CACHE_TTL_SECONDS"],
        error_cache_ttl_seconds=app.config["METADATA_ERROR_CACHE_TTL_SECONDS"],
        review_analysis_enabled=app.config["REVIEW_ANALYSIS_ENABLED"],
        review_sample_size=app.config["REVIEW_SAMPLE_SIZE"],
    )
    reference_resolver = AppReferenceResolver(app.config["APP_REFERENCE_ALIAS_CSV"])
    limiter = FixedWindowRateLimiter()

    app.extensions["directory_index"] = directory_index
    app.extensions["risk_model"] = risk_model
    app.extensions["metadata_service"] = metadata_service
    app.extensions["reference_resolver"] = reference_resolver
    app.extensions["rate_limiter"] = limiter

    @app.context_processor
    def inject_globals():
        lang = getattr(g, "lang", "en")
        selected_cookie = request.cookies.get("slc_lang")
        selected_session = session.get("language_selected")
        return {
            "csrf_token": _csrf_token,
            "app_version": app.config["APP_VERSION"],
            "production_mode": app.config["IS_PRODUCTION"],
            "current_lang": lang,
            "show_language_gate": not bool(selected_session or selected_cookie in {"en", "hi"}),
            "t": lambda key, **kwargs: _translate(key, lang, **kwargs),
        }

    @app.before_request
    def request_guards():
        requested_lang = session.get("lang") or request.cookies.get("slc_lang")
        g.lang = requested_lang if requested_lang in {"en", "hi"} else "en"

        incoming = request.headers.get("X-Request-ID", "")
        g.request_id = incoming[:80] if incoming and incoming.replace("-", "").isalnum() else uuid.uuid4().hex

        if request.endpoint == "check" and request.method == "POST":
            allowed, retry_after = limiter.allow(
                f"web:{_client_ip()}",
                limit=app.config["CHECK_RATE_LIMIT_PER_MINUTE"],
                window_seconds=60,
            )
            if not allowed:
                response = jsonify({"error": "Too many checks. Please wait and retry.", "request_id": g.request_id})
                response.status_code = 429
                response.headers["Retry-After"] = str(retry_after)
                return response
            _check_csrf()

        if request.endpoint == "api_check" and request.method == "POST":
            allowed, retry_after = limiter.allow(
                f"api:{_client_ip()}",
                limit=app.config["API_RATE_LIMIT_PER_MINUTE"],
                window_seconds=60,
            )
            if not allowed:
                response = jsonify({"error": "Rate limit exceeded.", "request_id": g.request_id})
                response.status_code = 429
                response.headers["Retry-After"] = str(retry_after)
                return response

    @app.after_request
    def security_headers(response):
        response.headers["X-Request-ID"] = getattr(g, "request_id", uuid.uuid4().hex)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=(), payment=()"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; "
            "font-src 'self'; "
            "connect-src 'self'; "
            "object-src 'none'; "
            "base-uri 'self'; "
            "form-action 'self'; "
            "frame-ancestors 'none'"
        )
        if app.config.get("FORCE_HSTS") and request.is_secure:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        if response.mimetype == "text/html" or request.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store, max-age=0"
        return response

    def current_data_mode():
        if Path(app.config["DLA_CSV"]).name == "dla_directory_real.csv":
            return "REAL RBI DIRECTORY" if directory_index.meta.get("available") else "RBI DIRECTORY UNAVAILABLE"
        return "DEMO DATA"

    def analyze(mapping) -> dict:
        identity = validate_identity(mapping)
        manual_features = parse_manual_listing_features(mapping)
        cost_inputs = validate_cost(mapping)

        # Resolve a direct Play URL or a source-backed official website alias.
        # Arbitrary websites are never crawled by the Flask server.
        reference = reference_resolver.resolve(identity["app_reference_url"])
        resolved_play_url = reference.get("play_store_url") or identity["play_store_url"]

        metadata = metadata_service.fetch(resolved_play_url) if resolved_play_url else {
            "status": "not_requested",
            "attempted": False,
            "package_id": None,
        }

        # A verified URL identity is stronger than free-text naming. When public
        # Play metadata is available, use its current title/developer. Otherwise
        # use the dated alias identity before falling back to user text.
        effective_app_name = identity["app_name"]
        effective_developer = identity["developer_name"]
        if metadata.get("status") == "ok":
            effective_app_name = str(metadata.get("title") or "").strip() or effective_app_name
            effective_developer = str(metadata.get("developer") or "").strip() or effective_developer
        elif reference.get("status") == "resolved":
            effective_app_name = str(reference.get("canonical_app_name") or "").strip() or effective_app_name
            effective_developer = str(reference.get("canonical_developer") or "").strip() or effective_developer

        if not effective_app_name:
            raise ValidationError("The supplied URL did not resolve an app name. Enter the app name manually.")

        directory = directory_index.lookup(effective_app_name, effective_developer, resolved_play_url)
        metadata = metadata_service.enrich_with_directory(metadata, directory)
        auto_features = metadata.get("public_features", {}) if metadata.get("status") == "ok" else {}
        features, feature_sources = _merge_features(manual_features, auto_features)

        risk = risk_model.score(app_name=effective_app_name, features=features)

        cost = calculate_cost(**cost_inputs) if cost_inputs else None
        threshold = float(risk.get("threshold", app.config["HIGH_RISK_THRESHOLD"]))
        decision = decide(
            directory_status=directory["status"],
            risk_probability=risk.get("risk_probability"),
            cost_result=cost,
            high_risk_threshold=threshold,
            affordability_threshold=app.config["AFFORDABILITY_THRESHOLD"],
            listing_signal_level=risk.get("listing_signal_level", "Insufficient"),
            directory_stale=bool(directory.get("snapshot", {}).get("stale")),
            model_ready=bool(risk.get("ready")),
        )

        cost_attention = False
        if cost and cost.get("valid") and cost.get("apr_percent") is not None:
            cost_attention = float(cost["apr_percent"]) >= float(app.config["COST_ATTENTION_APR"])

        return {
            "app_name": effective_app_name,
            "developer_name": effective_developer,
            "app_reference_url": identity["app_reference_url"],
            "play_store_url": resolved_play_url,
            "reference": reference,
            "directory": directory,
            "risk": risk,
            "features": features,
            "feature_sources": feature_sources,
            "metadata": _public_metadata_view(metadata),
            "cost": cost,
            "decision": decision,
            "cost_attention": cost_attention,
            "cost_attention_apr": app.config["COST_ATTENTION_APR"],
            "affordability_threshold": app.config["AFFORDABILITY_THRESHOLD"],
            "high_risk_threshold": threshold,
            "data_mode": current_data_mode(),
            "analysis_time": datetime.now(timezone.utc).isoformat(),
            "request_id": getattr(g, "request_id", None),
        }

    @app.get("/language/<lang>")
    def set_language(lang):
        lang = str(lang or "").lower()
        if lang not in {"en", "hi"}:
            abort(404)
        session["lang"] = lang
        session["language_selected"] = True
        response = redirect(_safe_next_url(request.args.get("next")))
        response.set_cookie(
            "slc_lang",
            lang,
            max_age=60 * 60 * 24 * 365,
            secure=app.config.get("SESSION_COOKIE_SECURE", False),
            httponly=True,
            samesite="Lax",
        )
        return response

    @app.get("/")
    def home():
        return render_template(
            "home.html",
            demo_mode=app.config["DEMO_MODE"],
            data_mode=current_data_mode(),
            directory_meta=directory_index.meta,
        )

    @app.get("/check")
    def check_app():
        return render_template(
            "check.html",
            demo_mode=app.config["DEMO_MODE"],
            data_mode=current_data_mode(),
            directory_meta=directory_index.meta,
            metadata_enabled=app.config["AUTO_METADATA_ENABLED"],
            errors=[],
            form_values={},
        )

    @app.post("/check")
    def check():
        try:
            result = analyze(request.form)
        except ValidationError as exc:
            return render_template(
                "check.html",
                demo_mode=app.config["DEMO_MODE"],
                data_mode=current_data_mode(),
                directory_meta=directory_index.meta,
                metadata_enabled=app.config["AUTO_METADATA_ENABLED"],
                errors=[str(exc)],
                form_values=request.form,
            ), 400

        return render_template(
            "result.html",
            **result,
            demo_mode=app.config["DEMO_MODE"],
        )

    @app.get("/methodology")
    def methodology():
        return render_template(
            "methodology.html",
            demo_mode=app.config["DEMO_MODE"],
            data_mode=current_data_mode(),
            directory_meta=directory_index.meta,
        )

    @app.get("/about")
    def about():
        return render_template(
            "about.html",
            demo_mode=app.config["DEMO_MODE"],
            data_mode=current_data_mode(),
            directory_meta=directory_index.meta,
        )

    @app.get("/privacy")
    def privacy():
        return render_template("privacy.html", data_mode=current_data_mode(), directory_meta=directory_index.meta)

    @app.get("/terms")
    def terms():
        return render_template("terms.html", data_mode=current_data_mode(), directory_meta=directory_index.meta)

    @app.get("/status")
    def status_page():
        return render_template(
            "status.html",
            data_mode=current_data_mode(),
            directory_meta=directory_index.meta,
            model_health=risk_model.health,
            metadata_provider_available=metadata_service.provider_available(),
            metadata_enabled=app.config["AUTO_METADATA_ENABLED"],
        )

    @app.get("/healthz")
    def healthz():
        # Liveness: the Flask process is serving requests.
        return jsonify({"status": "ok", "version": app.config["APP_VERSION"]})

    @app.get("/readyz")
    def readyz():
        ready = bool(directory_index.meta.get("available")) and risk_model.ready
        payload = {
            "status": "ready" if ready else "not_ready",
            "version": app.config["APP_VERSION"],
            "directory": directory_index.meta,
            "model": risk_model.health,
            "metadata_provider_available": metadata_service.provider_available(),
        }
        return jsonify(payload), (200 if ready else 503)

    @app.get("/api/v1/status")
    def api_status():
        if not app.config["ENABLE_API"]:
            abort(404)
        return jsonify({
            "version": app.config["APP_VERSION"],
            "directory": directory_index.meta,
            "model": risk_model.health,
            "metadata": {
                "enabled": app.config["AUTO_METADATA_ENABLED"],
                "provider_available": metadata_service.provider_available(),
                "review_analysis_enabled": app.config["REVIEW_ANALYSIS_ENABLED"],
            },
        })

    @app.post("/api/v1/check")
    def api_check():
        if not app.config["ENABLE_API"]:
            abort(404)
        if not request.is_json:
            return jsonify({"error": "Content-Type must be application/json", "request_id": g.request_id}), 415
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify({"error": "JSON body must be an object", "request_id": g.request_id}), 400
        try:
            result = analyze(payload)
        except ValidationError as exc:
            return jsonify({"error": str(exc), "request_id": g.request_id}), 400
        return jsonify({
            "app_name": result["app_name"],
            "developer_name": result["developer_name"],
            "directory": result["directory"],
            "risk": result["risk"],
            "reference": result["reference"],
            "public_listing": result["metadata"],
            "cost": result["cost"],
            "decision": result["decision"],
            "analysis_time": result["analysis_time"],
            "request_id": result["request_id"],
            "disclaimer": "Educational awareness output only. Not a legality determination, loan approval, financial advice or legal advice.",
        })

    @app.errorhandler(400)
    def bad_request(error):
        return render_template(
            "error.html",
            code=400,
            title=_translate("error.invalid_title", getattr(g, "lang", "en")),
            message=getattr(error, "description", _translate("error.invalid_message", getattr(g, "lang", "en"))),
            data_mode=current_data_mode(),
            directory_meta=directory_index.meta,
        ), 400

    @app.errorhandler(404)
    def not_found(error):
        return render_template(
            "error.html", code=404, title=_translate("error.not_found_title", getattr(g, "lang", "en")), message=_translate("error.not_found_message", getattr(g, "lang", "en")),
            data_mode=current_data_mode(), directory_meta=directory_index.meta,
        ), 404

    @app.errorhandler(413)
    def too_large(error):
        return render_template(
            "error.html", code=413, title=_translate("error.too_large_title", getattr(g, "lang", "en")), message=_translate("error.too_large_message", getattr(g, "lang", "en")),
            data_mode=current_data_mode(), directory_meta=directory_index.meta,
        ), 413

    @app.errorhandler(500)
    def internal_error(error):
        logger.exception("Unhandled request error request_id=%s", getattr(g, "request_id", "unknown"))
        return render_template(
            "error.html", code=500, title=_translate("error.service_title", getattr(g, "lang", "en")),
            message=_translate("error.service_message", getattr(g, "lang", "en")),
            data_mode=current_data_mode(), directory_meta=directory_index.meta,
        ), 500

    return app


app = create_app()

if __name__ == "__main__":
    # Local development only. Production deployment uses Gunicorn via wsgi.py.
    app.run(host="127.0.0.1", port=5000, debug=app.config.get("DEBUG", False))
