from __future__ import annotations

import logging
import os

try:
    from dotenv import load_dotenv

    load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
except Exception:
    pass
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Any

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from ai_service import generate_incident_report, search_logs_nl
from analytics import build_alerts_from_endpoints, build_dashboard
from auth import get_user_id, issue_local_token
from config import get_settings
from models import (
    DevLoginResponse,
    HealthResponse,
    IncidentReportRequest,
    LogSearchRequest,
    AlertPatch,
)
import store as store_mod
from store import get_store
from store.local_store import new_id

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

app = FastAPI(title="API Health & SLA Monitor", version="0.1.0")

_settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=_settings.cors_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _store():
    return get_store()


def _recompute_and_persist(
    st: Any, user_id: str, session_id: str, range_key: str = "1h"
) -> dict[str, Any]:
    """After upload: persist one analysis snapshot and seed alerts if empty."""
    logs = st.get_session_logs(user_id, session_id)
    board = build_dashboard(logs, range_key)
    sla = {e["service"]: e["sla_risk"] for e in board["endpoints"]}
    st.save_analysis(
        user_id,
        session_id,
        board,
        {"by_service": sla, "endpoints": board["endpoints"]},
    )
    if not st.get_alerts(user_id, session_id):
        alerts = build_alerts_from_endpoints(session_id, board["endpoints"])
        for a in alerts:
            a["id"] = new_id()
        st.save_alerts(user_id, session_id, alerts)
    return board


def _build_board_only(
    st: Any, user_id: str, session_id: str, range_key: str
) -> dict[str, Any]:
    logs = st.get_session_logs(user_id, session_id)
    return build_dashboard(logs, range_key)


def _ensure_alerts(
    st: Any, user_id: str, session_id: str, board: dict[str, Any]
) -> None:
    if st.get_alerts(user_id, session_id):
        return
    alerts = build_alerts_from_endpoints(session_id, board["endpoints"])
    for a in alerts:
        a["id"] = new_id()
    st.save_alerts(user_id, session_id, alerts)


@app.get("/api/health", response_model=HealthResponse)
def api_health() -> HealthResponse:
    s = get_settings()
    st = get_store()
    h = st.health() if hasattr(st, "health") else {}
    if h.get("store") == "supabase":
        store_name = "supabase"
    elif s.force_local_store or not s.use_supabase:
        store_name = "local"
    else:
        store_name = "local"
    ai = "openrouter" if s.openrouter_api_key else "local"
    return HealthResponse(
        store=store_name,
        ai=ai,
        version=s.version,
        app_name=s.app_name,
        store_fallback=store_mod.using_store_fallback,
    )


class DevLoginBody(BaseModel):
    password: str | None = None


@app.post("/api/auth/dev-login", response_model=DevLoginResponse)
def dev_login(body: DevLoginBody | None = None) -> DevLoginResponse:
    s = get_settings()
    if not s.demo_mode:
        raise HTTPException(404, "Demo login disabled")
    token = issue_local_token()
    return DevLoginResponse(access_token=token)


@app.post("/api/auth/token")
def issue_token_for_hackathon() -> dict[str, str]:
    """Always returns a local JWT (for judge without Supabase). Do not use in production."""
    return {"access_token": issue_local_token(), "token_type": "bearer"}


@app.get("/api/sessions")
def list_sessions(user_id: Annotated[str, Depends(get_user_id)]):
    return {"sessions": _store().list_sessions(user_id)}


class UploadIn(BaseModel):
    filename: str = "api_logs.json"
    logs: list[dict[str, Any]]


@app.post("/api/upload-logs")
def upload_logs(
    body: UploadIn, user_id: Annotated[str, Depends(get_user_id)]
):
    st = _store()
    session_id = st.upload_logs(user_id, body.filename, body.logs)
    _recompute_and_persist(st, user_id, session_id, "1h")
    return {"session_id": session_id, "ok": True}


@app.get("/api/sessions/{session_id}/results")
def session_results(
    session_id: str, user_id: Annotated[str, Depends(get_user_id)]
):
    st = _store()
    a = st.get_analysis(user_id, session_id)
    if not a:
        raise HTTPException(404, "No analysis for session")
    return a


@app.get("/api/dashboard")
def dashboard(
    user_id: Annotated[str, Depends(get_user_id)],
    session_id: str | None = None,
    range_key: str = Query("1h", alias="range"),
):
    st = _store()
    sessions = st.list_sessions(user_id)
    if not session_id and sessions:
        session_id = sessions[0]["id"]
    if not session_id:
        return {"ok": True, "empty": True, "session_id": None, "data": None}
    board = _build_board_only(st, user_id, session_id, range_key)
    if not st.get_analysis(user_id, session_id) and board.get("endpoints"):
        sla = {e["service"]: e["sla_risk"] for e in board["endpoints"]}
        st.save_analysis(
            user_id,
            session_id,
            board,
            {"by_service": sla, "endpoints": board["endpoints"]},
        )
    _ensure_alerts(st, user_id, session_id, board)
    alerts = st.get_alerts(user_id, session_id)
    incidents = st.get_incident_reports(user_id, session_id)
    s = get_settings()
    return {
        "ok": True,
        "empty": False,
        "session_id": session_id,
        "range": range_key,
        "data": board,
        "alerts": alerts,
        "incident_reports": incidents,
        "store": (st.health() or {}).get("store", "local"),
        "ai": "openrouter" if s.openrouter_api_key else "local",
    }


@app.get("/api/sla-status")
def sla_status(
    user_id: Annotated[str, Depends(get_user_id)],
    session_id: str,
    range_key: str = Query("1h", alias="range"),
):
    st = _store()
    logs = st.get_session_logs(user_id, session_id)
    return build_dashboard(logs, range_key)["endpoints"]


@app.get("/api/health-summary")
def health_summary(
    user_id: Annotated[str, Depends(get_user_id)],
    session_id: str,
    range_key: str = Query("1h", alias="range"),
):
    st = _store()
    logs = st.get_session_logs(user_id, session_id)
    return build_dashboard(logs, range_key)


@app.post("/api/incident-report")
async def incident_report(
    body: IncidentReportRequest, user_id: Annotated[str, Depends(get_user_id)]
):
    st = _store()
    session_id = body.session_id
    logs = st.get_session_logs(user_id, session_id)
    board = build_dashboard(logs, "1h")
    label = "All APIs"
    stat: dict = {}
    svc = body.service
    if svc:
        for e in board.get("endpoints", []):
            if e.get("service") == svc:
                label = str(e.get("api_label") or svc)
                stat = e
                break
        if not stat and board.get("endpoints"):
            stat = board["endpoints"][0]
            label = str(stat.get("api_label") or "Service")
    elif body.endpoint:
        for e in board.get("endpoints", []):
            if e.get("endpoint") == body.endpoint:
                label = str(e.get("api_label") or e.get("service"))
                stat = e
                break
        if not stat:
            stat = board.get("endpoints", [{}])[0] if board.get("endpoints") else {}
    else:
        if board.get("endpoints"):
            # Worst endpoint first (already sorted in build_dashboard)
            stat = board["endpoints"][0]
            label = str(stat.get("api_label") or "Service")
    if not stat:
        stat = {"note": "no log data"}
    text, mode = await generate_incident_report(
        str(label or svc or "Service"),
        "1h",
        stat,
    )
    key = f"{label}-{datetime.now(timezone.utc).strftime('%H%M')}"
    st.save_incident_report(user_id, session_id, key, text)
    return {"text": text, "ai_mode": mode, "key": key}


@app.post("/api/log-search")
def log_search(
    body: LogSearchRequest, user_id: Annotated[str, Depends(get_user_id)]
):
    st = _store()
    logs = st.get_session_logs(user_id, body.session_id)
    return search_logs_nl(logs, body.query)


class AlertPatchPydantic(AlertPatch):
    pass


@app.patch("/api/alerts/{alert_id}")
def patch_alert(
    alert_id: str,
    body: AlertPatchPydantic,
    user_id: Annotated[str, Depends(get_user_id)],
):
    st = _store()
    fields: dict = {}
    if body.resolution_status is not None:
        fields["resolution_status"] = body.resolution_status
        if body.resolution_status == "resolved":
            fields["resolved_at"] = datetime.now(timezone.utc).isoformat()
    if body.assignee is not None:
        fields["assignee"] = body.assignee
    ok = st.update_alert(user_id, alert_id, fields)
    if not ok:
        raise HTTPException(404, "Alert not found")
    return {"ok": True}


@app.get("/api/logs")
def get_logs(
    user_id: Annotated[str, Depends(get_user_id)], session_id: str
):
    return {"logs": _store().get_session_logs(user_id, session_id)}


# --- Optional: static sample file load ---
@app.get("/api/debug/sample-logs")
def sample_logs_path():
    p = Path(__file__).parent / "data" / "api_logs.json"
    if not p.is_file():
        return {"ok": False}
    return {"ok": True, "path": str(p)}
