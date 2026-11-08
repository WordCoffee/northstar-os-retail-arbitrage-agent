"""rivalboard — the competitive landscape behind the Rival Board.

RivalBoard.jsx has no dedicated endpoint: it reads ``api.scanner()``, i.e.
``GET /api/kirkland/scanner``, and derives each rival's posture from price,
ROI and seller counts. This module exercises that real route through the ASGI
app and asserts the competitive-intelligence contract:

* the bff/v1 envelope and cache-only containment (the scan must never be a
  live provider call when ``SCANNER_LIVE_ALLOWED`` is off);
* ``candidates_returned`` equals the rows actually returned, and the
  completeness contract version is pinned;
* only allowlisted fields are exposed — financial projection fields that the
  page must not see are absent;
* rows are ordered by the documented ranking key (economics tier, net profit,
  ROI, fewer sellers, FBA sellers, demand, price spread) — the "who is
  winning" order, not insertion order;
* the ranking key itself prefers fewer competitors and sorts nulls last;
* no scanner row is ever ``ready_for_test_buy`` without operator review;
* the one mutating route in the family (``POST /api/kirkland/refresh``)
  refuses with 403 while the live gate is off.

Offline: the live gate is pinned off for the module, and ``network_guard``
blocks real ``requests`` calls. No Amazon, no provider spend.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "Northstar_backend"))

import network_guard  # noqa: F401  (offline: blocks real requests calls)

import pytest
from fastapi.testclient import TestClient

import main

SCANNER_PATH = "/api/kirkland/scanner"

#: Fields that must never reach the Scout/Rival table (financial projections
#: computed elsewhere; see test_scanner_endpoint.FORBIDDEN).
FORBIDDEN_FIELDS = {
    "prep_cost",
    "inbound_shipping_cost",
    "landed_cost",
    "projected_net_profit",
    "projected_roi_pct",
    "financial_data_gaps",
    "financial_status",
    "financial_decision_status",
    "amazon_fees_total",
    "amazon_payout_before_inventory_costs",
    "cogs",
    "fba_sellers_estimated",
    "fba_seller_preference",
    "lowest_price_seller_type",
    "highest_price_seller_type",
}

COMPLETENESS_KEYS = {
    "score",
    "score_max",
    "status",
    "status_reason",
    "category_scores",
    "category_reasons",
    "missing_inputs",
    "roi_readiness",
    "next_action",
    "purchase_authorized",
}

COMPLETENESS_CATEGORIES = {
    "identity_mapping",
    "source_cost",
    "market_coverage",
    "fees_economics",
    "demand",
    "invoice_readiness",
}

SUMMARY_KEYS = {
    "candidates_returned",
    "tier_found",
    "costco_catalog",
    "costco_discovery",
    "search_source",
    "enrichment_source",
    "scanner_mode",
    "live_allowed",
    "cache_status",
    "cache_fetched_at",
    "cache_source",
    "upstream_hint",
    "completeness_contract_version",
}


@pytest.fixture(scope="module", autouse=True)
def _live_gate_off():
    """Pin the provider gate off so the scan is cache-only and deterministic."""
    patcher = pytest.MonkeyPatch()
    patcher.setenv("SCANNER_LIVE_ALLOWED", "0")
    patcher.delenv("NS_LIVE_PER_RUN_ARMED", raising=False)
    yield
    patcher.undo()


@pytest.fixture(scope="module")
def client():
    yield TestClient(main.app)


@pytest.fixture(scope="module")
def envelope(client):
    response = client.get(SCANNER_PATH)
    assert response.status_code == 200, response.text[:300]
    return response.json()


@pytest.fixture(scope="module")
def data(envelope):
    return envelope["data"]


@pytest.fixture(scope="module", autouse=True)
def _close_data_layer():
    """Close the shared DataLayer connection so no ResourceWarning leaks out."""
    yield
    import data_layer

    instance = getattr(data_layer, "_db_instance", None)
    if instance is not None:
        try:
            instance.close()
        except Exception:
            pass
        data_layer._db_instance = None


def _is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def test_bff_envelope(envelope):
    assert envelope["contract"] == "bff/v1"
    assert envelope["status"] in ("ok", "empty")
    assert envelope["error"] is None
    assert envelope["meta"]["service"] == "northstar"
    assert isinstance(envelope["request_id"], str)
    assert envelope["request_id"].startswith("req_")
    assert isinstance(envelope["data"], dict)


def test_scan_is_cache_only_and_contained(data):
    summary = data["summary"]
    assert summary["live_allowed"] is False
    assert summary["scanner_mode"] == "cache_only"
    assert summary["enrichment_source"] == "OFF"
    assert data["status"] in {"ok", "no_candidates", "upstream_unavailable"}
    if data["products"]:
        assert data["status"] == "ok"


def test_candidates_returned_matches_rows(data):
    summary = data["summary"]
    assert SUMMARY_KEYS <= set(summary)
    assert summary["candidates_returned"] == len(data["products"])
    assert summary["completeness_contract_version"] == 1
    assert isinstance(data["products"], list)
    assert isinstance(data["generated_at"], str) and data["generated_at"]


def test_only_allowlisted_fields_are_exposed(data):
    allowed = set(main.SCANNER_ALLOWED_KEYS) | {"completeness"}
    for product in data["products"]:
        extra = set(product) - allowed
        assert not extra, f"scanner leaked non-allowlisted fields: {sorted(extra)}"
        assert not (set(product) & FORBIDDEN_FIELDS), sorted(set(product) & FORBIDDEN_FIELDS)
        assert "completeness" in product


def test_competitive_signals_are_real_values_or_honest_nulls(data):
    for product in data["products"]:
        # The Rival Board posture columns: ROI / profit / seller counts.
        for key in ("roi_pct", "net_profit", "costco_cost", "amazon_price"):
            value = product.get(key)
            assert value is None or _is_number(value), f"{key}={value!r}"
        for key in ("total_sellers", "fba_sellers", "sales_rank"):
            value = product.get(key)
            assert value is None or (isinstance(value, int) and value >= 0), f"{key}={value!r}"
        seller = product.get("buy_box_seller")
        assert seller is None or isinstance(seller, str)


def test_rows_are_ranked_by_the_competitive_order(data):
    products = data["products"]
    assert products == sorted(products, key=main._scanner_sort_key), (
        "scanner must serve the documented ranking, not insertion order"
    )
    groups = [main._economics_group(p) for p in products]
    assert groups == sorted(groups), "estimated economics must outrank provisional/unavailable"


def test_ranking_key_prefers_fewer_competitors_and_sorts_nulls_last():
    base = {
        "economics_confidence": "estimated",
        "net_profit": 10.0,
        "roi_pct": 50.0,
        "monthly_sales_estimate": 100,
    }
    crowded = dict(base, total_sellers=9, fba_sellers=9)
    open_field = dict(base, total_sellers=1, fba_sellers=1)
    unknown = dict(base, net_profit=None, roi_pct=None, total_sellers=None, fba_sellers=None)
    unknown["economics_confidence"] = None

    ordered = sorted([unknown, crowded, open_field], key=main._scanner_sort_key)
    assert ordered == [open_field, crowded, unknown], (
        "fewer sellers must rank ahead at equal profit; null profit ranks last"
    )


def test_no_scanner_row_is_purchase_ready(data):
    for product in data["products"]:
        completeness = product["completeness"]
        assert set(completeness) == COMPLETENESS_KEYS
        assert set(completeness["category_scores"]) == COMPLETENESS_CATEGORIES
        # Scanner rows never carry account-review approval, so the best
        # reachable status is 'blocked' (completeness_score._classify_status).
        assert completeness["status"] != "ready_for_test_buy", product.get("asin")
        score = completeness["score"]
        assert score is None or (isinstance(score, int) and 0 <= score <= completeness["score_max"])
        assert isinstance(completeness["score_max"], int) and completeness["score_max"] >= 0
        assert isinstance(completeness["purchase_authorized"], bool)


def test_live_refresh_is_refused_while_gate_is_off(client, monkeypatch):
    monkeypatch.setenv("SCANNER_LIVE_ALLOWED", "0")
    response = client.post("/api/kirkland/refresh")
    assert response.status_code == 403, response.text[:300]
    detail = response.json().get("detail", "")
    assert "SCANNER_LIVE_ALLOWED" in detail, detail
