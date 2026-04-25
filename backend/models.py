from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class LogEntryIn(BaseModel):
    id: str | None = None
    timestamp: str
    endpoint: str
    method: str = "GET"
    status_code: int
    response_time_ms: float
    error_message: str | None = None
    service: str = ""
    trace_id: str | None = None
    api_label: str | None = None


class UploadPayload(BaseModel):
    filename: str = "api_logs.json"
    logs: list[LogEntryIn]


class IncidentReportRequest(BaseModel):
    session_id: str
    endpoint: str | None = None
    service: str | None = None
    range_key: str = "1h"


class LogSearchRequest(BaseModel):
    session_id: str
    query: str


class AlertPatch(BaseModel):
    resolution_status: str | None = None
    assignee: str | None = None


class DevLoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class HealthResponse(BaseModel):
    store: str
    ai: str
    version: str
    app_name: str
    store_fallback: bool = False
