from __future__ import annotations

from pathlib import Path
import json
import sqlite3
import time


class MetadataCache:
    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self):
        conn = sqlite3.connect(self.db_path, timeout=5)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        return conn

    def _init_db(self):
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS app_metadata_cache (
                    package_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    fetched_at INTEGER NOT NULL
                )
                """
            )

    def get(self, package_id: str):
        with self._connect() as conn:
            row = conn.execute(
                "SELECT status, payload_json, fetched_at FROM app_metadata_cache WHERE package_id = ?",
                (package_id,),
            ).fetchone()
        if not row:
            return None
        status, payload_json, fetched_at = row
        age = int(time.time()) - int(fetched_at)
        try:
            payload = json.loads(payload_json)
        except json.JSONDecodeError:
            return None
        payload["cache_hit"] = True
        payload["cache_age_seconds"] = max(0, age)
        payload["cache_status"] = status
        return payload

    def put(self, package_id: str, status: str, payload: dict):
        stored = dict(payload)
        stored.pop("cache_hit", None)
        stored.pop("cache_age_seconds", None)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO app_metadata_cache(package_id, status, payload_json, fetched_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(package_id) DO UPDATE SET
                    status=excluded.status,
                    payload_json=excluded.payload_json,
                    fetched_at=excluded.fetched_at
                """,
                (package_id, status, json.dumps(stored, ensure_ascii=False), int(time.time())),
            )
