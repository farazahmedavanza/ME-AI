"""Rule-based natural language -> filters for log search (no LLM)."""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any


def _now() -> datetime:
    return datetime.now(timezone.utc)


def parse_nl_query(
    q: str, now: datetime | None = None
) -> dict[str, Any]:
    now = now or _now()
    text = (q or "").lower().strip()
    out: dict[str, Any] = {
        "status_min": None,
        "status_max": None,
        "status_code": None,
        "method": None,
        "endpoint_substr": None,
        "time_start": None,
        "time_end": now,
        "keywords": [],
    }
    m = re.search(r"last\s+(\d+)\s*(hour|hours|h)\b", text)
    if m:
        h = int(m.group(1))
        out["time_start"] = now - timedelta(hours=h)
    m = re.search(r"last\s+(\d+)\s*(minute|minutes|min|m)\b", text)
    if m and out["time_start"] is None:
        mn = int(m.group(1))
        out["time_start"] = now - timedelta(minutes=mn)
    if "5xx" in text or "500s" in text or "5 xx" in text:
        out["status_min"] = 500
        out["status_max"] = 599
    if "4xx" in text or "400s" in text:
        out["status_min"] = 400
        out["status_max"] = 499
    m = re.search(r"\b(503|502|500|401|404|429)\b", text)
    if m and out["status_min"] is None:
        out["status_code"] = int(m.group(1))
    for verb in ("get", "post", "put", "patch", "delete"):
        if re.search(rf"\b{verb}\b", text):
            out["method"] = verb.upper()
    if "payment" in text or "payments" in text:
        out["endpoint_substr"] = "payment"
    if "transfer" in text:
        out["endpoint_substr"] = "transfer"
    if "balance" in text:
        out["endpoint_substr"] = "balance"
    if "recon" in text or "batch" in text:
        out["endpoint_substr"] = "recon"
    if out["time_start"] is None:
        out["time_start"] = now - timedelta(hours=2)
    return out


def apply_filters(logs: list[dict[str, Any]], f: dict[str, Any]) -> list[dict[str, Any]]:
    from analytics import _parse_ts  # local import to avoid cycle at module level

    start = f.get("time_start")
    end = f.get("time_end")
    smin, smax = f.get("status_min"), f.get("status_max")
    scode = f.get("status_code")
    method = f.get("method")
    sub = f.get("endpoint_substr")
    res: list[dict[str, Any]] = []
    for row in logs:
        try:
            ts = _parse_ts(str(row.get("timestamp", "")))
        except Exception:
            continue
        if start and ts < start:
            continue
        if end and ts > end:
            continue
        code = int(row.get("status_code") or 0)
        if scode is not None and code != scode:
            continue
        if smin is not None and smax is not None and not (smin <= code <= smax):
            continue
        if method and str(row.get("method", "")).upper() != method:
            continue
        if sub and sub not in (str(row.get("endpoint", "")) + " " + str(row.get("service", ""))).lower():
            continue
        res.append(row)
    return res
