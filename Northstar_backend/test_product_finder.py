"""Product Finder / SourceScout — the real routes, real data, offline.

The product-finder service is two surfaces in ``main.py``:

    GET  /api/sourcescout            the SourceScout manifest (470 pre-matched rows)
    GET  /api/sourcescout/matches    only PASS quantity matches
    GET  /api/sourcescout/mismatches only FAIL quantity matches
    GET  /api/sourcescout/review     only REVIEW quantity matches
    GET  /api/sourcescout/summary    the quantity-match summary
    GET  /api/products/finder        candidates scored by the universal filter
    POST /api/filters/universal/evaluate  score one product dict, with reasons

Every assertion is about behaviour a user would notice: honest counts, a
disjoint three-way partition of the manifest, threshold overrides that change
the verdict, and rejection reasons that name the gate that failed. No network
is used; the candidate cache is a temp file and the warehouse is a temp SQLite.
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

SOURCE_ITEM_KEYS = {
    "asin",
    "title",
    "brand",
    "price",
    "currency",
    "reviews_count",
    "rating",
    "bsr_text",
    "buybox_price",
    "quantity_match",
}


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


def _write_cache(tmp_path, products):
    path = tmp_path / "scanner-cache.json"
    path.write_text(json.dumps({"products": products}), encoding="utf-8")
    return path


GOOD = {
    "asin": "B0GOOD00001",
    "name": "Acme Widget",
    "brand": "Acme",
    "amazon_price": 30.0,
    "net_profit": 12.0,
    "monthly_sales_estimate": 2000,
    "weight_lbs": 1.0,
    "fba_sellers": 1,
}
STORE_BRAND = {
    "asin": "B0BRAND0001",
    "name": "Kirkland Signature Water",
    "brand": "Kirkland Signature",
    "net_profit": 20.0,
    "monthly_sales_estimate": 5000,
    "weight_lbs": 1.0,
    "fba_sellers": 0,
}
THIN = {
    "asin": "B0THIN00001",
    "name": "Low Margin Thing",
    "brand": "Other",
    "net_profit": 2.0,
    "monthly_sales_estimate": 50,
    "weight_lbs": 9.0,
    "fba_sellers": 9,
}


def test_sourcescout_manifest_is_self_consistent():
    response = client.get("/api/sourcescout")

    assert response.status_code == 200
    body = response.json()
    assert body["kind"] == "sourcescout_manifest"
    assert body["count"] == len(body["items"])
    assert body["count"] > 0
    for item in body["items"]:
        # Every row carries identity + a quantity verdict; the extended retail
        # fields are present on some rows only (the manifest is heterogeneous).
        assert {"asin", "title", "quantity_match"} <= set(item)
        assert item["asin"]
        assert item["quantity_match"]["status"] in {"PASS", "FAIL", "REVIEW"}
    assert any(SOURCE_ITEM_KEYS <= set(item) for item in body["items"])
    summary = body["quantity_match_summary"]
    assert summary["total"] == body["count"]


def test_sourcescout_buckets_partition_the_manifest():
    manifest = client.get("/api/sourcescout").json()
    buckets = {
        name: client.get(f"/api/sourcescout/{name}").json()
        for name in ("matches", "mismatches", "review")
    }
    expected_status = {"matches": "PASS", "mismatches": "FAIL", "review": "REVIEW"}

    for name, bucket in buckets.items():
        assert bucket["count"] == len(bucket["items"])
        assert all(
            item["quantity_match"]["status"] == expected_status[name]
            for item in bucket["items"]
        )

    # Three disjoint buckets that add up to the whole manifest: no row is
    # dropped and none is counted twice.
    all_asins = [item["asin"] for bucket in buckets.values() for item in bucket["items"]]
    assert len(all_asins) == len(set(all_asins)) == manifest["count"]
    assert set(all_asins) == {item["asin"] for item in manifest["items"]}


def test_sourcescout_summary_matches_the_buckets():
    summary = client.get("/api/sourcescout/summary").json()
    counts = {
        name: client.get(f"/api/sourcescout/{name}").json()["count"]
        for name in ("matches", "mismatches", "review")
    }

    assert summary["total"] == summary["pass"] + summary["fail"] + summary["review"]
    assert summary["pass"] == counts["matches"]
    assert summary["fail"] == counts["mismatches"]
    assert summary["review"] == counts["review"]
    assert summary["pass_rate"] == pytest.approx(
        summary["pass"] / summary["total"], abs=1e-9
    )


def test_finder_scores_the_cache_with_the_universal_filter(db, tmp_path, monkeypatch):
    cache = _write_cache(tmp_path, [GOOD, STORE_BRAND, THIN])
    monkeypatch.setenv("SCANNER_SEARCH_CACHE_PATH", str(cache))

    data = client.get("/api/products/finder").json()["data"]

    assert data["filter_source"] == "cache-only"
    assert data["stocked_count"] == 0
    assert data["candidate_count"] == 3
    assert data["passed_count"] == 1
    assert [c["asin"] for c in data["passed"]] == ["B0GOOD00001"]
    assert data["passed"][0]["universal_filter_gates"] == [
        "ROI",
        "Demand",
        "Weight",
        "Competition",
    ]
    # Passing candidates sort ahead of rejected ones.
    assert data["evaluated"][0]["asin"] == "B0GOOD00001"
    rejected = {
        c["asin"]: c["universal_filter_reasons"]
        for c in data["evaluated"]
        if not c["universal_filter_passed"]
    }
    assert any("Brand excluded" in reason for reason in rejected["B0BRAND0001"])
    assert any("demand floor" in reason for reason in rejected["B0THIN00001"])
    assert data["thresholds"]["min_roi_per_unit"] == 10.0
    assert data["thresholds"]["max_fba_sellers"] == 2


def test_finder_threshold_override_changes_the_verdict(db, tmp_path, monkeypatch):
    cache = _write_cache(tmp_path, [GOOD])
    monkeypatch.setenv("SCANNER_SEARCH_CACHE_PATH", str(cache))

    data = client.get(
        "/api/products/finder", params={"min_roi_per_unit": 25}
    ).json()["data"]

    assert data["passed_count"] == 0
    assert data["passed"] == []
    assert data["thresholds"]["min_roi_per_unit"] == 25.0
    reasons = data["evaluated"][0]["universal_filter_reasons"]
    assert any("below $25.00 floor" in reason for reason in reasons)


def test_finder_merges_live_stocked_rows_with_the_cache(db, tmp_path, monkeypatch):
    monkeypatch.setenv("SCANNER_SEARCH_CACHE_PATH", str(tmp_path / "missing.json"))
    db.products.upsert_live(
        {
            "asin": "B0LIVE00001",
            "title": "Warehouse Widget",
            "brand": "Acme",
            "amazon_price": 25.0,
            "net_profit": 18.0,
            "monthly_sales_estimate": 2500,
            "weight_lbs": 1.2,
            "seller_count": 1,
        },
        provider_id="test-fixture",
    )

    data = client.get("/api/products/finder").json()["data"]

    assert data["stocked_count"] == 1
    assert data["filter_source"] == "stock+cache"
    assert data["candidate_count"] == 1
    row = data["evaluated"][0]
    assert row["asin"] == "B0LIVE00001"
    # seller_count is mapped onto the filter's fba_sellers field.
    assert row["fba_sellers"] == 1
    assert row["universal_filter_passed"] is True


def test_finder_reports_zero_honestly_when_no_source_exists(db, tmp_path, monkeypatch):
    monkeypatch.setenv("SCANNER_SEARCH_CACHE_PATH", str(tmp_path / "missing.json"))

    data = client.get("/api/products/finder").json()["data"]

    assert data["stocked_count"] == 0
    assert data["candidate_count"] == 0
    assert data["passed_count"] == 0
    assert data["passed"] == []
    assert data["evaluated"] == []
    assert data["filter_source"] == "cache-only"


def test_universal_filter_explains_every_rejection():
    response = client.post(
        "/api/filters/universal/evaluate",
        json={
            "product": {
                "net_profit": 3.0,
                "monthly_sales_estimate": 100,
                "weight_lbs": 9.0,
                "fba_sellers": 8,
            }
        },
    )

    assert response.status_code == 200
    body = response.json()
    # Legacy /api/filters/universal* is wrapped by BffEnvelopeMiddleware.
    assert body["contract"] == "bff/v1"
    assert body["status"] == "ok"
    body = body["data"]
    assert body["passed"] is False
    assert body["passed_gates"] == []
    joined = " | ".join(body["reasons"])
    assert "below $10.00 floor" in joined
    assert "demand floor" in joined
    assert "hard ceiling" in joined
    assert "seller limit" in joined


def test_universal_filter_passes_a_qualified_product():
    response = client.post(
        "/api/filters/universal/evaluate",
        json={
            "product": {
                "net_profit": 12.0,
                "monthly_sales_estimate": 2000,
                "weight_lbs": 1.0,
                "fba_sellers": 0,
            }
        },
    )

    body = response.json()["data"]
    assert body["passed"] is True
    assert body["reasons"] == []
    assert body["passed_gates"] == ["ROI", "Demand", "Weight", "Competition"]
    assert body["thresholds"]["min_roi_per_unit"] == 10.0


def test_universal_filter_requires_a_product():
    response = client.post("/api/filters/universal/evaluate", json={})

    assert response.status_code == 400
    assert response.json()["detail"] == "product is required"
