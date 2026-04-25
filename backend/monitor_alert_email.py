"""Send SLA / downtime alert emails: SMTP, then Resend API, then FormSubmit public relay."""
from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage
from typing import Any
from urllib.parse import quote

import httpx

from config import get_settings, Settings

log = logging.getLogger(__name__)


def resolve_alert_recipient(ep: dict[str, Any], settings: Settings) -> str:
    raw = (str(ep.get("alert_email") or "")).strip()
    if raw:
        return raw
    return (settings.default_monitor_alert_email or "").strip()


def _smtp_effective_host(settings: Settings) -> str:
    h = (settings.smtp_host or "").strip()
    if h:
        return h
    if (settings.smtp_user or "").strip() and (settings.smtp_password or "").strip():
        return "smtp.gmail.com"
    return ""


def smtp_configured(settings: Settings) -> bool:
    if not (settings.smtp_user or "").strip() or not (settings.smtp_password or "").strip():
        return False
    return bool(_smtp_effective_host(settings))


def _build_sla_message(
    s: Settings,
    endpoint_name: str,
    url: str,
    status_code: Any,
    error: str | None,
    failure_threshold: int,
    consecutive_failures: int,
) -> tuple[str, str]:
    subj = f"[{s.app_name}] SLA breach / endpoint down: {endpoint_name}"
    body = (
        f"Endpoint: {endpoint_name}\n"
        f"URL: {url}\n"
        f"Consecutive failed checks: {consecutive_failures} (threshold: {failure_threshold})\n"
        f"Status code: {status_code!s}\n"
        f"Error: {error or 'n/a'}\n"
    )
    return subj, body


def _send_via_smtp(
    s: Settings,
    deliver_to: str,
    subj: str,
    body: str,
) -> bool:
    if not smtp_configured(s):
        return False
    host = _smtp_effective_host(s)
    port = int(s.smtp_port or 587)
    from_addr = (s.smtp_from or s.smtp_user or deliver_to).strip()
    msg = EmailMessage()
    msg["Subject"] = subj
    msg["From"] = from_addr
    msg["To"] = deliver_to
    msg.set_content(body)
    try:
        with smtplib.SMTP(host, port, timeout=20) as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.ehlo()
            smtp.login(s.smtp_user, s.smtp_password)
            smtp.send_message(msg)
        log.info("SLA downtime email sent via SMTP to %s", deliver_to)
        return True
    except Exception:
        log.exception("SLA email SMTP failed (to=%s); trying fallbacks if enabled", deliver_to)
        return False


def _send_via_resend(
    s: Settings,
    deliver_to: str,
    subj: str,
    body: str,
) -> bool:
    key = (s.resend_api_key or "").strip()
    if not key:
        return False
    from_addr = (s.resend_from or "onboarding@resend.dev").strip()
    try:
        r = httpx.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={
                "from": from_addr,
                "to": [deliver_to],
                "subject": subj,
                "text": body,
            },
            timeout=30.0,
        )
        if r.is_success:
            log.info("SLA downtime email sent via Resend to %s", deliver_to)
            return True
        log.warning("Resend error %s: %s", r.status_code, (r.text or "")[:500])
    except Exception:
        log.exception("Resend request failed; trying next fallback (to=%s)", deliver_to)
    return False


def _send_via_formsubmit(
    s: Settings,
    deliver_to: str,
    subj: str,
    body: str,
) -> bool:
    if not s.formsubmit_fallback:
        return False
    # Public relay: no API key. Recipient is in the path. First use may need inbox confirmation
    # (see https://formsubmit.co/documentation). _captcha=false for server-to-server.
    try:
        enc = quote(deliver_to, safe="")
        r = httpx.post(
            f"https://formsubmit.co/ajax/{enc}",
            data={
                "_subject": subj,
                "_captcha": "false",
                "name": s.app_name,
                "message": body,
            },
            timeout=35.0,
        )
        if 200 <= r.status_code < 300:
            log.info("SLA downtime email submitted via FormSubmit to %s", deliver_to)
            return True
        log.warning("FormSubmit error %s: %s", r.status_code, (r.text or "")[:500])
    except Exception:
        log.exception("FormSubmit request failed (to=%s)", deliver_to)
    return False


def send_sla_downtime_email(
    to_addr: str,
    *,
    endpoint_name: str,
    url: str,
    status_code: Any,
    error: str | None,
    failure_threshold: int,
    consecutive_failures: int,
) -> bool:
    """Send a single notification. Tries SMTP, then Resend, then FormSubmit. Returns True if one path succeeded."""
    s = get_settings()
    logical = (to_addr or "").strip()
    if not logical:
        log.warning("SLA email skipped: no recipient (set alert_email or DEFAULT_MONITOR_ALERT_EMAIL)")
        return False
    subj, body = _build_sla_message(
        s,
        endpoint_name,
        url,
        status_code,
        error,
        failure_threshold,
        consecutive_failures,
    )
    override = (s.alert_delivery_to_override or "").strip()
    deliver_to = override or logical
    if override and override != logical:
        body = (
            f"{body}\n\n"
            f"---\n"
            f"Logical alert recipient (endpoint / default): {logical}\n"
            f"Delivery override active (ALERT_DELIVERY_TO_OVERRIDE).\n"
        )
        log.info("Alert email delivery override: sending to %s (logical=%s)", deliver_to, logical)

    if _send_via_smtp(s, deliver_to, subj, body):
        return True
    if _send_via_resend(s, deliver_to, subj, body):
        return True
    if _send_via_formsubmit(s, deliver_to, subj, body):
        return True

    if smtp_configured(s):
        log.error(
            "SLA email: SMTP configured but send failed, and other channels did not succeed (deliver_to=%s)",
            deliver_to,
        )
    else:
        log.warning(
            "SLA email not sent (deliver_to=%s, logical=%s). Set RESEND_API_KEY, optional "
            "ALERT_DELIVERY_TO_OVERRIDE=your-resend-inbox, or USE_FORM_SUBMIT_EMAIL_FALLBACK=1.",
            deliver_to,
            logical,
        )
    return False
