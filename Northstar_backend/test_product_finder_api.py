"""The /api/products/finder contract ProductFinder.jsx now depends on.

The page added a real call on 2026-11-09. These tests pin the response shape it
maps, the exact-ASIN lookup it performs client-side, and the honest-miss case -
without them the wiring could rot back into a comment.

No network: the candidate cache is a temp file and the warehouse is a temp
SQLite store. The route is cache-only and makes no provider call.
"""

from __future__ import annotations

import json
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

CANDIDATE = {
    "asin": "B0CONTRACT1",
    "name": "Contract Probe Widget",
    "brand": "Acme",
    "amazon_price": 29.48,
    "net_profit": 11.0,
    "monthly_sales_estimate": 2400,
    "weight_lbs": 1.0,
    "fba_sellers": 1,
}
SECOND = {
    "asin": "B0CONTRACT2",
    "name": "Second Probe Widget",
    "brand": "Acme",
    "amazon_price": 19.99,
    "net_profit": 1.0,
    "monthly_sales_estimate": 50,
    "weight_lbs": 4.0,
    "fba_sellers": 9,
}


@pytest.fixture()
def db(tmp_path, monkeypatch):
    monkeypatch.setattr(data_layer, "_SQLITE_PATH", tmp_path / "northstar.db")
    monkeypatch.setattr(data_layer, "_get_postgres_url", lambda: None)
    monkeypatch.setattr(data_layer, "_db_instance", None)
    layer = data_layer.get_db()
    try:
        yield data_layer.get_northstar_db()
    finally:
        layer.close()


def _write_cache(tmp_path, products):
    path = tmp_path / "finder-cache.json"
    path.write_text(json.dumps({"products": products}), encoding="utf-8")
    return path


def test_finder_returns_rows_the_page_can_map(db, tmp_path, monkeypatch):
    cache = _write_cache(tmp_path, [CANDIDATE, SECOND])
    monkeypatch.setenv("SCANNER_SEARCH_CACHE_PATH", str(cache))

    response = client.get("/api/products/finder", params={"limit": 100})

    assert response.status_code == 200
    body = response.json()
    # The UI accepts both envelope shapes; the server currently uses bff/v1.
    assert body["contract"] == "bff/v1"
    data = body["data"]
    assert data["filter_source"] == "cache-only"
    assert data["candidate_count"] == 2
    assert len(data["evaluated"]) == 2

    rows = {row["asin"]: row for row in data["evaluated"]}
    assert set(rows) == {"B0CONTRACT1", "B0CONTRACT2"}
    row = rows["B0CONTRACT1"]
    # Exactly the fields the page maps into its table.
    assert row["name"] == "Contract Probe Widget"
    assert row["amazon_price"] == 29.48
    assert isinstance(row["universal_filter_passed"], bool)
    rejected = rows["B0CONTRACT2"]
    assert rejected["universal_filter_passed"] is False
    assert isinstance(rejected["universal_filter_reasons"], list)
    assert rejected["universal_filter_reasons"]


def test_exact_asin_lookup_finds_one_row_and_a_missing_asin_is_absent(db, tmp_path, monkeypatch):
    cache = _write_cache(tmp_path, [CANDIDATE, SECOND])
    monkeypatch.setenv("SCANNER_SEARCH_CACHE_PATH", str(cache))
    evaluated = client.get("/api/products/finder").json()["data"]["evaluated"]

    def lookup(asin):
        wanted = asin.strip().upper()
        return [row for row in evaluated if str(row.get("asin", "")).upper() == wanted]

    assert len(lookup("b0contract1")) == 1
    assert lookup("B0NOTCACHED") == []


def test_duplicate_asins_are_deduped_before_scoring(db, tmp_path, monkeypatch):
    cache = _write_cache(tmp_path, [CANDIDATE, dict(CANDIDATE, name="Duplicate")])
    monkeypatch.setenv("SCANNER_SEARCH_CACHE_PATH", str(cache))

    data = client.get("/api/products/finder").json()["data"]

    assert data["candidate_count"] == 1
    assert len({row["asin"] for row in data["evaluated"]}) == 1
