"""Phase A / A3 — live data warehouse + live catalog tests (offline)."""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import data_layer  # noqa: E402
import live_catalog  # noqa: E402
import wholesale_catalog as wc  # noqa: E402


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    """A fresh DataLayer on a temp SQLite file, installed as the singleton."""
    monkeypatch.setattr(data_layer, "_SQLITE_PATH", tmp_path / "test.db")
    monkeypatch.setattr(data_layer, "_db_instance", None)
    layer = data_layer.DataLayer()
    monkeypatch.setattr(data_layer, "_db_instance", layer)
    yield layer


# --- schema migration ---

def test_products_has_live_columns(temp_db):
    cur = temp_db.execute("PRAGMA table_info(products)")
    cols = {row[1] for row in cur.fetchall()}
    for c in ("data_kind", "provider_id", "fetched_at", "fresh_until"):
        assert c in cols


def test_live_pulls_table_exists(temp_db):
    cur = temp_db.execute("PRAGMA table_info(live_pulls)")
    cols = {row[1] for row in cur.fetchall()}
    assert {"id", "query", "task_type", "provider_id", "rows_returned"} <= cols


# --- ProductsDB live ops ---

def test_upsert_live_sets_provenance(temp_db):
    p = data_layer.ProductsDB(temp_db)
    p.upsert_live({"asin": "B0TEST0001", "title": "Test Widget", "amazon_price": 9.99},
                  provider_id="chocodata", ttl_seconds=3600)
    row = p.get_by_asin("B0TEST0001")
    assert row["data_kind"] == "live"
    assert row["provider_id"] == "chocodata"
    assert row["fetched_at"] and row["fresh_until"]


def test_list_stocked_excludes_demo_and_stale(temp_db):
    p = data_layer.ProductsDB(temp_db)
    p.upsert_live({"asin": "B0LIVE001", "title": "Live One"}, provider_id="chocodata", ttl_seconds=3600)
    p.upsert_live({"asin": "B0STALE01", "title": "Stale One"}, provider_id="chocodata", ttl_seconds=-10)
    p.upsert({"asin": "B0DEMO001", "title": "Demo One"})  # data_kind defaults to 'demo'
    fresh = {r["asin"] for r in p.list_stocked(fresh_only=True)}
    assert "B0LIVE001" in fresh
    assert "B0STALE01" not in fresh
    assert "B0DEMO001" not in fresh
    assert p.count_live() == 2  # both live rows regardless of freshness


# --- LivePullsDB ---

def test_live_pulls_record_and_recent(temp_db):
    lp = data_layer.LivePullsDB(temp_db)
    lp.record(query="gift for mom", task_type="amazon_search", provider_id="chocodata", rows_returned=60)
    lp.record(query="coffee", task_type="amazon_search", provider_id="bright_data", rows_returned=0, ok=False, error="429")
    assert lp.count() == 2
    recent = lp.recent(limit=5)
    assert len(recent) == 2
    assert any(r["provider_id"] == "chocodata" for r in recent)


# --- live_catalog ---

def test_normalize_row_requires_asin():
    assert live_catalog._normalize_row({"title": "no asin"}) is None
    row = live_catalog._normalize_row({"asin": "B01", "title": "T", "price": 5.0}, query="q")
    assert row["asin"] == "B01" and row["amazon_price"] == 5.0
    assert row["data_sources"]["source"] == "live_search"


def test_get_or_pull_offline_empty(temp_db):
    out = live_catalog.get_or_pull("nonexistent product xyz", live=False)
    assert out["source"] == "empty" and out["rows"] == []


def test_get_or_pull_stock_hit(temp_db):
    data_layer.ProductsDB(temp_db).upsert_live(
        {"asin": "B0STOCK01", "title": "Sumatra Coffee Beans 2lb"}, provider_id="chocodata", ttl_seconds=3600
    )
    out = live_catalog.get_or_pull("coffee beans", live=False)
    assert out["source"] == "stock"
    assert out["rows"][0]["asin"] == "B0STOCK01"


def test_stock_offline_does_not_pull(temp_db):
    """live=False must never fire a provider call — 0 stocked, no caller needed."""
    out = live_catalog.stock("anything", live=False)
    assert out["stocked"] == 0


# --- wholesale catalog (Tundra) ---

def test_normalize_wholesale_row_requires_sku_or_name():
    assert wc.normalize_wholesale_row({"brand": "X"}) is None
    row = wc.normalize_wholesale_row({"sku": "SKU1", "name": "Widget", "price": 4.5})
    assert row["supplier_sku"] == "SKU1" and row["wholesale_price"] == 4.5


def test_stock_supplier_catalog_persists(temp_db):
    summary = wc.stock_supplier_catalog(wc.TUNDRA, [
        {"sku": "T-1", "name": "Sumatra Beans 5lb", "price": 12.0, "category": "grocery"},
        {"sku": "T-2", "name": "Ceramic Mug 12oz", "price": 3.25},
        {"brand": "brand-only, no sku/name"},  # skipped
    ])
    assert summary["supplier_id"] == "tundra"
    assert summary["added"] == 2 and summary["skipped"] == 1
    stocked = wc.list_stocked_supplier_products("tundra")
    assert {r["supplier_sku"] for r in stocked} == {"T-1", "T-2"}


def test_stock_wholesale_no_caller_offline(temp_db):
    out = wc.stock_wholesale("any", live=False)
    assert out["mode"] == "no_caller" and out["added"] == 0 and out["ok"] is False


# --- stock runner CLI ---

def test_stock_runner_offline(temp_db, capsys):
    import stock_runner
    rc = stock_runner.main(["--query", "widget"])
    assert rc == 0
    out = capsys.readouterr().out
    assert '"live": false' in out and '"total_stocked": 0' in out
