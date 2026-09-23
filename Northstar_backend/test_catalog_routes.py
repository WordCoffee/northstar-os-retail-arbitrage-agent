"""Phase B — live catalog route contract tests (offline)."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi.testclient import TestClient  # noqa: E402

from main import app  # noqa: E402

c = TestClient(app)


def _ok(resp):
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["contract"] == "bff/v1" and body["status"] == "ok"
    return body["data"]


def test_catalog_stocked_envelope():
    data = _ok(c.get("/api/v1/catalog/stocked?limit=5"))
    assert "rows" in data and "count" in data


def test_catalog_stock_offline_no_live():
    data = _ok(c.post("/api/v1/catalog/stock", json={"queries": ["coffee beans"], "live": False}))
    assert data["total_stocked"] == 0
    assert data["results"][0]["query"] == "coffee beans"


def test_catalog_pull_stock_first():
    data = _ok(c.get("/api/v1/catalog/pull?query=definitely-not-stocked-xyz"))
    assert data["source"] in ("empty", "stock", "live", "live_empty")


def test_catalog_wholesale_stock_offline_no_caller():
    data = _ok(c.post("/api/v1/catalog/wholesale/stock", json={"query": "coffee", "live": False}))
    assert data["mode"] == "no_caller" and data["added"] == 0


def test_catalog_wholesale_products_envelope():
    data = _ok(c.get("/api/v1/catalog/wholesale/products"))
    assert "rows" in data and "count" in data
