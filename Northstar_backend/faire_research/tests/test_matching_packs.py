import unittest

from faire_research import (
    MatchConfidence,
    PackConfiguration,
    ProductAttributes,
    assess_match,
    case_break_allowed,
    pack_configuration,
)


class IdentityMatchTests(unittest.TestCase):
    def test_exact_gtin_match(self):
        c, _ = assess_match(ProductAttributes(brand="Acme", gtin="012345678905"),
                            ProductAttributes(brand="Acme", gtin="012345678905"))
        self.assertEqual(c, MatchConfidence.EXACT_IDENTIFIER_MATCH)
        self.assertTrue(c.may_advance_automatically)

    def test_exact_mpn_plus_brand(self):
        c, _ = assess_match(ProductAttributes(brand="Acme", mpn="AX-100"),
                            ProductAttributes(brand="Acme", mpn="AX-100"))
        self.assertEqual(c, MatchConfidence.EXACT_IDENTIFIER_MATCH)

    def test_wrong_pack_quantity_is_mismatch(self):
        c, reasons = assess_match(ProductAttributes(brand="Acme", unit_count=1),
                                  ProductAttributes(brand="Acme", unit_count=12))
        self.assertEqual(c, MatchConfidence.MISMATCH)

    def test_wrong_color_is_mismatch(self):
        c, _ = assess_match(ProductAttributes(brand="Acme", color="Blue"),
                            ProductAttributes(brand="Acme", color="Red"))
        self.assertEqual(c, MatchConfidence.MISMATCH)

    def test_wrong_size_is_mismatch(self):
        c, _ = assess_match(ProductAttributes(brand="Acme", size="Small"),
                            ProductAttributes(brand="Acme", size="Large"))
        self.assertEqual(c, MatchConfidence.MISMATCH)

    def test_similar_title_missing_gtin_not_exact(self):
        c, _ = assess_match(ProductAttributes(brand="Acme", title="Widget Holder"),
                            ProductAttributes(brand="Acme", title="Widget Holder Deluxe"),
                            fuzzy_score=0.7)
        self.assertNotEqual(c, MatchConfidence.EXACT_IDENTIFIER_MATCH)
        self.assertNotEqual(c, MatchConfidence.EXACT_ATTRIBUTE_MATCH)

    def test_ambiguous_listing(self):
        c, _ = assess_match(ProductAttributes(brand="Acme"),
                            ProductAttributes(brand="Acme"))
        self.assertIn(c, (MatchConfidence.AMBIGUOUS, MatchConfidence.INSUFFICIENT_DATA))

    def test_insufficient_data(self):
        c, _ = assess_match(ProductAttributes(), ProductAttributes())
        self.assertEqual(c, MatchConfidence.INSUFFICIENT_DATA)

    def test_variation_mismatch_material(self):
        c, _ = assess_match(ProductAttributes(brand="Acme", material="Cotton"),
                            ProductAttributes(brand="Acme", material="Polyester"))
        self.assertEqual(c, MatchConfidence.MISMATCH)

    def test_gtin_match_but_brand_differs(self):
        c, _ = assess_match(ProductAttributes(brand="Acme", gtin="012345678905"),
                            ProductAttributes(brand="OtherCo", gtin="012345678905"))
        self.assertEqual(c, MatchConfidence.MISMATCH)


class PackTests(unittest.TestCase):
    def test_case_of_retail_ready_singles(self):
        pc = pack_configuration(units_per_case=12, inner_units=None, retail_ready_singles=True)
        self.assertEqual(pc, PackConfiguration.MANUFACTURER_SINGLE_UNITS_INSIDE_CASE)

    def test_manufacturer_multipack(self):
        self.assertEqual(pack_configuration(units_per_case=6, inner_units=None, manufacturer_multipack=True),
                         PackConfiguration.MANUFACTURER_MULTIPACK)

    def test_seller_created_multipack(self):
        self.assertEqual(pack_configuration(units_per_case=2, inner_units=None, seller_created=True),
                         PackConfiguration.SELLER_CREATED_MULTIPACK)

    def test_bundle_of_different(self):
        self.assertEqual(pack_configuration(units_per_case=3, inner_units=None, bundle_of_different=True),
                         PackConfiguration.BUNDLE_OF_DIFFERENT_PRODUCTS)

    def test_inner_pack(self):
        self.assertEqual(pack_configuration(units_per_case=24, inner_units=6),
                         PackConfiguration.INNER_PACK)

    def test_unknown_pack(self):
        self.assertEqual(pack_configuration(units_per_case=None, inner_units=None),
                         PackConfiguration.PACK_CONFIGURATION_UNKNOWN)

    def test_case_break_allowed_when_all_true(self):
        ok, failed = case_break_allowed(
            retail_ready_unit=True, matches_single_asin=True, correct_label=True,
            no_not_for_individual_sale=True, brand_terms_allow=True,
            no_sealed_packaging_required=True, undamaged_by_separation=True,
            amazon_condition_met=True, direct_supplier_permits_amazon=True)
        self.assertTrue(ok)
        self.assertEqual(failed, [])

    def test_case_break_denied_not_for_individual_sale(self):
        ok, failed = case_break_allowed(
            retail_ready_unit=True, matches_single_asin=True, correct_label=True,
            no_not_for_individual_sale=False, brand_terms_allow=True,
            no_sealed_packaging_required=True, undamaged_by_separation=True,
            amazon_condition_met=True, direct_supplier_permits_amazon=True)
        self.assertFalse(ok)
        self.assertIn("no_not_for_individual_sale", failed)

    def test_case_break_denied_without_supplier_amazon_permission(self):
        ok, failed = case_break_allowed(
            retail_ready_unit=True, matches_single_asin=True, correct_label=True,
            no_not_for_individual_sale=True, brand_terms_allow=True,
            no_sealed_packaging_required=True, undamaged_by_separation=True,
            amazon_condition_met=True, direct_supplier_permits_amazon=False)
        self.assertFalse(ok)
        self.assertIn("direct_supplier_permits_amazon", failed)


if __name__ == "__main__":
    unittest.main()
