"""Unit tests for the offline Costco catalog resolver / run-manifest prep.

Never makes live calls — reads only temp file data. Covers the four resolution
lanes (manifest seed, catalog exact, reviewed fuzzy, catalog alt for known-dead
ids), the reject list (dog food must NOT auto-resolve to cat food), and the
prepared manifest / audit CSV output shape.
"""

import csv
import json
import os
import tempfile
import unittest

import test_network_guard  # noqa: F401  (blocks real network calls)

import bright_data_costco_prepare as prep


def _write_json(path, data):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False)


def _write_csv(path, rows):
    with open(path, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["item_name", "costco_cost"])
        for r in rows:
            w.writerow(r)


class ResolverTestBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = self.tmp.name
        self.csv_path = os.path.join(self.dir, "items.csv")
        self.catalog_path = os.path.join(self.dir, "catalog.json")
        self.manifest_path = os.path.join(self.dir, "manifest.json")
        self.out_manifest = os.path.join(self.dir, "prepared.json")
        self.out_audit = os.path.join(self.dir, "audit.csv")

        _write_json(
            self.catalog_path,
            {
                "items": [
                    {
                        "item_name": "Kirkland Signature Whole Almonds, Baking Nuts, 3 lbs",
                        "costco_item_id": "284601",
                        "source_url": "https://www.costcobusinessdelivery.com/kirkland-signature-whole-almonds-baking-nuts.product.10183563.html",
                        "url_derived": False,
                    }
                ],
                "held_for_review": [],
                "unmatched": [],
                "stale_rows": [],
            },
        )
        _write_json(
            self.manifest_path,
            {
                "items": [
                    {
                        "item_id": "1089787",
                        "requested_title": "Flex-Tech 13-Gallon Kitchen Trash Bag, 200-count",
                        "requested_pack": "200 count",
                    },
                    {
                        "item_id": "1493188",
                        "requested_title": "Baby Wipes Fragrance Free, 900-count",
                        "requested_pack": "900-count (9x100ct)",
                    },
                ]
            },
        )


class ResolveProductTests(ResolverTestBase):
    def test_manifest_seed_resolves_flex_tech_trash_bag(self):
        _write_csv(self.csv_path, [
            ["Kirkland Signature Flex-Tech 13-Gallon Kitchen Trash Bag, 200-count", "24.74"],
        ])
        products = prep._load_csv(self.csv_path)
        catalog = prep._load_catalog(self.catalog_path)
        manifest = prep._load_manifest(self.manifest_path)
        item = prep.resolve_product(products[0], catalog, manifest)
        self.assertEqual(item["item_id"], "1089787")
        self.assertEqual(item["resolution"], "resolved_manifest_seed")
        self.assertEqual(item["requested_pack"], "200 count")
        self.assertEqual(item["requested_brand"], "Kirkland Signature")

    def test_known_dead_baby_wipes_uses_catalog_alt(self):
        _write_csv(self.csv_path, [
            ["Kirkland Signature Baby Wipes Fragrance Free, 900-count", "21.99"],
        ])
        products = prep._load_csv(self.csv_path)
        catalog = prep._load_catalog(self.catalog_path)
        manifest = prep._load_manifest(self.manifest_path)
        item = prep.resolve_product(products[0], catalog, manifest)
        self.assertEqual(item["item_id"], "1493488")
        self.assertEqual(item["resolution"], "resolved_catalog_alt_for_dead")
        self.assertNotEqual(item["item_id"], "1493188")

    def test_catalog_exact_resolution(self):
        _write_csv(self.csv_path, [
            ["Kirkland Signature Whole Almonds, Baking Nuts, 3 lbs", "17.15"],
        ])
        products = prep._load_csv(self.csv_path)
        catalog = prep._load_catalog(self.catalog_path)
        item = prep.resolve_product(products[0], catalog, [])
        self.assertEqual(item["item_id"], "284601")
        self.assertEqual(item["resolution"], "resolved_catalog_exact")
        self.assertEqual(item["match_score"], 1.0)
        self.assertFalse(item["url_derived"])
        self.assertEqual(item["requested_pack"], None)  # 3 lbs not a count pack

    def test_reviewed_fuzzy_allowlist(self):
        _write_csv(self.csv_path, [
            ["Kirkland Signature, Pure Sea Salt, 30 oz", "4.39"],
        ])
        products = prep._load_csv(self.csv_path)
        item = prep.resolve_product(products[0], [], [])
        self.assertEqual(item["item_id"], "384732")
        self.assertEqual(item["resolution"], "resolved_catalog_fuzzy")
        self.assertEqual(item["match_score"], 0.71)

    def test_rejected_fuzzy_dog_food_never_auto_resolves(self):
        _write_csv(self.csv_path, [
            ["Kirkland Signature Adult Formula Lamb, Rice and Vegetable Dog Food, 25 lbs", "29.14"],
        ])
        products = prep._load_csv(self.csv_path)
        catalog = [{
            "item_name": "Kirkland Signature Cat Food, Chicken and Rice Formula",
            "costco_item_id": "52296",
            "source_url": "http://x/…",
            "url_derived": False,
            "pool": "items",
        }]
        item = prep.resolve_product(products[0], catalog, [])
        self.assertIsNone(item["item_id"])
        self.assertEqual(item["resolution"], "unresolved_needs_lookup")
        self.assertIn("Cat Food 52296", item["resolution_notes"])

    def test_unresolved_when_no_candidate(self):
        _write_csv(self.csv_path, [
            ["Kirkland Signature Paper Towels, 2-Ply, 160 Sheets, 12 Rolls", "26.39"],
        ])
        products = prep._load_csv(self.csv_path)
        item = prep.resolve_product(products[0], [], [])
        self.assertIsNone(item["item_id"])
        self.assertEqual(item["resolution"], "unresolved_needs_lookup")

    def test_count_pack_extraction_from_name(self):
        self.assertEqual(
            prep._count_pack_from_name("Kirkland Signature Dishwasher Detergent Pacs 115 Count"),
            "115 count",
        )
        self.assertEqual(
            prep._count_pack_from_name("Kirkland Signature Paper Towels, 160 Sheets, 12 Rolls"),
            "160 sheets",
        )
        self.assertIsNone(prep._count_pack_from_name("Kirkland Signature Whole Almonds, 3 lbs"))


class BuildPreparedManifestTests(ResolverTestBase):
    def test_full_build_summary_and_manifest_shape(self):
        _write_csv(self.csv_path, [
            ["Kirkland Signature Whole Almonds, Baking Nuts, 3 lbs", "17.15"],
            ["Kirkland Signature Paper Towels, 2-Ply, 160 Sheets", "26.39"],
            ["Kirkland Signature Flex-Tech 13-Gallon Kitchen Trash Bag, 200-count", "24.74"],
            ["Kirkland Signature Baby Wipes Fragrance Free, 900-count", "21.99"],
        ])
        items, summary = prep.build_prepared_manifest(
            self.csv_path, self.catalog_path, self.manifest_path
        )
        self.assertEqual(len(items), 4)
        self.assertEqual(summary["tracked_products"], 4)
        self.assertEqual(summary["resolved_total"], 3)
        self.assertEqual(summary["unresolved_needs_lookup"], 1)
        self.assertEqual(
            summary["resolution_counts"]["resolved_catalog_exact"], 1
        )
        self.assertEqual(
            summary["resolution_counts"]["resolved_manifest_seed"], 1
        )
        self.assertEqual(
            summary["resolution_counts"]["resolved_catalog_alt_for_dead"], 1
        )

        ids = [it["item_id"] for it in items]
        self.assertIn("284601", ids)
        self.assertIn("1089787", ids)
        self.assertIn("1493488", ids)
        self.assertNotIn("1493188", ids)

    def test_cli_writes_manifest_and_audit(self):
        _write_csv(self.csv_path, [
            ["Kirkland Signature Whole Almonds, Baking Nuts, 3 lbs", "17.15"],
        ])
        rc = prep._cli([
            "--csv", self.csv_path,
            "--catalog", self.catalog_path,
            "--manifest", self.manifest_path,
            "--out", self.out_manifest,
            "--audit", self.out_audit,
        ])
        self.assertEqual(rc, 0)
        with open(self.out_manifest, encoding="utf-8") as fh:
            data = json.load(fh)
        self.assertEqual(data["kind"], "brightdata_costco_prepared_run_manifest")
        self.assertEqual(len(data["items"]), 1)
        self.assertEqual(data["items"][0]["item_id"], "284601")
        with open(self.out_audit, encoding="utf-8-sig") as fh:
            rows = list(csv.DictReader(fh))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["resolution"], "resolved_catalog_exact")


if __name__ == "__main__":
    unittest.main()