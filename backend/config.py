"""Application settings from environment."""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


def _b(key: str, default: bool = False) -> bool:
    v = os.getenv(key)
    if v is None:
        return default
    return v.lower() in ("1", "true", "yes", "on")


def _p(key: str, default: Path) -> Path:
    v = os.getenv(key)
    return Path(v) if v else default


class Settings(BaseModel):
    app_name: str = "API Health & SLA Monitor"
    version: str = "0.1.0"

    openrouter_api_key: str = ""
    openrouter_model: str = "meta-llama/llama-3.1-8b-instruct:free"
    openrouter_timeout_s: float = 12.0

    supabase_url: str = ""
    supabase_service_key: str = ""
    supabase_jwt_secret: str = ""

    # USE_DEGRADED_MODE env — force SQLite (see force_local_store)
    use_local_store: bool = False
    use_degraded_mode: bool = False
    # If Supabase is configured, try it first; on failure use LocalStore
    store_auto_fallback: bool = True
    demo_mode: bool = False
    demo_bearer_token: str = ""
    jwt_secret: str = "dev-local-jwt-secret-change-me"

    local_db_path: Path = Field(
        default_factory=lambda: Path(__file__).resolve().parent / "local_store.db"
    )

    # Background JSON snapshot for dashboard overview (see live_monitor_snapshot.py)
    live_monitor_snapshot_interval_sec: int = 420
    live_monitor_snapshot_path: Path = Field(
        default_factory=lambda: Path(__file__).resolve().parent
        / "data"
        / "live_monitor_snapshot.json"
    )

    # Live monitor: optional per-endpoint `alert_email`; if blank, this address is used
    default_monitor_alert_email: str = "meaiavanzahackathon@gmail.com"
    # SMTP (e.g. Gmail: create an app password for the sender account)
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""

    # When SMTP is unavailable: Resend (HTTPS) and/or public FormSubmit relay (HTTPS)
    resend_api_key: str = ""
    resend_from: str = "onboarding@resend.dev"
    # POST to formsubmit.co/ajax/{recipient} — no key; may require one-time email activation per inbox
    formsubmit_fallback: bool = True

    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    class Config:
        extra = "ignore"

    @property
    def cors_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def force_local_store(self) -> bool:
        return self.use_local_store or self.use_degraded_mode

    @property
    def use_supabase(self) -> bool:
        if self.force_local_store:
            return False
        return bool(self.supabase_url and self.supabase_service_key)


@lru_cache
def get_settings() -> Settings:
    d: dict[str, Any] = {
        "openrouter_api_key": (os.getenv("OPENROUTER_API_KEY", "") or "").strip(),
        "openrouter_model": os.getenv("OPENROUTER_MODEL", "meta-llama/llama-3.1-8b-instruct:free"),
        "openrouter_timeout_s": float(os.getenv("OPENROUTER_TIMEOUT_S", "12")),
        "supabase_url": (os.getenv("SUPABASE_URL", "") or "").strip(),
        "supabase_service_key": (os.getenv("SUPABASE_KEY", "") or "").strip(),
        "supabase_jwt_secret": (os.getenv("SUPABASE_JWT_SECRET", "") or "").strip(),
        "use_local_store": _b("USE_LOCAL_STORE", False),
        "use_degraded_mode": _b("USE_DEGRADED_MODE", False),
        "store_auto_fallback": _b("STORE_AUTO_FALLBACK", True),
        "demo_mode": _b("DEMO_MODE", False),
        "demo_bearer_token": os.getenv("DEMO_BEARER_TOKEN", ""),
        "jwt_secret": os.getenv("JWT_SECRET", "dev-local-jwt-secret-change-me"),
        "cors_origins": os.getenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"),
    }
    d["local_db_path"] = _p("LOCAL_DB_PATH", Path(__file__).resolve().parent / "local_store.db")
    d["live_monitor_snapshot_interval_sec"] = max(
        60,
        int(os.getenv("LIVE_MONITOR_SNAPSHOT_INTERVAL_SEC", "420")),
    )
    d["live_monitor_snapshot_path"] = _p(
        "LIVE_MONITOR_SNAPSHOT_PATH",
        Path(__file__).resolve().parent / "data" / "live_monitor_snapshot.json",
    )
    d["default_monitor_alert_email"] = (
        os.getenv("DEFAULT_MONITOR_ALERT_EMAIL", "meaiavanzahackathon@gmail.com") or ""
    ).strip()
    d["smtp_host"] = (os.getenv("SMTP_HOST", "") or "").strip()
    d["smtp_port"] = int(os.getenv("SMTP_PORT", "587") or 587)
    d["smtp_user"] = (os.getenv("SMTP_USER", "") or "").strip()
    d["smtp_password"] = (os.getenv("SMTP_PASSWORD", "") or "").strip()
    d["smtp_from"] = (os.getenv("SMTP_FROM", "") or "").strip()
    d["resend_api_key"] = (os.getenv("RESEND_API_KEY", "") or "").strip()
    d["resend_from"] = (os.getenv("RESEND_FROM", "onboarding@resend.dev") or "").strip()
    d["formsubmit_fallback"] = _b("USE_FORM_SUBMIT_EMAIL_FALLBACK", True)
    return Settings.model_validate(d)


def clear_settings_cache() -> None:
    get_settings.cache_clear()
