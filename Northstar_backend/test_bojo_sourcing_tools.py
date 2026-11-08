"""Tests for the Bojo sourcing tools (`catalog_pull`, `golden_goose_scan`).

Offline: no database, no network, no provider keys. The catalog is the one
injectable dependency and is faked here; Golden Goose is pure code and is
exercised for real (fee stack -> composite -> tier -> rank), so the assertions
pin real arithmetic rather than a stub's output.
"""

from __future__ import annotations

import json
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from bojo_tools import sourcing  # noqa: E402
from bojo_tools.sourcing import TOOLS, catalog_pull, golden_goose_scan  # noqa: E402

# ---------------------------------------------------------------------------
# Fixtures / helpers.
# ---------------------------------------------------------------------------

GOOD = {
    "asin": "B00GOOD001",
    "title": "Tide Pods 30 ct",
    "brand": "Tide",
    "category_slug": "health-household",
    "amazon_price": 34.99,
    "wholesale_price": 24.99,
    "pack_count": 3,
    "bsr": 1200,
    "review_rating": 4.6,
    "review_count": 2400,
    "fba_sellers": 0,
    "weight_oz": 10.0,
    "seller_name": "Joes Resale",
    "is_brand_seller": False,
    "is_amazon_seller": False,
}

# Thin margin: $7.48/unit, LOW tier, but NOT REJECT -> survives selection.
MARGINAL = {
    "asin": "B00MARG001",
    "title": "Tide Pods 30 ct",
    "brand": "Tide",
    "category_slug": "health-household",
    "amazon_price": 24.99,
    "wholesale_price": 19.99,
    "pack_count": 3,
    "bsr": 1200,
    "review_rating": 4.6,
    "review_count": 2400,
    "fba_sellers": 0,
    "weight_oz": 10.0,
    "seller_name": "Joes Resale",
    "is_brand_seller": False,
    "is_amazon_seller": False,
}

# Nothing verifiable: no prices, no pack count, no seller identity.
JUNK = {"asin": "B00JUNK001", "title": "Mystery Item"}


class FakeCatalog:
    """Stands in for `live_catalog` in tests (records the real call shape)."""

    def __init__(self, rows, source="stock", pulled=None, error=None):
        self.rows = rows
        self.source = source
        self.pulled = pulled
        self.error = error
        self.calls = []

    def get_or_pull(self, query, category=None, limit=50, live=False):
        self.calls.append(
            {"query": query, "category": category, "limit": limit, "live": live}
        )
        if self.error is not None:
            raise self.error
        return {"source": self.source, "rows": self.rows, "pulled": self.pulled}


WEIGHTS = {
    "profit": 0.35,
    "demand": 0.20,
    "competition": 0.15,
    "listing_health": 0.10,
    "price_gap": 0.10,
    "ad_feasibility": 0.10,
}


# ---------------------------------------------------------------------------
# Registry.
# ---------------------------------------------------------------------------


def test_tools_registry_exports_both_tools():
    assert set(TOOLS) == {"catalog_pull", "golden_goose_scan"}
    assert TOOLS["catalog_pull"] is catalog_pull
    assert TOOLS["golden_goose_scan"] is golden_goose_scan
    assert all(callable(fn) for fn in TOOLS.values())


# ---------------------------------------------------------------------------
# catalog_pull.
# ---------------------------------------------------------------------------


def test_catalog_pull_returns_rows_and_forwards_the_real_call():
    rows = [
        {"asin": "B001", "title": "Mr. Clean Magic Eraser"},
        {"asin": "B002", "title": "Mr. Clean Spray"},
    ]
    catalog = FakeCatalog(rows)

    result = catalog_pull(
        "  mr clean  ", limit=7, category="household", live=True, catalog=catalog
    )

    assert result["ok"] is True
    assert result["tool"] == "catalog_pull"
    assert result["data"]["query"] == "mr clean"
    assert result["data"]["count"] == 2
    assert result["data"]["rows"] == rows
    assert result["data"]["source"] == "stock"
    assert result["data"]["live"] is True
    # The wrapper called the production signature, not a re-implementation.
    assert catalog.calls == [
        {"query": "mr clean", "category": "household", "limit": 7, "live": True}
    ]
    json.dumps(result)  # contract: JSON-serialisable


def test_catalog_pull_reports_live_pull_metadata():
    catalog = FakeCatalog(
        [{"asin": "B003", "title": "Pulled fresh"}],
        source="live",
        pulled={"stocked": 1, "provider": "chocodata", "mode": "live", "ok": True},
    )
    result = catalog_pull("fresh", live=True, catalog=catalog)

    assert result["ok"] is True
    assert result["data"]["source"] == "live"
    assert result["data"]["pulled"] == {
        "stocked": 1,
        "provider": "chocodata",
        "mode": "live",
        "ok": True,
    }


def test_catalog_pull_truncates_to_limit_after_the_search():
    catalog = FakeCatalog([{"asin": "B%03d" % i} for i in range(5)])
    result = catalog_pull("anything", limit=2, catalog=catalog)

    assert result["data"]["count"] == 2
    assert [r["asin"] for r in result["data"]["rows"]] == ["B000", "B001"]


def test_catalog_pull_empty_catalog_is_a_business_failure():
    result = catalog_pull("nothing here", catalog=FakeCatalog([], source="empty"))

    assert result == {
        "ok": False,
        "tool": "catalog_pull",
        "reason": "no catalog rows for 'nothing here' (source=empty)",
    }


def test_catalog_pull_dependency_error_does_not_raise():
    catalog = FakeCatalog([], error=RuntimeError("warehouse offline"))
    result = catalog_pull("tide", catalog=catalog)

    assert result["ok"] is False
    assert result["tool"] == "catalog_pull"
    assert result["reason"].startswith("catalog pull failed: RuntimeError")
    assert "warehouse offline" in result["reason"]


def test_catalog_pull_rejects_empty_query_and_bad_limit():
    assert catalog_pull("   ", catalog=FakeCatalog([]))["reason"] == "query is empty"
    assert (
        catalog_pull("tide", limit=0, catalog=FakeCatalog([]))["reason"]
        == "limit must be >= 1"
    )


def test_catalog_pull_programmer_errors_raise():
    with pytest.raises(TypeError):
        catalog_pull(None)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        catalog_pull("tide", limit="50")  # type: ignore[arg-type]


def test_default_catalog_dependency_is_the_real_live_catalog_module():
    import live_catalog

    assert sourcing._default_catalog() is live_catalog
    assert catalog_pull.__defaults__[-1] is None  # catalog defaults to None -> real


# ---------------------------------------------------------------------------
# golden_goose_scan.
# ---------------------------------------------------------------------------


def test_golden_goose_scan_happy_path_uses_real_economics_and_scoring():
    result = golden_goose_scan([GOOD])

    assert result["ok"] is True
    assert result["tool"] == "golden_goose_scan"
    data = result["data"]
    assert data["evaluated"] == 1
    assert data["returned"] == 1
    assert data["summary"]["high"] == 1
    assert data["summary"]["best_asin"] == "B00GOOD001"

    opp = data["opportunities"][0]
    econ = opp["economics"]

    # Real fee maths: unit COGS is wholesale / pack_count.
    assert econ["unit_cogs"] == pytest.approx(24.99 / 3, abs=0.01)
    # Net profit is price minus the total cost stack (no invented values).
    assert econ["net_profit_per_unit"] == pytest.approx(
        econ["amazon_price"] - econ["total_costs_per_unit"], abs=0.01
    )
    assert econ["net_profit_per_unit"] == pytest.approx(14.11, abs=0.01)
    # ROI is net profit over unit COGS, as a percentage.
    assert econ["roi_per_unit"] == pytest.approx(
        econ["net_profit_per_unit"] / econ["unit_cogs"] * 100.0, abs=0.05
    )
    # Per-pack profit is per-unit profit times the pack count.
    assert econ["net_profit_per_pack"] == pytest.approx(
        econ["net_profit_per_unit"] * 3, abs=0.05
    )

    # Composite is the documented weighted sum of the returned components.
    expected = round(
        sum(WEIGHTS[key] * opp["scores"][key] for key in WEIGHTS), 4
    )
    assert opp["composite_score"] == pytest.approx(expected, abs=1e-4)

    assert opp["tier"] == "HIGH"
    assert opp["composite_score"] >= 0.60
    assert opp["filters"]["all"] is True
    assert "no_fba_competition" in opp["tags"]

    json.dumps(result)  # contract: JSON-serialisable


def test_golden_goose_scan_ranks_descending_and_keeps_non_reject_rows():
    result = golden_goose_scan([MARGINAL, GOOD])

    scores = [o["composite_score"] for o in result["data"]["opportunities"]]
    assert scores == sorted(scores, reverse=True)
    assert [o["asin"] for o in result["data"]["opportunities"]] == [
        "B00GOOD001",
        "B00MARG001",
    ]
    tiers = {o["asin"]: o["tier"] for o in result["data"]["opportunities"]}
    assert tiers == {"B00GOOD001": "HIGH", "B00MARG001": "LOW"}
    summary = result["data"]["summary"]
    assert summary["high"] == 1
    assert summary["low"] == 1
    assert summary["rejected"] == 0


def test_golden_goose_scan_limit_keeps_only_the_best():
    result = golden_goose_scan([MARGINAL, GOOD], limit=1)

    assert result["data"]["returned"] == 1
    assert result["data"]["opportunities"][0]["asin"] == "B00GOOD001"


def test_golden_goose_scan_no_candidate_above_threshold_is_a_business_failure():
    result = golden_goose_scan([JUNK])

    assert result["ok"] is False
    assert result["tool"] == "golden_goose_scan"
    assert "no candidates survived Golden Goose selection" in result["reason"]
    assert "roi_floor=$10.00" in result["reason"]


def test_golden_goose_scan_can_return_rejected_rows_on_request():
    result = golden_goose_scan([JUNK], include_rejected=True)

    assert result["ok"] is True
    opp = result["data"]["opportunities"][0]
    assert opp["tier"] == "REJECT"
    assert opp["filters"]["all"] is False
    assert result["data"]["summary"]["rejected"] == 1


def test_golden_goose_scan_empty_candidates_is_a_business_failure():
    result = golden_goose_scan([])

    assert result == {
        "ok": False,
        "tool": "golden_goose_scan",
        "reason": "no candidates supplied",
    }


def test_golden_goose_scan_programmer_errors_raise():
    with pytest.raises(TypeError):
        golden_goose_scan({"asin": "B001"})  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        golden_goose_scan([GOOD, 42])  # type: ignore[list-item]
    with pytest.raises(TypeError):
        golden_goose_scan([GOOD], min_monthly_sales="1000")  # type: ignore[arg-type]


def test_golden_goose_default_scorer_is_the_real_implementation():
    from agents.golden_goose_finder import breakdown_economics, opportunity_scorer

    gg = sourcing._golden_goose()
    assert gg["score_batch"] is opportunity_scorer.score_batch
    assert (
        gg["calculate_breakdown_economics"]
        is breakdown_economics.calculate_breakdown_economics
    )
    # No fake scorer is installed unless a caller injects one.
    assert golden_goose_scan.__defaults__[-1] is None


def test_golden_goose_scorer_failure_is_reported_not_raised():
    def broken_scorer(economics, **kwargs):
        raise RuntimeError("scorer exploded")

    result = golden_goose_scan([GOOD], scorer=broken_scorer)

    assert result["ok"] is False
    assert result["tool"] == "golden_goose_scan"
    assert result["reason"].startswith("scoring failed: RuntimeError")
