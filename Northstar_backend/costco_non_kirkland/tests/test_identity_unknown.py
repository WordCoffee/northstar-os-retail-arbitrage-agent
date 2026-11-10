"""Identity validation + unknown-semantics + split-pack tests (Phases 3-4)."""
from __future__ import annotations

import unittest

import test_network_guard  # noqa: F401

from costco_non_kirkland.identity import assess_identity, evaluate_split_pack
from costco_non_kirkland.enums import IdentityState, SplitPackState
from costco_non_kirkland.provider_imports.validators import (
    parse_bool_3way,
    parse_int,
    parse_float,
)
from .fixtures import source_fixture


def listing(**kw):
    l = {
        "asin": "B0SELL0101",
        "brand": "Dream Plush",
        "title": "Dream Plush Adjustable Wedge Pillow with Cooling Cover",
        "upc": "799488123456",
        "ean": None,
        "gtin": None,
        "mpn": None,
        "model": None,
        "manufacturer": "Dream Plush",
        "item_count": 1,
        "pack_count": 1,
        "unit_count": 1,
        "unit_measure": None,
        "variation_theme": None,
        "selected_variation": None,
        "unit_size": None,
    }
    l.update(kw)
    return l


class UnknownSemanticsTests(unittest.TestCase):
    # 9-12: missing fields remain unknown (not 0 / not False)
    def test_missing_fba_count_is_none(self):
        from costco_non_kirkland.provider_imports.mapping import map_row_to_canonical
        snap = map_row_to_canonical(
            {"asin": "B0TEST1234", "title": "X"}, provider="selleramp", kind="csv",
            provider_export_filename="f.csv", provider_export_sha256="abc",
            provider_schema_version="v1", provider_row_number=1)
        self.assertIsNone(snap["marketplace"].get("active_fba_seller_count"))

    def test_missing_amazon_retail_is_none(self):
        from costco_non_kirkland.provider_imports.mapping import map_row_to_canonical
        snap = map_row_to_canonical(
            {"asin": "B0TEST1234", "title": "X"}, provider="selleramp", kind="csv",
            provider_export_filename="f.csv", provider_export_sha256="abc",
            provider_schema_version="v1", provider_row_number=1)
        self.assertIsNone(snap["marketplace"].get("amazon_retail_active"))

    def test_missing_weight_is_none(self):
        from costco_non_kirkland.provider_imports.mapping import map_row_to_canonical
        snap = map_row_to_canonical(
            {"asin": "B0TEST1234", "title": "X"}, provider="selleramp", kind="csv",
            provider_export_filename="f.csv", provider_export_sha256="abc",
            provider_schema_version="v1", provider_row_number=1)
        self.assertIsNone(snap["size"].get("shipping_weight_lb"))

    def test_missing_fba_fee_is_none(self):
        from costco_non_kirkland.provider_imports.mapping import map_row_to_canonical
        snap = map_row_to_canonical(
            {"asin": "B0TEST1234", "title": "X"}, provider="selleramp", kind="csv",
            provider_export_filename="f.csv", provider_export_sha256="abc",
            provider_schema_version="v1", provider_row_number=1)
        self.assertIsNone(snap["fees"].get("fba_fulfillment_fee"))

    def test_bool_3way_unknown(self):
        self.assertIsNone(parse_bool_3way(""))
        self.assertIsNone(parse_bool_3way("unknown"))
        self.assertIsNone(parse_bool_3way("not_reported"))
        self.assertIs(parse_bool_3way("No"), False)
        self.assertIs(parse_bool_3way("Yes"), True)

    def test_int_float_unknown(self):
        self.assertIsNone(parse_int(""))
        self.assertIsNone(parse_float("not_available_in_export"))


class IdentityValidationTests(unittest.TestCase):
    # 16. Exact UPC match -> provider-reported state
    def test_upc_exact_provider_reported(self):
        src = source_fixture()
        res = assess_identity(src, listing(), provider_reported=True)
        self.assertEqual(res.state, IdentityState.EXACT_MATCH_PROVIDER_REPORTED.value)

    def test_upc_exact_verified_when_not_provider(self):
        src = source_fixture()
        res = assess_identity(src, listing(), provider_reported=False)
        self.assertEqual(res.state, IdentityState.EXACT_MATCH_VERIFIED.value)

    def test_upc_conflict_brand(self):
        src = source_fixture()
        res = assess_identity(src, listing(brand="DifferentBrand"), provider_reported=True)
        self.assertEqual(res.state, IdentityState.IDENTIFIER_MISMATCH.value)

    # 17. Title-only match cannot qualify
    def test_title_only_candidate(self):
        # No identifier, no unit/pack evidence -> only title+brand similarity.
        src = source_fixture(upc=None, manufacturer_part_number=None, model_number=None,
                             normalized_unit_count=None, item_count=None, pack_count=None,
                             size_or_weight_raw=None)
        res = assess_identity(src, listing(upc=None, mpn=None, model=None,
                                           item_count=None, pack_count=None, unit_count=None,
                                           unit_measure=None), provider_reported=True)
        self.assertEqual(res.state, IdentityState.TITLE_PACK_CANDIDATE.value)

    # 18. Pack mismatch blocks
    def test_pack_mismatch(self):
        src = source_fixture(upc=None, manufacturer_part_number=None, model_number=None,
                             normalized_unit_count=2, item_count=2, pack_count=2)
        res = assess_identity(src, listing(upc=None, mpn=None, model=None,
                                           item_count=1, pack_count=1, unit_count=1),
                              provider_reported=True)
        self.assertEqual(res.state, IdentityState.PACK_MISMATCH.value)

    # 19. Variation mismatch blocks
    def test_variation_mismatch(self):
        src = source_fixture(upc=None, manufacturer_part_number=None, model_number=None,
                             variation="Blue", formula_or_flavor="Blue")
        res = assess_identity(src, listing(upc=None, mpn=None, model=None,
                                           selected_variation="Red", variation_theme="Color"),
                              provider_reported=True)
        self.assertEqual(res.state, IdentityState.VARIATION_MISMATCH.value)

    def test_brand_mismatch(self):
        src = source_fixture(upc=None, manufacturer_part_number=None, model_number=None,
                             brand_raw="DifferentBrand")
        res = assess_identity(src, listing(upc=None, mpn=None, model=None),
                              provider_reported=True)
        self.assertEqual(res.state, IdentityState.BRAND_MISMATCH.value)

    def test_no_match(self):
        # No identifiers, no brand evidence, totally unrelated titles.
        src = source_fixture(upc=None, manufacturer_part_number=None, model_number=None,
                             brand_raw=None, title_raw="Totally Unrelated Product",
                             normalized_unit_count=None, item_count=None, pack_count=None,
                             size_or_weight_raw=None)
        res = assess_identity(src, listing(upc=None, mpn=None, model=None, brand=None,
                                           title="Completely Different Item",
                                           item_count=None, pack_count=None, unit_count=None,
                                           unit_measure=None), provider_reported=True)
        self.assertEqual(res.state, IdentityState.NO_MATCH.value)

    # MPN + brand exact
    def test_mpn_brand_exact(self):
        src = source_fixture(upc=None)
        res = assess_identity(src, listing(upc=None, mpn="DP-100", model=None), provider_reported=True)
        self.assertEqual(res.state, IdentityState.EXACT_MATCH_PROVIDER_REPORTED.value)


class SplitPackTests(unittest.TestCase):
    # 20. Prohibited split blocks
    def test_prohibited_split(self):
        src = source_fixture(split_allowed=False)
        self.assertEqual(evaluate_split_pack(src, listing()), SplitPackState.PROHIBITED_SPLIT)

    def test_not_for_individual_resale(self):
        src = source_fixture(not_for_individual_resale=True)
        self.assertEqual(evaluate_split_pack(src, listing()), SplitPackState.PROHIBITED_SPLIT)

    # 21. Approved retail-ready exact-unit split can continue
    def test_approved_split(self):
        src = source_fixture(normalized_unit_count=2, item_count=2, pack_count=2,
                             manufacturer_bundle=True, inner_units_sealed=True,
                             inner_units_retail_ready=True)
        self.assertEqual(evaluate_split_pack(src, listing()), SplitPackState.APPROVED_SPLIT)

    def test_intact_only_when_equal_pack(self):
        src = source_fixture()
        self.assertEqual(evaluate_split_pack(src, listing()), SplitPackState.INTACT_ONLY)

    def test_manual_review_when_split_requires_confirmation(self):
        src = source_fixture(normalized_unit_count=3, item_count=3, pack_count=3,
                             inner_units_sealed=None, inner_units_retail_ready=None)
        self.assertEqual(evaluate_split_pack(src, listing()), SplitPackState.MANUAL_REVIEW_REQUIRED)


if __name__ == "__main__":
    unittest.main()