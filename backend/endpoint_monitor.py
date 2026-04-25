"""
HTTP endpoint monitoring: seed definitions, single-request checks, SLA helpers.
The always-failing row uses https://httpstat.us/503 — returns 503 (not 2xx) for reproducible 'down' demos.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

# 10 public GET-friendly URLs + 1 intentionally failing (httpstat 503).
DEFAULT_MONITORED: list[dict[str, Any]] = [
    {
        "name": "GitHub Zen",
        "url": "https://api.github.com/zen",
        "method": "GET",
        "expected_status_min": 200,
        "expected_status_max": 299,
        "timeout_ms": 12_000,
        "enabled": 1,
        "sla_max_latency_ms": 2500,
        "sla_min_uptime_pct": 99.0,
        "failure_threshold": 2,
        "webhook_url": None,
    },
    {
        "name": "httpbin",
        "url": "https://httpbin.org/get",
        "method": "GET",
        "expected_status_min": 200,
        "expected_status_max": 299,
        "timeout_ms": 12_000,
        "enabled": 1,
        "sla_max_latency_ms": 3000,
        "sla_min_uptime_pct": 99.0,
        "failure_threshold": 2,
        "webhook_url": None,
    },
    {
        "name": "JSONPlaceholder",
        "url": "https://jsonplaceholder.typicode.com/posts/1",
        "method": "GET",
        "expected_status_min": 200,
        "expected_status_max": 299,
        "timeout_ms": 12_000,
        "enabled": 1,
        "sla_max_latency_ms": 2500,
        "sla_min_uptime_pct": 99.0,
        "failure_threshold": 2,
        "webhook_url": None,
    },
    {
        "name": "DummyJSON",
        "url": "https://dummyjson.com/products/1",
        "method": "GET",
        "expected_status_min": 200,
        "expected_status_max": 299,
        "timeout_ms": 12_000,
        "enabled": 1,
        "sla_max_latency_ms": 3000,
        "sla_min_uptime_pct": 99.0,
        "failure_threshold": 2,
        "webhook_url": None,
    },
    {
        "name": "PokéAPI",
        "url": "https://pokeapi.co/api/v2/pokemon/1",
        "method": "GET",
        "expected_status_min": 200,
        "expected_status_max": 299,
        "timeout_ms": 12_000,
        "enabled": 1,
        "sla_max_latency_ms": 4000,
        "sla_min_uptime_pct": 99.0,
        "failure_threshold": 2,
        "webhook_url": None,
    },
    {
        "name": "Dog CEO",
        "url": "https://dog.ceo/api/breeds/image/random",
        "method": "GET",
        "expected_status_min": 200,
        "expected_status_max": 299,
        "timeout_ms": 12_000,
        "enabled": 1,
        "sla_max_latency_ms": 3500,
        "sla_min_uptime_pct": 99.0,
        "failure_threshold": 2,
        "webhook_url": None,
    },
    {
        "name": "Open Library",
        "url": "https://openlibrary.org/works/OL45804W.json",
        "method": "GET",
        "expected_status_min": 200,
        "expected_status_max": 299,
        "timeout_ms": 15_000,
        "enabled": 1,
        "sla_max_latency_ms": 5000,
        "sla_min_uptime_pct": 99.0,
        "failure_threshold": 2,
        "webhook_url": None,
    },
    {
        "name": "Cloudflare trace",
        "url": "https://www.cloudflare.com/cdn-cgi/trace",
        "method": "GET",
        "expected_status_min": 200,
        "expected_status_max": 299,
        "timeout_ms": 12_000,
        "enabled": 1,
        "sla_max_latency_ms": 2500,
        "sla_min_uptime_pct": 99.0,
        "failure_threshold": 2,
        "webhook_url": None,
    },
    {
        "name": "Data USA",
        "url": "https://datausa.io/api/data?drilldowns=Nation&measures=Population&year=2020",
        "method": "GET",
        "expected_status_min": 200,
        "expected_status_max": 299,
        "timeout_ms": 15_000,
        "enabled": 1,
        "sla_max_latency_ms": 6000,
        "sla_min_uptime_pct": 99.0,
        "failure_threshold": 2,
        "webhook_url": None,
    },
    {
        "name": "CoinGecko ping",
        "url": "https://api.coingecko.com/api/v3/ping",
        "method": "GET",
        "expected_status_min": 200,
        "expected_status_max": 299,
        "timeout_ms": 12_000,
        "enabled": 1,
        "sla_max_latency_ms": 3000,
        "sla_min_uptime_pct": 99.0,
        "failure_threshold": 2,
        "webhook_url": None,
    },
    {
        "name": "Simulated outage (httpstat 503)",
        "url": "https://httpstat.us/503",
        "method": "GET",
        "expected_status_min": 200,
        "expected_status_max": 299,
        "timeout_ms": 10_000,
        "enabled": 1,
        "sla_max_latency_ms": 500,
        "sla_min_uptime_pct": 99.0,
        "failure_threshold": 1,
        "webhook_url": None,
    },
]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def run_http_check(
    client: httpx.AsyncClient,
    url: str,
    method: str,
    expected_min: int,
    expected_max: int,
    timeout_ms: int,
) -> dict[str, Any]:
    t = max(timeout_ms, 1000) / 1000.0
    m = (method or "GET").upper()
    t0 = datetime.now(timezone.utc)
    err: str | None = None
    code: int | None = None
    try:
        if m == "GET":
            r = await client.get(url, timeout=t)
        elif m == "HEAD":
            r = await client.head(url, timeout=t)
        else:
            r = await client.request(m, url, timeout=t)
        code = r.status_code
        ok = expected_min <= code <= expected_max
    except httpx.HTTPError as e:
        err = str(e)[:500]
        ok = False
    t1 = datetime.now(timezone.utc)
    latency_ms = (t1 - t0).total_seconds() * 1000.0
    return {
        "ok": ok,
        "status_code": code,
        "latency_ms": round(latency_ms, 2),
        "error": err,
        "checked_at": _now_iso(),
    }


def window_start_24h() -> str:
    return (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()


def compute_uptime_pct(
    history_rows: list[dict[str, Any]], min_ts_iso: str
) -> float | None:
    """history_rows: { ok: bool/int, checked_at: str } sorted any order."""
    in_win = [r for r in history_rows if (r.get("checked_at") or "") >= min_ts_iso]
    if not in_win:
        return None
    ok_n = sum(1 for r in in_win if r.get("ok") in (True, 1, "1"))
    return round(100.0 * ok_n / len(in_win), 2)


def consecutive_failures_from_history(
    recent_desc: list[dict[str, Any]],
) -> int:
    """Recent checks newest first; count leading failures."""
    n = 0
    for r in recent_desc:
        okv = r.get("ok")
        is_ok = okv in (True, 1, "1")
        if is_ok:
            break
        n += 1
    return n
