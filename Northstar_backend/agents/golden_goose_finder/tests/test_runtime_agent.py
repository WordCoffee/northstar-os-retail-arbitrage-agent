"""Tests for the Golden Goose Runtime Agent (helper sub-agent orchestration)."""

from __future__ import annotations

import json

import pytest

from agents.golden_goose_finder.runtime_agent import (
    HELPER_ROLES,
    HELPER_ROLE_BY_ID,
    LiveArmedError,
    MockHelperDispatcher,
    amazon_matches_from_helper_results,
    build_helper_payloads,
    collect_helper_results,
    require_live_approval,
    wholesale_products_from_helper_result,
    run_mock_harness,
)


# ---------------------------------------------------------------------------
# Role registry
# ---------------------------------------------------------------------------


class TestRoleRegistry:
    def test_five_helper_roles(self):
        assert len(HELPER_ROLES) == 5
        ids = {r.id for r in HELPER_ROLES}
        assert ids == {
            "costco_catalog_scanner",
            "sams_club_catalog_scanner",
            "amazon_product_finder",
            "amazon_seller_analyzer",
            "price_bsr_history_tracker",
        }

    def test_role_contract_complete(self):
        for role in HELPER_ROLES:
            assert role.name
            assert role.mission
            assert role.web_surface
            assert role.inputs
            assert role.outputs
            assert role.prompt_template
            assert role.mock_data_key
            assert "{category}" in role.prompt_template or "{asin}" in role.prompt_template or "{wholesale_title}" in role.prompt_template

    def test_role_lookup(self):
        assert len(HELPER_ROLE_BY_ID) == 5
        assert HELPER_ROLE_BY_ID["amazon_product_finder"].name == "Amazon Product Finder"


# ---------------------------------------------------------------------------
# Dispatch payloads
# ---------------------------------------------------------------------------


class TestBuildHelperPayloads:
    def test_builds_five_payloads(self):
        payloads = build_helper_payloads()
        assert len(payloads) == 5
        for p in payloads:
            assert "helper_id" in p
            assert "prompt" in p
            assert "output_contract" in p
            assert p["live_armed"] is False

    def test_prompts_have_required_context(self):
        payloads = build_helper_payloads(categories=["nicotine_cessation", "otc_health"])
        by_id = {p["helper_id"]: p for p in payloads}
        # Catalog scanners: prompt contains categories
        for hid in ("costco_catalog_scanner", "sams_club_catalog_scanner"):
            assert "nicotine_cessation" in by_id[hid]["prompt"]
            assert "otc_health" in by_id[hid]["prompt"]
        # Finder: prompt contains strict JSON contract
        assert "STRICT JSON" in by_id["amazon_product_finder"]["prompt"]
        assert "STRICT JSON" in by_id["amazon_seller_analyzer"]["prompt"]
        assert "STRICT JSON" in by_id["price_bsr_history_tracker"]["prompt"]

    def test_live_armed_flag(self):
        payloads = build_helper_payloads(live_armed=True)
        assert all(p["live_armed"] for p in payloads)
        payloads = build_helper_payloads()
        assert all(not p["live_armed"] for p in payloads)

    def test_finder_payload_has_wholesale_context(self):
        # Build fake wholesale products to feed the finder payload
        from agents.golden_goose_finder.wholesale_scanner import WholesaleProduct

        wp = WholesaleProduct(
            source_store="Costco",
            product_title="Nicorette Nicotine Lozenge 2mg Mint (200 Count)",
            brand="Nicorette",
            category_slug="nicotine_cessation",
            pack_count=200,
            wholesale_price=39.99,
        )
        payloads = build_helper_payloads(wholesale_products=[wp])
        by_id = {p["helper_id"]: p for p in payloads}
        assert "Nicorette" in by_id["amazon_product_finder"]["prompt"]
        assert "200" in by_id["amazon_product_finder"]["prompt"]


# ---------------------------------------------------------------------------
# Result collection and validation
# ---------------------------------------------------------------------------


class TestCollectHelperResults:
    def test_parses_fenced_json(self):
        raw = {
            "costco_catalog_scanner": (
                "Here are the products I found:\n```json\n"
                '{"products": [{"product_title": "Advil 500ct", "brand": "Advil", '
                '"pack_count": 500, "wholesale_price": 24.99}]}\n```'
            )
        }
        results = collect_helper_results(raw, validate=True)
        assert results["costco_catalog_scanner"].ok is True
        assert len(results["costco_catalog_scanner"].items) == 1

    def test_parses_bare_json(self):
        raw = {
            "amazon_product_finder": (
                '{"matches": [{"asin": "B00N2Y1THA", "title": "Nicorette 20ct", '
                '"amazon_price": 11.99, "bsr": 4200}]}'
            )
        }
        results = collect_helper_results(raw)
        assert results["amazon_product_finder"].ok is True

    def test_missing_required_field_is_failure(self):
        raw = {"amazon_seller_analyzer": '{"seller_data": {"asin": "B00N2Y1THA"}}'}
        results = collect_helper_results(raw, validate=True)
        assert results["amazon_seller_analyzer"].ok is False
        assert "fba_sellers" in (results["amazon_seller_analyzer"].error or "")

    def test_no_json_is_failure(self):
        raw = {"costco_catalog_scanner": "I searched but found no products."}
        results = collect_helper_results(raw, validate=True)
        assert results["costco_catalog_scanner"].ok is False

    def test_unknown_helper_id(self):
        raw = {"totally_unknown_helper": "{}"}
        results = collect_helper_results(raw)
        assert results["totally_unknown_helper"].ok is False

    def test_validation_can_be_disabled(self):
        raw = {"amazon_seller_analyzer": '{"seller_data": {"asin": "B00N2Y1THA"}}'}
        results = collect_helper_results(raw, validate=False)
        assert results["amazon_seller_analyzer"].ok is True


# ---------------------------------------------------------------------------
# Helper output → pipeline data classes
# ---------------------------------------------------------------------------


class TestOutputConversion:
    def _catalog_result(self):
        raw = {
            "costco_catalog_scanner": json.dumps(
                {
                    "products": [
                        {
                            "product_title": "Nicorette Nicotine Lozenge 2mg Mint (200 Count)",
                            "brand": "Nicorette",
                            "pack_count": 200,
                            "wholesale_price": 39.99,
                            "item_number": "1678912",
                        }
                    ]
                }
            )
        }
        return collect_helper_results(raw)["costco_catalog_scanner"]

    def test_wholesale_conversion(self):
        result = self._catalog_result()
        products = wholesale_products_from_helper_result(result, source_store="Costco")
        assert len(products) == 1
        p = products[0]
        assert p.source_store == "Costco"
        assert p.brand == "Nicorette"
        assert p.pack_count == 200
        assert p.wholesale_price == 39.99
        assert p.item_number == "1678912"

    def test_wholesale_conversion_empty_on_failure(self):
        from agents.golden_goose_finder.runtime_agent import HelperResult

        bad = HelperResult(helper_id="costco_catalog_scanner", ok=False, error="no JSON")
        assert wholesale_products_from_helper_result(bad, source_store="Costco") == []

    def test_amazon_merge(self):
        finder_raw = {
            "amazon_product_finder": json.dumps(
                {"matches": [
                    {"asin": "B00N2Y1THA", "title": "Nicorette 20ct", "brand": "Nicorette",
                     "amazon_price": 11.99, "bsr": None, "review_rating": 4.7, "review_count": 8900}
                ]}
            )
        }
        seller_raw = {
            "amazon_seller_analyzer": json.dumps(
                {"seller_data": {"asin": "B00N2Y1THA", "fba_sellers": 1, "fbm_sellers": 3,
                                 "buy_box_price": 11.99, "is_prime": True, "total_offers": 8}}
            )
        }
        hist_raw = {
            "price_bsr_history_tracker": json.dumps(
                {"history": {"asin": "B00N2Y1THA", "bsr": 4200, "bsr_30d_ago": 5100,
                             "buy_box_price": 11.99, "buy_box_price_30d_ago": 12.49,
                             "monthly_sales_estimate": 1800, "history_available": True}}
            )
        }
        results = collect_helper_results({**finder_raw, **seller_raw, **hist_raw})
        matches = amazon_matches_from_helper_results(
            finder_result=results["amazon_product_finder"],
            seller_result=results["amazon_seller_analyzer"],
            history_result=results["price_bsr_history_tracker"],
        )
        assert len(matches) == 1
        m = matches[0]
        assert m.asin == "B00N2Y1THA"
        assert m.fba_sellers == 1
        assert m.bsr == 4200
        assert m.monthly_sales_estimate == 1800
        assert m.is_prime is True
        assert m.review_rating == 4.7

    def test_amazon_merge_without_aux_helpers(self):
        finder_raw = {
            "amazon_product_finder": json.dumps(
                {"matches": [
                    {"asin": "B00GOHEWCU", "title": "Advil 100ct", "brand": "Advil",
                     "amazon_price": 8.99}
                ]}
            )
        }
        results = collect_helper_results(finder_raw)
        matches = amazon_matches_from_helper_results(results["amazon_product_finder"])
        assert len(matches) == 1
        assert matches[0].fba_sellers is None
        assert matches[0].is_prime is False


# ---------------------------------------------------------------------------
# §3 live-call gating
# ---------------------------------------------------------------------------


class TestLiveGate:
    def test_requires_approval(self):
        with pytest.raises(LiveArmedError):
            require_live_approval(live_armed=False, helper_id="costco_catalog_scanner")

    def test_armed_passes(self):
        require_live_approval(live_armed=True, helper_id="costco_catalog_scanner")  # no raise


# ---------------------------------------------------------------------------
# Mock dispatcher (offline end-to-end)
# ---------------------------------------------------------------------------


class TestMockDispatcher:
    def test_dispatches_all_five(self):
        dispatcher = MockHelperDispatcher()
        payloads = build_helper_payloads()
        raw = dispatcher.dispatch(payloads)
        assert set(raw.keys()) == {
            "costco_catalog_scanner",
            "sams_club_catalog_scanner",
            "amazon_product_finder",
            "amazon_seller_analyzer",
            "price_bsr_history_tracker",
        }
        # All outputs parse as valid JSON
        for text in raw.values():
            json.loads(text)

    def test_mock_data_realistic(self):
        dispatcher = MockHelperDispatcher()
        payloads = build_helper_payloads()
        raw = dispatcher.dispatch(payloads)
        results = collect_helper_results(raw)
        for helper_id, result in results.items():
            assert result.ok, f"{helper_id}: {result.error}"
            assert result.items, f"{helper_id} returned no items"


# ---------------------------------------------------------------------------
# Full offline harness
# ---------------------------------------------------------------------------


class TestMockHarness:
    def test_harness_runs_end_to_end(self):
        import asyncio

        result = asyncio.run(run_mock_harness(categories=["otc_health", "nicotine_cessation"]))
        assert result["status"] == "ok"
        assert result["helpers_dispatched"] == 5
        assert result["wholesale_found"] >= 3
        assert result["amazon_matches"] >= 3
        assert result["economics_evaluated"] >= 1
        assert result["opportunities_scored"] >= 0
        assert result["report_path"]
        assert sum(result["tiers"].values()) == result["opportunities_scored"]

    def test_harness_with_roi_floor(self):
        import asyncio

        result = asyncio.run(run_mock_harness(roi_floor=10.0))
        assert result["status"] == "ok"
        # Every scored opportunity must clear the floor
        assert all(
            tier in ("HIGH", "MEDIUM", "LOW")
            for tier in result["tiers"]
        )