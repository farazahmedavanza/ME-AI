"""One-off: test SLA email via Resend with settings from .env (run from repo: python scripts/test_resend_alert.py)."""
from __future__ import annotations

import sys
from pathlib import Path

# Ensure backend/ is on path and .env is loaded before config
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from config import clear_settings_cache, get_settings  # noqa: E402
from monitor_alert_email import send_sla_downtime_email  # noqa: E402

clear_settings_cache()


def main() -> None:
    s = get_settings()
    to_addr = s.default_monitor_alert_email or "meaiavanzahackathon@gmail.com"
    print("Config (no secrets):")
    print("  DEFAULT_MONITOR_ALERT_EMAIL (TO for this test):", to_addr)
    print("  RESEND_FROM (FROM if using Resend):", s.resend_from or "(not set)")
    print("  Resend key present:", bool((s.resend_api_key or "").strip()))
    print("  SMTP configured:", end=" ")
    from monitor_alert_email import smtp_configured

    print(smtp_configured(s))
    print()
    ok = send_sla_downtime_email(
        to_addr,
        endpoint_name="Resend test (scripts/test_resend_alert.py)",
        url="https://httpstat.us/503",
        status_code=503,
        error="intentional test from ME-AI alert path",
        failure_threshold=2,
        consecutive_failures=2,
    )
    print("send_sla_downtime_email returned:", ok)
    if not ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
