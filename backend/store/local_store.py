"""SQLite-backed store (single-tenant per user_id string, hackathon / degraded mode)."""
from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from config import Settings


def new_id() -> str:
    return str(uuid4())

SCHEMA = """
CREATE TABLE IF NOT EXISTS upload_sessions (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  filename TEXT NOT NULL,
  uploaded_at TEXT NOT NULL,
  log_count INTEGER,
  status TEXT DEFAULT 'completed'
);
CREATE TABLE IF NOT EXISTS api_logs (
  id TEXT PRIMARY KEY,
  session_id TEXT NOT NULL,
  user_id TEXT NOT NULL,
  log_timestamp TEXT,
  endpoint TEXT,
  method TEXT,
  status_code INTEGER,
  response_time_ms REAL,
  error_message TEXT,
  service TEXT,
  trace_id TEXT,
  raw_json TEXT
);
CREATE TABLE IF NOT EXISTS analysis_results (
  id TEXT PRIMARY KEY,
  session_id TEXT NOT NULL,
  user_id TEXT NOT NULL,
  created_at TEXT NOT NULL,
  health_summary TEXT,
  sla_status TEXT,
  incident_reports TEXT
);
CREATE TABLE IF NOT EXISTS alerts (
  id TEXT PRIMARY KEY,
  session_id TEXT NOT NULL,
  user_id TEXT NOT NULL,
  created_at TEXT NOT NULL,
  endpoint TEXT,
  severity TEXT,
  description TEXT,
  resolution_status TEXT DEFAULT 'open',
  resolved_at TEXT,
  assignee TEXT,
  title TEXT
);
CREATE INDEX IF NOT EXISTS idx_logs_session ON api_logs(session_id);
CREATE INDEX IF NOT EXISTS idx_alerts_session ON alerts(session_id);
"""


class LocalStore:
    def __init__(self, settings: Settings):
        self._settings = settings
        self._db = Path(settings.local_db_path)
        self._lock = threading.Lock()
        self._init_db()
        self._seed_demo_if_empty()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        self._db.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            c = self._connect()
            try:
                c.executescript(SCHEMA)
                c.commit()
            finally:
                c.close()

    def health(self) -> dict[str, Any]:
        return {"store": "local", "ok": True}

    def _seed_demo_if_empty(self) -> None:
        with self._lock:
            c = self._connect()
            try:
                n = c.execute("SELECT COUNT(*) FROM upload_sessions").fetchone()[0]
                if n > 0:
                    return
            finally:
                c.close()
        data_path = Path(__file__).resolve().parent.parent / "data" / "api_logs.json"
        if not data_path.is_file():
            return
        payload = json.loads(data_path.read_text(encoding="utf-8"))
        uid = "00000000-0000-0000-0000-000000000001"
        self.upload_logs(uid, "api_logs.json", payload)

    def list_sessions(self, user_id: str) -> list[dict[str, Any]]:
        c = self._connect()
        try:
            cur = c.execute(
                "SELECT id, filename, uploaded_at, log_count, status FROM upload_sessions "
                "WHERE user_id = ? ORDER BY uploaded_at DESC",
                (user_id,),
            )
            return [dict(r) for r in cur.fetchall()]
        finally:
            c.close()

    def get_session_logs(self, user_id: str, session_id: str) -> list[dict[str, Any]]:
        c = self._connect()
        try:
            cur = c.execute(
                "SELECT raw_json FROM api_logs WHERE user_id = ? AND session_id = ? ORDER BY log_timestamp",
                (user_id, session_id),
            )
            out = []
            for r in cur.fetchall():
                if r[0]:
                    out.append(json.loads(r[0]))
            return out
        finally:
            c.close()

    def get_analysis(self, user_id: str, session_id: str) -> dict[str, Any] | None:
        c = self._connect()
        try:
            cur = c.execute(
                "SELECT health_summary, sla_status, incident_reports FROM analysis_results "
                "WHERE user_id = ? AND session_id = ? ORDER BY created_at DESC LIMIT 1",
                (user_id, session_id),
            )
            row = cur.fetchone()
            if not row:
                return None
            h, s, i = row[0] or "{}", row[1] or "{}", row[2] or "{}"
            return {
                "health_summary": json.loads(h),
                "sla_status": json.loads(s),
                "incident_reports": json.loads(i),
            }
        finally:
            c.close()

    def get_alerts(self, user_id: str, session_id: str) -> list[dict[str, Any]]:
        c = self._connect()
        try:
            cur = c.execute(
                "SELECT id, created_at, endpoint, severity, description, resolution_status, resolved_at, assignee, title "
                "FROM alerts WHERE user_id = ? AND session_id = ? ORDER BY created_at DESC",
                (user_id, session_id),
            )
            return [dict(r) for r in cur.fetchall()]
        finally:
            c.close()

    def upload_logs(
        self, user_id: str, filename: str, log_rows: list[dict[str, Any]]
    ) -> str:
        session_id = new_id()
        now = datetime.now(timezone.utc).isoformat()
        with self._lock:
            c = self._connect()
            try:
                c.execute(
                    "INSERT INTO upload_sessions (id, user_id, filename, uploaded_at, log_count, status) VALUES (?,?,?,?,?,?)",
                    (session_id, user_id, filename, now, len(log_rows), "completed"),
                )
                for row in log_rows:
                    lid = str(row.get("id") or new_id())
                    raw = json.dumps(row, default=str)
                    c.execute(
                        "INSERT INTO api_logs (id, session_id, user_id, log_timestamp, endpoint, method, status_code, "
                        "response_time_ms, error_message, service, trace_id, raw_json) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                        (
                            lid,
                            session_id,
                            user_id,
                            str(row.get("timestamp")),
                            str(row.get("endpoint") or ""),
                            str(row.get("method") or "GET"),
                            int(row.get("status_code") or 0),
                            float(row.get("response_time_ms") or 0),
                            row.get("error_message"),
                            str(row.get("service") or ""),
                            str(row.get("trace_id") or ""),
                            raw,
                        ),
                    )
                c.commit()
            finally:
                c.close()
        return session_id

    def save_analysis(
        self,
        user_id: str,
        session_id: str,
        health_summary: dict,
        sla_status: dict,
        incident_slot: dict | None = None,
    ) -> None:
        prev = self.get_analysis(user_id, session_id) or {}
        inc = (prev.get("incident_reports") or {}) if isinstance(prev.get("incident_reports"), dict) else {}
        if incident_slot:
            inc = {**inc, **incident_slot}
        now = datetime.now(timezone.utc).isoformat()
        rid = new_id()
        with self._lock:
            c = self._connect()
            try:
                c.execute(
                    "INSERT INTO analysis_results (id, session_id, user_id, created_at, health_summary, sla_status, incident_reports) "
                    "VALUES (?,?,?,?,?,?,?)",
                    (
                        rid,
                        session_id,
                        user_id,
                        now,
                        json.dumps(health_summary, default=str),
                        json.dumps(sla_status, default=str),
                        json.dumps(inc, default=str),
                    ),
                )
                c.commit()
            finally:
                c.close()

    def save_alerts(
        self, user_id: str, session_id: str, alerts: list[dict[str, Any]]
    ) -> list[str]:
        ids: list[str] = []
        now = datetime.now(timezone.utc).isoformat()
        with self._lock:
            c = self._connect()
            try:
                for a in alerts:
                    aid = str(a.get("id") or new_id())
                    ids.append(aid)
                    c.execute(
                        "INSERT INTO alerts (id, session_id, user_id, created_at, endpoint, severity, description, resolution_status, resolved_at, assignee, title) "
                        "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                        (
                            aid,
                            session_id,
                            user_id,
                            a.get("created_at") or now,
                            a.get("endpoint") or "",
                            a.get("severity") or "medium",
                            a.get("description") or "",
                            a.get("resolution_status") or "open",
                            a.get("resolved_at"),
                            a.get("assignee") or "",
                            a.get("title") or "",
                        ),
                    )
                c.commit()
            finally:
                c.close()
        return ids

    def update_alert(
        self, user_id: str, alert_id: str, fields: dict[str, Any]
    ) -> bool:
        c = self._connect()
        try:
            cur = c.execute(
                "SELECT 1 FROM alerts WHERE id = ? AND user_id = ?",
                (alert_id, user_id),
            )
            if not cur.fetchone():
                return False
            if "resolution_status" in fields:
                c.execute(
                    "UPDATE alerts SET resolution_status = ? WHERE id = ? AND user_id = ?",
                    (fields["resolution_status"], alert_id, user_id),
                )
            if "assignee" in fields:
                c.execute(
                    "UPDATE alerts SET assignee = ? WHERE id = ? AND user_id = ?",
                    (fields["assignee"], alert_id, user_id),
                )
            c.commit()
            return True
        finally:
            c.close()

    def save_incident_report(
        self, user_id: str, session_id: str, key: str, text: str
    ) -> None:
        prev = self.get_analysis(user_id, session_id) or {}
        self.save_analysis(
            user_id,
            session_id,
            prev.get("health_summary") or {},
            prev.get("sla_status") or {},
            {key: text},
        )

    def get_incident_reports(
        self, user_id: str, session_id: str
    ) -> dict[str, str]:
        a = self.get_analysis(user_id, session_id)
        if not a:
            return {}
        r = a.get("incident_reports")
        if isinstance(r, dict):
            return {k: str(v) for k, v in r.items() if isinstance(v, str)}
        return {}