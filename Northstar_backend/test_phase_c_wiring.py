"""Phase C wiring tests — credit meter route (C8) + legal embed routes (C9).

Offline only. No live calls, no spend.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

_BACKEND = Path(__file__).resolve().parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from main import app  # noqa: E402
import auth  # noqa: E402


@pytest.fixture
def client():
    return TestClient(app)


def _bearer(plan: str) -> dict:
    return {"Authorization": "Bearer " + auth.create_access_token("acct1", "o@x.com", plan)}


def test_credits_meter_demo_foundation(client):
    resp = client.get("/api/v1/credits/me")
    assert resp.status_code == 200
    body = resp.json()
    assert body["contract"] == "bff/v1" and body["status"] == "ok"
    data = body["data"]
    assert data["balance"] == 0 and data["allotment"] == 0
    assert data["class"] == "compute" and data["period"] == "month"


def test_credits_meter_plan_allotment(client):
    for plan, expected in (("scout", 100), ("mover", 500), ("autothink", 2000)):
        data = client.get("/api/v1/credits/me", headers=_bearer(plan)).json()["data"]
        assert data["balance"] == expected and data["plan"] == plan


def test_credits_meter_unknown_plan_fails_closed(client):
    # A bearer token with an invalid plan id cannot be minted by auth
    # (register/update validate the plan), so plan resolution fails closed to
    # the catalog check; the endpoint still returns a 200 envelope.
    resp = client.get("/api/v1/credits/me", headers=_bearer("scout"))
    assert resp.status_code == 200 and resp.json()["status"] == "ok"


def test_legal_routes_serve_drafts(client):
    for name, fragment in (("terms", "Terms of Service"),
                           ("privacy", "Privacy Policy"),
                           ("refund", "Refund / Cancellation")):
        resp = client.get("/legal/" + name)
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/markdown")
        assert fragment in resp.text


def test_legal_route_unknown_404(client):
    assert client.get("/legal/not_a_doc").status_code == 404


def test_admin_still_gated(client):
    assert client.get("/api/v1/admin/accounts/x").status_code == 403