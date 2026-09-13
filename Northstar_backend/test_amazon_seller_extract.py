"""Offline tests for amazon_seller_extract.py (zero network, zero provider calls).

All transports are exercised through fixture HTML files; no live call can fire.
"""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))

from amazon_seller_extract import (
    extract_buy_box_seller,
    extract_buy_box_fulfillment,
    extract_total_sellers,
    extract_other_sellers_present,
    extract_lowest_price,
    extract_seller_markers,
    extract_seller_data,
)


class SellerExtractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixture_dir = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "tests", "fixtures", "fixtures", "seller_extract"
        )
        with open(os.path.join(fixture_dir, "expected.json"), "r", encoding="utf-8") as f:
            cls.expected = json.load(f)
        cls.fixtures = {}
        for name in ("standard", "fbm", "amazon_retail", "sparse",
                     "variant_counts", "other_sellers", "clp"):
            path = os.path.join(fixture_dir, name + ".html")
            with open(path, "r", encoding="utf-8") as f:
                cls.fixtures[name] = f.read()

    def _check(self, name, result):
        exp = self.expected[name]
        for key, expected_value in exp.items():
            actual = result.get(key)
            self.assertEqual(
                actual, expected_value,
                f"{name}: {key} = {actual!r}, expected {expected_value!r}"
            )

    def test_standard(self):
        result = extract_seller_data(self.fixtures["standard"], buy_box_price=19.99)
        self._check("standard", result)

    def test_fbm(self):
        result = extract_seller_data(self.fixtures["fbm"], buy_box_price=24.50)
        self._check("fbm", result)

    def test_amazon_retail(self):
        result = extract_seller_data(self.fixtures["amazon_retail"], buy_box_price=15.00)
        self._check("amazon_retail", result)

    def test_sparse(self):
        result = extract_seller_data(self.fixtures["sparse"], buy_box_price=9.99)
        self._check("sparse", result)

    def test_variant_counts(self):
        result = extract_seller_data(self.fixtures["variant_counts"], buy_box_price=22.00)
        self._check("variant_counts", result)

    def test_other_sellers(self):
        result = extract_seller_data(self.fixtures["other_sellers"], buy_box_price=30.00)
        self._check("other_sellers", result)

    def test_clp(self):
        result = extract_seller_data(self.fixtures["clp"])
        self._check("clp", result)

    def test_marker_counts_present(self):
        """Verify marker_counts dict is always present with all keys."""
        for name in self.fixtures:
            result = extract_seller_data(self.fixtures[name])
            markers = result.get("marker_counts")
            self.assertIsInstance(markers, dict, f"{name}: marker_counts missing")
            expected_keys = (
                "byline_sold_by", "fallback1_sold_by", "fallback2_sold_by",
                "fulfilled_by_amazon", "ships_from_sold_by", "new_from_count",
                "new_offers_variants", "other_sellers_text", "aod_offer",
                "offer_list", "buying_options"
            )
            for k in expected_keys:
                self.assertIn(k, markers, f"{name}: marker {k} missing")
                self.assertIsInstance(markers[k], int, f"{name}: marker {k} not int")

    def test_buy_box_fulfillment_logic(self):
        """Test fulfillment classification independently."""
        html_fba = '<div id="availability">Fulfilled by Amazon</div>'
        html_fbm = '<div id="availability">Ships from Seller Sold by Seller</div>'
        html_amazon = '<div id="bylineInfo">Sold by Amazon.com</div>'
        html_unknown = '<div>No fulfillment info</div>'

        self.assertEqual(extract_buy_box_fulfillment(html_fba, "Some Seller"), "FBA")
        self.assertEqual(extract_buy_box_fulfillment(html_fbm, "Some Seller"), "FBM")
        self.assertEqual(extract_buy_box_fulfillment(html_amazon, "Amazon.com"), "Amazon")
        self.assertEqual(extract_buy_box_fulfillment(html_unknown, "Some Seller"), "Unknown")

    def test_total_sellers_variants(self):
        """Test each count variant pattern independently."""
        patterns = {
            "New (5) from $19.99": 5,
            "(10 new offers)": 10,
            "12 new from $22.00": 12,
            "New (8)": 8,
            "(5) new": 5,
        }
        for html_fragment, expected in patterns.items():
            with self.subTest(fragment=html_fragment):
                html = f"<html><body>{html_fragment}</body></html>"
                result = extract_total_sellers(html)
                self.assertEqual(result, expected, f"Failed for {html_fragment}")

    def test_other_sellers_markers(self):
        """Test each other-sellers marker independently."""
        markers = {
            "Other sellers on Amazon": True,
            "aod-offer": True,
            "aod-container": True,
            "aod-list": True,
            "offer-list": True,
            "See All Buying Options": True,
            "All Buying Options": True,
            "No markers here": False,
        }
        for fragment, expected in markers.items():
            with self.subTest(fragment=fragment):
                html = f"<html><body>{fragment}</body></html>"
                result = extract_other_sellers_present(html)
                self.assertEqual(result, expected, f"Failed for {fragment}")

    def test_extract_lowest_price(self):
        html = '<div>New (5) from $19.99</div>'
        self.assertEqual(extract_lowest_price(html, buy_box_price=25.00), 19.99)
        # No pattern found -> None (does not fall back to buy_box_price)
        html_no_price = '<div>No price here</div>'
        self.assertIsNone(extract_lowest_price(html_no_price, buy_box_price=25.00))
        # None when neither
        self.assertIsNone(extract_lowest_price(html_no_price, buy_box_price=None))


if __name__ == "__main__":
    unittest.main()