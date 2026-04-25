"""Supabase Postgres via service role (server-side). Optional if env configured."""
from __future__ import annotations

import json
from datetime import datetime, timezone
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
