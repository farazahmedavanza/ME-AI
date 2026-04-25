"""Periodic JSON snapshot of live endpoint monitoring for dashboard overview."""
from __future__ import annotations

import asyncio
import json
import logging
import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from config import get_settings
from endpoint_monitor_service import run_endpoint_monitors
from store import get_store

log = logging.getLogger(__name__)


def _snapshot_path() -> Path:
    s = get_settings()
    p = s.live_monitor_snapshot_path
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def read_snapshot_file() -> dict[str, Any] | None:
    path = _snapshot_path()
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        log.exception("Failed to read live monitor snapshot")
        return None


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(payload, indent=2, default=str)
    fd, tmp = tempfile.mkstemp(
        dir=str(path.parent), prefix=".live_monitor_snapshot_", suffix=".tmp"
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.isfile(tmp):
            try:
                os.unlink(tmp)
            except OSError:
                pass


def build_synthetic_api_logs(monitors_payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Rows compatible with /api/upload-logs and analytics (api_logs.json shape)."""
    checked_at_fallback = monitors_payload.get("checked_at") or datetime.now(
        timezone.utc
    ).isoformat()
    rows: list[dict[str, Any]] = []
    for e in monitors_payload.get("endpoints") or []:
        eid = str(e.get("id") or uuid4())
        name = str(e.get("name") or "monitor")
        url = str(e.get("url") or "").strip()
        method = str(e.get("method") or "GET")
        if not url:
            url = f"/live-monitor/{eid}"

        lc = e.get("last_check")
        if isinstance(lc, dict):
            ts = str(lc.get("checked_at") or checked_at_fallback)
            status = lc.get("status_code")
            if status is None:
                status = 0
            lat = float(lc.get("latency_ms") or 0)
            ok = lc.get("ok")
            err: str | None = lc.get("error")
            if ok is False and not err:
                err = "check failed"
        else:
            if not e.get("enabled"):
                continue
            ts = checked_at_fallback
            status = 0
            lat = 0.0
            err = "no check data yet"

        rows.append(
            {
                "id": str(uuid4()),
                "timestamp": ts,
                "endpoint": url,
                "method": method,
                "status_code": int(status) if status is not None else 0,
                "response_time_ms": lat,
                "error_message": err,
                "service": f"live-monitor:{name}",
                "trace_id": eid,
                "api_label": name,
            }
        )
    return rows


def synthetic_api_logs_from_stored_snapshot(snap: dict[str, Any]) -> list[dict[str, Any]]:
    """Rebuild upload rows from a snapshot dict (e.g. legacy file without embedded logs)."""
    cached = snap.get("synthetic_api_logs")
    if isinstance(cached, list) and cached:
        return list(cached)
    fallback_ts = snap.get("exported_at") or snap.get("last_run_at") or datetime.now(
        timezone.utc
    ).isoformat()
    rows: list[dict[str, Any]] = []
    for ep in snap.get("endpoints") or []:
        eid = str(ep.get("id") or uuid4())
        name = str(ep.get("name") or "monitor")
        url = str(ep.get("url") or "").strip()
        method = str(ep.get("method") or "GET")
        if not url:
            url = f"/live-monitor/{eid}"
        if not ep.get("enabled"):
            continue
        checked_at = ep.get("checked_at")
        status = ep.get("status_code")
        lat = ep.get("latency_ms")
        ok = ep.get("ok")
        if checked_at is None and status is None and lat is None:
            continue
        ts = str(checked_at or fallback_ts)
        sc = int(status) if status is not None else 0
        rtm = float(lat or 0)
        err: str | None = None
        if ok is False:
            err = "check failed"
        rows.append(
            {
                "id": str(uuid4()),
                "timestamp": ts,
                "endpoint": url,
                "method": method,
                "status_code": sc,
                "response_time_ms": rtm,
                "error_message": err,
                "service": f"live-monitor:{name}",
                "trace_id": eid,
                "api_label": name,
            }
        )
    return rows


def build_user_snapshot(monitors_payload: dict[str, Any]) -> dict[str, Any]:
    """Summarize one user's monitor run for overview / file storage."""
    endpoints_in = monitors_payload.get("endpoints") or []
    endpoints_out: list[dict[str, Any]] = []
    enabled = [e for e in endpoints_in if e.get("enabled")]
    with_check = [e for e in enabled if e.get("last_check")]
    ok_count = sum(
        1
        for e in with_check
        if ((e.get("last_check") or {}).get("ok")) is True
    )
    pct_up = (100.0 * ok_count / len(with_check)) if with_check else None
    breach_count = sum(
        1
        for e in enabled
        if (e.get("sla") or {}).get("breached") is True
    )

    for e in endpoints_in:
        lc = e.get("last_check")
        endpoints_out.append(
            {
                "id": e.get("id"),
                "name": e.get("name"),
                "url": e.get("url"),
                "method": e.get("method") or "GET",
                "enabled": bool(e.get("enabled")),
                "ok": lc.get("ok") if isinstance(lc, dict) else None,
                "status_code": lc.get("status_code") if isinstance(lc, dict) else None,
                "latency_ms": lc.get("latency_ms") if isinstance(lc, dict) else None,
                "checked_at": lc.get("checked_at") if isinstance(lc, dict) else None,
                "sla_breached": (e.get("sla") or {}).get("breached"),
            }
        )

    alerts = monitors_payload.get("alerts") or []
    open_alerts = [a for a in alerts if a.get("resolution_status") == "open"]
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    recent_alerts = 0
    for a in alerts:
        ca = a.get("created_at")
        if not ca:
            continue
        try:
            ts = datetime.fromisoformat(str(ca).replace("Z", "+00:00"))
            if ts >= cutoff:
                recent_alerts += 1
        except Exception:
            continue

    overall = "unknown"
    if not enabled:
        overall = "no_endpoints"
    elif with_check:
        any_down = any(
            ((e.get("last_check") or {}).get("ok")) is False for e in with_check
        )
        any_breach = any(
            (e.get("sla") or {}).get("breached") is True for e in enabled
        )
        if any_down or any_breach:
            overall = "degraded"
        else:
            overall = "healthy"

    synthetic = build_synthetic_api_logs(monitors_payload)

    return {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "last_run_at": monitors_payload.get("checked_at"),
        "check_window_hours": 24,
        "endpoints": endpoints_out,
        "open_alerts_count": len(open_alerts),
        "recent_alerts_count": recent_alerts,
        "kpis": {
            "pct_up": pct_up,
            "breach_count": breach_count,
            "total_endpoints": len(endpoints_in),
            "enabled_count": len(enabled),
        },
        "overall_health": overall,
        "synthetic_api_logs": synthetic,
    }


async def refresh_snapshots_for_all_users() -> None:
    st = get_store()
    if not hasattr(st, "list_distinct_monitored_endpoint_user_ids"):
        return
    user_ids = st.list_distinct_monitored_endpoint_user_ids()
    if not user_ids:
        return

    prev = read_snapshot_file() or {}
    by_user: dict[str, Any] = dict(prev.get("by_user") or {})

    for uid in user_ids:
        try:
            result = await run_endpoint_monitors(st, uid)
            if not result.get("ok") and result.get("error"):
                log.warning("Monitor run for snapshot user=%s: %s", uid, result.get("error"))
                continue
            by_user[str(uid)] = build_user_snapshot(result)
        except Exception:
            log.exception("Snapshot refresh failed for user %s", uid)

    payload = {
        "version": 1,
        "by_user": by_user,
        "file_updated_at": datetime.now(timezone.utc).isoformat(),
    }
    atomic_write_json(_snapshot_path(), payload)
    log.info("Live monitor snapshot written (%s users)", len(by_user))


async def snapshot_background_loop(stop: asyncio.Event) -> None:
    s = get_settings()
    interval = max(60, int(s.live_monitor_snapshot_interval_sec))
    log.info("Live monitor snapshot loop every %ss -> %s", interval, _snapshot_path())
    while True:
        try:
            await refresh_snapshots_for_all_users()
        except Exception:
            log.exception("Live monitor snapshot cycle failed")
        try:
            await asyncio.wait_for(stop.wait(), timeout=interval)
            break
        except asyncio.TimeoutError:
            continue
