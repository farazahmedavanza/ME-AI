"""Storage backends: local SQLite and Supabase."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from config import Settings

log = logging.getLogger(__name__)

# Set True when we intended Supabase but fell back to SQLite (exposed in /api/health).
using_store_fallback: bool = False


@runtime_checkable
class Store(Protocol):
    def health(self) -> dict[str, Any]: ...
    def list_sessions(self, user_id: str) -> list[dict[str, Any]]: ...
    def get_session_logs(self, user_id: str, session_id: str) -> list[dict[str, Any]]: ...
    def get_analysis(self, user_id: str, session_id: str) -> dict[str, Any] | None: ...
    def get_alerts(self, user_id: str, session_id: str) -> list[dict[str, Any]]: ...
    def upload_logs(
        self, user_id: str, filename: str, log_rows: list[dict[str, Any]]
    ) -> str: ...
    def save_analysis(
        self,
        user_id: str,
        session_id: str,
        health_summary: dict,
        sla_status: dict,
        incident_slot: dict | None = None,
    ) -> None: ...
    def save_alerts(self, user_id: str, session_id: str, alerts: list[dict[str, Any]]) -> list[str]: ...
    def update_alert(
        self, user_id: str, alert_id: str, fields: dict[str, Any]
    ) -> bool: ...
    def save_incident_report(
        self, user_id: str, session_id: str, key: str, text: str
    ) -> None: ...
    def get_incident_reports(
        self, user_id: str, session_id: str
    ) -> dict[str, str]: ...


def get_store(settings: "Settings | None" = None) -> Any:
    from config import get_settings

    global using_store_fallback
    s = settings or get_settings()
    using_store_fallback = False

    if s.force_local_store:
        from store.local_store import LocalStore

        return LocalStore(s)

    if s.use_supabase:
        if s.store_auto_fallback:
            try:
                from store.supabase_store import SupabaseStore

                st = SupabaseStore(s)
                st.ping()
                return st
            except Exception as e:
                log.warning("Supabase unavailable, using local SQLite: %s", e)
                using_store_fallback = True
                from store.local_store import LocalStore

                return LocalStore(s)
        from store.supabase_store import SupabaseStore

        return SupabaseStore(s)
    from store.local_store import LocalStore

    return LocalStore(s)
