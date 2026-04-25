"""Templated incident report (fallback when OpenRouter fails or key missing)."""
from __future__ import annotations

from typing import Any

FALLBACK_INCIDENT_REPORT = """During the monitoring window, multiple services showed elevated latency and error signals in the synthetic API log feed. The Fund Transfer API exhibited a sustained period of 503 responses consistent with an upstream or dependency failure pattern.

User-facing impact is estimated as high for payment-adjacent flows: failed transfers and retries can extend customer wait time and may breach internal experience targets. Downstream support and reconciliation queues may see increased volume if the issue persists.

Recommended actions: (1) scale or restart the transfer service and validate connectivity to the beneficiary validation dependency; (2) enable circuit-breaking or cached read paths where safe; (3) post a short status to channels and run a canary test against the critical transfer endpoint."""


def build_template_report(
    service_name: str,
    window_desc: str,
    stats: dict[str, Any] | None,
) -> str:
    stats = stats or {}
    p95 = stats.get("p95_ms", "N/A")
    err = stats.get("error_rate", "N/A")
    risk = stats.get("sla_risk", "unknown")
    p1 = (
        f"During {window_desc}, the {service_name} endpoint showed a {risk.upper()} SLA risk class "
        f"in our rule-based model. Observed p95 latency was {p95} ms and the error share was {err}%. "
        "These values are derived from the uploaded log sample and the configured SLA heuristics."
    )
    p2 = (
        f"If this pattern were observed in production, {service_name} could degrade the customer experience "
        f"on dependent journeys (payments, confirmation screens, and retries). Elevated 5xx rates typically "
        "correlate with support tickets and with reconciliation backlog for operations teams."
    )
    p3 = (
        "Next steps: validate dependency health, review recent deploys, review rate limits, and follow your "
        "runbook for partial outages. If errors persist, fail over to a safe read-only mode where applicable "
        "and keep stakeholders updated with a two-line impact summary and ETA."
    )
    return "\n\n".join([p1, p2, p3])


def build_template_api_health_narrative(
    board: dict[str, Any] | None, range_key: str
) -> str:
    """Deterministic API health blurb from dashboard DTO (used when no LLM)."""
    board = board or {}
    kpis = board.get("kpis") or {}
    endpoints = list(board.get("endpoints") or [])
    total = int(kpis.get("total_apis") or 0)
    up = kpis.get("overall_uptime_pct", "N/A")
    err_p = kpis.get("error_rate_pct", "N/A")
    avg = kpis.get("avg_response_ms", "N/A")
    donut = kpis.get("sla_breach_donut") or {}
    p1 = (
        f"Over the {range_key} window, the uploaded log sample covers {total} API surface(s) "
        f"with about {up}% effective uptime, {err_p}% error share, and {avg} ms average latency "
        f"in this aggregate view. The rule-based model labels "
        f"{donut.get('red', 0)} endpoint(s) red, {donut.get('amber', 0)} amber, and "
        f"{donut.get('green', 0)} green for SLA risk."
    )
    worst = ", ".join(
        f"{e.get('api_label', '?')} ({e.get('sla_risk', '?')}, p95 {e.get('p95_ms', '?')} ms)"
        for e in endpoints[:4]
    )
    p2 = (
        f"Worst-ranked services in this window: {worst or 'n/a'}. "
        "Use the overview table to confirm per-endpoint error rates and latency before escalating."
    )
    p3 = (
        "Operational follow-up: validate dependencies for any red/amber row, check deploy and capacity "
        "for latency regressions, and set up synthetic checks on the noisiest paths in your next run."
    )
    return "\n\n".join([p1, p2, p3])
