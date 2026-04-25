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
        "openrouter_api_key": os.getenv("OPENROUTER_API_KEY", ""),
        "openrouter_model": os.getenv("OPENROUTER_MODEL", "meta-llama/llama-3.1-8b-instruct:free"),
        "openrouter_timeout_s": float(os.getenv("OPENROUTER_TIMEOUT_S", "12")),
        "supabase_url": os.getenv("SUPABASE_URL", ""),
        "supabase_service_key": os.getenv("SUPABASE_KEY", ""),
        "supabase_jwt_secret": os.getenv("SUPABASE_JWT_SECRET", ""),
        "use_local_store": _b("USE_LOCAL_STORE", False),
        "use_degraded_mode": _b("USE_DEGRADED_MODE", False),
        "store_auto_fallback": _b("STORE_AUTO_FALLBACK", True),
        "demo_mode": _b("DEMO_MODE", False),
        "demo_bearer_token": os.getenv("DEMO_BEARER_TOKEN", ""),
        "jwt_secret": os.getenv("JWT_SECRET", "dev-local-jwt-secret-change-me"),
        "cors_origins": os.getenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"),
    }
    d["local_db_path"] = _p("LOCAL_DB_PATH", Path(__file__).resolve().parent / "local_store.db")
    return Settings.model_validate(d)


def clear_settings_cache() -> None:
    get_settings.cache_clear()
