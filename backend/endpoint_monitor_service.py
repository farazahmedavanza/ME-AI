"""Run HTTP checks, persist state/history, emit monitor alerts. Used by /api/endpoint-monitors."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

import httpx

from config import get_settings
from endpoint_monitor import (
    compute_uptime_pct,
    run_http_check,
    window_start_24h,
)
from monitor_alert_email import resolve_alert_recipient, send_sla_downtime_email

log = logging.getLogger(__name__)


def _i_ok(v: Any) -> int:
    if v in (1, "1", True):
        return 1
    return 0


def _i_enabled(ep: dict[str, Any]) -> bool:
    e = ep.get("enabled")
    if e is None:
        return True
    if isinstance(e, bool):
        return e
    return int(e) == 1


# Serialize monitor runs per user so concurrent API + background snapshot do not race
# on consecutive_failures (which blocked cfail from ever reaching failure_threshold).
_user_ep_locks: dict[str, asyncio.Lock] = {}
_ep_locks_init = asyncio.Lock()


async def _acquire_user_ep_lock(user_id: str) -> asyncio.Lock:
    async with _ep_locks_init:
        if user_id not in _user_ep_locks:
            _user_ep_locks[user_id] = asyncio.Lock()
        return _user_ep_locks[user_id]


async def run_endpoint_monitors(
    st: Any, user_id: str
) -> dict[str, Any]:
    if not hasattr(st, "list_monitored_endpoints"):
        return {
            "ok": False,
            "error": "Store does not support endpoint monitoring",
            "endpoints": [],
            "alerts": [],
        }
    lock = await _acquire_user_ep_lock(user_id)
    async with lock:
        return await _run_endpoint_monitors_locked(st, user_id)


async def _run_endpoint_monitors_locked(
    st: Any, user_id: str
) -> dict[str, Any]:
    eps = st.list_monitored_endpoints(user_id)
    if not eps:
        return {
            "ok": True,
            "endpoints": [],
            "alerts": st.list_endpoint_monitor_alerts(user_id, 50)
            if hasattr(st, "list_endpoint_monitor_alerts")
            else [],
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }

    since_24h = window_start_24h()
    out: list[dict[str, Any]] = []
    last_checked_at: str = datetime.now(timezone.utc).isoformat()

    timeout = httpx.Timeout(30.0)
    async with httpx.AsyncClient(
        follow_redirects=True,
        timeout=timeout,
        headers={"User-Agent": "Avanza-Ops-EndpointMonitor/0.1"},
    ) as client:
        for ep in eps:
            eid = str(ep["id"])
            if not _i_enabled(ep):
                st_row = st.get_monitor_state(user_id, eid) or {}
                out.append(
                    {
                        "id": eid,
                        "name": ep.get("name"),
                        "url": ep.get("url"),
                        "method": ep.get("method") or "GET",
                        "enabled": False,
                        "expected_status_min": int(ep.get("expected_status_min") or 200),
                        "expected_status_max": int(ep.get("expected_status_max") or 299),
                        "timeout_ms": int(ep.get("timeout_ms") or 10_000),
                        "alert_email": ep.get("alert_email"),
                        "webhook_url": ep.get("webhook_url"),
                        "last_check": None,
                        "consecutive_failures": int(
                            st_row.get("consecutive_failures") or 0
                        ),
                        "uptime_24h_pct": None,
                        "sla": {
                            "breached": None,
                            "latency_ok": None,
                            "uptime_ok": None,
                        },
                        "sparkline": [],
                        "config": {
                            "sla_max_latency_ms": int(ep.get("sla_max_latency_ms") or 3000),
                            "sla_min_uptime_pct": float(ep.get("sla_min_uptime_pct") or 99.0),
                            "failure_threshold": int(ep.get("failure_threshold") or 2),
                        },
                    }
                )
                continue

            ex_min = int(ep.get("expected_status_min") or 200)
            ex_max = int(ep.get("expected_status_max") or 299)
            to_ms = int(ep.get("timeout_ms") or 10_000)
            sla_max_lat = int(ep.get("sla_max_latency_ms") or 3000)
            sla_min_up = float(ep.get("sla_min_uptime_pct") or 99.0)
            fail_thr = max(1, int(ep.get("failure_threshold") or 2))
            u = str(ep.get("url") or "")
            m = str(ep.get("method") or "GET")

            chk = await run_http_check(client, u, m, ex_min, ex_max, to_ms)
            last_checked_at = str(chk.get("checked_at") or last_checked_at)
            result_ok = bool(chk.get("ok"))
            lat = float(chk.get("latency_ms") or 0)
            latency_sla_breach = result_ok and lat > sla_max_lat

            prev = st.get_monitor_state(user_id, eid)
            if prev is None:
                pl_ok = 1
                prev_cf = 0
            else:
                pl_ok = int(prev.get("last_ok") or 0)
                prev_cf = int(prev.get("consecutive_failures") or 0)

            cfail = 0 if result_ok else (prev_cf + 1)

            st.insert_endpoint_check(
                user_id,
                eid,
                1 if result_ok else 0,
                chk.get("status_code"),
                chk.get("latency_ms"),
                chk.get("error"),
                str(chk.get("checked_at") or last_checked_at),
            )
            st.upsert_monitor_state(
                user_id,
                eid,
                1 if result_ok else 0,
                cfail,
                chk.get("status_code"),
                chk.get("latency_ms"),
                str(chk.get("checked_at") or last_checked_at),
                chk.get("error"),
            )

            if not result_ok:
                if pl_ok == 1:
                    st.insert_endpoint_monitor_alert(
                        user_id,
                        eid,
                        str(ep.get("name") or eid),
                        "critical",
                        f"Endpoint down: {ep.get('name') or eid}",
                        f"Request failed or status outside {ex_min}–{ex_max}. "
                        f"code={chk.get('status_code')!s}, err={chk.get('error')!s}",
                        "transition",
                    )
                elif cfail == fail_thr and fail_thr > 1:
                    if st.count_open_monitor_alerts(user_id, eid) == 0:
                        st.insert_endpoint_monitor_alert(
                            user_id,
                            eid,
                            str(ep.get("name") or eid),
                            "high",
                            f"Repeated failure ({fail_thr}x): {ep.get('name') or eid}",
                            f"{fail_thr} consecutive failed checks. code={chk.get('status_code')!s}.",
                            "consecutive",
                        )

            if not result_ok and cfail == fail_thr:
                settings = get_settings()
                to_addr = resolve_alert_recipient(ep, settings)
                err_v = chk.get("error")
                err_out: str | None = None if err_v in (None, "") else str(err_v)
                try:
                    await asyncio.to_thread(
                        send_sla_downtime_email,
                        to_addr,
                        endpoint_name=str(ep.get("name") or eid),
                        url=u,
                        status_code=chk.get("status_code"),
                        error=err_out,
                        failure_threshold=fail_thr,
                        consecutive_failures=cfail,
                    )
                except Exception:
                    log.exception("SLA email task failed (endpoint_id=%s)", eid)

            hist = st.history_for_uptime(user_id, eid, since_24h)
            up_pct = compute_uptime_pct(
                [
                    {
                        "ok": _i_ok(x.get("ok")),
                        "checked_at": str(x.get("checked_at") or ""),
                    }
                    for x in hist
                ],
                since_24h,
            )
            uptime_breach: bool | None = None
            if up_pct is not None:
                uptime_breach = up_pct < sla_min_up

            recent = st.recent_endpoint_history(user_id, eid, 12)
            spark: list[int] = []
            for row in reversed(recent):
                spark.append(1 if _i_ok(row.get("ok")) else 0)

            status_breach = not result_ok
            breached = bool(
                status_breach
                or (up_pct is not None and (uptime_breach or False))
                or latency_sla_breach
            )

            out.append(
                {
                    "id": eid,
                    "name": ep.get("name"),
                    "url": ep.get("url"),
                    "method": m,
                    "enabled": True,
                    "expected_status_min": ex_min,
                    "expected_status_max": ex_max,
                    "timeout_ms": to_ms,
                    "alert_email": ep.get("alert_email"),
                    "webhook_url": ep.get("webhook_url"),
                    "last_check": chk,
                    "consecutive_failures": cfail,
                    "uptime_24h_pct": up_pct,
                    "sla": {
                        "breached": breached,
                        "latency_ok": not latency_sla_breach,
                        "uptime_ok": (not uptime_breach) if up_pct is not None else None,
                        "max_latency_ms": sla_max_lat,
                        "min_uptime_pct": sla_min_up,
                    },
                    "sparkline": spark,
                    "config": {
                        "sla_max_latency_ms": sla_max_lat,
                        "sla_min_uptime_pct": sla_min_up,
                        "failure_threshold": fail_thr,
                    },
                }
            )

    al = st.list_endpoint_monitor_alerts(user_id, 50)
    return {
        "ok": True,
        "endpoints": out,
        "alerts": al,
        "checked_at": last_checked_at,
    }


def snapshot_endpoint_monitors(st: Any, user_id: str) -> dict[str, Any]:
    """Last persisted checks only (no HTTP). For initial page load or cheap polls."""
    if not hasattr(st, "list_monitored_endpoints"):
        return {"ok": False, "endpoints": [], "alerts": []}
    eps = st.list_monitored_endpoints(user_id)
    since_24h = window_start_24h()
    out: list[dict[str, Any]] = []
    last_checked_at: str | None = None
    for ep in eps:
        eid = str(ep["id"])
        if not _i_enabled(ep):
            st_row = st.get_monitor_state(user_id, eid) or {}
            out.append(
                {
                    "id": eid,
                    "name": ep.get("name"),
                    "url": ep.get("url"),
                    "method": ep.get("method") or "GET",
                    "enabled": False,
                    "expected_status_min": int(ep.get("expected_status_min") or 200),
                    "expected_status_max": int(ep.get("expected_status_max") or 299),
                    "timeout_ms": int(ep.get("timeout_ms") or 10_000),
                    "alert_email": ep.get("alert_email"),
                    "webhook_url": ep.get("webhook_url"),
                    "last_check": None,
                    "consecutive_failures": int(st_row.get("consecutive_failures") or 0),
                    "uptime_24h_pct": None,
                    "sla": {"breached": None, "latency_ok": None, "uptime_ok": None},
                    "sparkline": [],
                    "config": {
                        "sla_max_latency_ms": int(ep.get("sla_max_latency_ms") or 3000),
                        "sla_min_uptime_pct": float(ep.get("sla_min_uptime_pct") or 99.0),
                        "failure_threshold": int(ep.get("failure_threshold") or 2),
                    },
                }
            )
            continue
        sla_max_lat = int(ep.get("sla_max_latency_ms") or 3000)
        sla_min_up = float(ep.get("sla_min_uptime_pct") or 99.0)
        st_row = st.get_monitor_state(user_id, eid) or {}
        lc = None
        if st_row.get("last_checked_at"):
            oks = int(st_row.get("last_ok") or 0)
            lc = {
                "ok": oks == 1,
                "status_code": st_row.get("last_status_code"),
                "latency_ms": st_row.get("last_latency_ms"),
                "error": st_row.get("last_error"),
                "checked_at": st_row.get("last_checked_at"),
            }
            last_checked_at = str(st_row.get("last_checked_at") or last_checked_at or "")
        cfail = int(st_row.get("consecutive_failures") or 0)
        lat = float((lc or {}).get("latency_ms") or 0) if lc else 0.0
        oks = (lc or {}).get("ok")
        result_ok = bool(oks) if oks is not None else False
        latency_sla_breach = bool(result_ok and lat > sla_max_lat)

        hist = st.history_for_uptime(user_id, eid, since_24h)
        up_pct = compute_uptime_pct(
            [
                {
                    "ok": _i_ok(x.get("ok")),
                    "checked_at": str(x.get("checked_at") or ""),
                }
                for x in hist
            ],
            since_24h,
        )
        uptime_breach = up_pct < sla_min_up if up_pct is not None else None
        recent = st.recent_endpoint_history(user_id, eid, 12)
        spark: list[int] = [
            1 if _i_ok(r.get("ok")) else 0 for r in reversed(recent)
        ]
        status_breach = not result_ok if lc else None
        breached: bool | None = None
        if lc is not None:
            breached = bool(
                status_breach
                or (up_pct is not None and (uptime_breach or False))
                or latency_sla_breach
            )
        out.append(
            {
                "id": eid,
                "name": ep.get("name"),
                "url": ep.get("url"),
                "method": ep.get("method") or "GET",
                "enabled": True,
                "expected_status_min": int(ep.get("expected_status_min") or 200),
                "expected_status_max": int(ep.get("expected_status_max") or 299),
                "timeout_ms": int(ep.get("timeout_ms") or 10_000),
                "alert_email": ep.get("alert_email"),
                "webhook_url": ep.get("webhook_url"),
                "last_check": lc,
                "consecutive_failures": cfail,
                "uptime_24h_pct": up_pct,
                "sla": {
                    "breached": breached,
                    "latency_ok": not latency_sla_breach if lc else None,
                    "uptime_ok": (not uptime_breach) if up_pct is not None else None,
                    "max_latency_ms": sla_max_lat,
                    "min_uptime_pct": sla_min_up,
                },
                "sparkline": spark,
                "config": {
                    "sla_max_latency_ms": sla_max_lat,
                    "sla_min_uptime_pct": sla_min_up,
                    "failure_threshold": int(ep.get("failure_threshold") or 2),
                },
            }
        )
    al = st.list_endpoint_monitor_alerts(user_id, 50)
    return {
        "ok": True,
        "endpoints": out,
        "alerts": al,
        "checked_at": last_checked_at
        or datetime.now(timezone.utc).isoformat(),
    }
