"""OpenRouter (optional) + narrative fallbacks for incident reports and NL log search help."""
from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from config import get_settings
from narrative import build_template_report, FALLBACK_INCIDENT_REPORT
from nl_query import apply_filters, parse_nl_query

log = logging.getLogger(__name__)


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


def search_logs_nl(logs: list[dict[str, Any]], query: str) -> dict[str, Any]:
    f = parse_nl_query(query)
    rows = apply_filters(logs, f)
    return {
        "parsed_filters": {k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in f.items()},
        "row_count": len(rows),
        "rows": rows[:500],
    }
