"""Provider import tests (Phase 2) — zero network, CSV+JSON, idempotency, dry-run.

SellerAmp is the only supported manual-export provider. SellerSprite was retired
2026-09-27 (trial expired) and MUST fail closed by name as retired/unsupported.
"""
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

import test_network_guard  # noqa: F401

from costco_non_kirkland.provider_imports import (
    SellerAmpImporter,
    build_import_report,
)
from costco_non_kirkland.provider_imports.common import sha256_file, detect_provider
from costco_non_kirkland.provider_imports.mapping import ensure_provider_provenance
from costco_non_kirkland.providers import provider_factory, ProviderRetired, RETIRED_PROVIDERS
from .fixtures import (
    write_selleramp_csv,
    write_selleramp_json,
    SELLERAMP_CSV,
)


def _isolated_store():
    import data_layer
    tmp = Path(tempfile.mkdtemp(prefix="cnk-imp-"))
    data_layer._SQLITE_PATH = tmp / "northstar.db"
    data_layer._db_instance = None
    from costco_non_kirkland.store import PipelineStore
    return PipelineStore()


class ProviderImportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="cnk-prov-"))

    def _selleramp_csv(self):
        p = self.tmp / "selleramp.csv"
        write_selleramp_csv(p)
        return str(p)

    def _selleramp_json(self):
        p = self.tmp / "selleramp.json"
        write_selleramp_json(p)
        return str(p)

    # 1. SellerAmp CSV import succeeds with zero network calls
    def test_selleramp_csv_import(self):
        store = _isolated_store()
        imp = SellerAmpImporter(store=store)
        res = imp.import_file(self._selleramp_csv(), dry_run=True)
        self.assertEqual(res["provider"], "selleramp")
        self.assertEqual(res["rows_total"], 2)
        self.assertEqual(res["network_calls_made"], 0)
        self.assertEqual(res["rows_imported"], 2)

    # 2. SellerAmp JSON import succeeds
    def test_selleramp_json_import(self):
        store = _isolated_store()
        imp = SellerAmpImporter(store=store)
        res = imp.import_file(self._selleramp_json(), dry_run=True)
        self.assertEqual(res["provider"], "selleramp")
        self.assertEqual(res["rows_imported"], 2)
        self.assertEqual(res["network_calls_made"], 0)

    # 3. Duplicate source file hash does not create duplicate snapshots
    def test_duplicate_hash_no_duplicate_snapshots(self):
        store = _isolated_store()
        path = self._selleramp_csv()
        imp = SellerAmpImporter(store=store)
        imp.import_file(path, dry_run=False)
        imp.import_file(path, dry_run=False)
        snapshots = store.list_market_snapshots(provider="selleramp")
        asins = [s.get("asin") for s in snapshots]
        self.assertEqual(len(set(asins)), len(asins))
        res2 = imp.import_file(path, dry_run=True)
        self.assertEqual(res2["row_status_counts"].get("duplicate", 0), 2)

    # 4. Dry run does not write DB records
    def test_dry_run_no_writes(self):
        store = _isolated_store()
        imp = SellerAmpImporter(store=store)
        imp.import_file(self._selleramp_csv(), dry_run=True)
        self.assertEqual(len(store.list_market_snapshots(provider="selleramp")), 0)

    # 5. Unsupported provider schema fails closed
    def test_unsupported_provider_fails(self):
        provider, note = detect_provider([{"foo": "bar"}], filename="unknown.csv", explicit="notaprovider")
        self.assertIsNone(provider)
        self.assertIn("unsupported explicit provider", note)
        p = self.tmp / "unknown.csv"
        p.write_text("foo,bar\n1,2\n", encoding="utf-8")
        imp = SellerAmpImporter(store=None)
        res = imp.import_file(str(p), dry_run=True)
        self.assertEqual(res["rows_imported"], 0)
        self.assertEqual(res["network_calls_made"], 0)

    # 6. Retired provider (SellerSprite) is rejected by name
    def test_retired_provider_rejected_by_name(self):
        provider, note = detect_provider([], filename="export.csv", explicit="sellersprite")
        self.assertIsNone(provider)
        self.assertIn("retired provider", note)
        self.assertIn("sellersprite", RETIRED_PROVIDERS)

    # 7. Retired provider factory fails closed with ProviderRetired
    def test_retired_provider_factory_raises(self):
        with self.assertRaises(ProviderRetired):
            provider_factory("sellersprite")

    # 8. Retired-provider file is rejected even without an explicit provider
    def test_retired_provider_file_rejected(self):
        provider, note = detect_provider([{"asin": "B0X"}], filename="my-sellersprite-export.csv", explicit=None)
        self.assertIsNone(provider)
        self.assertIn("retired provider file detected", note)

    # 9. Ambiguous provider detection requires explicit provider choice
    def test_ambiguous_detection_requires_explicit(self):
        provider, note = detect_provider([], filename="unknown.txt", explicit=None)
        self.assertIsNone(provider)
        self.assertIn("--provider required", note)

    # 10. Imported provider data has complete provenance
    def test_provenance_complete(self):
        store = _isolated_store()
        imp = SellerAmpImporter(store=store)
        res = imp.import_file(self._selleramp_csv(), dry_run=True)
        snap = res["snapshots"][0]
        field = snap["fields"]["asin"]
        for key in ("provider_name", "provider_export_filename", "provider_export_sha256",
                    "provider_schema_version", "provider_row_number", "provider_record_id",
                    "provider_snapshot_id", "observed_at", "ingested_at", "field_provenance",
                    "field_confidence", "is_provider_reported", "raw_source_reference",
                    "freshness_status"):
            self.assertIn(key, field, f"missing provenance key {key}")
        self.assertTrue(ensure_provider_provenance(snap))

    # 11. Direct Amazon.com URL input is rejected by amazon_guard
    def test_amazon_url_rejected(self):
        from costco_non_kirkland.amazon_guard import assert_no_amazon_direct_scan, AmazonDirectScanProhibited
        with self.assertRaises(AmazonDirectScanProhibited):
            assert_no_amazon_direct_scan("https://www.amazon.com/dp/B0TEST")

    # 12. No provider import code path performs network access
    def test_no_network(self):
        import requests
        from network_guard import NetworkGuardViolation
        with self.assertRaises(NetworkGuardViolation):
            requests.get("http://127.0.0.1:9/", timeout=0.1)

    def test_import_report_confirmation(self):
        store = _isolated_store()
        imp = SellerAmpImporter(store=store)
        res = imp.import_file(self._selleramp_csv(), dry_run=True)
        report = build_import_report(res)
        self.assertEqual(report["confirmation"], "Network calls made: 0")
        self.assertEqual(report["network_calls_made"], 0)

    def test_sha256_stable(self):
        path = self._selleramp_csv()
        self.assertEqual(sha256_file(path), sha256_file(path))


if __name__ == "__main__":
    unittest.main()
