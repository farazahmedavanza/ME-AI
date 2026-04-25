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
