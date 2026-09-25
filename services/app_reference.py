from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse
import csv

from .validators import package_id_from_play_url


def _host(value: str) -> str:
    try:
        host = (urlparse(str(value or "").strip()).hostname or "").lower().rstrip(".")
    except Exception:
        return ""
    return host[4:] if host.startswith("www.") else host


def _domain_matches(host: str, domain: str) -> bool:
    host = (host or "").lower().strip(".")
    domain = (domain or "").lower().strip(".")
    if domain.startswith("www."):
        domain = domain[4:]
    return bool(host and domain and (host == domain or host.endswith("." + domain)))


class AppReferenceResolver:
    """Resolve a submitted public app URL without crawling arbitrary websites.

    Security matters here: fetching arbitrary user-supplied websites from the Flask
    server would create SSRF and reliability problems. Instead, this resolver accepts
    HTTPS website URLs and resolves only domains in a small, dated, source-backed
    local alias registry. Google Play links pass through directly.
    """

    def __init__(self, alias_csv: Path):
        self.alias_csv = Path(alias_csv)
        self.aliases: list[dict] = []
        self.reload()

    def reload(self):
        self.aliases = []
        if not self.alias_csv.exists():
            return
        with self.alias_csv.open("r", encoding="utf-8-sig", newline="") as f:
            for raw in csv.DictReader(f):
                domain = str(raw.get("website_domain") or "").strip().lower()
                package_id = str(raw.get("package_id") or "").strip()
                play_url = str(raw.get("play_store_url") or "").strip()
                if not domain or not package_id or not play_url:
                    continue
                self.aliases.append({
                    "website_domain": domain,
                    "package_id": package_id,
                    "play_store_url": play_url,
                    "canonical_app_name": str(raw.get("canonical_app_name") or "").strip(),
                    "canonical_developer": str(raw.get("canonical_developer") or "").strip(),
                    "source_url": str(raw.get("source_url") or "").strip(),
                    "source_note": str(raw.get("source_note") or "").strip(),
                    "verified_on": str(raw.get("verified_on") or "").strip(),
                })

    def resolve(self, reference_url: str) -> dict:
        reference_url = str(reference_url or "").strip()
        if not reference_url:
            return {
                "status": "not_requested",
                "input_url": "",
                "play_store_url": "",
                "package_id": None,
                "method": None,
            }

        package_id = package_id_from_play_url(reference_url)
        if package_id:
            return {
                "status": "play_store",
                "input_url": reference_url,
                "play_store_url": reference_url,
                "package_id": package_id,
                "canonical_app_name": "",
                "canonical_developer": "",
                "source_url": reference_url,
                "source_note": "Google Play URL supplied directly by the user.",
                "verified_on": None,
                "method": "direct_google_play",
                "reason": "Google Play package id read directly from the submitted URL.",
            }

        host = _host(reference_url)
        for alias in self.aliases:
            if _domain_matches(host, alias["website_domain"]):
                return {
                    "status": "resolved",
                    "input_url": reference_url,
                    **alias,
                    "method": "verified_domain_alias",
                    "reason": (
                        f"Official website domain {host} matched a dated local alias and was resolved "
                        f"to Google Play package {alias['package_id']}."
                    ),
                }

        return {
            "status": "unresolved_website",
            "input_url": reference_url,
            "play_store_url": "",
            "package_id": None,
            "canonical_app_name": "",
            "canonical_developer": "",
            "source_url": "",
            "source_note": "",
            "verified_on": None,
            "method": "no_verified_alias",
            "reason": "The website URL is valid, but no dated local website-to-Play mapping is registered for this domain.",
        }
