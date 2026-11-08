"""Sourcing — landed cost, supplier discovery and wholesale stock, offline.

Sourcing sits on the supplier + wholesale routes in ``main.py``:

    POST /api/suppliers/analyze                  pre-account cost-benefit maths
    POST /api/suppliers/discover                 supplier discovery (offline seed)
    POST /api/v1/catalog/wholesale/stock         wholesaler pull + persist
    GET  /api/v1/catalog/wholesale/products      stocked wholesaler SKUs
    POST /api/suppliers                          create/update a supplier
    POST /api/suppliers/{sid}/products           add SKUs, optionally analyse

The tests check the arithmetic a buyer would act on (unit COGS, landed cost,
net profit, ROI, verdict), the honest refusal when no wholesaler caller exists,
and the 404/400 edges. No network, no keys, temp SQLite only.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

BACKEND = Path(__file__).resolve().parents[1] / "Northstar_backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

import data_layer  # noqa: E402
import main  # noqa: E402

client = TestClient(main.app)


@pytest.fixture()
def db(tmp_path, monkeypatch):
    """A throwaway SQLite warehouse behind the real route handlers."""
    monkeypatch.setattr(data_layer, "_SQLITE_PATH", tmp_path / "northstar.db")
    monkeypatch.setattr(data_layer, "_get_postgres_url", lambda: None)
    monkeypatch.setattr(data_layer, "_db_instance", None)
    layer = data_layer.get_db()
    try:
        yield data_layer.get_northstar_db()
    finally:
        layer.close()


def _analyze(product, match=None):
    response = client.post(
        "/api/suppliers/analyze",
        json={"supplier_product": product, "amazon_match": match or {}},
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]


def test_cost_benefit_computes_landed_cost_and_verdict():
    data = _analyze(
        {
            "product_name": "Advil 200ct",
            "wholesale_price": 18.5,
            "unit_count": 6,
            "weight_lbs": 1.5,
        },
        {"amazon_price": 34.99},
    )

    # Unit COGS is wholesale price spread across the sellable units.
    assert data["unit_cogs"] == pytest.approx(18.5 / 6, abs=1e-4)
    assert data["referral_fee_estimate"] == pytest.approx(5.25, abs=1e-9)
    assert data["inbound_cost_estimate"] == 0.35
    assert data["landed_cost"] == pytest.approx(18.5 / 6 + 0.35, abs=1e-3)
    assert data["fba_fee_estimate"] > 0

    expected_net = (
        data["amazon_price"]
        - data["landed_cost"]
        - data["referral_fee_estimate"]
        - data["fba_fee_estimate"]
    )
    assert data["estimated_net_profit"] == pytest.approx(expected_net, abs=1e-2)
    assert data["estimated_roi_pct"] == pytest.approx(
        data["estimated_net_profit"] / data["landed_cost"] * 100, abs=0.5
    )
    assert data["profit_margin_pct"] == pytest.approx(
        data["estimated_net_profit"] / data["amazon_price"] * 100, abs=0.5
    )

    assert data["decision_flag"] == "viable"
    assert data["meets_threshold"] is True
    assert data["min_roi_threshold"] == 20.0
    assert any("Meets thresholds" in note for note in data["notes"])


def test_cost_benefit_without_a_retail_price_asks_for_review():
    data = _analyze({"product_name": "Unknown Widget", "wholesale_price": 5.0})

    assert data["decision_flag"] == "needs_manual_review"
    assert data["meets_threshold"] is False
    assert data["amazon_price"] is None
    assert data["estimated_net_profit"] is None
    assert data["estimated_roi_pct"] is None
    assert any("Amazon price" in note for note in data["notes"])


def test_cost_benefit_without_a_wholesale_price_asks_for_review():
    data = _analyze({"product_name": "No Price Widget"})

    assert data["unit_cogs"] is None
    assert data["decision_flag"] == "needs_manual_review"
    assert data["meets_threshold"] is False
    assert any("Missing wholesale price" in note for note in data["notes"])


def test_cost_benefit_rejects_an_unprofitable_deal():
    data = _analyze(
        {
            "product_name": "Overpriced Widget",
            "wholesale_price": 30.0,
            "unit_count": 1,
            "weight_lbs": 0.4,
        },
        {"amazon_price": 32.0},
    )

    assert data["estimated_net_profit"] < 0
    assert data["decision_flag"] == "reject"
    assert data["meets_threshold"] is False
    assert any("Rejected" in note for note in data["notes"])


def test_cost_benefit_requires_a_supplier_product():
    response = client.post("/api/suppliers/analyze", json={})

    assert response.status_code == 400
    assert response.json()["detail"] == "supplier_product is required"


def test_supplier_discovery_is_offline_and_seeded():
    response = client.post("/api/suppliers/discover", json={"category": "otc_health"})

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["mode"] == "offline"
    assert data["live_requested"] is False
    assert data["live_armed"] is False
    assert data["error"] is None
    assert data["suppliers"], "the offline seed must return supplier profiles"
    assert all(s["name"] for s in data["suppliers"])
    assert any(
        "otc_health" in (s.get("categories_supplied") or []) for s in data["suppliers"]
    )
    # Nothing was persisted because persist was not requested.
    assert data["persisted_ids"] == []


@pytest.mark.parametrize("live", [False, True])
def test_wholesale_stock_without_a_caller_refuses_to_invent_rows(db, live):
    response = client.post(
        "/api/v1/catalog/wholesale/stock", json={"query": "vitamins", "live": live}
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["supplier_id"] == "tundra"
    assert data["added"] == 0
    assert data["ok"] is False
    assert data["mode"] == "no_caller"
    assert "caller" in (data["error"] or "")
    # A refused pull writes nothing to the supplier warehouse.
    stocked = client.get("/api/v1/catalog/wholesale/products").json()["data"]
    assert stocked["count"] == 0
    assert stocked["rows"] == []


def test_supplier_workflow_persists_products_and_runs_cost_benefit(db):
    created = client.post(
        "/api/suppliers",
        json={
            "id": "acme-src",
            "name": "Acme Source",
            "categories_supplied": ["otc_health"],
        },
    )
    assert created.status_code == 200
    assert created.json()["data"]["id"] == "acme-src"

    added = client.post(
        "/api/suppliers/acme-src/products",
        json={
            "products": [
                {
                    "supplier_sku": "SKU-1",
                    "product_name": "Advil 200ct",
                    "wholesale_price": 18.5,
                    "unit_count": 6,
                    "weight_lbs": 1.5,
                }
            ],
            "analyze": True,
            "amazon_prices": {"SKU-1": 34.99},
        },
    )

    assert added.status_code == 200
    body = added.json()["data"]
    assert body["added"] == 1
    assert len(body["analyses"]) == 1
    analysis = body["analyses"][0]
    assert analysis["decision_flag"] == "viable"
    assert analysis["landed_cost"] > 0
    assert analysis["estimated_net_profit"] > 0

    listing = client.get("/api/suppliers/acme-src/products").json()["data"]
    assert listing["count"] == 1
    assert listing["products"][0]["supplier_sku"] == "SKU-1"


def test_supplier_product_routes_reject_unknown_supplier_and_empty_list(db):
    assert client.get("/api/suppliers/nope/products").status_code == 404
    missing = client.post(
        "/api/suppliers/nope/products", json={"products": [{"product_name": "x"}]}
    )
    assert missing.status_code == 404

    client.post("/api/suppliers", json={"id": "acme-src", "name": "Acme Source"})
    empty = client.post("/api/suppliers/acme-src/products", json={"products": []})
    assert empty.status_code == 400
    assert empty.json()["detail"] == "products must be a non-empty list"
