"""Offline tests for intel_schema.py — BSR evidence contract, snapshot validation,
and fixture generation. ZERO network, ZERO provider calls."""

import unittest
import intel_schema as schema


class NormalizeBsrTests(unittest.TestCase):
    """BSR capture states: verified, missing_live, missing_csv_reference,
    provider_not_supported, parse_error, identity_conflict, unavailable."""

    def test_full_capture_primary_only(self):
        """Raw BSR string parses to structured fact with primary rank+category."""
        raw = "#4,960 in Health & Household"
        result = schema.normalize_bsr(raw, source="test")
        self.assertEqual(result["bsr_primary_rank"], 4960)
        self.assertEqual(result["bsr_primary_category"], "Health & Household")
        self.assertIsNone(result["bsr_secondary_rank"])
        self.assertIsNone(result["bsr_secondary_category"])
        self.assertEqual(result["bsr_capture_status"], "verified")
        self.assertEqual(result["bsr_source"], "test")
        self.assertEqual(result["bsr_raw"], raw)

    def test_full_capture_with_secondary(self):
        """Raw BSR with two ranked categories captures both (parens preserved)."""
        raw = "#1,234 in Beauty & Personal Care (#5,678 in Skin Care)"
        result = schema.normalize_bsr(raw, source="test")
        self.assertEqual(result["bsr_primary_rank"], 1234)
        self.assertEqual(result["bsr_primary_category"], "Beauty & Personal Care (")
        self.assertEqual(result["bsr_secondary_rank"], 5678)
        self.assertEqual(result["bsr_secondary_category"], "Skin Care)")
        self.assertEqual(result["bsr_capture_status"], "verified")

    def test_missing_live_returns_unavailable(self):
        """None/empty raw yields status 'unavailable' with null ranks."""
        for raw in (None, "", "   "):
            result = schema.normalize_bsr(raw)
            self.assertEqual(result["bsr_capture_status"], "unavailable")
            self.assertIsNone(result["bsr_primary_rank"])
            self.assertIsNone(result["bsr_primary_category"])

    def test_not_listed_on_page_unavailable(self):
        """'Not listed on page' (case-insensitive) yields unavailable."""
        for raw in ("Not listed on page", "not listed on page", "NOT LISTED"):
            result = schema.normalize_bsr(raw)
            self.assertEqual(result["bsr_capture_status"], "unavailable")
            self.assertIsNone(result["bsr_primary_rank"])

    def test_parse_error_unparseable_string(self):
        """Unparseable raw string yields parse_error status."""
        raw = "Some weird text #abc in Category"
        result = schema.normalize_bsr(raw)
        self.assertEqual(result["bsr_capture_status"], "parse_error")
        self.assertIsNone(result["bsr_primary_rank"])
        self.assertEqual(result["bsr_raw"], raw)

    def test_provider_not_supported_status_via_caller(self):
        """normalize_bsr itself doesn't set provider_not_supported; callers do.
        This test confirms the status enum exists and is available for callers."""
        self.assertIn("provider_not_supported", schema.BSR_STATUSES)

    def test_identity_conflict_status_via_caller(self):
        """normalize_bsr itself doesn't set identity_conflict; callers do.
        Confirms the status enum exists."""
        self.assertIn("identity_conflict", schema.BSR_STATUSES)

    def test_missing_csv_reference_status_via_caller(self):
        """Confirms the status enum exists for benchmark missing BSR."""
        self.assertIn("missing_csv_reference", schema.BSR_STATUSES)

    def test_raw_preserved_always(self):
        """The original raw string is always preserved in bsr_raw."""
        raw = "#123 in Test Category"
        result = schema.normalize_bsr(raw, source="src")
        self.assertEqual(result["bsr_raw"], raw)


class BsrFieldCompletenessTests(unittest.TestCase):
    """Per-field capture status for normalized BSR fact."""

    def test_verified_fields_captured(self):
        bsr = {"bsr_capture_status": "verified",
               "bsr_primary_rank": 100, "bsr_primary_category": "Cat",
               "bsr_secondary_rank": 200, "bsr_secondary_category": "Sub"}
        result = schema.bsr_field_completeness(bsr)
        self.assertEqual(result["bsr_primary_rank"], "captured")
        self.assertEqual(result["bsr_primary_category"], "captured")
        self.assertEqual(result["bsr_secondary_rank"], "captured")
        self.assertEqual(result["bsr_secondary_category"], "captured")

    def test_verified_partial_nulls_unavailable(self):
        bsr = {"bsr_capture_status": "verified",
               "bsr_primary_rank": 100, "bsr_primary_category": None,
               "bsr_secondary_rank": None, "bsr_secondary_category": None}
        result = schema.bsr_field_completeness(bsr)
        self.assertEqual(result["bsr_primary_rank"], "captured")
        self.assertEqual(result["bsr_primary_category"], "unavailable")
        self.assertEqual(result["bsr_secondary_rank"], "unavailable")
        self.assertEqual(result["bsr_secondary_category"], "unavailable")

    def test_missing_live_propagates(self):
        for status in ("missing_live", "missing_csv_reference",
                       "provider_not_supported", "parse_error", "identity_conflict"):
            bsr = {"bsr_capture_status": status}
            result = schema.bsr_field_completeness(bsr)
            for key in ("bsr_primary_rank", "bsr_primary_category",
                        "bsr_secondary_rank", "bsr_secondary_category"):
                self.assertEqual(result[key], status)

    def test_unavailable_when_status_unknown(self):
        bsr = {"bsr_capture_status": "unknown_status"}
        result = schema.bsr_field_completeness(bsr)
        for key in ("bsr_primary_rank", "bsr_primary_category",
                    "bsr_secondary_rank", "bsr_secondary_category"):
            self.assertEqual(result[key], "unavailable")


class SnapshotValidationTests(unittest.TestCase):
    """validate_snapshot enforces: nulls for unknown, no zero-forbidden,
    provenance on populated value fields."""

    def _valid_minimal(self):
        return schema.fixture_minimal()

    def test_fixture_minimal_is_valid(self):
        """The minimal fixture passes validation with no errors."""
        snap = self._valid_minimal()
        errors = schema.validate_snapshot(snap)
        self.assertEqual(errors, [])

    def test_fixture_minimal_structure(self):
        """fixture_minimal has all required top-level keys and null facts."""
        snap = self._valid_minimal()
        for key in schema.REQUIRED_TOP_LEVEL:
            self.assertIn(key, snap)
        self.assertEqual(snap["schema_version"], schema.SCHEMA_VERSION)
        self.assertIsNone(snap["facts"]["identity"]["name"])
        self.assertIsNone(snap["facts"]["market"]["amazon_price"])
        bsr = snap["facts"]["market"]["bsr"]
        self.assertEqual(bsr["bsr_capture_status"], "unavailable")

    def test_zero_forbidden_rejected(self):
        """Numeric fields in ZERO_FORBIDDEN must be null, never 0."""
        snap = self._valid_minimal()
        snap["facts"]["market"]["amazon_price"] = 0
        errors = schema.validate_snapshot(snap)
        self.assertTrue(any("amazon_price is 0" in e for e in errors))

    def test_configured_zero_cost_allowed(self):
        """Prep/inbound/packaging/reserve costs at 0.00 are legitimate (not in ZERO_FORBIDDEN).
        They still require provenance when populated."""
        snap = self._valid_minimal()
        prov = {"source": "fee_engine", "fetched_at": "2026-08-17T12:00:00+00:00"}
        snap["facts"]["fees"]["prep_cost_per_unit"] = 0.0
        snap["facts"]["fees"]["inbound_cost_per_unit"] = 0.0
        snap["facts"]["fees"]["packaging_cost_per_unit"] = 0.0
        snap["facts"]["fees"]["return_reserve_rate"] = 0.0
        snap["facts"]["provenance"]["fees.prep_cost_per_unit"] = prov
        snap["facts"]["provenance"]["fees.inbound_cost_per_unit"] = prov
        snap["facts"]["provenance"]["fees.packaging_cost_per_unit"] = prov
        snap["facts"]["provenance"]["fees.return_reserve_rate"] = prov
        errors = schema.validate_snapshot(snap)
        # These are NOT in ZERO_FORBIDDEN, so no zero-forbidden error
        self.assertFalse(any("prep_cost" in e and "is 0" in e for e in errors))
        self.assertFalse(any("inbound_cost" in e and "is 0" in e for e in errors))

    def test_populated_value_requires_provenance(self):
        """Any non-null value field must carry provenance unless exempt."""
        snap = self._valid_minimal()
        snap["facts"]["market"]["amazon_price"] = 12.99
        # No provenance entry -> error
        errors = schema.validate_snapshot(snap)
        self.assertTrue(any("market.amazon_price has no provenance" in e for e in errors))

    def test_provenance_satisfied(self):
        """Provenance entry for the field clears the error."""
        snap = self._valid_minimal()
        snap["facts"]["market"]["amazon_price"] = 12.99
        snap["facts"]["provenance"]["market.amazon_price"] = {"source": "easyparser", "fetched_at": "2026-08-17T12:00:00+00:00"}
        errors = schema.validate_snapshot(snap)
        self.assertFalse(any("market.amazon_price has no provenance" in e for e in errors))

    def test_status_fields_exempt_from_provenance(self):
        """Fields with 'status', 'confidence', 'match', etc. are provenance-exempt."""
        snap = self._valid_minimal()
        snap["facts"]["cost"]["cost_status"] = "invoice_confirmed"
        snap["facts"]["economics"]["economics_confidence"] = "estimated"
        # No provenance needed for these
        errors = schema.validate_snapshot(snap)
        self.assertFalse(any("cost_status" in e or "economics_confidence" in e for e in errors))

    def test_schema_version_enforced(self):
        snap = self._valid_minimal()
        snap["schema_version"] = 999
        errors = schema.validate_snapshot(snap)
        self.assertTrue(any("schema_version must be 1" in e for e in errors))

    def test_asin_format_enforced(self):
        snap = self._valid_minimal()
        snap["asin"] = "INVALID"
        errors = schema.validate_snapshot(snap)
        self.assertTrue(any("asin must be a 10-character" in e for e in errors))

    def test_ingested_at_required(self):
        snap = self._valid_minimal()
        snap["ingested_at"] = ""
        errors = schema.validate_snapshot(snap)
        self.assertTrue(any("ingested_at must be a non-empty" in e for e in errors))

    def test_sources_must_be_dict(self):
        snap = self._valid_minimal()
        snap["sources"] = "not a dict"
        errors = schema.validate_snapshot(snap)
        self.assertTrue(any("sources must be a dict" in e for e in errors))

    def test_facts_must_be_dict(self):
        snap = self._valid_minimal()
        snap["facts"] = "not a dict"
        errors = schema.validate_snapshot(snap)
        self.assertTrue(any("facts must be a dict" in e for e in errors))

    def test_buy_box_available_requires_price_and_source(self):
        snap = self._valid_minimal()
        snap["facts"]["market"]["buy_box"] = {"available": True, "price": None, "source": None}
        errors = schema.validate_snapshot(snap)
        self.assertTrue(any("buy_box.available is true but price is null" in e for e in errors))
        self.assertTrue(any("buy_box.source required" in e for e in errors))

    def test_buy_box_price_zero_rejected(self):
        snap = self._valid_minimal()
        snap["facts"]["market"]["buy_box"] = {"available": True, "price": 0, "source": "test"}
        errors = schema.validate_snapshot(snap)
        self.assertTrue(any("buy_box.price is 0" in e for e in errors))

    def test_offer_price_zero_rejected(self):
        snap = self._valid_minimal()
        snap["facts"]["market"]["offers"] = [{"price": 0, "fulfillment": "FBA"}]
        errors = schema.validate_snapshot(snap)
        self.assertTrue(any("price is 0" in e for e in errors))

    def test_offer_fulfillment_values(self):
        snap = self._valid_minimal()
        snap["facts"]["market"]["offers"] = [{"price": 10, "fulfillment": "INVALID"}]
        errors = schema.validate_snapshot(snap)
        self.assertTrue(any("fulfillment invalid" in e for e in errors))

    def test_offers_must_be_list(self):
        snap = self._valid_minimal()
        snap["facts"]["market"]["offers"] = "not a list"
        errors = schema.validate_snapshot(snap)
        self.assertTrue(any("offers must be a list" in e for e in errors))


class SnapshotFromFixtureTests(unittest.TestCase):
    """snapshot_from_fixture stamps schema_version and asin placeholders."""

    def test_stamps_missing_fields(self):
        fixture = {"asin": "B0TEST1234"}
        snap = schema.snapshot_from_fixture(fixture)
        self.assertEqual(snap["schema_version"], schema.SCHEMA_VERSION)
        self.assertEqual(snap["asin"], "B0TEST1234")

    def test_preserves_existing(self):
        fixture = {"schema_version": 5, "asin": "B0EXIST123"}
        snap = schema.snapshot_from_fixture(fixture)
        self.assertEqual(snap["schema_version"], 5)
        self.assertEqual(snap["asin"], "B0EXIST123")


class SnapshotShapeTests(unittest.TestCase):
    """Verify the overall snapshot shape matches the spec's required sections."""

    def test_top_level_keys(self):
        snap = schema.fixture_minimal()
        required = {"schema_version", "asin", "ingested_at", "sources", "facts"}
        self.assertEqual(set(snap.keys()), required)

    def test_facts_sections(self):
        snap = schema.fixture_minimal()
        facts = snap["facts"]
        required = {"identity", "cost", "fees", "demand", "market", "economics", "provenance"}
        self.assertEqual(set(facts.keys()), required)

    def test_identity_subkeys(self):
        snap = schema.fixture_minimal()
        id_keys = set(snap["facts"]["identity"].keys())
        self.assertEqual(id_keys, {"name", "pack_match", "upc_or_ean", "net_weight_lbs"})

    def test_cost_subkeys(self):
        snap = schema.fixture_minimal()
        cost_keys = set(snap["facts"]["cost"].keys())
        self.assertEqual(cost_keys, {"costco_cost", "cost_status", "source", "paid_cost_invoice"})

    def test_fees_subkeys(self):
        snap = schema.fixture_minimal()
        fees_keys = set(snap["facts"]["fees"].keys())
        expected = {"referral_fee", "referral_fee_confidence", "fba_fee", "fba_fee_status",
                    "prep_cost_per_unit", "inbound_cost_per_unit", "packaging_cost_per_unit",
                    "return_reserve_rate"}
        self.assertEqual(fees_keys, expected)

    def test_demand_subkeys(self):
        snap = schema.fixture_minimal()
        demand_keys = set(snap["facts"]["demand"].keys())
        self.assertEqual(demand_keys, {"estimated_monthly_sales", "sales_estimation_method",
                                       "sales_estimation_confidence"})

    def test_market_subkeys(self):
        snap = schema.fixture_minimal()
        mkt_keys = set(snap["facts"]["market"].keys())
        # fixture_minimal includes these market fields; prime_fba is optional
        expected = {"amazon_price", "bsr", "buy_box", "seller_counts", "coverage",
                    "offers", "prime_fba"}
        self.assertTrue(expected.issuperset(mkt_keys),
                        f"market keys {mkt_keys} not subset of expected {expected}")

    def test_economics_subkeys(self):
        snap = schema.fixture_minimal()
        econ_keys = set(snap["facts"]["economics"].keys())
        self.assertEqual(econ_keys, {"net_profit", "roi_pct", "economics_confidence", "economics_status"})


if __name__ == "__main__":
    unittest.main()