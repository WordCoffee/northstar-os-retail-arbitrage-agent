"""competitor-monitor — the competitor feed behind Rival Board.

Exercises the real route the Competitor Monitor page reads
(``signals.ncCompetitorObservations`` ->
``GET /api/v1/noncreative/competitor/observations``) through the ASGI app, and
asserts the market-observation contract rather than mere liveness:

* the envelope is ``{kind, count, items, summary}`` and the counts agree;
* the summary is arithmetic over the rows that were actually returned
  (``source_with_price``, ``source_avg_price``, ``distinct_brands``), and an
  unknown is an explicit ``None`` + reason, never a fabricated zero;
* each item is the 15-field projection in ``noncreative_reads.py`` with no
  extra fields leaking through, and every item is a ``data_kind='live'`` row —
  a demo fixture row must never look like a market observation;
* the read is bounded: ``limit`` is forwarded to the stock-first read and
  values above 500 are rejected with a 422.

Offline: ``network_guard`` blocks real ``requests`` calls, and the route only
reads local SQLite (no provider calls). No Amazon, no paid provider.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "Northstar_backend"))

import network_guard  # noqa: F401  (offline: blocks real requests calls)

import pytest
from fastapi.testclient import TestClient

import live_catalog
import main

PATH = "/api/v1/noncreative/competitor/observations"

#: The projection in noncreative_reads.competitor_observations, verbatim.
ITEM_KEYS = {
    "asin",
    "title",
    "brand",
    "category",
    "marketplace",
    "amazon_price",
    "buy_box_price",
    "costco_cost",
    "bsr_rank",
    "seller_count",
    "net_profit",
    "roi_pct",
    "data_kind",
    "fetched_at",
    "provider_id",
}

#: Columns selected from costco_source_products.
SOURCE_KEYS = {
    "costco_item_number",
    "title_normalized",
    "brand_normalized",
    "costco_price",
    "currency",
    "availability_status",
    "freshness_status",
    "identity_status",
    "exclusion_reason",
    "observed_at",
}

SUMMARY_KEYS = {
    "products",
    "source_products",
    "source_with_price",
    "source_avg_price",
    "distinct_brands",
    "unavailable",
}


@pytest.fixture(scope="module")
def client():
    yield TestClient(main.app)


@pytest.fixture(scope="module")
def body(client):
    response = client.get(PATH)
    assert response.status_code == 200, response.text[:300]
    return response.json()


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


def test_envelope_counts_agree_with_items(body):
    assert body["kind"] == "competitor_observations"
    assert isinstance(body["count"], int)
    assert isinstance(body["items"], list)
    assert body["count"] == len(body["items"])
    assert body["summary"]["products"] == body["count"]
    for item in body["items"]:
        assert set(item) == ITEM_KEYS, f"projection drifted: {sorted(set(item) ^ ITEM_KEYS)}"
        # The stock-first read is live-only; a demo/default row must never be
        # presented as a market observation.
        assert item["data_kind"] == "live", item


def test_summary_arithmetic_over_synthetic_source_rows(client, monkeypatch):
    """The summary math must hold for rows, not only for the empty local DB."""
    import noncreative_reads

    rows = [
        {"costco_item_number": "1", "title_normalized": "A", "brand_normalized": "Acme",
         "costco_price": 10.0, "currency": "USD", "availability_status": "in_stock",
         "freshness_status": "fresh", "identity_status": "confirmed", "exclusion_reason": None,
         "observed_at": "2026-11-08T00:00:00+00:00"},
        {"costco_item_number": "2", "title_normalized": "B", "brand_normalized": "acme",
         "costco_price": 20.0, "currency": "USD", "availability_status": "in_stock",
         "freshness_status": "fresh", "identity_status": "confirmed", "exclusion_reason": None,
         "observed_at": "2026-11-08T00:00:00+00:00"},
        {"costco_item_number": "3", "title_normalized": "C", "brand_normalized": "Beta",
         "costco_price": None, "currency": "USD", "availability_status": "unknown",
         "freshness_status": "stale", "identity_status": "candidate", "exclusion_reason": "no price",
         "observed_at": "2026-11-08T00:00:00+00:00"},
    ]
    monkeypatch.setattr(noncreative_reads, "_optional_rows", lambda *a, **k: (list(rows), None))

    payload = client.get(PATH).json()
    summary = payload["summary"]
    assert summary["source_with_price"] == 2
    assert summary["source_avg_price"] == 15.0
    assert summary["distinct_brands"] == 2  # "Acme"/"acme" collapse; Beta distinct
    assert len(summary["source_products"]) == 3
    assert summary["unavailable"] is None
    assert set(summary["source_products"][0]) == SOURCE_KEYS


def test_summary_is_arithmetic_over_returned_rows(body):
    summary = body["summary"]
    assert set(summary) == SUMMARY_KEYS

    rows = summary["source_products"]
    assert isinstance(rows, list)

    priced = [r["costco_price"] for r in rows if _is_number(r.get("costco_price"))]
    assert summary["source_with_price"] == len(priced)
    expected_avg = round(sum(priced) / len(priced), 2) if priced else None
    assert summary["source_avg_price"] == expected_avg
    assert summary["distinct_brands"] == len(
        {(r.get("brand_normalized") or "").lower() for r in rows if r.get("brand_normalized")}
    )

    for row in rows:
        assert set(row) == SOURCE_KEYS, f"source projection drifted: {sorted(set(row) ^ SOURCE_KEYS)}"

    # "Unknown is not zero": a missing table is reported with a reason and a
    # null average, never a confident 0.0.
    unavailable = summary["unavailable"]
    if unavailable is not None:
        assert isinstance(unavailable, dict) and unavailable
        assert all(isinstance(reason, str) and reason.strip() for reason in unavailable.values())
        if not rows:
            assert summary["source_avg_price"] is None


def test_limit_is_forwarded_to_the_stocked_read_and_projection_holds(client, monkeypatch):
    stocked_row = {
        "asin": "B0TEST0001",
        "title": "Rival Test Product",
        "brand": "Acme",
        "category": "grocery",
        "marketplace": "US",
        "amazon_price": 24.99,
        "buy_box_price": 24.49,
        "costco_cost": 12.0,
        "bsr_rank": 1234,
        "seller_count": 3,
        "net_profit": 5.25,
        "roi_pct": 43.75,
        "data_kind": "live",
        "fetched_at": "2026-11-08T00:00:00+00:00",
        "provider_id": "offline_test",
        # Not part of the observation contract — must be dropped.
        "fresh_until": "2026-11-09T00:00:00+00:00",
        "internal_only": "must not leak",
    }
    calls = {}

    def fake_get_stocked(limit=500):
        calls["limit"] = limit
        return [stocked_row]

    monkeypatch.setattr(live_catalog, "get_stocked", fake_get_stocked)

    response = client.get(PATH, params={"limit": 7})
    assert response.status_code == 200, response.text[:300]
    payload = response.json()

    assert calls["limit"] == 7, "limit must bound the stock-first read"
    assert payload["count"] == 1
    assert payload["summary"]["products"] == 1

    item = payload["items"][0]
    assert set(item) == ITEM_KEYS
    assert item["asin"] == stocked_row["asin"]
    assert item["seller_count"] == 3
    assert item["roi_pct"] == 43.75
    assert item["data_kind"] == "live"
    assert "fresh_until" not in item and "internal_only" not in item


def test_over_limit_is_rejected(client):
    response = client.get(PATH, params={"limit": 501})
    assert response.status_code == 422, response.text[:200]
    detail = response.json()["detail"]
    assert any(entry.get("loc") == ["query", "limit"] for entry in detail), detail

    response = client.get(PATH, params={"limit": "many"})
    assert response.status_code == 422, response.text[:200]
