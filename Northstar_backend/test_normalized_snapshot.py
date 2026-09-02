"""Offline tests for normalized_snapshot.py — provider-neutral normalization pipeline.
ZERO network, ZERO provider calls."""

import unittest
from unittest import mock

import normalized_snapshot as ns


class NormalizeLiveSnapshotTests(unittest.TestCase):
    """Fail-closed normalization of raw provider responses."""

    def _minimal_raw(self, **overrides):
        """Minimal valid raw response that passes all gates."""
        base = {
            "asin": "B000000001",
            "title": "Test Product (100ct)",
            "price": 12.99,
            "bsr": "#4960 in Health & Household",
        }
        base.update(overrides)
        return base

    def _manifest(self, **overrides):
        """Manifest record for the benchmark ASIN."""
        base = {
            "asin": "B000000001",
            "benchmark_title": "Test Product (100ct)",
        }
        base.update(overrides)
        return base

    def test_full_capture_valid_snapshot(self):
        """Valid raw + matching manifest produces a complete snapshot."""
        raw = self._minimal_raw()
        manifest = self._manifest()
        snap = ns.normalize_live_snapshot(raw, manifest, provider="EASYPARSER")
        self.assertEqual(snap["asin"], "B000000001")
        self.assertEqual(snap["schema_version"], 1)
        self.assertIn("EASYPARSER", snap["sources"])
        self.assertEqual(snap["facts"]["market"]["amazon_price"], 12.99)
        self.assertEqual(snap["facts"]["identity"]["name"], "Test Product (100ct)")
        self.assertEqual(snap["facts"]["identity"]["pack_match"], "match")
        bsr = snap["facts"]["market"]["bsr"]
        self.assertEqual(bsr["bsr_primary_rank"], 4960)
        self.assertEqual(bsr["bsr_primary_category"], "Health & Household")
        self.assertEqual(bsr["bsr_capture_status"], "verified")

    def test_missing_asin_raises(self):
        """Raw payload without ASIN raises NormalizationError."""
        raw = {"title": "Test", "price": 10.0}
        manifest = self._manifest()
        with self.assertRaises(ns.NormalizationError) as ctx:
            ns.normalize_live_snapshot(raw, manifest)
        self.assertEqual(ctx.exception.status, "missing_asin")

    def test_wrong_asin_raises_identity_conflict(self):
        """Returned ASIN != manifest ASIN raises identity_conflict."""
        raw = self._minimal_raw(asin="B000000002")
        manifest = self._manifest(asin="B000000001")
        with self.assertRaises(ns.NormalizationError) as ctx:
            ns.normalize_live_snapshot(raw, manifest)
        self.assertEqual(ctx.exception.status, "identity_conflict")

    def test_missing_price_raises(self):
        """Raw payload without amazon_price raises NormalizationError."""
        raw = self._minimal_raw()
        del raw["price"]
        manifest = self._manifest()
        with self.assertRaises(ns.NormalizationError) as ctx:
            ns.normalize_live_snapshot(raw, manifest)
        self.assertEqual(ctx.exception.status, "missing_market_price")

    def test_provider_rejection_raises(self):
        """DataForSEO task_error state raises provider_rejected_*."""
        raw = {
            "asin": "B000000001",
            "title": "Test",
            "price": 10.0,
            "tasks_error": 1,
            "tasks": [{"status_code": 40402, "status_message": "Invalid Path."}],
        }
        manifest = self._manifest()
        with self.assertRaises(ns.NormalizationError) as ctx:
            ns.normalize_live_snapshot(raw, manifest, provider="DATAFORSEO")
        self.assertTrue(ctx.exception.status.startswith("provider_rejected_"))

    def test_secret_in_payload_refused(self):
        """Secret-like strings in raw payload raise secret_detected.
        Patterns match unquoted key formats (api_key=value, api_key: value)."""
        # Use a raw string format that the _SECRET_PATTERNS can detect
        raw = self._minimal_raw()
        raw["extra_field"] = 'api_key=sk_live_abcdefghijklmnop'  # unquoted key format
        manifest = self._manifest()
        with self.assertRaises(ns.NormalizationError) as ctx:
            ns.normalize_live_snapshot(raw, manifest)
        self.assertEqual(ctx.exception.status, "secret_detected")

    def test_title_brand_pack_conflict_raises(self):
        """Title identity conflict with benchmark raises identity_conflict."""
        raw = self._minimal_raw(title="Completely Different Product (200ct)")
        manifest = self._manifest(benchmark_title="Test Product (100ct)")
        with self.assertRaises(ns.NormalizationError) as ctx:
            ns.normalize_live_snapshot(raw, manifest)
        self.assertEqual(ctx.exception.status, "identity_conflict")

    def test_bsr_parse_error_raises(self):
        """Unparseable BSR raw string raises parse_error."""
        raw = self._minimal_raw(bsr="#abc in Category")
        manifest = self._manifest()
        with self.assertRaises(ns.NormalizationError) as ctx:
            ns.normalize_live_snapshot(raw, manifest)
        self.assertEqual(ctx.exception.status, "parse_error")

    def test_missing_bsr_is_unavailable_not_error(self):
        """Missing BSR is fine - status unavailable, not an error."""
        raw = self._minimal_raw()
        del raw["bsr"]
        manifest = self._manifest()
        snap = ns.normalize_live_snapshot(raw, manifest)
        self.assertEqual(snap["facts"]["market"]["bsr"]["bsr_capture_status"], "unavailable")

    def test_pack_conflict_detection(self):
        """Pack size conflict sets pack_status=conflict and raises."""
        raw = self._minimal_raw(title="Test Product (200ct)")
        manifest = self._manifest(benchmark_title="Test Product (100ct)")
        with self.assertRaises(ns.NormalizationError) as ctx:
            ns.normalize_live_snapshot(raw, manifest)
        self.assertEqual(ctx.exception.status, "identity_conflict")

    def test_unsupported_provider_raises(self):
        """Unsupported provider name raises provider_not_supported."""
        raw = self._minimal_raw()
        manifest = self._manifest()
        with self.assertRaises(ns.NormalizationError) as ctx:
            ns.normalize_live_snapshot(raw, manifest, provider="NONEXISTENT")
        self.assertEqual(ctx.exception.status, "provider_not_supported")

    def test_try_normalize_accepted(self):
        """try_normalize returns accepted=True on success."""
        raw = self._minimal_raw()
        manifest = self._manifest()
        result = ns.try_normalize(raw, manifest)
        self.assertTrue(result["accepted"])
        self.assertIn("snapshot", result)
        self.assertEqual(result["asin"], "B000000001")

    def test_try_normalize_rejected(self):
        """try_normalize returns accepted=False with status/reason on failure."""
        raw = {"title": "Test"}  # missing ASIN and price
        manifest = self._manifest()
        result = ns.try_normalize(raw, manifest)
        self.assertFalse(result["accepted"])
        self.assertIn("status", result)
        self.assertIn("reason", result)

    def test_provenance_populated(self):
        """Snapshot carries provenance for market.amazon_price and market.bsr."""
        raw = self._minimal_raw()
        manifest = self._manifest()
        snap = ns.normalize_live_snapshot(raw, manifest, provider="BRIGHTDATA")
        prov = snap["facts"]["provenance"]
        self.assertIn("market.amazon_price", prov)
        self.assertEqual(prov["market.amazon_price"]["source"], "BRIGHTDATA")
        self.assertIn("market.bsr", prov)
        self.assertEqual(prov["market.bsr"]["source"], "BRIGHTDATA")

    def test_seller_counts_observed(self):
        """Seller counts computed from offers (observed, not claimed)."""
        raw = self._minimal_raw(
            offers=[
                {"fulfillment": "FBA", "price": 12.99},
                {"fulfillment": "FBA", "price": 13.50},
                {"fulfillment": "FBM", "price": 11.00},
            ]
        )
        manifest = self._manifest()
        snap = ns.normalize_live_snapshot(raw, manifest)
        sc = snap["facts"]["market"]["seller_counts"]
        self.assertEqual(sc["total_observed"], 3)
        self.assertEqual(sc["fba_observed"], 2)
        self.assertEqual(sc["fbm_observed"], 1)
        self.assertIsNone(sc["amazon_observed"])
        self.assertIsNone(sc["claimed_total"])

    def test_coverage_partial_when_no_offers(self):
        """Empty offers yields partial coverage with reason."""
        raw = self._minimal_raw()
        raw["offers"] = []
        manifest = self._manifest()
        snap = ns.normalize_live_snapshot(raw, manifest)
        cov = snap["facts"]["market"]["coverage"]
        self.assertFalse(cov["offer_list_available"])
        self.assertEqual(cov["offers_complete_status"], "unknown")
        self.assertIn("no offer roster", cov["coverage_reason"])

    def test_buy_box_populated_when_present(self):
        """Buy Box info included when present in raw."""
        raw = self._minimal_raw(
            buy_box={"price": 12.99, "seller_name": "Test Seller", "fulfillment": "FBA"}
        )
        manifest = self._manifest()
        snap = ns.normalize_live_snapshot(raw, manifest)
        bb = snap["facts"]["market"]["buy_box"]
        self.assertTrue(bb["available"])
        self.assertEqual(bb["price"], 12.99)
        self.assertEqual(bb["seller_name"], "Test Seller")
        self.assertEqual(bb["fulfillment"], "FBA")

    def test_pack_match_unavailable_when_title_missing(self):
        """Missing live or benchmark title -> pack_match unavailable."""
        raw = self._minimal_raw()
        del raw["title"]
        manifest = self._manifest()
        snap = ns.normalize_live_snapshot(raw, manifest)
        self.assertEqual(snap["facts"]["identity"]["pack_match"], "unavailable")


class ExtractHelpersTests(unittest.TestCase):
    """Direct tests of extraction helpers."""

    def test_extract_asin_variants(self):
        for key in ("asin", "ASIN", "product_asin", "item_asin"):
            raw = {key: "B0TEST1234"}
            self.assertEqual(ns._extract_asin(raw), "B0TEST1234")

    def test_extract_asin_nested_result(self):
        raw = {"result": [{"asin": "B0NESTED01"}]}
        self.assertEqual(ns._extract_asin(raw), "B0NESTED01")

    def test_extract_price_variants(self):
        for key in ("price", "amazon_price", "buybox_price", "buy_box_price"):
            raw = {key: "$12.99"}
            self.assertEqual(ns._extract_price(raw), 12.99)

    def test_extract_price_from_buy_box(self):
        raw = {"buy_box": {"price": 15.00}}
        self.assertEqual(ns._extract_price(raw), 15.00)

    def test_extract_reviews_variants(self):
        for key in ("reviews", "review_count", "reviews_count", "ratings_total"):
            raw = {key: "1,234"}
            self.assertEqual(ns._extract_reviews(raw), 1234)

    def test_extract_prime_fba_variants(self):
        for val in ("fba", "amazon", "FBA", "Amazon"):
            raw = {"prime_fba": val}
            self.assertEqual(ns._extract_prime_fba(raw), "yes")
        raw = {"prime_fba": "fbm"}
        self.assertEqual(ns._extract_prime_fba(raw), "no")

    def test_extract_bsr_raw(self):
        raw = {"bsr": "#123 in Category"}
        self.assertEqual(ns._extract_bsr_raw(raw), "#123 in Category")


class PackMatchTests(unittest.TestCase):
    """Pack size token matching logic."""

    def test_exact_match(self):
        self.assertEqual(ns._pack_match("Product (100ct)", "Product (100ct)"), "match")

    def test_conflict(self):
        self.assertEqual(ns._pack_match("Product (100ct)", "Product (200ct)"), "conflict")

    def test_unavailable_when_missing(self):
        self.assertEqual(ns._pack_match(None, "Product"), "unavailable")
        self.assertEqual(ns._pack_match("Product", None), "unavailable")
        self.assertEqual(ns._pack_match(None, None), "unavailable")


if __name__ == "__main__":
    unittest.main()