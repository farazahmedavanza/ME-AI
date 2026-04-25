"""OpenRouter (optional) for incident reports + Ollama only for 'other log file' import; NL log search."""
from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from config import Settings, get_settings
from narrative import (
    build_template_api_health_narrative,
    build_template_report,
    FALLBACK_INCIDENT_REPORT,
)
from nl_query import apply_filters, parse_nl_query

log = logging.getLogger(__name__)


def _ollama_configured(s: Settings) -> bool:
    return bool((s.ollama_model or "").strip())


def _board_compact_for_llm(board: dict[str, Any]) -> dict[str, Any]:
    k = board.get("kpis") or {}
    ep = board.get("endpoints") or []
    slim: list[dict[str, Any]] = []
    keys = (
        "service",
        "api_label",
        "endpoint",
        "status",
        "sla_risk",
        "p95_ms",
        "error_rate",
        "uptime_30m_pct",
        "breach_probability",
        "minutes_to_breach",
    )
    for e in ep[:30]:
        slim.append({key: e.get(key) for key in keys})
    return {"range": board.get("range"), "kpis": k, "endpoints": slim}


async def openrouter_chat(messages: list[dict[str, str]], timeout_s: float) -> str:
    s = get_settings()
    if not s.openrouter_api_key:
        raise ValueError("no OpenRouter key")
    url = "https://openrouter.ai/api/v1/chat/completions"
    async with httpx.AsyncClient(timeout=timeout_s) as client:
        r = await client.post(
            url,
            headers={
                "Authorization": f"Bearer {s.openrouter_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": s.openrouter_model,
                "messages": messages,
            },
        )
        r.raise_for_status()
        data = r.json()
    return str(data["choices"][0]["message"]["content"])


async def ollama_chat(
    messages: list[dict[str, str]], timeout_s: float, model: str | None = None
) -> str:
    s = get_settings()
    m = model or s.ollama_model
    if not m:
        raise ValueError("no Ollama model")
    base = (s.ollama_base_url or "http://127.0.0.1:11434").rstrip("/")
    url = f"{base}/api/chat"
    async with httpx.AsyncClient(timeout=timeout_s) as client:
        r = await client.post(
            url,
            json={
                "model": m,
                "messages": messages,
                "stream": False,
            },
        )
        r.raise_for_status()
        data = r.json()
    msg = data.get("message") or {}
    return str(msg.get("content") or data.get("response") or "")


async def generate_incident_report(
    service_label: str,
    range_key: str,
    stats: dict[str, Any],
) -> tuple[str, str]:
    """
    Returns (text, mode) where mode is openrouter | template | static.
    """
    s = get_settings()
    system = "You are an SRE. Write exactly three short paragraphs: summary, business impact, recommended actions. Plain English, no bullet lists."
    user = (
        f"Service: {service_label}. Window: {range_key}.\n"
        f"Stats (JSON): {json.dumps(stats, default=str)[:4000]}"
    )
    if s.openrouter_api_key:
        try:
            text = await openrouter_chat(
                [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                s.openrouter_timeout_s,
            )
            return (text.strip(), "openrouter")
        except Exception as e:
            log.warning("openrouter failed: %s", e)
    try:
        return (
            build_template_report(
                service_label, f"the selected window ({range_key})", stats
            ),
            "template",
        )
    except Exception:
        return (FALLBACK_INCIDENT_REPORT, "static")


async def ollama_api_health_narrative_for_other_log_import(
    board: dict[str, Any],
    range_key: str,
) -> tuple[str, str]:
    """
    Used only for text/Rdv/'other' log file uploads. Tries Ollama; otherwise template.
    (Does not use OpenRouter.)
    """
    s = get_settings()
    compact = _board_compact_for_llm(board)
    payload = json.dumps(compact, default=str)[:12_000]
    system = (
        "You are an SRE. Read the JSON dashboard summary (KPIs and per-endpoint stats). "
        "Write 2-3 short paragraphs: overall health, which APIs need attention, one concrete follow-up. "
        "Plain English, no bullet lists, no restating the raw field names."
    )
    user = f"Time window: {range_key}.\nDashboard (JSON):\n{payload}"
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    if _ollama_configured(s):
        try:
            text = await ollama_chat(messages, s.ollama_timeout_s)
            if text.strip():
                return (text.strip(), "ollama")
        except Exception as e:
            log.warning("ollama (other log import): %s", e)
    return (build_template_api_health_narrative(board, range_key), "template")


def search_logs_nl(logs: list[dict[str, Any]], query: str) -> dict[str, Any]:
    f = parse_nl_query(query)
    rows = apply_filters(logs, f)
    return {
        "parsed_filters": {k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in f.items()},
        "row_count": len(rows),
        "rows": rows[:500],
    }
