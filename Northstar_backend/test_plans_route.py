"""A2 tests — GET /api/v1/plans and GET /api/v1/plans/{plan_id}.

The list endpoint must keep returning the catalog (now projected from
shared/subscription-plans.json via auth.PLAN_ENTITLEMENTS), and the new
per-plan endpoint must resolve known ids and 404 on unknown ids.

Run: python -m pytest Northstar_backend/test_plans_route.py -q
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi.testclient import TestClient  # noqa: E402

import auth  # noqa: E402
from main import app  # noqa: E402


@pytest.fixture
def client():
    return TestClient(app)


def test_plans_list_matches_catalog(client):
    resp = client.get("/api/v1/plans")
    assert resp.status_code == 200
    data = resp.json()
    assert data["plans"] == auth.PLAN_ENTITLEMENTS
    assert set(data["plans"]) == {"foundation", "scout", "mover", "autothink"}


def test_plans_list_prices_and_gates_preserved(client):
    data = client.get("/api/v1/plans").json()["plans"]
    assert data["foundation"]["price"] == 0
    assert data["scout"]["price"] == 29
    assert data["mover"]["price"] == 79
    assert data["autothink"]["price"] == 149
    assert data["autothink"]["gates"] == [
        "sourcescout_live_pull",
        "sourcescout_enrich",
        "listingforge_copy",
        "listingforge_media",
        "adpilot_ads_read",
        "adpilot_bulk_exec",
        "socialpulse_attrib",
        "socialpulse_publish",
        "autothink_workspace",
    ]


def test_plan_by_id(client):
    resp = client.get("/api/v1/plans/scout")
    assert resp.status_code == 200
    assert resp.json()["plan"] == auth.PLAN_ENTITLEMENTS["scout"]


def test_plan_by_id_autothink(client):
    resp = client.get("/api/v1/plans/autothink")
    assert resp.status_code == 200
    assert resp.json()["plan"]["name"] == "AutothinK"
    assert resp.json()["plan"]["price"] == 149


def test_plan_by_id_unknown_404(client):
    resp = client.get("/api/v1/plans/nope_plan")
    assert resp.status_code == 404
    assert "Unknown plan" in resp.json()["detail"]


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))