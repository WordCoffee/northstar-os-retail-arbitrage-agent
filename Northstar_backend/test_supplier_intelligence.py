"""Tests for the supplier intelligence module (Phase 1).

Covers: SuppliersDB persistence, pre-account cost-benefit analysis, supplier
discovery (offline seed + live gating), catalog ingestion (CSV/HTML/JSON-LD),
and the end-to-end supplier pipeline.
"""

import json
import sqlite3

import pytest

import data_layer
from data_layer import DataLayer, SuppliersDB
from analysis.supplier_cost_benefit import (
    MARGINAL,
    MANUAL_REVIEW,
    REJECT,
    VIABLE,
    SupplierCostBenefitAnalyzer,
    analyze_supplier_product,
    decision_flag,
)
from scrapers.supplier_discovery import SupplierDiscoveryScraper, discover_suppliers
from scrapers.supplier_catalog_ingestion import (
    SupplierCatalogIngestion,
    extract_unit_count,
    matrix_to_products,
    parse_csv_bytes,
    parse_html_catalog,
    parse_pack_size,
)
from tasks.supplier_pipeline import SupplierPipeline


# ---------------------------------------------------------------------------
# Isolated DB fixture
# ---------------------------------------------------------------------------

@pytest.fixture()
def suppliers_db(tmp_path, monkeypatch):
    """A SuppliersDB backed by a throwaway SQLite file."""
    db_file = tmp_path / "supplier-test.db"
    monkeypatch.setattr(data_layer, "_SQLITE_PATH", db_file)
    layer = DataLayer()
    yield SuppliersDB(layer)
    layer.close()


def _supplier(**overrides):
    s = {
        "id": "acme-wholesale",
        "name": "Acme Wholesale",
        "public_catalog_url": "https://acme.example/catalog",
        "account_friction_level": "low",
        "requires_liftgate": False,
        "categories_supplied": ["otc_health", "personal_care"],
        "decision_flag": "needs_manual_review",
    }
    s.update(overrides)
    return s


# ---------------------------------------------------------------------------
# SuppliersDB
# ---------------------------------------------------------------------------

def test_supplier_upsert_and_get(suppliers_db):
    sid = suppliers_db.upsert(_supplier())
    assert sid == "acme-wholesale"
    row = suppliers_db.get_by_id("acme-wholesale")
    assert row["name"] == "Acme Wholesale"
    assert json.loads(row["categories_supplied"]) == ["otc_health", "personal_care"]


def test_supplier_upsert_is_idempotent(suppliers_db):
    suppliers_db.upsert(_supplier())
    suppliers_db.upsert(_supplier(account_friction_level="high"))
    row = suppliers_db.get_by_id("acme-wholesale")
    assert row["account_friction_level"] == "high"


def test_supplier_list_filters(suppliers_db):
    suppliers_db.upsert(_supplier())
    suppliers_db.upsert(_supplier(id="beta", name="Beta Supply", requires_liftgate=True,
                                   decision_flag="viable"))
    assert len(suppliers_db.list_all()) == 2
    assert len(suppliers_db.list_all(requires_liftgate=True)) == 1
    assert len(suppliers_db.list_all(decision_flag="viable")) == 1
    assert len(suppliers_db.list_all(category_slug="otc_health")) == 2


def test_supplier_update_flag(suppliers_db):
    suppliers_db.upsert(_supplier())
    assert suppliers_db.update_flag("acme-wholesale", "viable") is True
    assert suppliers_db.get_by_id("acme-wholesale")["decision_flag"] == "viable"


def test_supplier_products_crud(suppliers_db):
    suppliers_db.upsert(_supplier())
    pid = suppliers_db.add_product("acme-wholesale", {
        "supplier_sku": "SKU-1",
        "product_name": "Acme Pain Relief 200 ct",
        "wholesale_price": 8.5,
        "unit_count": 200,
    })
    assert pid
    assert suppliers_db.count_products("acme-wholesale") == 1
    products = suppliers_db.get_products("acme-wholesale")
    assert products[0]["supplier_sku"] == "SKU-1"
    assert products[0]["wholesale_price"] == 8.5


def test_supplier_products_idempotent_by_sku(suppliers_db):
    suppliers_db.upsert(_supplier())
    suppliers_db.add_product("acme-wholesale", {"supplier_sku": "SKU-1", "product_name": "X", "wholesale_price": 5.0})
    suppliers_db.add_product("acme-wholesale", {"supplier_sku": "SKU-1", "product_name": "X", "wholesale_price": 6.0})
    products = suppliers_db.get_products("acme-wholesale")
    assert len(products) == 1
    assert products[0]["wholesale_price"] == 6.0


def test_supplier_replace_products(suppliers_db):
    suppliers_db.upsert(_supplier())
    suppliers_db.add_products("acme-wholesale", [
        {"supplier_sku": "A", "product_name": "A", "wholesale_price": 1.0},
        {"supplier_sku": "B", "product_name": "B", "wholesale_price": 2.0},
    ])
    assert suppliers_db.count_products("acme-wholesale") == 2
    suppliers_db.replace_products("acme-wholesale", [
        {"supplier_sku": "C", "product_name": "C", "wholesale_price": 3.0},
    ])
    assert suppliers_db.count_products("acme-wholesale") == 1


def test_supplier_cost_analysis_persist(suppliers_db):
    suppliers_db.upsert(_supplier())
    pid = suppliers_db.add_product("acme-wholesale", {
        "supplier_sku": "SKU-1", "product_name": "X", "wholesale_price": 5.0,
    })
    aid = suppliers_db.add_cost_analysis(pid, {
        "amazon_price": 19.99,
        "estimated_net_profit": 8.0,
        "estimated_roi_pct": 55.0,
        "decision_flag": "viable",
        "notes": ["looks good"],
    })
    assert aid
    rows = suppliers_db.get_analyses(product_id=pid)
    assert len(rows) == 1
    assert rows[0]["decision_flag"] == "viable"
    assert json.loads(rows[0]["notes"]) == ["looks good"]


# ---------------------------------------------------------------------------
# Cost-benefit analyzer
# ---------------------------------------------------------------------------

def test_decision_flag_matrix():
    assert decision_flag(15.0, 50.0, 30.0, 5.0, 20.0, 15.0) == VIABLE
    assert decision_flag(6.0, 10.0, 8.0, 5.0, 20.0, 15.0) == MARGINAL
    assert decision_flag(3.0, 40.0, 30.0, 5.0, 20.0, 15.0) == REJECT
    assert decision_flag(-1.0, -5.0, -2.0, 5.0, 20.0, 15.0) == REJECT
    assert decision_flag(None, None, None, 5.0, 20.0, 15.0) == REJECT
    assert decision_flag(6.0, None, 30.0, 5.0, 20.0, 15.0) == MANUAL_REVIEW


def test_viable_analysis():
    result = analyze_supplier_product(
        {"id": "p1", "product_name": "Widget", "wholesale_price": 10.0},
        {"asin": "B001", "title": "Widget", "amazon_price": 29.99},
    )
    assert result.decision_flag == VIABLE
    assert result.meets_threshold is True
    assert result.estimated_net_profit > 10
    assert result.estimated_roi_pct > 100


def test_marginal_analysis():
    result = analyze_supplier_product(
        {"id": "p2", "product_name": "Pricey", "wholesale_price": 100.0},
        {"asin": "B002", "amazon_price": 124.0},
    )
    assert result.decision_flag == MARGINAL


def test_reject_analysis():
    result = analyze_supplier_product(
        {"id": "p3", "product_name": "Thin", "wholesale_price": 10.0},
        {"asin": "B003", "amazon_price": 12.0},
    )
    assert result.decision_flag == REJECT


def test_missing_amazon_price_needs_review():
    result = analyze_supplier_product(
        {"id": "p4", "product_name": "NoMatch", "wholesale_price": 10.0},
        None,
    )
    assert result.decision_flag == MANUAL_REVIEW
    assert any("Amazon price" in n for n in result.notes)


def test_missing_wholesale_price_needs_review():
    result = analyze_supplier_product({"id": "p5", "product_name": "NoPrice"}, {"amazon_price": 30.0})
    assert result.decision_flag == MANUAL_REVIEW


def test_unit_cogs_divides_by_unit_count():
    result = analyze_supplier_product(
        {"id": "p6", "product_name": "6-pack", "wholesale_price": 30.0, "unit_count": 6},
        {"amazon_price": 12.0},
    )
    assert result.unit_cogs == 5.0


def test_fba_fee_included_when_weight_known():
    with_weight = analyze_supplier_product(
        {"id": "p7", "product_name": "Heavy", "wholesale_price": 10.0, "weight_lbs": 3.0},
        {"amazon_price": 30.0},
    )
    assert with_weight.fba_fee_estimate is not None
    assert with_weight.fba_fee_estimate > 0


def test_analysis_as_dict_round_trips():
    result = analyze_supplier_product(
        {"id": "p8", "product_name": "X", "wholesale_price": 10.0},
        {"amazon_price": 30.0},
    )
    d = result.as_dict()
    assert d["decision_flag"] in (VIABLE, MARGINAL, REJECT, MANUAL_REVIEW)
    assert isinstance(d["notes"], list)


# ---------------------------------------------------------------------------
# Supplier discovery (offline)
# ---------------------------------------------------------------------------

def test_discover_offline_returns_seed_suppliers():
    suppliers = discover_suppliers("otc_health")
    assert suppliers
    assert all(s.categories_supplied for s in suppliers)


def test_discover_offline_includes_liftgate_warning():
    suppliers = discover_suppliers("otc_health")
    liftgate = [s for s in suppliers if s.requires_liftgate]
    assert liftgate
    assert any(s.liftgate_notes for s in liftgate)


def test_discover_profile_maps_to_supplier_columns():
    s = discover_suppliers("snacks_bars")[0]
    d = s.as_dict()
    assert d["id"]
    assert "account_friction_level" in d
    assert "requires_liftgate" in d


def test_live_discovery_gated_without_approval(monkeypatch):
    monkeypatch.delenv("SUPPLIER_DISCOVERY_LIVE_OPERATOR_APPROVED", raising=False)
    scraper = SupplierDiscoveryScraper(fetch_fn=lambda c, k: [{"name": "X"}])
    result = scraper.discover("otc_health", mode="live")
    assert result == []
    assert "gated" in (scraper.last_error or "")


def test_live_discovery_with_gate_and_transport(monkeypatch):
    monkeypatch.setenv("SUPPLIER_DISCOVERY_LIVE_OPERATOR_APPROVED", "1")

    def fake_fetch(category, keywords):
        return [{
            "name": "Live Supplier",
            "categories_supplied": [category],
            "requires_liftgate": True,
            "liftgate_notes": "LTL, liftgate required",
            "confidence": 0.9,
        }]

    scraper = SupplierDiscoveryScraper(fetch_fn=fake_fetch)
    result = scraper.discover("otc_health", mode="live")
    assert len(result) == 1
    assert result[0].name == "Live Supplier"
    assert result[0].requires_liftgate is True


# ---------------------------------------------------------------------------
# Catalog ingestion
# ---------------------------------------------------------------------------

def test_csv_ingestion_maps_columns():
    csv_bytes = (
        "Item Code,Item Name,Price,Unit Count,Brand\n"
        "SKU-1,Acme Pain Relief 200 ct,8.50,200,Acme\n"
        "SKU-2,Acme Cold Syrup 12 oz,4.25,,Acme\n"
    ).encode("utf-8")
    result = parse_csv_bytes(csv_bytes, "acme-wholesale", "acme.csv")
    assert result.rows_parsed == 2
    assert result.rows_imported == 2
    p = result.products[0]
    assert p["supplier_sku"] == "SKU-1"
    assert p["wholesale_price"] == 8.5
    assert p["unit_count"] == 200
    assert p["brand"] == "Acme"


def test_csv_ingestion_skips_bad_rows():
    csv_bytes = b"name,price\n,5.00\nNo Price,\nGood Item,3.00\n"
    result = parse_csv_bytes(csv_bytes, "s1")
    assert result.rows_parsed == 3
    assert result.rows_imported == 1
    assert len(result.skip_reasons) == 2


def test_csv_currency_and_pack_parsing():
    csv_bytes = b"name,price,currency\nAcme Coffee 48 oz,12.00,CAD\n"
    result = parse_csv_bytes(csv_bytes, "s1")
    assert result.products[0]["wholesale_currency"] == "CAD"
    assert result.products[0]["pack_size"] == "48 oz"


def test_matrix_to_products_empty():
    result = matrix_to_products([], "s1")
    assert result.products == []


def test_parse_pack_size_and_unit_count():
    assert parse_pack_size("Acme Tablets 500 ct") == "500 ct"
    assert extract_unit_count("Acme Tablets 500 ct") == 500
    assert extract_unit_count("Acme 24 pack") == 24
    assert extract_unit_count("No numbers here") is None


def test_html_catalog_parsing():
    html = """
    <html><body>
      <div class="product-item">
        <h3 class="product-title">Acme Pain Relief 200 ct</h3>
        <span class="price">$8.50</span>
        <span class="sku">SKU-1</span>
      </div>
      <div class="product-item">
        <h3 class="product-title">Acme Syrup</h3>
        <span class="price">$4.25</span>
      </div>
    </body></html>
    """
    result = parse_html_catalog(html, "acme-wholesale", "acme.html")
    assert result.rows_imported == 2
    assert result.products[0]["wholesale_price"] == 8.5


def test_json_ld_catalog_fallback():
    html = """
    <html><head>
    <script type="application/ld+json">
    {"@type": "Product", "name": "Acme Vitamins 100 ct",
     "sku": "V-100", "offers": {"price": "14.99"}}
    </script>
    </head></html>
    """
    result = parse_html_catalog(html, "acme-wholesale")
    assert result.rows_imported == 1
    assert result.products[0]["wholesale_price"] == 14.99


def test_live_url_ingestion_gated(monkeypatch):
    monkeypatch.delenv("SUPPLIER_CATALOG_LIVE_OPERATOR_APPROVED", raising=False)
    ing = SupplierCatalogIngestion(fetch_fn=lambda url: b"")
    result = ing.ingest_url("acme-wholesale", "https://acme.example/catalog")
    assert result.products == []
    assert "gated" in (ing.last_error or "")


def test_live_url_ingestion_with_gate(monkeypatch):
    monkeypatch.setenv("SUPPLIER_CATALOG_LIVE_OPERATOR_APPROVED", "1")
    html = b'<div class="product-item"><h3 class="product-title">T 100 ct</h3><span class="price">$9.99</span></div>'
    ing = SupplierCatalogIngestion(fetch_fn=lambda url: html)
    result = ing.ingest_url("acme-wholesale", "https://acme.example/catalog")
    assert result.rows_imported == 1


# ---------------------------------------------------------------------------
# Pipeline (end to end, offline)
# ---------------------------------------------------------------------------

def test_pipeline_ingest_and_analyze(suppliers_db):
    pipeline = SupplierPipeline(db=suppliers_db)
    suppliers_db.upsert(_supplier())
    result = pipeline.ingest_products(
        "acme-wholesale",
        [
            {"supplier_sku": "A", "product_name": "Good", "wholesale_price": 10.0},
            {"supplier_sku": "B", "product_name": "Thin", "wholesale_price": 10.0},
        ],
        amazon_price_lookup=lambda name: 29.99 if name == "Good" else 12.0,
    )
    assert result.product_count == 2
    assert result.viable_count == 1
    assert result.reject_count == 1
    assert suppliers_db.count_products("acme-wholesale") == 2
    # an analysis row persisted for each product
    assert len(suppliers_db.get_analyses()) == 2


def test_pipeline_run_discovers_and_persists(suppliers_db):
    pipeline = SupplierPipeline(db=suppliers_db)
    result = pipeline.run("otc_health")
    assert result.discovered is True
    assert result.supplier_id
    assert suppliers_db.get_by_id(result.supplier_id) is not None


def test_pipeline_run_with_supplied_profile(suppliers_db):
    pipeline = SupplierPipeline(db=suppliers_db)
    result = pipeline.run("anything", supplier_profile=_supplier(id="custom", name="Custom"))
    assert result.supplier_name == "Custom"
    assert suppliers_db.get_by_id("custom") is not None
