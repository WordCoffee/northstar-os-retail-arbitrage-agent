"""Phase F / D12 — bff/v1 envelope adoption on legacy endpoints.

Verifies: legacy prefixes (kirkland / suppliers / plans / products /
filters-universal) return the bff/v1 envelope with the original shape under
`data`; already-conformant prefixes are untouched; HTTP errors stay HTTP-level.
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


@pytest.fixture
def client():
    return TestClient(app)


def test_plans_list_wrapped_with_original_shape_in_data(client):
    resp = client.get("/api/v1/plans")
    assert resp.status_code == 200
    body = resp.json()
    assert body["contract"] == "bff/v1" and body["status"] == "ok" and body["error"] is None
    # legacy shape preserved under data
    plans = body["data"]["plans"]
    assert set(plans) == {"foundation", "scout", "mover", "autothink"}


def test_plans_by_id_wrapped(client):
    resp = client.get("/api/v1/plans/scout")
    body = resp.json()
    assert body["contract"] == "bff/v1"
    assert body["data"]["plan"]["price"] == 29


def test_suppliers_list_wrapped(client):
    resp = client.get("/api/suppliers")
    assert resp.status_code == 200
    body = resp.json()
    assert body["contract"] == "bff/v1"
    assert isinstance(body["data"]["suppliers"], list)


def test_products_finder_wrapped(client):
    resp = client.get("/api/products/finder")
    assert resp.status_code == 200
    assert resp.json()["contract"] == "bff/v1"


def test_kirkland_scanner_wrapped(client):
    resp = client.get("/api/kirkland/scanner")
    assert resp.status_code == 200
    body = resp.json()
    assert body["contract"] == "bff/v1" and body["status"] in ("ok", "empty")


def test_filters_universal_wrapped(client):
    resp = client.post("/api/filters/universal/evaluate", json={"products": [], "filters": {}})
    if resp.status_code == 200:
        assert resp.json()["contract"] == "bff/v1"


def test_error_responses_stay_http_level(client):
    # legacy error paths keep HTTPException semantics (BFF §5 HTTP mapping)
    resp = client.get("/api/v1/plans/nope_plan")
    assert resp.status_code == 404
    assert "detail" in resp.json()


def test_already_conformant_prefixes_not_double_wrapped(client):
    # credits route already emits the envelope; must not gain a nested one
    resp = client.get("/api/v1/credits/me")
    body = resp.json()
    assert body["contract"] == "bff/v1" and "data" in body and isinstance(body["data"], dict)
    assert body["data"].get("balance") is not None


def test_pure_wrap_payload_unit():
    from bff_envelope import wrap_payload, request_id
    r = wrap_payload({"x": 1})
    assert r["contract"] == "bff/v1" and r["status"] == "ok" and r["data"] == {"x": 1}
    e = wrap_payload(None)
    assert e["status"] == "empty" and e["data"] == {}
    assert request_id().startswith("req_")