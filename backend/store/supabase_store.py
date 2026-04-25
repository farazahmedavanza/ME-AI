"""Supabase Postgres via service role (server-side). Optional if env configured."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from config import Settings


def new_id() -> str:
    return str(uuid4())


class SupabaseStore:
    def __init__(self, settings: Settings):
        from supabase import create_client  # type: ignore

        self._client = create_client(settings.supabase_url, settings.supabase_service_key)
        self._settings = settings

    def ping(self) -> None:
        """Lightweight call to verify DB connectivity; raises on failure."""
        self._client.table("upload_sessions").select("id").limit(1).execute()

    def health(self) -> dict[str, Any]:
        return {"store": "supabase", "ok": True}

    def list_sessions(self, user_id: str) -> list[dict[str, Any]]:
        r = (
            self._client.table("upload_sessions")
            .select("id, filename, uploaded_at, log_count, status")
            .eq("user_id", user_id)
            .order("uploaded_at", desc=True)
            .execute()
        )
        return list(r.data or [])

    def get_session_logs(self, user_id: str, session_id: str) -> list[dict[str, Any]]:
        r = (
            self._client.table("api_logs")
            .select("raw_json, log_timestamp, endpoint, method, status_code, response_time_ms, error_message, service, trace_id, id")
            .eq("user_id", user_id)
            .eq("session_id", session_id)
            .order("log_timestamp", desc=False)
            .execute()
        )
        out: list[dict[str, Any]] = []
        for row in r.data or []:
            raw = row.get("raw_json")
            if raw:
                try:
                    out.append(json.loads(raw))
                    continue
                except Exception:
                    pass
            # fallback: rebuild from columns if raw not stored
            out.append(
                {
                    "id": row.get("id"),
                    "timestamp": row.get("timestamp") or row.get("log_timestamp"),
                    "endpoint": row.get("endpoint"),
                    "method": row.get("method"),
                    "status_code": row.get("status_code"),
                    "response_time_ms": row.get("response_time_ms"),
                    "error_message": row.get("error_message"),
                    "service": row.get("service"),
                    "trace_id": row.get("trace_id"),
                }
            )
        return out

    def get_analysis(self, user_id: str, session_id: str) -> dict[str, Any] | None:
        r = (
            self._client.table("analysis_results")
            .select("health_summary, sla_status, incident_reports")
            .eq("user_id", user_id)
            .eq("session_id", session_id)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        if not r.data:
            return None
        row = r.data[0]
        return {
            "health_summary": row.get("health_summary") or {},
            "sla_status": row.get("sla_status") or {},
            "incident_reports": row.get("incident_reports") or {},
        }

    def get_alerts(self, user_id: str, session_id: str) -> list[dict[str, Any]]:
        r = (
            self._client.table("alerts")
            .select(
                "id, created_at, endpoint, severity, description, resolution_status, resolved_at, assignee, title"
            )
            .eq("user_id", user_id)
            .eq("session_id", session_id)
            .order("created_at", desc=True)
            .execute()
        )
        return list(r.data or [])

    def upload_logs(
        self, user_id: str, filename: str, log_rows: list[dict[str, Any]]
    ) -> str:
        sid = new_id()
        now = datetime.now(timezone.utc).isoformat()
        self._client.table("upload_sessions").insert(
            {
                "id": sid,
                "user_id": user_id,
                "filename": filename,
                "uploaded_at": now,
                "log_count": len(log_rows),
                "status": "completed",
            }
        ).execute()
        batch: list[dict[str, Any]] = []
        for row in log_rows:
            rid = str(row.get("id") or new_id())
            batch.append(
                {
                    "id": rid,
                    "session_id": sid,
                    "user_id": user_id,
                    "log_timestamp": str(row.get("timestamp")),
                    "endpoint": str(row.get("endpoint") or ""),
                    "method": str(row.get("method") or "GET"),
                    "status_code": int(row.get("status_code") or 0),
                    "response_time_ms": float(row.get("response_time_ms") or 0),
                    "error_message": row.get("error_message"),
                    "service": str(row.get("service") or ""),
                    "trace_id": str(row.get("trace_id") or ""),
                    "raw_json": json.dumps(row, default=str),
                }
            )
            if len(batch) >= 200:
                self._client.table("api_logs").insert(batch).execute()
                batch = []
        if batch:
            self._client.table("api_logs").insert(batch).execute()
        return sid

    def save_analysis(
        self,
        user_id: str,
        session_id: str,
        health_summary: dict,
        sla_status: dict,
        incident_slot: dict | None = None,
    ) -> None:
        prev = self.get_analysis(user_id, session_id) or {}
        inc: dict = {}
        pinc = prev.get("incident_reports")
        if isinstance(pinc, dict):
            inc = {**pinc}
        if incident_slot:
            inc = {**inc, **incident_slot}
        self._client.table("analysis_results").insert(
            {
                "id": new_id(),
                "session_id": session_id,
                "user_id": user_id,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "health_summary": health_summary,
                "sla_status": sla_status,
                "incident_reports": inc,
            }
        ).execute()

    def save_alerts(
        self, user_id: str, session_id: str, alerts: list[dict[str, Any]]
    ) -> list[str]:
        ids: list[str] = []
        now = datetime.now(timezone.utc).isoformat()
        for a in alerts:
            aid = str(a.get("id") or new_id())
            ids.append(aid)
            self._client.table("alerts").insert(
                {
                    "id": aid,
                    "session_id": session_id,
                    "user_id": user_id,
                    "created_at": a.get("created_at") or now,
                    "endpoint": a.get("endpoint") or "",
                    "severity": a.get("severity") or "medium",
                    "description": a.get("description") or "",
                    "resolution_status": a.get("resolution_status") or "open",
                    "resolved_at": a.get("resolved_at"),
                    "assignee": a.get("assignee") or "",
                    "title": a.get("title") or "",
                }
            ).execute()
        return ids

    def update_alert(
        self, user_id: str, alert_id: str, fields: dict[str, Any]
    ) -> bool:
        r = (
            self._client.table("alerts")
            .update(
                {k: v for k, v in fields.items() if v is not None and k in ("resolution_status", "assignee", "resolved_at")}
            )
            .eq("id", alert_id)
            .eq("user_id", user_id)
            .execute()
        )
        return bool(r.data)

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

    # --- External HTTP endpoint monitor ---

    def list_distinct_monitored_endpoint_user_ids(self) -> list[str]:
        r = (
            self._client.table("monitored_endpoints")
            .select("user_id")
            .execute()
        )
        seen: set[str] = set()
        out: list[str] = []
        for row in r.data or []:
            uid = str(row.get("user_id") or "")
            if uid and uid not in seen:
                seen.add(uid)
                out.append(uid)
        out.sort()
        return out

    def insert_monitored_endpoint(
        self, user_id: str, fields: dict[str, Any]
    ) -> str:
        eid = new_id()
        en = fields.get("enabled", True)
        enabled_b = en if isinstance(en, bool) else bool(int(en))
        self._client.table("monitored_endpoints").insert(
            {
                "id": eid,
                "user_id": user_id,
                "name": fields["name"],
                "url": fields["url"],
                "method": fields.get("method") or "GET",
                "expected_status_min": int(fields.get("expected_status_min", 200)),
                "expected_status_max": int(fields.get("expected_status_max", 299)),
                "timeout_ms": int(fields.get("timeout_ms", 10_000)),
                "enabled": enabled_b,
                "sla_max_latency_ms": int(fields.get("sla_max_latency_ms", 3000)),
                "sla_min_uptime_pct": float(fields.get("sla_min_uptime_pct", 99.0)),
                "failure_threshold": int(fields.get("failure_threshold", 2)),
                "webhook_url": fields.get("webhook_url"),
                "alert_email": fields.get("alert_email"),
            }
        ).execute()
        return eid

    def delete_monitored_endpoint(self, user_id: str, endpoint_id: str) -> bool:
        chk = (
            self._client.table("monitored_endpoints")
            .select("id")
            .eq("id", endpoint_id)
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )
        if not chk.data:
            return False
        self._client.table("monitored_endpoints").delete().eq("id", endpoint_id).eq(
            "user_id", user_id
        ).execute()
        return True

    def _seed_monitors_if_empty(self, user_id: str) -> None:
        from endpoint_monitor import DEFAULT_MONITORED

        r = (
            self._client.table("monitored_endpoints")
            .select("id")
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )
        if r.data:
            return
        for spec in DEFAULT_MONITORED:
            self._client.table("monitored_endpoints").insert(
                {
                    "id": new_id(),
                    "user_id": user_id,
                    "name": spec["name"],
                    "url": spec["url"],
                    "method": spec.get("method") or "GET",
                    "expected_status_min": int(spec.get("expected_status_min", 200)),
                    "expected_status_max": int(spec.get("expected_status_max", 299)),
                    "timeout_ms": int(spec.get("timeout_ms", 10_000)),
                    "enabled": bool(int(spec.get("enabled", 1))),
                    "sla_max_latency_ms": int(spec.get("sla_max_latency_ms", 3000)),
                    "sla_min_uptime_pct": float(spec.get("sla_min_uptime_pct", 99.0)),
                    "failure_threshold": int(spec.get("failure_threshold", 2)),
                    "webhook_url": spec.get("webhook_url"),
                    "alert_email": spec.get("alert_email"),
                }
            ).execute()

    def list_monitored_endpoints(self, user_id: str) -> list[dict[str, Any]]:
        self._seed_monitors_if_empty(user_id)
        r = (
            self._client.table("monitored_endpoints")
            .select(
                "id, name, url, method, expected_status_min, expected_status_max, "
                "timeout_ms, enabled, sla_max_latency_ms, sla_min_uptime_pct, failure_threshold, webhook_url, alert_email"
            )
            .eq("user_id", user_id)
            .order("name", desc=False)
            .execute()
        )
        return list(r.data or [])

    def update_monitored_endpoint(
        self, user_id: str, endpoint_id: str, fields: dict[str, Any]
    ) -> bool:
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
        payload = {k: v for k, v in fields.items() if k in allowed}
        if "enabled" in payload and payload["enabled"] is not None:
            e = payload["enabled"]
            payload["enabled"] = e if isinstance(e, bool) else bool(int(e))
        if not payload:
            return True
        r = (
            self._client.table("monitored_endpoints")
            .update(payload)
            .eq("id", endpoint_id)
            .eq("user_id", user_id)
            .execute()
        )
        return bool(r.data)

    def get_monitor_state(
        self, user_id: str, endpoint_id: str
    ) -> dict[str, Any] | None:
        r = (
            self._client.table("endpoint_monitor_state")
            .select(
                "last_ok, consecutive_failures, last_status_code, last_latency_ms, last_checked_at, last_error"
            )
            .eq("user_id", user_id)
            .eq("endpoint_id", endpoint_id)
            .limit(1)
            .execute()
        )
        if not r.data:
            return None
        return r.data[0]

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
        row = {
            "user_id": user_id,
            "endpoint_id": endpoint_id,
            "last_ok": last_ok,
            "consecutive_failures": consecutive_failures,
            "last_status_code": last_status_code,
            "last_latency_ms": last_latency_ms,
            "last_checked_at": last_checked_at,
            "last_error": last_error,
        }
        self._client.table("endpoint_monitor_state").upsert(
            row, on_conflict="user_id,endpoint_id"
        ).execute()  # requires UNIQUE(user_id, endpoint_id) in DB

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
        self._client.table("endpoint_check_history").insert(
            {
                "id": rid,
                "user_id": user_id,
                "endpoint_id": endpoint_id,
                "ok": bool(ok),
                "status_code": status_code,
                "latency_ms": latency_ms,
                "error": error,
                "checked_at": checked_at,
            }
        ).execute()
        self._client.table("endpoint_check_history").delete().eq("user_id", user_id).lt(
            "checked_at", cutoff
        ).execute()
        return rid

    def recent_endpoint_history(
        self, user_id: str, endpoint_id: str, limit: int
    ) -> list[dict[str, Any]]:
        r = (
            self._client.table("endpoint_check_history")
            .select("ok, status_code, latency_ms, error, checked_at")
            .eq("user_id", user_id)
            .eq("endpoint_id", endpoint_id)
            .order("checked_at", desc=True)
            .limit(limit)
            .execute()
        )
        return list(r.data or [])

    def history_for_uptime(
        self, user_id: str, endpoint_id: str, since_iso: str
    ) -> list[dict[str, Any]]:
        r = (
            self._client.table("endpoint_check_history")
            .select("ok, checked_at")
            .eq("user_id", user_id)
            .eq("endpoint_id", endpoint_id)
            .gte("checked_at", since_iso)
            .order("checked_at", desc=False)
            .execute()
        )
        return list(r.data or [])

    def count_open_monitor_alerts(
        self, user_id: str, endpoint_id: str
    ) -> int:
        r = (
            self._client.table("endpoint_monitor_alerts")
            .select("id")
            .eq("user_id", user_id)
            .eq("endpoint_id", endpoint_id)
            .eq("resolution_status", "open")
            .execute()
        )
        return len(r.data or [])

    def list_endpoint_monitor_alerts(
        self, user_id: str, limit: int = 100
    ) -> list[dict[str, Any]]:
        r = (
            self._client.table("endpoint_monitor_alerts")
            .select(
                "id, endpoint_id, name, severity, title, description, kind, created_at, "
                "resolution_status, resolved_at"
            )
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return list(r.data or [])

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
        self._client.table("endpoint_monitor_alerts").insert(
            {
                "id": aid,
                "user_id": user_id,
                "endpoint_id": endpoint_id,
                "name": name,
                "severity": severity,
                "title": title,
                "description": description,
                "kind": kind,
                "created_at": now,
                "resolution_status": "open",
            }
        ).execute()
        return aid

    def update_endpoint_monitor_alert(
        self, user_id: str, alert_id: str, fields: dict[str, Any]
    ) -> bool:
        f = {k: v for k, v in fields.items() if k in ("resolution_status", "resolved_at")}
        if "resolution_status" in f and f["resolution_status"] == "resolved" and "resolved_at" not in f:
            f["resolved_at"] = datetime.now(timezone.utc).isoformat()
        if not f:
            return False
        r = (
            self._client.table("endpoint_monitor_alerts")
            .update(f)
            .eq("id", alert_id)
            .eq("user_id", user_id)
            .execute()
        )
        return bool(r.data)
