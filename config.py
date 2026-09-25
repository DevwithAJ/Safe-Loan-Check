import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


def env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


class Config:
    APP_VERSION = "2.6.3-team-roles"
    APP_ENV = os.getenv("APP_ENV", os.getenv("FLASK_ENV", "development")).strip().lower()
    IS_PRODUCTION = APP_ENV == "production"
    DEBUG = env_bool("FLASK_DEBUG", not IS_PRODUCTION)

    SECRET_KEY = os.getenv("SECRET_KEY", "dev-safe-loan-check-change-me")
    MAX_CONTENT_LENGTH = int(os.getenv("MAX_CONTENT_LENGTH", str(64 * 1024)))

    # Cookie/session hardening. Secure is enabled automatically in production.
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = env_bool("SESSION_COOKIE_SECURE", IS_PRODUCTION)
    PERMANENT_SESSION_LIFETIME = 1800

    # Risk / cost thresholds. These are project thresholds, not legal limits.
    HIGH_RISK_THRESHOLD = float(os.getenv("HIGH_RISK_THRESHOLD", "0.42"))
    AFFORDABILITY_THRESHOLD = float(os.getenv("AFFORDABILITY_THRESHOLD", "0.30"))
    COST_ATTENTION_APR = float(os.getenv("COST_ATTENTION_APR", "36.0"))

    # Directory snapshot behaviour.
    REAL_DLA_CSV = BASE_DIR / "data" / "dla_directory_real.csv"
    DEMO_DLA_CSV = BASE_DIR / "data" / "dla_directory.csv"
    _REAL_DLA_USABLE = REAL_DLA_CSV.exists() and REAL_DLA_CSV.stat().st_size > 100
    # Never silently fall back to demo data in production. A production process must
    # fail validation if the dated real RBI snapshot is missing or unusable.
    DLA_CSV = REAL_DLA_CSV if (_REAL_DLA_USABLE or IS_PRODUCTION) else DEMO_DLA_CSV
    DIRECTORY_STALE_AFTER_DAYS = int(os.getenv("DIRECTORY_STALE_AFTER_DAYS", "45"))

    # Model artifact.
    MODEL_PATH = BASE_DIR / "models" / "risk_model.joblib"
    MODEL_META = BASE_DIR / "models" / "risk_model_meta.json"

    # Dated website-domain -> Google Play mappings. The server never crawls
    # arbitrary user-supplied websites; only source-backed aliases are resolved.
    APP_REFERENCE_ALIAS_CSV = BASE_DIR / "data" / "app_reference_aliases.csv"

    # Public Google Play metadata. Uses a cache so the app does not repeatedly query the store.
    AUTO_METADATA_ENABLED = env_bool("AUTO_METADATA_ENABLED", True)
    REVIEW_ANALYSIS_ENABLED = env_bool("REVIEW_ANALYSIS_ENABLED", False)
    REVIEW_SAMPLE_SIZE = max(10, min(int(os.getenv("REVIEW_SAMPLE_SIZE", "50")), 100))
    METADATA_CACHE_TTL_SECONDS = max(300, int(os.getenv("METADATA_CACHE_TTL_SECONDS", "43200")))
    METADATA_ERROR_CACHE_TTL_SECONDS = max(60, int(os.getenv("METADATA_ERROR_CACHE_TTL_SECONDS", "900")))
    METADATA_CACHE_DB = BASE_DIR / "instance" / "metadata_cache.sqlite3"

    # Request protection. This built-in limiter is intentionally paired with one Gunicorn worker.
    CHECK_RATE_LIMIT_PER_MINUTE = max(1, int(os.getenv("CHECK_RATE_LIMIT_PER_MINUTE", "20")))
    API_RATE_LIMIT_PER_MINUTE = max(1, int(os.getenv("API_RATE_LIMIT_PER_MINUTE", "30")))

    # Reverse proxy / HTTPS behaviour.
    TRUST_PROXY = env_bool("TRUST_PROXY", IS_PRODUCTION)
    FORCE_HSTS = env_bool("FORCE_HSTS", IS_PRODUCTION)

    # Feature flags.
    ENABLE_API = env_bool("ENABLE_API", True)
    DEMO_MODE = env_bool("DEMO_MODE", False)

    @classmethod
    def validate(cls):
        problems = []
        if cls.IS_PRODUCTION and cls.SECRET_KEY in {
            "",
            "dev-safe-loan-check-change-me",
            "change-this-in-production",
        }:
            problems.append("SECRET_KEY must be changed before APP_ENV=production.")
        if not (0 < cls.HIGH_RISK_THRESHOLD < 1):
            problems.append("HIGH_RISK_THRESHOLD must be between 0 and 1.")
        if not (0 < cls.AFFORDABILITY_THRESHOLD <= 1):
            problems.append("AFFORDABILITY_THRESHOLD must be between 0 and 1.")
        if cls.COST_ATTENTION_APR <= 0:
            problems.append("COST_ATTENTION_APR must be greater than 0.")
        if cls.IS_PRODUCTION and not cls._REAL_DLA_USABLE:
            problems.append("A usable data/dla_directory_real.csv is required in production; demo fallback is disabled.")
        if cls.IS_PRODUCTION and not cls.MODEL_PATH.exists():
            problems.append("models/risk_model.joblib is required in production.")
        if cls.IS_PRODUCTION and not cls.MODEL_META.exists():
            problems.append("models/risk_model_meta.json is required in production.")
        if cls.IS_PRODUCTION and not cls.APP_REFERENCE_ALIAS_CSV.exists():
            problems.append("data/app_reference_aliases.csv is required in production.")
        return problems
