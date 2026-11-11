"""SQLite storage for the audit log and feedback (single file, mounted as a volume)."""
from __future__ import annotations

import hashlib
import sqlite3
import threading
import time
from pathlib import Path

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


class Store:
    def __init__(self, path: str | Path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(path), check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.lock = threading.Lock()
        with self.lock:
            self.db.executescript(SCHEMA)

    def log(self, request_id, client, source, v, text, log_text: str) -> None:
        keep = log_text == "all" or (log_text == "flagged" and v["decision"] != "allow")
        with self.lock:
            self.db.execute(
                "INSERT OR REPLACE INTO audit VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (request_id, time.time(), client, source, v["decision"], v["score"], v["stage"],
                 v["matched_rule"], v["model_version"], v["latency_ms"],
                 hashlib.sha256(text.encode()).hexdigest(), text if keep else None))
            self.db.commit()

    def audit_text(self, request_id: str) -> str | None:
        row = self.db.execute("SELECT text FROM audit WHERE request_id=?", (request_id,)).fetchone()
        return row["text"] if row else None

    def add_feedback(self, client, request_id, text, label, note) -> int:
        with self.lock:
            cur = self.db.execute(
                "INSERT INTO feedback (ts, client, request_id, text, label, note) VALUES (?,?,?,?,?,?)",
                (time.time(), client, request_id, text, label, note))
            self.db.commit()
            return cur.lastrowid

    def list_feedback(self, status: str | None = None, limit: int = 200) -> list[dict]:
        q, args = "SELECT * FROM feedback", []
        if status:
            q, args = q + " WHERE status=?", [status]
        rows = self.db.execute(q + " ORDER BY id DESC LIMIT ?", [*args, limit]).fetchall()
        return [dict(r) for r in rows]

    def review_feedback(self, fid: int, status: str, label: int | None) -> bool:
        with self.lock:
            cur = self.db.execute(
                "UPDATE feedback SET status=?, label=COALESCE(?, label) WHERE id=?", (status, label, fid))
            self.db.commit()
            return cur.rowcount == 1

    def stats(self, since_s: float = 86400) -> dict:
        rows = self.db.execute("SELECT decision, COUNT(*) n FROM audit WHERE ts>? GROUP BY decision",
                               (time.time() - since_s,)).fetchall()
        pending = self.db.execute("SELECT COUNT(*) FROM feedback WHERE status='pending'").fetchone()[0]
        return {"last_24h": {r["decision"]: r["n"] for r in rows}, "feedback_pending": pending}
