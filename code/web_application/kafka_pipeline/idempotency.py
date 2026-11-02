"""Persistent idempotency store (SQLite) keyed by correlation_id.

status = in_progress  -> message was started but the process died before finishing
status = done         -> output already produced; a replay must cause no new side effect
"""

import json
import sqlite3
from pathlib import Path

from .kafka_io import now_iso


class IdempotencyStore:
    def __init__(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.path = str(path)
        self.db = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS processed (key TEXT PRIMARY KEY, status TEXT NOT NULL,"
            " started_at TEXT, finished_at TEXT, attempts INTEGER DEFAULT 0, result TEXT)")

    def status(self, key):
        row = self.db.execute("SELECT status FROM processed WHERE key=?", (key,)).fetchone()
        return row[0] if row else None

    def mark_started(self, key):
        self.db.execute(
            "INSERT INTO processed(key, status, started_at, attempts) VALUES(?, 'in_progress', ?, 1)"
            " ON CONFLICT(key) DO UPDATE SET attempts = attempts + 1, started_at = excluded.started_at",
            (key, now_iso()))

    def mark_done(self, key, result=None):
        self.db.execute("UPDATE processed SET status='done', finished_at=?, result=? WHERE key=?",
                        (now_iso(), json.dumps(result, default=str), key))

    def close(self):
        self.db.close()
