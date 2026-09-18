"""Tests for the supplier + universal-filter API routes (Phase 1).

Route handlers are invoked directly (the pattern used by the other main.py
route tests) against an isolated SQLite database — no live call is made.
"""

import pytest
from fastapi import HTTPException

import data_layer


@pytest.fixture()
def routes(tmp_path, monkeypatch):
    """Import main with an isolated SQLite DB backing get_db()."""
    monkeypatch.setattr(data_layer, "_SQLITE_PATH", tmp_path / "routes.db")
    monkeypatch.setattr(data_layer, "_db_instance", None)
    import main

    yield main
    if data_layer._db_instance is not None:
        data_layer._db_instance.close()
        data_layer._db_instance = None


def _create_supplier(main, **overrides):
    body = {
        "id": "acme",
        "name": "Acme Wholesale",
        "requires_liftgate": True,
        "categories_supplied": ["otc_health"],
        "decision_flag": "needs_manual_review",
    }
    body.update(overrides)
    return main.upsert_supplier_route(body)


def test_list_suppliers_empty(routes):
    assert routes.list_suppliers_route()["count"] == 0


def test_upsert_and_get_supplier(routes):
    created = _create_supplier(routes)
    assert created["id"] == "acme"
    detail = routes.get_supplier_route("acme")
    assert detail["supplier"]["name"] == "Acme Wholesale"
    assert detail["supplier"]["logistics_warning"]
    assert detail["product_count"] == 0


def test_upsert_requires_name(routes):
    with pytest.raises(HTTPException) as exc:
        routes.upsert_supplier_route({"id": "x"})
    assert exc.value.status_code == 400


def test_get_missing_supplier_404(routes):
    with pytest.raises(HTTPException) as exc:
        routes.get_supplier_route("nope")
    assert exc.value.status_code == 404


def test_delete_supplier(routes):
    _create_supplier(routes)
    assert routes.delete_supplier_route("acme")["deleted"] is True
    with pytest.raises(HTTPException):
        routes.delete_supplier_route("acme")


def test_list_filters_by_liftgate(routes):
    _create_supplier(routes, id="a", name="A", requires_liftgate=True)
    _create_supplier(routes, id="b", name="B", requires_liftgate=False)
    assert routes.list_suppliers_route(requires_liftgate=True)["count"] == 1


def test_discover_offline_endpoint(routes):
    result = routes.discover_suppliers_route({"category": "otc_health"})
    assert result["mode"] == "offline"
    assert result["live_armed"] is False
    assert len(result["suppliers"]) >= 1


def test_discover_persist(routes):
    result = routes.discover_suppliers_route({"category": "otc_health", "persist": True})
    assert result["persisted_ids"]
    assert routes.list_suppliers_route()["count"] == len(result["persisted_ids"])


def test_analyze_endpoint(routes):
    result = routes.analyze_supplier_route({
        "supplier_product": {"product_name": "Widget", "wholesale_price": 10.0},
        "amazon_match": {"amazon_price": 29.99},
    })
    assert result["decision_flag"] == "viable"
    assert result["estimated_net_profit"] > 10


def test_analyze_requires_product(routes):
    with pytest.raises(HTTPException) as exc:
        routes.analyze_supplier_route({})
    assert exc.value.status_code == 400


def test_import_csv_endpoint(routes):
    _create_supplier(routes)
    result = routes.import_supplier_csv_route({
        "supplier_id": "acme",
        "csv_text": "name,price\nAcme Widget 100 ct,10.00\nAcme Thin,10.00\n",
    })
    assert result["rows_imported"] == 2
    assert result["pipeline"]["product_count"] == 2
    assert routes.get_supplier_route("acme")["product_count"] == 2


def test_import_csv_unknown_supplier_404(routes):
    with pytest.raises(HTTPException) as exc:
        routes.import_supplier_csv_route({"supplier_id": "missing", "csv_text": "name,price\nA,1\n"})
    assert exc.value.status_code == 404


def test_import_csv_requires_fields(routes):
    with pytest.raises(HTTPException):
        routes.import_supplier_csv_route({"supplier_id": "acme"})


def test_add_products_with_analysis(routes):
    _create_supplier(routes)
    result = routes.add_supplier_products_route("acme", {
        "products": [{"supplier_sku": "S1", "product_name": "Widget", "wholesale_price": 10.0}],
        "analyze": True,
        "amazon_prices": {"S1": 30.0},
    })
    assert result["added"] == 1
    assert result["analyses"][0]["decision_flag"] == "viable"


def test_analytics_counts(routes):
    _create_supplier(routes)
    routes.import_supplier_csv_route({
        "supplier_id": "acme",
        "csv_text": "name,price\nWidget,10.00\n",
    })
    stats = routes.suppliers_analytics_route()
    assert stats["suppliers_total"] == 1
    assert stats["suppliers_liftgate"] == 1
    assert stats["analyses_total"] == 1


def test_universal_filter_evaluate_passes(routes):
    result = routes.universal_filter_evaluate_route({
        "product": {
            "name": "Good 100 ct", "brand": "Acme",
            "net_profit_per_unit": 12.0, "monthly_sales_estimate": 2000,
            "weight_lbs": 1.0, "fba_sellers": 1,
        }
    })
    assert result["passed"] is True
    assert result["thresholds"]["min_roi_per_unit"] == 10.0


def test_universal_filter_evaluate_rejects_store_brand(routes):
    result = routes.universal_filter_evaluate_route({
        "product": {
            "name": "Kirkland Signature Coffee", "brand": "Kirkland Signature",
            "net_profit_per_unit": 12.0, "monthly_sales_estimate": 2000,
            "weight_lbs": 1.0, "fba_sellers": 1,
        }
    })
    assert result["passed"] is False
    assert result["reasons"]


def test_product_finder_cache_only(routes):
    result = routes.product_finder_route()
    assert result["filter_source"] == "cache-only"
    assert isinstance(result["candidate_count"], int)
    assert "passed" in result
