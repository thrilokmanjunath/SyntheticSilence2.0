"""
Small on-disk cache for finished claim results.

Re-checking the same claim costs several LLM calls and search requests; a cached result is returned
instantly and for free. Only successful results are stored: a failure is never cached, so an outage
or a spent search budget cannot be replayed later as if it were an answer.

The key includes everything that changes the answer (model, mode, retrievers, prompt version), so a
configuration change never serves a result produced by a different configuration.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Dict, Optional

# Bump when prompts or aggregation rules change so older cached verdicts are not reused.
CACHE_VERSION = "2"


def make_key(claim_text: str, fingerprint: Dict[str, Any]) -> str:
    normalized = " ".join(claim_text.lower().split())
    payload = json.dumps({"v": CACHE_VERSION, "claim": normalized, "cfg": fingerprint}, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class ResultCache:
    def __init__(self, path: Path | str, max_entries: int = 500, ttl_seconds: int = 7 * 24 * 3600):
        self.path = str(path)
        self.max_entries = max_entries
        self.ttl_seconds = ttl_seconds
        self._lock = threading.Lock()
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(self.path, check_same_thread=False)
        self._db.execute(
            "CREATE TABLE IF NOT EXISTS results ("
            "key TEXT PRIMARY KEY, value TEXT NOT NULL, created REAL NOT NULL, used REAL NOT NULL)"
        )
        self._db.commit()
        self.hits = 0
        self.misses = 0

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        now = time.time()
        with self._lock:
            row = self._db.execute("SELECT value, created FROM results WHERE key = ?", (key,)).fetchone()
            if row is None:
                self.misses += 1
                return None
            value, created = row
            if now - created > self.ttl_seconds:
                self._db.execute("DELETE FROM results WHERE key = ?", (key,))
                self._db.commit()
                self.misses += 1
                return None
            self._db.execute("UPDATE results SET used = ? WHERE key = ?", (now, key))
            self._db.commit()
            self.hits += 1
        try:
            return json.loads(value)
        except ValueError:
            return None

    def set(self, key: str, value: Dict[str, Any]) -> None:
        now = time.time()
        encoded = json.dumps(value, separators=(",", ":"))
        with self._lock:
            self._db.execute(
                "INSERT INTO results (key, value, created, used) VALUES (?, ?, ?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value, created = excluded.created, used = excluded.used",
                (key, encoded, now, now),
            )
            # Least recently used entries go first.
            self._db.execute(
                "DELETE FROM results WHERE key IN ("
                "SELECT key FROM results ORDER BY used DESC LIMIT -1 OFFSET ?)",
                (self.max_entries,),
            )
            self._db.commit()

    def __len__(self) -> int:
        with self._lock:
            return self._db.execute("SELECT COUNT(*) FROM results").fetchone()[0]

    def clear(self) -> None:
        with self._lock:
            self._db.execute("DELETE FROM results")
            self._db.commit()

    def close(self) -> None:
        with self._lock:
            self._db.close()
