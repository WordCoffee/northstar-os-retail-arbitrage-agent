"""Tests for sign-in gate, disallowed product classes, and Amazon-scan guard."""
from __future__ import annotations

import unittest
from unittest import mock

import test_network_guard  # noqa: F401

from costco_non_kirkland.disallowed import (
    classify_disallowed,
    evaluate_disallowed,
    audit_disallowed,
)
from costco_non_kirkland.signin import (
    require_signin,
    mark_signed_in,
    SIGN_IN_URLS,
)
from costco_non_kirkland.amazon_guard import (
    AmazonDirectScanProhibited,
    is_amazon_direct_url,
    assert_no_amazon_direct_scan,
    authorized_market_source,
    verify_market_provenance,
)


def _isolated_store():
    import tempfile
    from pathlib import Path
    import data_layer
    tmp = Path(tempfile.mkdtemp(prefix="cnk-signin-"))
    data_layer._SQLITE_PATH = tmp / "northstar.db"
    data_layer._db_instance = None
    from costco_non_kirkland.store import PipelineStore
    return PipelineStore()


# ---------------------------------------------------------------------------
# Disallowed product classes
# ---------------------------------------------------------------------------

HAZARDOUS = {"brand_raw": "Acme", "item_name": "Muriatic Acid Cleaner, 1 gal"}
MELTABLE = {"brand_raw": "SweetCo", "item_name": "Belgian Milk Chocolate Bar, 24 count"}
EXPIRY = {"brand_raw": "FarmCo", "item_name": "Refrigerated Dairy Yogurt Cups, 12 count"}
OVERSIZED = {"brand_raw": "HeavyCo", "item_name": "Pallet Rack Storage System", "size_or_weight_raw": "250 lb"}
ALLOWED = {"brand_raw": "Dream Plush", "item_name": "Adjustable Wedge Pillow with Cooling Cover"}


class DisallowedClassTests(unittest.TestCase):
    def test_hazardous_classified(self):
        classes = classify_disallowed(HAZARDOUS)
        self.assertIn("hazardous", classes)

    def test_meltable_classified(self):
        self.assertIn("meltable", classify_disallowed(MELTABLE))

    def test_expiry_classified(self):
        self.assertIn("expiry_risk", classify_disallowed(EXPIRY))

    def test_oversize_size_hint(self):
        classes = classify_disallowed(OVERSIZED)
        self.assertIn("oversized", classes)

    def test_allowed_product_no_classes(self):
        self.assertEqual(classify_disallowed(ALLOWED), [])

    def test_evaluate_disallowed_marks_never_deletes(self):
        res = evaluate_disallowed(HAZARDOUS)
        self.assertTrue(res.excluded)
        self.assertEqual(res.exclusion_reason, "disallowed_product_class")
        self.assertEqual(res.disallowed_classes, ["hazardous"])
        rec = res.to_record(dict(HAZARDOUS))
        self.assertFalse(rec["eligible_for_costco_non_kirkland_workflow"])
        self.assertEqual(rec["exclusion_reason"], "disallowed_product_class")
        self.assertEqual(rec["item_name"], HAZARDOUS["item_name"])  # preserved

    def test_allowed_evaluate(self):
        res = evaluate_disallowed(ALLOWED)
        self.assertFalse(res.excluded)
        self.assertEqual(res.reason_code, "allowed")

    def test_audit_disallowed_counts(self):
        audit = audit_disallowed([HAZARDOUS, MELTABLE, EXPIRY, OVERSIZED, ALLOWED])
        self.assertEqual(audit.excluded_disallowed, 4)
        self.assertEqual(audit.allowed, 1)
        self.assertGreaterEqual(audit.by_class.get("hazardous", 0), 1)
        self.assertGreaterEqual(audit.by_class.get("oversized", 0), 1)

    def test_audit_never_mutates(self):
        recs = [dict(HAZARDOUS), dict(ALLOWED)]
        snapshot = [dict(r) for r in recs]
        audit_disallowed(recs)
        self.assertEqual(recs, snapshot)


# ---------------------------------------------------------------------------
# Sign-in gate
# ---------------------------------------------------------------------------

class SignInGateTests(unittest.TestCase):
    def test_require_signin_prompts_when_not_confirmed(self):
        store = _isolated_store()
        prompt = require_signin("selleramp", store=store)
        self.assertTrue(prompt.required)
        self.assertIn("SIGN-IN REQUIRED", prompt.message)
        self.assertEqual(prompt.service, "selleramp")
        self.assertIn("selleramp", prompt.url or "")

    def test_mark_signed_in_then_required_false(self):
        store = _isolated_store()
        mark_signed_in("selleramp", store=store)
        prompt = require_signin("selleramp", store=store)
        self.assertFalse(prompt.required)
        self.assertTrue(prompt.signed_in)

    def test_env_flag_bypass(self):
        store = _isolated_store()
        with mock.patch.dict("os.environ", {"NORTHSTAR_SELLERAMP_SIGNED_IN": "1"}):
            prompt = require_signin("selleramp", store=store)
            self.assertFalse(prompt.required)

    def test_unknown_service(self):
        store = _isolated_store()
        prompt = require_signin("nope", store=store)
        self.assertTrue(prompt.required)
        self.assertIn("Unknown sign-in service", prompt.message)

    def test_retired_service_rejected(self):
        store = _isolated_store()
        prompt = require_signin("sellersprite", store=store)
        self.assertTrue(prompt.required)
        self.assertIn("retired", prompt.message.lower())
        self.assertIsNone(prompt.url)
        out = mark_signed_in("sellersprite", store=store)
        self.assertFalse(out["ok"])
        self.assertEqual(out.get("reason"), "retired_provider")

    def test_sign_in_urls_for_all_services(self):
        self.assertIn("costco", SIGN_IN_URLS)
        self.assertIn("selleramp", SIGN_IN_URLS)
        self.assertNotIn("sellersprite", SIGN_IN_URLS)

    def test_sign_in_cli_check_requires(self):
        # CLI path: default check returns exit 1 when not signed in.
        from costco_non_kirkland.signin import main as signin_main
        rc = signin_main(["--service", "selleramp"])
        self.assertEqual(rc, 1)


# ---------------------------------------------------------------------------
# Amazon direct-scan guard
# ---------------------------------------------------------------------------

class AmazonGuardTests(unittest.TestCase):
    def test_detects_amazon_urls(self):
        self.assertTrue(is_amazon_direct_url("https://www.amazon.com/dp/B0TEST"))
        self.assertTrue(is_amazon_direct_url("https://amazon.com/s?k=test"))

    def test_non_amazon_url_not_detected(self):
        self.assertFalse(is_amazon_direct_url("https://sas.selleramp.com/r/sas/lookup"))
        self.assertFalse(is_amazon_direct_url("https://example-export-host.test/search"))

    def test_assert_blocks_amazon_url(self):
        with self.assertRaises(AmazonDirectScanProhibited):
            assert_no_amazon_direct_scan("https://www.amazon.com/dp/B0TEST")

    def test_assert_allows_provider_deep_link(self):
        # SAS deep links are allowed; Amazon pages are not.
        assert_no_amazon_direct_scan("https://sas.selleramp.com/r/sas/lookup?search_term=B0TEST")
        assert_no_amazon_direct_scan(asin="B0TEST")

    def test_authorized_market_source(self):
        self.assertTrue(authorized_market_source("selleramp"))
        self.assertFalse(authorized_market_source("sellersprite"))  # retired
        self.assertFalse(authorized_market_source("amazon.com"))
        self.assertFalse(authorized_market_source(None))

    def test_verify_market_provenance_fail_closed(self):
        fields = {
            "price": {"source": "selleramp"},
            "bsr": {"source": "sellersprite"},  # retired -> not authorized
            "review_count": {"source": "amazon.com"},
        }
        checks = verify_market_provenance(fields)
        self.assertTrue(checks["price"]["ok"])
        self.assertFalse(checks["bsr"]["ok"])
        self.assertFalse(checks["review_count"]["ok"])


if __name__ == "__main__":
    unittest.main()