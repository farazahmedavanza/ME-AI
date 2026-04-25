"""
Generate 1000+ mock API log entries covering four hackathon scenarios.
Run: python data_generator.py
"""
from __future__ import annotations

import json
import random
import uuid
from collections.abc import Iterator
from datetime import datetime, timedelta, timezone
from pathlib import Path

OUT = Path(__file__).parent / "data" / "api_logs.json"
# Anchor to "now" so a 1h dashboard window always includes the seeded scenarios
BASE = datetime.now(timezone.utc) - timedelta(hours=2, minutes=5)

SERVICES = {
    "payment-gateway": ("/api/v1/payments", "POST", "Payment Gateway API"),
    "fund-transfer": ("/api/v1/transfers", "POST", "Fund Transfer API"),
    "account-balance": ("/api/v1/accounts/balance", "GET", "Account Balance API"),
    "customer-profile": ("/api/v1/customers/profile", "GET", "Customer Profile API"),
    "batch-recon": ("/api/v1/jobs/recon", "POST", "Batch Recon Job"),
}

random.seed(42)


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def iter_logs() -> Iterator[dict]:
    n = 0
    t0 = BASE

    # 1) Payment gateway: 200ms -> 2200ms p95-like climb over 30 min window
    start_pg = t0
    for i in range(400):
        ts = start_pg + timedelta(seconds=i * 4.5)  # spread across ~30 min
        t = i / 399
        # ramp mean latency
        base_ms = lerp(200, 2200, t) + random.gauss(0, 80)
        is_err = random.random() < 0.05
        code = 503 if is_err and random.random() < 0.3 else 200
        if code != 200:
            base_ms = min(base_ms, 500)
        n += 1
        yield {
            "id": str(uuid.uuid4()),
            "timestamp": ts.isoformat().replace("+00:00", "Z"),
            "endpoint": "/api/v1/payments",
            "method": "POST",
            "status_code": code,
            "response_time_ms": max(50, base_ms + random.gauss(0, 40)),
            "error_message": "Service Unavailable" if code == 503 else None,
            "service": "payment-gateway",
            "trace_id": f"tr-{n}",
            "api_label": "Payment Gateway API",
        }

    # 2) Fund transfer: ~15% 503s
    start_ft = t0 + timedelta(minutes=35)
    for i in range(300):
        ts = start_ft + timedelta(seconds=i * 2)
        is_503 = random.random() < 0.15
        code = 503 if is_503 else 200
        if code == 200:
            rt = random.lognormvariate(4.0, 0.35)  # ~55ms
        else:
            rt = random.uniform(80, 400)
        n += 1
        yield {
            "id": str(uuid.uuid4()),
            "timestamp": ts.isoformat().replace("+00:00", "Z"),
            "endpoint": "/api/v1/transfers",
            "method": "POST",
            "status_code": code,
            "response_time_ms": rt,
            "error_message": "Service Unavailable" if code == 503 else None,
            "service": "fund-transfer",
            "trace_id": f"tr-{n}",
            "api_label": "Fund Transfer API",
        }

    # 3) Account balance: zero errors, 40% slower than baseline
    start_ab = t0 + timedelta(minutes=5)
    baseline = 80
    for i in range(250):
        ts = start_ab + timedelta(seconds=i * 1.2)
        rt = baseline * 1.4 + abs(random.gauss(0, 25))
        n += 1
        yield {
            "id": str(uuid.uuid4()),
            "timestamp": ts.isoformat().replace("+00:00", "Z"),
            "endpoint": "/api/v1/accounts/balance",
            "method": "GET",
            "status_code": 200,
            "response_time_ms": rt,
            "error_message": None,
            "service": "account-balance",
            "trace_id": f"tr-{n}",
            "api_label": "Account Balance API",
        }

    # 4) Customer profile — healthy noise
    for i in range(200):
        ts = t0 + timedelta(minutes=10) + timedelta(seconds=i * 1.0)
        n += 1
        yield {
            "id": str(uuid.uuid4()),
            "timestamp": ts.isoformat().replace("+00:00", "Z"),
            "endpoint": "/api/v1/customers/profile",
            "method": "GET",
            "status_code": 200,
            "response_time_ms": max(20, random.lognormvariate(3.7, 0.25) * 30),
            "error_message": None,
            "service": "customer-profile",
            "trace_id": f"tr-{n}",
            "api_label": "Customer Profile API",
        }

    # 5) Batch job — longer "runs" in log stream (higher response_time_ms as proxy)
    for i in range(150):
        ts = t0 + timedelta(hours=1) + timedelta(seconds=i * 5)
        n += 1
        # simulate batch taking longer: responses stretch 3x
        rt = random.uniform(800, 4000) if random.random() < 0.2 else random.uniform(300, 900)
        code = 200 if random.random() > 0.02 else 500
        yield {
            "id": str(uuid.uuid4()),
            "timestamp": ts.isoformat().replace("+00:00", "Z"),
            "endpoint": "/api/v1/jobs/recon",
            "method": "POST",
            "status_code": code,
            "response_time_ms": rt,
            "error_message": "Batch step timeout" if code == 500 else None,
            "service": "batch-recon",
            "trace_id": f"tr-{n}",
            "api_label": "Batch Recon Job",
        }


def main() -> None:
    logs = list(iter_logs())
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(logs, indent=2), encoding="utf-8")
    print(f"Wrote {len(logs)} entries to {OUT}")


if __name__ == "__main__":
    main()
