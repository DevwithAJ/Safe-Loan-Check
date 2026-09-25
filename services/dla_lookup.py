from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
import csv
import hashlib
import re

from rapidfuzz import fuzz

from .validators import package_id_from_play_url


def _norm(value: str) -> str:
    text = str(value or "").lower().strip()
    text = text.replace("&", " and ")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def _compact(value: str) -> str:
    """Spacing/punctuation-insensitive identity key."""
    return re.sub(r"[^a-z0-9]+", "", str(value or "").lower())


def _company_norm(value: str) -> str:
    """Normalize common company suffix spelling differences for identity matching."""
    tokens = _norm(value).split()
    drop = {
        "private", "pvt", "limited", "ltd", "llp", "inc", "incorporated",
        "company", "co", "the",
    }
    tokens = [t for t in tokens if t not in drop]
    return " ".join(tokens)


def _parse_bool(value) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _parse_date(value: str):
    text = str(value or "").strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            pass
    return None


def _app_similarity(query: str, candidate: str) -> int:
    """Robust app-title similarity while preserving clone-safety via developer checks."""
    q = _norm(query)
    c = _norm(candidate)
    if not q or not c:
        return 0
    if _compact(q) == _compact(c) and len(_compact(q)) >= 4:
        return 100
    return int(round(max(
        fuzz.ratio(q, c),
        fuzz.token_set_ratio(q, c),
        fuzz.WRatio(q, c),
    )))


def _developer_similarity(query: str, row: dict) -> int:
    """Compare current Play developer to either DLA owner/LSP or regulated entity."""
    q = _company_norm(query)
    if not q:
        return 0
    candidates = [
        _company_norm(row.get("developer_name")),
        _company_norm(row.get("regulated_entity")),
    ]
    scores = []
    for c in candidates:
        if not c:
            continue
        if _compact(q) == _compact(c):
            scores.append(100)
        else:
            scores.append(max(fuzz.ratio(q, c), fuzz.token_set_ratio(q, c), fuzz.WRatio(q, c)))
    return int(round(max(scores))) if scores else 0


class DirectoryIndex:
    """In-memory indexed view of a dated RBI DLA snapshot.

    Identity priority in v2.5:
      1. exact Android package id,
      2. exact-equivalent DLA title + owner/entity,
      3. strong title + owner/entity match when the official row has no package id,
      4. otherwise Unclear/Not listed.

    This avoids the earlier failure mode where a store title changed while the same
    package remained in the RBI export, or where RBI's owner name differed from the
    Google Play developer spelling.
    """

    def __init__(self, csv_path: Path, stale_after_days: int = 45):
        self.csv_path = Path(csv_path)
        self.stale_after_days = int(stale_after_days)
        self.rows: list[dict] = []
        self.by_package: dict[str, list[dict]] = {}
        self.by_compact_app: dict[str, list[dict]] = {}
        self.meta: dict = {}
        self.reload()

    def reload(self):
        self.rows = []
        self.by_package = {}
        self.by_compact_app = {}
        if not self.csv_path.exists():
            self.meta = {
                "available": False,
                "row_count": 0,
                "path": str(self.csv_path),
                "sha256": None,
                "snapshot_date": None,
                "age_days": None,
                "stale": True,
                "package_rows": 0,
                "unique_packages": 0,
            }
            return

        digest = hashlib.sha256()
        with self.csv_path.open("rb") as fh:
            for block in iter(lambda: fh.read(1024 * 1024), b""):
                digest.update(block)

        source_dates = []
        with self.csv_path.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            for raw in reader:
                app_name = str(raw.get("app_name") or "").strip()
                if not app_name:
                    continue
                source_date = str(raw.get("source_date") or "").strip()
                parsed_date = _parse_date(source_date)
                if parsed_date:
                    source_dates.append(parsed_date)

                stored_pkg = str(raw.get("package_id") or "").strip()
                parsed_pkg = package_id_from_play_url(str(raw.get("app_url") or ""))
                package_id = stored_pkg or parsed_pkg
                if package_id and not re.fullmatch(r"[A-Za-z0-9_]+(?:\.[A-Za-z0-9_]+)+", package_id):
                    package_id = None

                row = {
                    "app_name": app_name,
                    "developer_name": str(raw.get("developer_name") or "").strip(),
                    "regulated_entity": str(raw.get("regulated_entity") or "").strip(),
                    "source_date": source_date,
                    "source_url": str(raw.get("source_url") or "").strip(),
                    "platform": str(raw.get("platform") or "").strip(),
                    "app_url": str(raw.get("app_url") or "").strip(),
                    "raw_app_url": str(raw.get("raw_app_url") or raw.get("app_url") or "").strip(),
                    "source_record_no": str(raw.get("source_record_no") or "").strip(),
                    "is_demo": _parse_bool(raw.get("is_demo")),
                    "_norm_app": _norm(app_name),
                    "_compact_app": _compact(app_name),
                    "_norm_dev": _norm(raw.get("developer_name")),
                    "_compact_dev": _compact(raw.get("developer_name")),
                    "_norm_entity": _norm(raw.get("regulated_entity")),
                    "_package_id": package_id,
                }
                self.rows.append(row)
                if package_id:
                    self.by_package.setdefault(package_id, []).append(row)
                if row["_compact_app"]:
                    self.by_compact_app.setdefault(row["_compact_app"], []).append(row)

        snapshot_date = max(source_dates) if source_dates else date.fromtimestamp(self.csv_path.stat().st_mtime)
        age_days = max(0, (date.today() - snapshot_date).days)
        package_rows = sum(1 for row in self.rows if row.get("_package_id"))
        self.meta = {
            "available": bool(self.rows),
            "row_count": len(self.rows),
            "path": str(self.csv_path),
            "sha256": digest.hexdigest(),
            "snapshot_date": snapshot_date.isoformat(),
            "age_days": age_days,
            "stale": age_days > self.stale_after_days,
            "stale_after_days": self.stale_after_days,
            "package_rows": package_rows,
            "unique_packages": len(self.by_package),
        }

    @staticmethod
    def _aggregate(rows: list[dict]):
        entities: list[str] = []
        developers: list[str] = []
        for row in rows:
            entity = str(row.get("regulated_entity") or "").strip()
            developer = str(row.get("developer_name") or "").strip()
            if entity and entity not in entities:
                entities.append(entity)
            if developer and developer not in developers:
                developers.append(developer)
        return entities, developers

    def _result(self, *, status: str, best: dict | None, score: int, reason: str, supporting_rows: list[dict], match_method: str):
        if self.meta.get("stale"):
            reason += " The loaded directory snapshot is older than the configured freshness window."
        entities, developers = self._aggregate(supporting_rows)
        return {
            "status": status,
            "match_score": int(score),
            "matched_app": best.get("app_name") if best else None,
            "matched_developer": best.get("developer_name") if best else None,
            "matched_developers": developers[:20],
            "regulated_entity": entities[0] if entities else (best.get("regulated_entity") if best else None),
            "regulated_entities": entities[:20],
            "match_count": len(supporting_rows),
            "source_date": best.get("source_date") if best else None,
            "source_url": best.get("source_url") if best else None,
            "is_demo": best.get("is_demo") if best else False,
            "reason": reason,
            "match_method": match_method,
            "package_id": best.get("_package_id") if best else None,
            "snapshot": self.meta,
        }

    def lookup(self, app_name: str, developer_name: str = "", app_url: str = "", fuzzy_threshold: int = 88) -> dict:
        if not self.rows:
            return self._result(
                status="Unclear", best=None, score=0,
                reason="No DLA directory data is loaded.", supporting_rows=[], match_method="directory_unavailable",
            )

        q_app = str(app_name or "").strip()
        q_dev = str(developer_name or "").strip()
        q_compact = _compact(q_app)
        q_package = package_id_from_play_url(app_url)

        # 1) Exact package-id match: strongest signal. Store title/developer may change.
        if q_package and q_package in self.by_package:
            package_rows = self.by_package[q_package]
            chosen = max(
                package_rows,
                key=lambda row: (_developer_similarity(q_dev, row), _app_similarity(q_app, row["app_name"])),
            )
            return self._result(
                status="Listed", best=chosen, score=100,
                reason=f"Exact Android package-id match ({q_package}) found in the loaded dated RBI DLA snapshot.",
                supporting_rows=package_rows, match_method="exact_package_id",
            )

        # 2) Exact-equivalent app name. If no developer was supplied, official exact name is enough.
        exact_app_rows = self.by_compact_app.get(q_compact, []) if q_compact else []
        if exact_app_rows:
            if not q_dev:
                chosen = exact_app_rows[0]
                return self._result(
                    status="Listed", best=chosen, score=100,
                    reason="Exact-equivalent DLA name found after normalizing spacing and punctuation.",
                    supporting_rows=exact_app_rows, match_method="exact_app_name",
                )

            ranked = sorted(exact_app_rows, key=lambda row: _developer_similarity(q_dev, row), reverse=True)
            chosen = ranked[0]
            dev_score = _developer_similarity(q_dev, chosen)

            # If a submitted package conflicts with a known official package for the exact same app,
            # do not promote it to Listed merely because the title was copied.
            known_packages = {r.get("_package_id") for r in exact_app_rows if r.get("_package_id")}
            if q_package and known_packages and q_package not in known_packages:
                return self._result(
                    status="Unclear", best=chosen, score=max(90, dev_score),
                    reason=(
                        "The app name matches a listed DLA, but the submitted Android package id does not match "
                        "the package id stored for that DLA. Verify the developer and package carefully."
                    ),
                    supporting_rows=exact_app_rows, match_method="exact_name_package_mismatch",
                )

            if dev_score >= 82:
                return self._result(
                    status="Listed", best=chosen, score=100,
                    reason="Exact-equivalent DLA name plus a strong owner/regulated-entity identity match was found.",
                    supporting_rows=exact_app_rows, match_method="exact_name_identity",
                )

            # Exact name but identity conflict is not 'Not listed'; it is a clone/identity-review case.
            return self._result(
                status="Unclear", best=chosen, score=95,
                reason="The DLA name is listed, but the submitted developer does not strongly match the listed owner or regulated entity.",
                supporting_rows=exact_app_rows, match_method="exact_name_identity_unclear",
            )

        # 3) Strong title + owner/entity identity. This covers RBI rows that contain only a
        # Play search link/website and therefore have no package id to compare.
        candidates = []
        for row in self.rows:
            app_score = _app_similarity(q_app, row["app_name"])
            dev_score = _developer_similarity(q_dev, row) if q_dev else 0
            if q_dev:
                combined = int(round(0.65 * app_score + 0.35 * dev_score))
            else:
                combined = app_score
            candidates.append((combined, app_score, dev_score, row))

        candidates.sort(key=lambda item: (item[0], item[1], item[2]), reverse=True)
        combined, app_score, dev_score, best = candidates[0]

        # If the best strong candidate has a known package different from submitted package,
        # keep it Unclear to avoid blessing a clone.
        if q_package and best.get("_package_id") and best.get("_package_id") != q_package and app_score >= 88:
            return self._result(
                status="Unclear", best=best, score=max(app_score, combined),
                reason="A listed DLA has a very similar title, but its stored Android package id differs from the submitted package.",
                supporting_rows=[best], match_method="strong_name_package_mismatch",
            )

        # Strong current Play title + developer/entity identity can confirm rows where RBI did
        # not publish a direct package-bearing link (for example, only a Play search URL).
        if q_dev and app_score >= 86 and dev_score >= 88 and combined >= 88:
            supporting = [
                row for _, a, d, row in candidates
                if a >= 86 and d >= 88 and _compact(row["app_name"]) == _compact(best["app_name"])
            ] or [best]
            return self._result(
                status="Listed", best=best, score=min(99, max(90, combined)),
                reason=(
                    "Strong DLA-title and owner/regulated-entity identity match found. "
                    "The official row did not provide a matching direct Android package link, so title/developer evidence was used."
                ),
                supporting_rows=supporting, match_method="strong_title_identity",
            )

        if combined >= fuzzy_threshold or app_score >= fuzzy_threshold:
            return self._result(
                status="Unclear", best=best, score=max(combined, app_score),
                reason="A similar DLA identity was found, but the evidence is not strong enough for an exact Listed result.",
                supporting_rows=[best], match_method="fuzzy_identity",
            )

        return self._result(
            status="Not listed", best=best, score=max(combined, app_score),
            reason="No sufficiently close DLA identity match was found in the loaded dated directory copy.",
            supporting_rows=[best] if best else [], match_method="no_match",
        )


def load_directory(csv_path: Path):
    """Backward-compatible helper for older scripts/tests."""
    return DirectoryIndex(csv_path).rows


def lookup_app(app_name: str, developer_name: str, csv_path: Path, fuzzy_threshold: int = 88, app_url: str = "") -> dict:
    """Backward-compatible request-level lookup."""
    return DirectoryIndex(csv_path).lookup(app_name, developer_name, app_url=app_url, fuzzy_threshold=fuzzy_threshold)
