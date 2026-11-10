"""Tests 3-7: Amazon matching — UPC exact, title+pack, 1-vs-2 pack, case vs unit,
variation ambiguity, never verified on mismatch."""
from __future__ import annotations

import unittest

from costco_non_kirkland.matching import (
    AmazonAttributes,
    assess_amazon_match,
    build_match_candidate,
)
from costco_non_kirkland.enums import IdentityStatus
from .fixtures import NON_KIRKLAND_WITH_UPC, NON_KIRKLAND


def _costco(record, **kw):
    from costco_non_kirkland.normalize import normalize_costco_record
    norm = normalize_costco_record(record)
    norm.update(kw)
    return norm


class AmazonMatchingTests(unittest.TestCase):
    def test_upc_exact_match(self):
        csp = _costco(NON_KIRKLAND_WITH_UPC)
        amazon = AmazonAttributes(
            asin="B0123456789", title="SWISSGEAR 8097 2-piece Softside Spinner",
            brand="SwissGear", upc="799488123456")
        res = assess_amazon_match(csp, amazon)
        self.assertEqual(res.identity_status, IdentityStatus.UPC_EXACT_CANDIDATE.value)
        self.assertGreaterEqual(res.match_confidence, 0.9)
        self.assertFalse(res.manual_review_required)

    def test_upc_conflict_when_brand_differs(self):
        csp = _costco(NON_KIRKLAND_WITH_UPC)
        amazon = AmazonAttributes(asin="B0X", title="Something Else",
                                  brand="DifferentBrand", upc="799488123456")
        res = assess_amazon_match(csp, amazon)
        self.assertEqual(res.identity_status, IdentityStatus.IDENTITY_CONFLICT.value)
        self.assertTrue(res.manual_review_required)

    def test_mpn_brand_exact(self):
        csp = _costco(NON_KIRKLAND_WITH_UPC)
        amazon = AmazonAttributes(asin="B0Y", title="SWISSGEAR 8097 Spinner",
                                  brand="SwissGear", manufacturer_part_number="8097")
        res = assess_amazon_match(csp, amazon)
        self.assertEqual(res.identity_status, IdentityStatus.MANUFACTURER_PART_EXACT_CANDIDATE.value)
        self.assertFalse(res.manual_review_required)

    def test_brand_title_pack_exact(self):
        csp = _costco(NON_KIRKLAND, normalized_unit_count=1)
        amazon = AmazonAttributes(asin="B0Z", title="Dream Plush Adjustable Wedge Pillow with Cooling Cover",
                                  brand="Dream Plush", pack_count=1)
        res = assess_amazon_match(csp, amazon)
        self.assertEqual(res.identity_status, IdentityStatus.TITLE_PACK_CANDIDATE.value)
        self.assertEqual(res.pack_match_status, "exact")
        self.assertFalse(res.manual_review_required)

    def test_one_pack_vs_two_pack_mismatch(self):
        csp = _costco(NON_KIRKLAND, normalized_unit_count=2)
        amazon = AmazonAttributes(asin="B0Z", title="Dream Plush Adjustable Wedge Pillow with Cooling Cover",
                                  brand="Dream Plush", pack_count=1)
        res = assess_amazon_match(csp, amazon)
        self.assertEqual(res.identity_status, IdentityStatus.PACK_MISMATCH.value)
        self.assertEqual(res.pack_match_status, "mismatch")
        self.assertTrue(res.manual_review_required)

    def test_case_pack_vs_single_unit_mismatch(self):
        # Costco case pack of 12, Amazon retail unit of 1.
        csp = _costco({"brand_raw": "Wetfly", "item_name": "WETFLY Ionic Convertible Fly & Spin Combo",
                       "regular_price": 179.99}, normalized_unit_count=12)
        amazon = AmazonAttributes(asin="B0C", title="WETFLY Ionic Convertible Fly & Spin Combo",
                                  brand="Wetfly", pack_count=1)
        res = assess_amazon_match(csp, amazon)
        self.assertEqual(res.identity_status, IdentityStatus.PACK_MISMATCH.value)
        self.assertTrue(res.manual_review_required)

    def test_variation_ambiguity(self):
        csp = _costco(NON_KIRKLAND, normalized_unit_count=1)
        amazon = AmazonAttributes(asin="B0V", title="Dream Plush Wedge Pillow (Cooling Cover)",
                                  brand="Dream Plush", pack_count=1, is_variation_child=True, parent_asin="B0PARENT")
        res = assess_amazon_match(csp, amazon)
        self.assertEqual(res.identity_status, IdentityStatus.VARIATION_AMBIGUOUS.value)
        self.assertEqual(res.variation_match_status, "ambiguous")
        self.assertTrue(res.manual_review_required)

    def test_title_candidate_requires_manual_review(self):
        csp = _costco(NON_KIRKLAND, normalized_unit_count=1)
        amazon = AmazonAttributes(asin="B0T", title="Dream Plush Wedge Pillow", brand="Dream Plush", pack_count=1)
        res = assess_amazon_match(csp, amazon)
        self.assertEqual(res.identity_status, IdentityStatus.MANUAL_REVIEW_REQUIRED.value)
        self.assertTrue(res.manual_review_required)

    def test_build_match_candidate_record(self):
        csp = _costco(NON_KIRKLAND_WITH_UPC)
        amazon = AmazonAttributes(asin="B0123456789", title="SWISSGEAR 8097 Spinner",
                                  brand="SwissGear", upc="799488123456")
        cand = build_match_candidate(csp, amazon)
        self.assertEqual(cand["asin"], "B0123456789")
        self.assertEqual(cand["identity_status"], IdentityStatus.UPC_EXACT_CANDIDATE.value)
        self.assertIn("costco_source_product_id", cand)


if __name__ == "__main__":
    unittest.main()