"""SQLite adapters for the audit log and feedback repository (one file, mounted as a volume).

Two small classes over one shared connection keep each port focused (Interface Segregation).
"""
from __future__ import annotations

import hashlib
import sqlite3
import threading
import time
from pathlib import Path

from ...domain.models import AuditRecord, Decision

SCHEMA = """
CREATE TABLE IF NOT EXISTS audit (
  request_id TEXT PRIMARY KEY, ts REAL, client TEXT, source TEXT, decision TEXT, score REAL,
  stage TEXT, rule TEXT, model_version TEXT, latency_ms REAL, text_sha256 TEXT, text TEXT
);
CREATE INDEX IF NOT EXISTS audit_ts ON audit(ts);
CREATE TABLE IF NOT EXISTS feedback (
  id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL, client TEXT, request_id TEXT, text TEXT,
  label INTEGER, note TEXT, status TEXT DEFAULT 'pending'
);
"""


class SqliteDatabase:
    def __init__(self, path: str | Path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.lock = threading.Lock()
        with self.lock:
            self.conn.executescript(SCHEMA)

    def write(self, sql: str, args: tuple = ()) -> sqlite3.Cursor:
        with self.lock:
            cur = self.conn.execute(sql, args)
            self.conn.commit()
            return cur

    def read(self, sql: str, args: tuple = ()) -> list[sqlite3.Row]:
        with self.lock:
            return self.conn.execute(sql, args).fetchall()


class SqliteAuditLog:
    """Stores a hash of every text; the text itself only as the retention mode allows."""

    def __init__(self, db: SqliteDatabase, text_retention: str = "flagged"):
        if text_retention not in ("none", "flagged", "all"):
            raise ValueError("text_retention must be none, flagged or all")
        self._db, self._retention = db, text_retention

    def record(self, e: AuditRecord) -> None:
        v = e.verdict
        keep = self._retention == "all" or (self._retention == "flagged" and v.decision != Decision.ALLOW)
        self._db.write(
            "INSERT OR REPLACE INTO audit VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (e.request_id, time.time(), e.client, e.source.value, v.decision.value, v.score, v.stage,
             v.matched_rule, v.model_version, v.latency_ms, hashlib.sha256(e.text.encode()).hexdigest(),
             e.text if keep else None))

    def text_of(self, request_id: str) -> str | None:
        rows = self._db.read("SELECT text FROM audit WHERE request_id=?", (request_id,))
        return rows[0]["text"] if rows else None

    def stats(self, since_seconds: float = 86400) -> dict:
        rows = self._db.read("SELECT decision, COUNT(*) n FROM audit WHERE ts>? GROUP BY decision",
                             (time.time() - since_seconds,))
        return {r["decision"]: r["n"] for r in rows}


class SqliteFeedbackRepository:
    def __init__(self, db: SqliteDatabase):
        self._db = db

    def add(self, client, request_id, text, label, note) -> int:
        return self._db.write(
            "INSERT INTO feedback (ts, client, request_id, text, label, note) VALUES (?,?,?,?,?,?)",
            (time.time(), client, request_id, text, label, note)).lastrowid

    def list(self, status: str | None = None, limit: int = 200) -> list[dict]:
        if status:
            rows = self._db.read("SELECT * FROM feedback WHERE status=? ORDER BY id DESC LIMIT ?", (status, limit))
        else:
            rows = self._db.read("SELECT * FROM feedback ORDER BY id DESC LIMIT ?", (limit,))
        return [dict(r) for r in rows]

    def review(self, feedback_id: int, status: str, label: int | None) -> bool:
        return self._db.write("UPDATE feedback SET status=?, label=COALESCE(?, label) WHERE id=?",
                              (status, label, feedback_id)).rowcount == 1

    def pending_count(self) -> int:
        return self._db.read("SELECT COUNT(*) n FROM feedback WHERE status='pending'")[0]["n"]
