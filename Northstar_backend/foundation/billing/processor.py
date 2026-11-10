"""Test-mode payment processor adapter (1C-06 master slice / Phase A).

Redirect-based hosted checkout ONLY — no embedded card fields, no card data
ever stored or handled. The processor is a fake/local adapter: it creates a
hosted checkout intent (a local page with a single "Confirm test
subscription" button) and emits HMAC-signed webhook events. Signature
verification + exactly-once settlement live in BillingService.

NEVER configured with real payment keys. Real live-key enablement requires
explicit owner authorization.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
from datetime import datetime, timezone


def webhook_secret() -> str:
    """Test-mode webhook secret (NEVER a real key)."""
    return os.environ.get("NORTHSTAR_TEST_WEBHOOK_SECRET",
                          "test-webhook-secret-not-real")


def sign_event(payload: dict, secret: str) -> str:
    body = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hmac.new(secret.encode("utf-8"), body.encode("utf-8"),
                    hashlib.sha256).hexdigest()


def verify_signature(payload: dict, signature: str, secret: str) -> bool:
    expected = sign_event(payload, secret)
    return hmac.compare_digest(expected, signature or "")


def build_event(*, event_id: str, event_type: str, **fields) -> dict:
    return {"id": event_id, "type": event_type,
            "timestamp": datetime.now(timezone.utc).isoformat(), **fields}


def payload_hash(payload: dict) -> str:
    body = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(body.encode("utf-8")).hexdigest()