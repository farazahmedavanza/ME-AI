"""SQLite-backed store (single-tenant per user_id string, hackathon / degraded mode)."""
from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from config import Settings

# Precomputed PBKDF2, password: DemoME2026! (see auth.verify_password)
_DEMO_1 = (
    "pbkdf2_sha256$100000$0123456789abcdef0123456789abcdef$"
    "3d3b36baacf1f7b35b926b04c1e851e351fc1886550e00637c8a54cdd5cc472f"
)
_DEMO_2 = (
    "pbkdf2_sha256$100000$fedcba9876543210fedcba9876543210$"
    "e4d7bd3f2d89b1acd2b6a1974f3b87fcc4b10093d9e7f57e88aff946574397e0"
)
# Seeded on every local DB init (upsert fixes wrong hashes from old INSERT OR IGNORE)
LOCAL_DEMO_ACCOUNTS: tuple[tuple[str, str, str], ...] = (
    ("00000000-0000-0000-0000-000000000001", "demo@me-ai.local", _DEMO_1),
    ("00000000-0000-0000-0000-000000000002", "ops@me-ai.local", _DEMO_2),
)
DEMO_LOCAL_EMAIL = "demo@me-ai.local"

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
CREATE TABLE IF NOT EXISTS monitored_endpoints (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  name TEXT NOT NULL,
  url TEXT NOT NULL,
  method TEXT DEFAULT 'GET',
  expected_status_min INTEGER DEFAULT 200,
  expected_status_max INTEGER DEFAULT 299,
  timeout_ms INTEGER DEFAULT 10000,
  enabled INTEGER DEFAULT 1,
  sla_max_latency_ms INTEGER DEFAULT 3000,
  sla_min_uptime_pct REAL DEFAULT 99.0,
  failure_threshold INTEGER DEFAULT 2,
  webhook_url TEXT,
  alert_email TEXT
);
CREATE TABLE IF NOT EXISTS endpoint_check_history (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  endpoint_id TEXT NOT NULL,
  ok INTEGER NOT NULL,
  status_code INTEGER,
  latency_ms REAL,
  error TEXT,
  checked_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS endpoint_monitor_state (
  user_id TEXT NOT NULL,
  endpoint_id TEXT NOT NULL,
  last_ok INTEGER,
  consecutive_failures INTEGER DEFAULT 0,
  last_status_code INTEGER,
  last_latency_ms REAL,
  last_checked_at TEXT,
  last_error TEXT,
  PRIMARY KEY (user_id, endpoint_id)
);
CREATE TABLE IF NOT EXISTS endpoint_monitor_alerts (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  endpoint_id TEXT NOT NULL,
  name TEXT,
  severity TEXT,
  title TEXT,
  description TEXT,
  kind TEXT,
  created_at TEXT NOT NULL,
  resolution_status TEXT DEFAULT 'open',
  resolved_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_ech_user_ep ON endpoint_check_history(user_id, endpoint_id, checked_at);
CREATE INDEX IF NOT EXISTS idx_ema_user ON endpoint_monitor_alerts(user_id, created_at);
CREATE TABLE IF NOT EXISTS users (
  id TEXT PRIMARY KEY,
  email TEXT NOT NULL UNIQUE COLLATE NOCASE,
  password_hash TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
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
                try:
                    c.execute(
                        "ALTER TABLE monitored_endpoints ADD COLUMN alert_email TEXT"
                    )
                except sqlite3.OperationalError:
                    pass
                for uid, em, ph in LOCAL_DEMO_ACCOUNTS:
                    c.execute(
                        """
                        INSERT INTO users (id, email, password_hash) VALUES (?, ?, ?)
                        ON CONFLICT(id) DO UPDATE SET
                          email = excluded.email,
                          password_hash = excluded.password_hash
                        """,
                        (uid, em, ph),
                    )
                c.commit()
            finally:
                c.close()

    def health(self) -> dict[str, Any]:
        return {"store": "local", "ok": True}

    def verify_user_login(self, email: str, password: str) -> str | None:
        from auth import verify_password

        e = (email or "").strip().lower()
        if not e or not password:
            return None
        c = self._connect()
        try:
            row = c.execute(
                "SELECT id, password_hash FROM users WHERE lower(email) = ?",
                (e,),
            ).fetchone()
            if not row:
                return None
            uid, ph = str(row[0]), str(row[1])
            if verify_password(password, ph):
                return uid
        finally:
            c.close()
        return None

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

    # --- External HTTP endpoint monitor (configure endpoints / live checks) ---

    def _seed_monitors_if_empty(self, user_id: str) -> None:
        from endpoint_monitor import DEFAULT_MONITORED

        with self._lock:
            c = self._connect()
            try:
                n = c.execute(
                    "SELECT COUNT(*) FROM monitored_endpoints WHERE user_id = ?",
                    (user_id,),
                ).fetchone()[0]
                if n > 0:
                    return
                for spec in DEFAULT_MONITORED:
                    eid = new_id()
                    c.execute(
                        "INSERT INTO monitored_endpoints (id, user_id, name, url, method, expected_status_min, "
                        "expected_status_max, timeout_ms, enabled, sla_max_latency_ms, sla_min_uptime_pct, "
                        "failure_threshold, webhook_url, alert_email) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (
                            eid,
                            user_id,
                            spec["name"],
                            spec["url"],
                            spec.get("method") or "GET",
                            int(spec.get("expected_status_min", 200)),
                            int(spec.get("expected_status_max", 299)),
                            int(spec.get("timeout_ms", 10_000)),
                            int(spec.get("enabled", 1)),
                            int(spec.get("sla_max_latency_ms", 3000)),
                            float(spec.get("sla_min_uptime_pct", 99.0)),
                            int(spec.get("failure_threshold", 2)),
                            spec.get("webhook_url"),
                            spec.get("alert_email"),
                        ),
                    )
                c.commit()
            finally:
                c.close()

    def list_distinct_monitored_endpoint_user_ids(self) -> list[str]:
        c = self._connect()
        try:
            cur = c.execute(
                "SELECT DISTINCT user_id FROM monitored_endpoints ORDER BY user_id"
            )
            return [str(r[0]) for r in cur.fetchall() if r[0]]
        finally:
            c.close()

    def insert_monitored_endpoint(
        self, user_id: str, fields: dict[str, Any]
    ) -> str:
        eid = new_id()
        with self._lock:
            c = self._connect()
            try:
                c.execute(
                    "INSERT INTO monitored_endpoints (id, user_id, name, url, method, "
                    "expected_status_min, expected_status_max, timeout_ms, enabled, "
                    "sla_max_latency_ms, sla_min_uptime_pct, failure_threshold, webhook_url, alert_email) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        eid,
                        user_id,
                        fields["name"],
                        fields["url"],
                        fields.get("method") or "GET",
                        int(fields.get("expected_status_min", 200)),
                        int(fields.get("expected_status_max", 299)),
                        int(fields.get("timeout_ms", 10_000)),
                        int(fields.get("enabled", 1)),
                        int(fields.get("sla_max_latency_ms", 3000)),
                        float(fields.get("sla_min_uptime_pct", 99.0)),
                        int(fields.get("failure_threshold", 2)),
                        fields.get("webhook_url"),
                        fields.get("alert_email"),
                    ),
                )
                c.commit()
            finally:
                c.close()
        return eid

    def delete_monitored_endpoint(self, user_id: str, endpoint_id: str) -> bool:
        with self._lock:
            c = self._connect()
            try:
                cur = c.execute(
                    "SELECT 1 FROM monitored_endpoints WHERE id = ? AND user_id = ?",
                    (endpoint_id, user_id),
                )
                if not cur.fetchone():
                    return False
                c.execute(
                    "DELETE FROM endpoint_check_history WHERE user_id = ? AND endpoint_id = ?",
                    (user_id, endpoint_id),
                )
                c.execute(
                    "DELETE FROM endpoint_monitor_state WHERE user_id = ? AND endpoint_id = ?",
                    (user_id, endpoint_id),
                )
                c.execute(
                    "DELETE FROM endpoint_monitor_alerts WHERE user_id = ? AND endpoint_id = ?",
                    (user_id, endpoint_id),
                )
                c.execute(
                    "DELETE FROM monitored_endpoints WHERE id = ? AND user_id = ?",
                    (endpoint_id, user_id),
                )
                c.commit()
                return True
            finally:
                c.close()

    def list_monitored_endpoints(self, user_id: str) -> list[dict[str, Any]]:
        self._seed_monitors_if_empty(user_id)
        c = self._connect()
        try:
            cur = c.execute(
                "SELECT id, name, url, method, expected_status_min, expected_status_max, timeout_ms, "
                "enabled, sla_max_latency_ms, sla_min_uptime_pct, failure_threshold, webhook_url, alert_email "
                "FROM monitored_endpoints WHERE user_id = ? ORDER BY name",
                (user_id,),
            )
            return [dict(r) for r in cur.fetchall()]
        finally:
            c.close()

    def update_monitored_endpoint(
        self, user_id: str, endpoint_id: str, fields: dict[str, Any]
    ) -> bool:
        if not fields:
            return True
        allowed = {
            "name",
            "url",
            "method",
            "expected_status_min",
            "expected_status_max",
            "timeout_ms",
            "enabled",
            "sla_max_latency_ms",
            "sla_min_uptime_pct",
            "failure_threshold",
            "webhook_url",
            "alert_email",
        }
        sets: list[str] = []
        vals: list[Any] = []
        for k, v in fields.items():
            if k not in allowed:
                continue
            sets.append(f"{k} = ?")
            vals.append(v)
        if not sets:
            return True
        vals.extend([endpoint_id, user_id])
        with self._lock:
            c = self._connect()
            try:
                r = c.execute(
                    f"UPDATE monitored_endpoints SET {', '.join(sets)} "
                    f"WHERE id = ? AND user_id = ?",
                    vals,
                )
                c.commit()
                return r.rowcount > 0
            finally:
                c.close()

    def get_monitor_state(
        self, user_id: str, endpoint_id: str
    ) -> dict[str, Any] | None:
        c = self._connect()
        try:
            r = c.execute(
                "SELECT last_ok, consecutive_failures, last_status_code, last_latency_ms, last_checked_at, last_error "
                "FROM endpoint_monitor_state WHERE user_id = ? AND endpoint_id = ?",
                (user_id, endpoint_id),
            ).fetchone()
            if not r:
                return None
            return dict(r)
        finally:
            c.close()

    def upsert_monitor_state(
        self,
        user_id: str,
        endpoint_id: str,
        last_ok: int,
        consecutive_failures: int,
        last_status_code: int | None,
        last_latency_ms: float | None,
        last_checked_at: str,
        last_error: str | None,
    ) -> None:
        with self._lock:
            c = self._connect()
            try:
                c.execute(
                    "INSERT INTO endpoint_monitor_state (user_id, endpoint_id, last_ok, consecutive_failures, "
                    "last_status_code, last_latency_ms, last_checked_at, last_error) VALUES (?,?,?,?,?,?,?,?) "
                    "ON CONFLICT(user_id, endpoint_id) DO UPDATE SET last_ok=excluded.last_ok, "
                    "consecutive_failures=excluded.consecutive_failures, last_status_code=excluded.last_status_code, "
                    "last_latency_ms=excluded.last_latency_ms, last_checked_at=excluded.last_checked_at, "
                    "last_error=excluded.last_error",
                    (
                        user_id,
                        endpoint_id,
                        last_ok,
                        consecutive_failures,
                        last_status_code,
                        last_latency_ms,
                        last_checked_at,
                        last_error,
                    ),
                )
                c.commit()
            finally:
                c.close()

    def insert_endpoint_check(
        self,
        user_id: str,
        endpoint_id: str,
        ok: int,
        status_code: int | None,
        latency_ms: float | None,
        error: str | None,
        checked_at: str,
    ) -> str:
        rid = new_id()
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=26)).isoformat()
        with self._lock:
            c = self._connect()
            try:
                c.execute(
                    "INSERT INTO endpoint_check_history (id, user_id, endpoint_id, ok, status_code, "
                    "latency_ms, error, checked_at) VALUES (?,?,?,?,?,?,?,?)",
                    (
                        rid,
                        user_id,
                        endpoint_id,
                        ok,
                        status_code,
                        latency_ms,
                        error,
                        checked_at,
                    ),
                )
                c.execute(
                    "DELETE FROM endpoint_check_history WHERE user_id = ? AND checked_at < ?",
                    (user_id, cutoff),
                )
                c.commit()
            finally:
                c.close()
        return rid

    def recent_endpoint_history(
        self, user_id: str, endpoint_id: str, limit: int
    ) -> list[dict[str, Any]]:
        c = self._connect()
        try:
            cur = c.execute(
                "SELECT ok, status_code, latency_ms, error, checked_at FROM endpoint_check_history "
                "WHERE user_id = ? AND endpoint_id = ? ORDER BY checked_at DESC LIMIT ?",
                (user_id, endpoint_id, limit),
            )
            return [dict(r) for r in cur.fetchall()]
        finally:
            c.close()

    def history_for_uptime(
        self, user_id: str, endpoint_id: str, since_iso: str
    ) -> list[dict[str, Any]]:
        c = self._connect()
        try:
            cur = c.execute(
                "SELECT ok, checked_at FROM endpoint_check_history WHERE user_id = ? AND endpoint_id = ? "
                "AND checked_at >= ? ORDER BY checked_at ASC",
                (user_id, endpoint_id, since_iso),
            )
            return [dict(r) for r in cur.fetchall()]
        finally:
            c.close()

    def count_open_monitor_alerts(
        self, user_id: str, endpoint_id: str
    ) -> int:
        c = self._connect()
        try:
            r = c.execute(
                "SELECT COUNT(*) FROM endpoint_monitor_alerts WHERE user_id = ? AND endpoint_id = ? "
                "AND resolution_status = 'open'",
                (user_id, endpoint_id),
            ).fetchone()
            return int(r[0]) if r else 0
        finally:
            c.close()

    def list_endpoint_monitor_alerts(
        self, user_id: str, limit: int = 100
    ) -> list[dict[str, Any]]:
        c = self._connect()
        try:
            cur = c.execute(
                "SELECT id, endpoint_id, name, severity, title, description, kind, created_at, "
                "resolution_status, resolved_at FROM endpoint_monitor_alerts WHERE user_id = ? "
                "ORDER BY created_at DESC LIMIT ?",
                (user_id, limit),
            )
            return [dict(r) for r in cur.fetchall()]
        finally:
            c.close()

    def insert_endpoint_monitor_alert(
        self,
        user_id: str,
        endpoint_id: str,
        name: str,
        severity: str,
        title: str,
        description: str,
        kind: str,
    ) -> str:
        aid = new_id()
        now = datetime.now(timezone.utc).isoformat()
        with self._lock:
            c = self._connect()
            try:
                c.execute(
                    "INSERT INTO endpoint_monitor_alerts (id, user_id, endpoint_id, name, severity, title, "
                    "description, kind, created_at, resolution_status) VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (
                        aid,
                        user_id,
                        endpoint_id,
                        name,
                        severity,
                        title,
                        description,
                        kind,
                        now,
                        "open",
                    ),
                )
                c.commit()
            finally:
                c.close()
        return aid

    def update_endpoint_monitor_alert(
        self, user_id: str, alert_id: str, fields: dict[str, Any]
    ) -> bool:
        if "resolution_status" in fields and fields["resolution_status"] == "resolved":
            if "resolved_at" not in fields:
                fields = {**fields, "resolved_at": datetime.now(timezone.utc).isoformat()}
        sets: list[str] = []
        vals: list[Any] = []
        for k in ("resolution_status", "resolved_at"):
            if k in fields:
                sets.append(f"{k} = ?")
                vals.append(fields[k])
        if not sets:
            return False
        vals.extend([alert_id, user_id])
        with self._lock:
            c = self._connect()
            try:
                cur = c.execute(
                    f"UPDATE endpoint_monitor_alerts SET {', '.join(sets)} WHERE id = ? AND user_id = ?",
                    vals,
                )
                c.commit()
                return cur.rowcount > 0
            finally:
                c.close()