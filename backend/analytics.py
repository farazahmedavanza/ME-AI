"""Compute KPIs, SLA risk, trends, and time-to-breach heuristics from log rows."""
from __future__ import annotations

import statistics
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

# SLA thresholds (ms) for p95 — demo values
DEFAULT_SLA_P95_MS = 800.0


def _parse_ts(raw: str) -> datetime:
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    return datetime.fromisoformat(raw)


def filter_by_range(
    logs: list[dict[str, Any]], range_key: str, now: datetime | None = None
) -> list[dict[str, Any]]:
    now = now or datetime.now(timezone.utc)
    deltas = {
        "15m": timedelta(minutes=15),
        "1h": timedelta(hours=1),
        "6h": timedelta(hours=6),
        "24h": timedelta(hours=24),
    }
    delta = deltas.get(range_key, deltas["1h"])
    start = now - delta
    out: list[dict[str, Any]] = []
    parse_ok = 0
    for row in logs:
        try:
            ts = _parse_ts(str(row.get("timestamp", "")))
            parse_ok += 1
            if ts >= start:
                out.append(row)
        except Exception:
            continue
    # Keep strict window behavior; only fall back when timestamps are unparseable.
    if parse_ok == 0:
        return logs
    return out


def group_by_service(logs: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    g: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in logs:
        svc = str(row.get("service") or "unknown")
        g[svc].append(row)
    return dict(g)


def _percentile(sorted_vals: list[float], p: float) -> float:
    if not sorted_vals:
        return 0.0
    k = (len(sorted_vals) - 1) * p
    f = int(k)
    c = min(f + 1, len(sorted_vals) - 1)
    if f == c:
        return float(sorted_vals[int(k)])
    return float(sorted_vals[f] + (sorted_vals[c] - sorted_vals[f]) * (k - f))


def p95(values: list[float]) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    return _percentile(s, 0.95)


def linear_slope_y_per_minute(points: list[tuple[datetime, float]]) -> float:
    """Least squares slope of y vs minutes from first t."""
    if len(points) < 2:
        return 0.0
    t0 = points[0][0].timestamp()
    xs: list[float] = []
    ys: list[float] = []
    for t, y in points:
        xs.append((t.timestamp() - t0) / 60.0)
        ys.append(y)
    n = len(xs)
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    num = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    den = sum((x - mean_x) ** 2 for x in xs) or 1e-9
    return num / den


def sla_risk_from_metrics(
    error_rate: float, p95_ms: float, slope_rt: float, sla_p95: float = DEFAULT_SLA_P95_MS
) -> str:
    """Return green | amber | red."""
    if error_rate > 0.05 or p95_ms > sla_p95 * 1.2:
        return "red"
    if error_rate > 0.01 or p95_ms > sla_p95 * 0.9 or slope_rt > 15:
        return "amber"
    return "green"


def status_label(risk: str, error_rate: float, p95_ms: float, sla_p95: float) -> str:
    if risk == "red":
        if error_rate > 0.1:
            return "Unstable"
        return "Degraded"
    if risk == "amber":
        return "At Risk"
    return "Healthy"


def estimate_breach(slope: float, p95_ms: float, sla_p95: float) -> tuple[float, int | None]:
    """
    Returns (probability 0-1, minutes until breach or None).
    Heuristic only.
    """
    if p95_ms >= sla_p95:
        return (0.92, 0)
    if slope <= 0:
        return (0.12, None)
    gap = sla_p95 - p95_ms
    minutes = max(1, int(gap / max(slope, 1e-6)))
    prob = min(0.95, 0.35 + min(0.55, slope / 50.0))
    return (prob, minutes)


def build_sparkline(
    rows: list[dict[str, Any]], field: str = "response_time_ms", buckets: int = 20
) -> list[float]:
    if not rows:
        return [0.0] * buckets
    rows_sorted = sorted(rows, key=lambda r: r.get("timestamp", ""))
    chunk = max(1, len(rows_sorted) // buckets)
    out: list[float] = []
    for i in range(0, len(rows_sorted), chunk):
        chunk_rows = rows_sorted[i : i + chunk]
        vals = [float(r.get(field) or 0) for r in chunk_rows]
        out.append(sum(vals) / max(1, len(vals)))
    while len(out) < buckets:
        out.append(out[-1] if out else 0.0)
    return out[:buckets]


def build_dashboard(
    logs: list[dict[str, Any]], range_key: str = "1h"
) -> dict[str, Any]:
    """Full dashboard DTO for the UI."""
    now = datetime.now(timezone.utc)
    window_logs = filter_by_range(logs, range_key, now)
    if not window_logs:
        window_logs = logs

    by_svc = group_by_service(window_logs)
    endpoints: list[dict[str, Any]] = []
    all_rts: list[float] = []
    all_err = 0
    n_all = 0
    risk_counts = {"red": 0, "amber": 0, "green": 0}
    p95_trend_series: dict[str, list[dict[str, Any]]] = {}

    for svc, rows in by_svc.items():
        rts = [float(r.get("response_time_ms") or 0) for r in rows]
        codes = [int(r.get("status_code") or 0) for r in rows]
        errs = sum(1 for c in codes if c >= 400)
        n = len(rows)
        error_rate = errs / n if n else 0.0
        p95v = p95(rts)
        for rt in rts:
            all_rts.append(rt)
        all_err += errs
        n_all += n

        points: list[tuple[datetime, float]] = []
        for r in sorted(rows, key=lambda x: x.get("timestamp", ""))[-200:]:
            try:
                points.append(
                    (
                        _parse_ts(str(r.get("timestamp", ""))),
                        float(r.get("response_time_ms") or 0),
                    )
                )
            except Exception:
                continue
        slope = linear_slope_y_per_minute(points)
        risk = sla_risk_from_metrics(error_rate, p95v, slope)
        risk_counts[risk] += 1
        st = status_label(risk, error_rate, p95v, DEFAULT_SLA_P95_MS)
        p95_baseline = p95v * 0.65  # mock "yesterday" baseline
        p95_delta = ((p95v - p95_baseline) / p95_baseline * 100) if p95_baseline else 0.0
        # error delta vs half-window heuristic
        err_delta = (error_rate - max(0.0, error_rate * 0.5)) * 100

        spark = build_sparkline(rows, buckets=12)
        prob, minutes = estimate_breach(slope, p95v, DEFAULT_SLA_P95_MS)
        label = str(rows[0].get("api_label") or svc.replace("-", " ").title())

        # P95 time series for chart (aggregate by 3-min buckets for readability)
        bucket_map: dict[int, list[float]] = defaultdict(list)
        t_min = None
        for r in rows:
            try:
                t = _parse_ts(str(r.get("timestamp", "")))
                t_min = t.minute + t.hour * 60 if t_min is None else t_min
                key = t.hour * 20 + t.minute // 3
                bucket_map[key].append(float(r.get("response_time_ms") or 0))
            except Exception:
                continue
        # stable order
        trend_pts = []
        for k in sorted(bucket_map.keys())[-40:]:
            v = sum(bucket_map[k]) / len(bucket_map[k])
            trend_pts.append(
                {
                    "t": k,
                    "p95": round(v, 1),
                }
            )
        if not trend_pts and rts:
            trend_pts = [{"t": 0, "p95": round(p95v, 1)}]
        p95_trend_series[label] = trend_pts

        first_path = str(rows[0].get("endpoint") or f"/{svc}")
        endpoints.append(
            {
                "service": svc,
                "api_label": label,
                "endpoint": first_path,
                "status": st,
                "sla_risk": risk,
                "p95_ms": round(p95v, 1),
                "p95_delta_pct": round(p95_delta, 1),
                "error_rate": round(error_rate * 100, 2),
                "error_delta_pp": round(err_delta, 2),
                "uptime_30m_pct": round((1.0 - error_rate) * 100, 2),
                "trend_sparkline": [round(x, 1) for x in spark],
                "slope_per_min": round(slope, 2),
                "breach_probability": round(prob, 2),
                "minutes_to_breach": minutes,
                "risk_tag": "High" if risk == "red" else ("Medium" if risk == "amber" else "Low"),
            }
        )

    # Global KPIs
    avg_rt = sum(all_rts) / max(1, len(all_rts))
    overall_error = all_err / max(1, n_all)
    overall_uptime = (1.0 - overall_error) * 100

    # Order endpoints for table: worst first
    endpoints.sort(
        key=lambda e: ({"red": 0, "amber": 1, "green": 2}.get(e["sla_risk"], 3), -e.get("p95_ms", 0))
    )

    # Chart-friendly multi-line series (use label keys)
    chart_series = []
    for label, pts in p95_trend_series.items():
        if not pts:
            continue
        chart_series.append(
            {
                "name": label,
                "points": [
                    {"x": i, "y": p["p95"]} for i, p in enumerate(pts)
                ],
            }
        )

    return {
        "generated_at": now.isoformat(),
        "range": range_key,
        "kpis": {
            "total_apis": len(by_svc),
            "overall_uptime_pct": round(overall_uptime, 2),
            "avg_response_ms": round(avg_rt, 1),
            "error_rate_pct": round(overall_error * 100, 2),
            "sla_breach_donut": {
                "red": risk_counts["red"],
                "amber": risk_counts["amber"],
                "green": risk_counts["green"],
            },
        },
        "endpoints": endpoints,
        "p95_chart": chart_series,
    }


def build_alerts_from_endpoints(
    session_id: str, endpoints: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Seed alerts for a session (assignees match mock)."""
    pool = [
        "Ravi Kumar",
        "Neha Sharma",
        "Arjun Verma",
    ]
    out: list[dict[str, Any]] = []
    for i, e in enumerate(endpoints):
        if e.get("sla_risk") in ("red", "amber"):
            if e["sla_risk"] == "red" and e.get("error_rate", 0) > 3:
                sev, title = "high", "High error rate"
            elif e["sla_risk"] == "red":
                sev, title = "high", "High response time"
            else:
                sev, title = "medium", "Slow performance"
            out.append(
                {
                    "session_id": session_id,
                    "endpoint": e.get("endpoint"),
                    "api_label": e.get("api_label"),
                    "severity": sev,
                    "title": title,
                    "description": f"{e.get('api_label')}: p95 {e.get('p95_ms')} ms, errors {e.get('error_rate')}%",
                    "resolution_status": "open" if sev == "high" else "investigating",
                    "assignee": pool[i % len(pool)],
                }
            )
    if not any("batch" in (x.get("api_label") or "").lower() for x in out):
        out.append(
            {
                "session_id": session_id,
                "endpoint": "/api/v1/jobs/recon",
                "api_label": "Batch Recon Job",
                "severity": "low",
                "title": "Batch job delay detected",
                "description": "Job duration exceeded scheduled window in logs.",
                "resolution_status": "resolved",
                "assignee": "System Auto-Heal",
            }
        )
    return out
