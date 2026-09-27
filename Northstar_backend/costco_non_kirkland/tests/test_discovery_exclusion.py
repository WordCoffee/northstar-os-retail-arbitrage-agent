"""Test 1-2: local Costco source discovery + Kirkland exclusion + audit."""
from __future__ import annotations

import unittest
from unittest import mock

from costco_non_kirkland import (
    evaluate_exclusion,
    audit_exclusion,
    normalize_costco_record,
)
from costco_non_kirkland.sources import discover_costco_sources
from costco_non_kirkland.normalize import load_csv_records, load_discovery_catalog
from .fixtures import (
    KIRKLAND_BRAND,
    KIRKLAND_TITLE_ONLY,
    NON_KIRKLAND,
    NON_KIRKLAND_WITH_UPC,
    MISSING_BRAND_KIRKLAND_HINT,
    MISSING_BRAND_NO_HINT,
    KIRKLAND_IN_URL,
    KIRKLAND_IN_NOTES,
    write_csv_fixture,
    write_discovery_catalog_fixture,
    make_tmp_data_dir,
)


class KirklandExclusionTests(unittest.TestCase):
    def test_kirkland_in_brand_excluded(self):
        res = evaluate_exclusion(KIRKLAND_BRAND)
        self.assertTrue(res.excluded)
        self.assertEqual(res.exclusion_reason, "kirkland_signature_out_of_scope")
        self.assertFalse(res.eligible_for_costco_non_kirkland_workflow)
        self.assertFalse(res.manual_review_required)

    def test_kirkland_in_title_excluded(self):
        res = evaluate_exclusion(KIRKLAND_TITLE_ONLY)
        self.assertTrue(res.excluded)
        self.assertEqual(res.exclusion_reason, "kirkland_signature_out_of_scope")
        self.assertFalse(res.eligible_for_costco_non_kirkland_workflow)

    def test_kirkland_in_url_excluded(self):
        res = evaluate_exclusion(KIRKLAND_IN_URL)
        self.assertTrue(res.excluded)
        self.assertEqual(res.exclusion_reason, "kirkland_signature_out_of_scope")

    def test_kirkland_in_notes_excluded(self):
        res = evaluate_exclusion(KIRKLAND_IN_NOTES)
        self.assertTrue(res.excluded)
        self.assertEqual(res.exclusion_reason, "kirkland_signature_out_of_scope")

    def test_non_kirkland_brand_retained(self):
        res = evaluate_exclusion(NON_KIRKLAND)
        self.assertFalse(res.excluded)
        self.assertTrue(res.eligible_for_costco_non_kirkland_workflow)
        self.assertIsNone(res.exclusion_reason)

    def test_non_kirkland_with_upc_retained(self):
        res = evaluate_exclusion(NON_KIRKLAND_WITH_UPC)
        self.assertFalse(res.excluded)
        self.assertTrue(res.eligible_for_costco_non_kirkland_workflow)

    def test_missing_brand_but_kirkland_hint_excluded_and_review(self):
        res = evaluate_exclusion(MISSING_BRAND_KIRKLAND_HINT)
        self.assertTrue(res.excluded)
        self.assertTrue(res.manual_review_required)
        self.assertEqual(res.reason_code, "missing_brand_title_hints_kirkland")

    def test_missing_brand_no_hint_flagged_review_not_excluded(self):
        res = evaluate_exclusion(MISSING_BRAND_NO_HINT)
        self.assertFalse(res.excluded)
        self.assertFalse(res.eligible_for_costco_non_kirkland_workflow)
        self.assertTrue(res.manual_review_required)
        self.assertEqual(res.reason_code, "missing_brand")

    def test_exclusion_marks_but_never_deletes(self):
        rec = dict(KIRKLAND_BRAND)
        marked = evaluate_exclusion(rec).to_record(rec)
        self.assertIn("exclusion_reason", marked)
        self.assertIn("eligible_for_costco_non_kirkland_workflow", marked)
        # original fields preserved
        self.assertEqual(marked["brand_raw"], KIRKLAND_BRAND["brand_raw"])
        self.assertEqual(marked["item_name"], KIRKLAND_BRAND["item_name"])

    def test_normalized_costco_record_preserves_source(self):
        norm = normalize_costco_record(NON_KIRKLAND_WITH_UPC, source_file="fixture.json")
        self.assertEqual(norm["brand_raw"], "SwissGear")
        self.assertEqual(norm["upc"], "799488123456")
        self.assertEqual(norm["evidence_class"], "cached_source_snapshot")
        self.assertIn(norm["freshness_status"], ("fresh", "aging", "stale", "unknown"))
        self.assertIsNotNone(norm["observed_at"])
        self.assertIsNotNone(norm["imported_at"])


class AuditExclusionTests(unittest.TestCase):
    def test_audit_counts(self):
        records = [KIRKLAND_BRAND, KIRKLAND_TITLE_ONLY, NON_KIRKLAND, NON_KIRKLAND_WITH_UPC,
                   MISSING_BRAND_KIRKLAND_HINT, MISSING_BRAND_NO_HINT, KIRKLAND_IN_URL]
        audit = audit_exclusion(records)
        self.assertEqual(audit.total_discovered, 7)
        self.assertEqual(audit.excluded_kirkland, 4)  # brand, title, url, missing-brand-hint
        self.assertEqual(audit.non_kirkland_eligible, 2)
        self.assertEqual(audit.missing_brand, 1)
        self.assertEqual(audit.ambiguous_brand, 2)
        self.assertGreaterEqual(audit.manual_review_required, 2)

    def test_audit_never_mutates_inputs(self):
        records = [dict(KIRKLAND_BRAND), dict(NON_KIRKLAND)]
        snapshot = [dict(r) for r in records]
        audit_exclusion(records)
        self.assertEqual(records, snapshot)


class SourceDiscoveryTests(unittest.TestCase):
    def test_discovers_fixture_csv(self):
        tmp = make_tmp_data_dir()
        write_csv_fixture([NON_KIRKLAND, KIRKLAND_BRAND], tmp / "costco-items.csv")
        with mock.patch("costco_non_kirkland.sources.DEFAULT_DATA_DIR", tmp):
            sources = discover_costco_sources(data_dir=str(tmp))
        csv_source = next(s for s in sources if s.source_name == "costco-items.csv")
        self.assertTrue(csv_source.exists)
        self.assertEqual(csv_source.raw_record_count, 2)

    def test_discovers_fixture_discovery_catalog(self):
        tmp = make_tmp_data_dir()
        write_discovery_catalog_fixture([NON_KIRKLAND, KIRKLAND_BRAND], tmp / "costco-discovery-catalog.json")
        sources = discover_costco_sources(data_dir=str(tmp))
        cat = next(s for s in sources if s.source_name == "costco-discovery-catalog.json")
        self.assertTrue(cat.exists)
        self.assertEqual(cat.raw_record_count, 2)

    def test_load_csv_records(self):
        tmp = make_tmp_data_dir()
        p = tmp / "costco-items.csv"
        write_csv_fixture([NON_KIRKLAND, KIRKLAND_BRAND], p)
        rows = load_csv_records(str(p))
        self.assertEqual(len(rows), 2)

    def test_load_discovery_catalog(self):
        tmp = make_tmp_data_dir()
        p = tmp / "costco-discovery-catalog.json"
        write_discovery_catalog_fixture([NON_KIRKLAND, KIRKLAND_BRAND], p)
        rows = load_discovery_catalog(str(p))
        self.assertEqual(len(rows), 2)


if __name__ == "__main__":
    unittest.main()