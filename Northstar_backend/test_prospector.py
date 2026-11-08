"""Prospector — stock-first product discovery, driven through the real app.

Prospector's API surface is the catalogue stream in ``main.py`` (the route at
``/api/v1/catalog/pull`` is documented there as "Prospector pull path"):

    GET  /api/v1/catalog/stocked   free read of fresh, live-stocked rows
    GET  /api/v1/catalog/pull      stock-first read; a live pull needs the §3 gate
    POST /api/v1/catalog/stock     pull + persist; offline unless the gate is armed

Each test drives the real FastAPI routes with ``TestClient`` against a throwaway
SQLite warehouse. Nothing touches the network: the live path is asserted as a
refusal, which is exactly what the gate is for.
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

#: The one live gate the free-tier router reads (free_tier_router.LIVE_GATE_ENV).
GATE_ENV = "GOLDEN_GOOSE_LIVE_OPERATOR_APPROVED"


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


def _seed(warehouse, asin, title, *, ttl_seconds=3600, **extra):
    """Write a real live row through the real warehouse API."""
    row = {
        "asin": asin,
        "title": title,
        "brand": "Acme",
        "amazon_price": 25.0,
        "net_profit": 15.0,
        "monthly_sales_estimate": 3000,
        "weight_lbs": 1.0,
        "seller_count": 0,
    }
    row.update(extra)
    return warehouse.products.upsert_live(
        row, provider_id="test-fixture", ttl_seconds=ttl_seconds
    )


def test_stocked_serves_only_fresh_live_rows(db):
    _seed(db, "B0FRESH0001", "Acme Widget Deluxe")
    _seed(db, "B0EXPIRED01", "Acme Widget Expired", ttl_seconds=-60)
    db.products.upsert({"asin": "B0DEMO00001", "title": "Demo Row"})

    response = client.get("/api/v1/catalog/stocked")

    assert response.status_code == 200
    body = response.json()
    assert body["contract"] == "bff/v1"
    assert body["status"] == "ok"
    assert body["error"] is None
    assert body["meta"]["service"] == "catalog"
    data = body["data"]
    assert {row["asin"] for row in data["rows"]} == {"B0FRESH0001"}
    assert data["count"] == 1


def test_stocked_limit_is_applied(db):
    for index in range(3):
        _seed(db, f"B0LIMIT000{index}", f"Acme Widget {index}")

    data = client.get("/api/v1/catalog/stocked", params={"limit": 2}).json()["data"]

    assert data["count"] == 2
    assert len(data["rows"]) == 2


def test_pull_hits_stock_without_touching_a_provider(db):
    _seed(db, "B0PULL00001", "Acme Widget Deluxe")

    data = client.get("/api/v1/catalog/pull", params={"query": "widget"}).json()["data"]

    assert data["source"] == "stock"
    assert data["pulled"] is None
    assert [row["asin"] for row in data["rows"]] == ["B0PULL00001"]


def test_pull_miss_is_reported_empty_not_invented(db):
    _seed(db, "B0PULL00002", "Acme Widget Deluxe")

    data = client.get(
        "/api/v1/catalog/pull", params={"query": "widget unicorn"}
    ).json()["data"]

    assert data["source"] == "empty"
    assert data["rows"] == []
    assert data["pulled"] is None


@pytest.mark.parametrize("live", [False, True])
def test_stock_refuses_to_dispatch_without_operator_approval(db, monkeypatch, live):
    monkeypatch.delenv(GATE_ENV, raising=False)

    response = client.post(
        "/api/v1/catalog/stock", json={"queries": ["acme widget"], "live": live}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["contract"] == "bff/v1"
    data = body["data"]
    result = data["results"][0]
    assert result["query"] == "acme widget"
    assert result["mode"] == "blocked"
    assert result["ok"] is False
    assert "gate" in (result["error"] or "").lower()
    assert result["stocked"] == 0
    assert data["total_stocked"] == 0
    # A refused pull is not a pull: no audit row and nothing written.
    assert db.live_pulls.count() == 0
    assert db.products.count_live() == 0


def test_stock_requires_queries(db):
    response = client.post("/api/v1/catalog/stock", json={"live": False})

    assert response.status_code == 422
    assert "queries" in response.text
