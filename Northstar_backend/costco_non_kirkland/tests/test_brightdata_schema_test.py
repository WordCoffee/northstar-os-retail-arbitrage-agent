"""Tests for Bright Data URL resolution + 3-item schema-test manifest (offline)."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import test_network_guard  # noqa: F401

from costco_non_kirkland.brightdata_costco_enrichment import (
    is_costco_product_url,
    resolve_product_url,
    build_schema_test_manifest,
    load_collector_config,
)
from .fixtures import source_fixture


def _isolated_store():
    import data_layer
    tmp = Path(tempfile.mkdtemp(prefix="cnk-sct-"))
    data_layer._SQLITE_PATH = tmp / "northstar.db"
    data_layer._db_instance = None
    from costco_non_kirkland.store import PipelineStore
    return PipelineStore()


class UrlResolutionTests(unittest.TestCase):
    def test_verified_source_url(self):
        r = source_fixture(id="u1", costco_item_number="986654",
                           source_url="https://www.costco.com/.product.986654.html")
        res = resolve_product_url(r)
        self.assertEqual(res["status"], "verified_source_url")
        self.assertEqual(res["url"], "https://www.costco.com/.product.986654.html")

    def test_derived_from_item_number_when_supported(self):
        r = source_fixture(id="u2", costco_item_number="123456", source_url=None)
        res = resolve_product_url(r, template_supported=True)
        self.assertEqual(res["status"], "derived_from_item_number")
        self.assertEqual(res["url"], "https://www.costco.com/.product.123456.html")

    def test_url_resolution_required_when_unsupported(self):
        r = source_fixture(id="u3", costco_item_number="123456", source_url=None)
        res = resolve_product_url(r, template_supported=False)
        self.assertEqual(res["status"], "url_resolution_required")
        self.assertIsNone(res["url"])

    def test_no_title_guessing(self):
        # Title present, but no URL and non-numeric item -> must NOT be resolved.
        r = source_fixture(id="u4", costco_item_number="ABC-XYZ", source_url=None,
                           title_raw="Unitex 100% Cotton Towel")
        res = resolve_product_url(r, template_supported=True)
        self.assertEqual(res["status"], "url_resolution_required")

    def test_is_costco_product_url(self):
        self.assertTrue(is_costco_product_url("https://www.costco.com/.product.986654.html"))
        self.assertFalse(is_costco_product_url("https://www.costco.com/fixture.html"))
        self.assertFalse(is_costco_product_url(None))

    def test_non_product_source_url_is_not_verified_but_derivable(self):
        # A non-product source_url must NOT be treated as a verified product URL;
        # it may still be derived from the item number via the supported pattern.
        r = source_fixture(id="u5", costco_item_number="986654",
                           source_url="https://www.costco.com/some/search.html")
        res = resolve_product_url(r)
        self.assertEqual(res["status"], "derived_from_item_number")
        self.assertEqual(res["url"], "https://www.costco.com/.product.986654.html")

    def test_non_numeric_item_url_resolution_required(self):
        r = source_fixture(id="u6", costco_item_number="N/A", source_url=None)
        self.assertEqual(resolve_product_url(r)["status"], "url_resolution_required")


class SchemaTestManifestTests(unittest.TestCase):
    def test_caps_and_criteria(self):
        store = _isolated_store()
        # 4 eligible records with verified URLs; only 3 should be selected.
        for i, item in enumerate(["986654", "1884230", "1900871", "1111111"]):
            store.upsert_source_product(source_fixture(
                id=f"m{i}", costco_item_number=item,
                source_url=f"https://www.costco.com/.product.{item}.html"), run_id="run_s")
        m = build_schema_test_manifest(store, run_id="run_s", max_items=3)
        self.assertEqual(m["sample_size"], 3)
        self.assertEqual(m["network_calls_made"], 0)
        for c in m["candidates"]:
            self.assertEqual(c["url_status"], "verified_source_url")
            self.assertTrue(is_costco_product_url(c["url"]))

    def test_collector_config_loaded(self):
        cfg = load_collector_config()
        self.assertEqual(cfg.get("source_id"), "gd_mkcbmac44j178pook")
        self.assertEqual(cfg.get("input_type"), "url")

    def test_zero_network(self):
        import requests
        from network_guard import NetworkGuardViolation
        with self.assertRaises(NetworkGuardViolation):
            requests.get("http://127.0.0.1:9/", timeout=0.1)


if __name__ == "__main__":
    unittest.main()
