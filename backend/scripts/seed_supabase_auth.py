#!/usr/bin/env python3
"""Create or update demo Auth users on Supabase (requires service role key).

Usage (from repo root or backend):
  pip install httpx python-dotenv  # httpx is already a backend dependency
  set SUPABASE_URL / SUPABASE_KEY in backend/.env (SUPABASE_KEY = service role)
  python backend/scripts/seed_supabase_auth.py

Demo accounts (password for all: DemoME2026!):
  - demo@me-ai.local
  - ops@me-ai.local
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

try:
    import httpx
except ImportError:
    print("Install httpx: pip install httpx", file=sys.stderr)
    sys.exit(1)

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None  # type: ignore

DEMO_PASSWORD = "DemoME2026!"
DEMO_EMAILS = ("demo@me-ai.local", "ops@me-ai.local")


def _load_env() -> None:
    if not load_dotenv:
        return
    for p in (
        Path(__file__).resolve().parent.parent / ".env",
        Path(__file__).resolve().parent.parent.parent / "backend" / ".env",
    ):
        if p.is_file():
            load_dotenv(p)
            return


def _admin_headers(service_key: str) -> dict[str, str]:
    return {
        "apikey": service_key,
        "Authorization": f"Bearer {service_key}",
        "Content-Type": "application/json",
    }


def main() -> int:
    _load_env()
    base = (os.getenv("SUPABASE_URL") or "").rstrip("/")
    key = (os.getenv("SUPABASE_KEY") or "").strip()
    if not base or not key:
        print(
            "Set SUPABASE_URL and SUPABASE_KEY (service role) in backend/.env",
            file=sys.stderr,
        )
        return 1

    h = _admin_headers(key)
    list_url = f"{base}/auth/v1/admin/users"

    with httpx.Client(timeout=60.0) as client:
        users: list[dict] = []
        page = 1
        while True:
            r = client.get(list_url, headers=h, params={"per_page": 200, "page": page})
            if r.status_code != 200:
                print(f"List users failed {r.status_code}: {r.text[:500]}", file=sys.stderr)
                return 1
            body = r.json()
            if isinstance(body, list):
                batch = body
            else:
                batch = body.get("users")
            if not batch:
                break
            users.extend(batch)
            if len(batch) < 200:
                break
            page += 1

        by_email = {str(u.get("email") or "").lower(): u for u in users}

        for email in DEMO_EMAILS:
            ep = f"{base}/auth/v1/admin/users"
            existing = by_email.get(email.lower())
            if existing:
                uid = existing.get("id")
                if not uid:
                    print(f"Skip {email}: no id", file=sys.stderr)
                    continue
                up = f"{ep}/{uid}"
                pr = client.put(
                    up, headers=h, json={"password": DEMO_PASSWORD, "email_confirm": True}
                )
                if pr.status_code == 405:
                    pr = client.patch(
                        up, headers=h, json={"password": DEMO_PASSWORD, "email_confirm": True}
                    )
                if pr.status_code in (200, 201):
                    print(f"Updated password for {email} ({uid})")
                else:
                    print(
                        f"Update {email} failed {pr.status_code}: {pr.text[:500]}",
                        file=sys.stderr,
                    )
            else:
                pr = client.post(
                    ep,
                    headers=h,
                    json={
                        "email": email,
                        "password": DEMO_PASSWORD,
                        "email_confirm": True,
                    },
                )
                if pr.status_code in (200, 201):
                    print(f"Created {email}")
                else:
                    print(
                        f"Create {email} failed {pr.status_code}: {pr.text[:500]}",
                        file=sys.stderr,
                    )

    print("Done. Use these to sign in from the app (Supabase email/password).")
    for e in DEMO_EMAILS:
        print(f"  {e} / {DEMO_PASSWORD}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
