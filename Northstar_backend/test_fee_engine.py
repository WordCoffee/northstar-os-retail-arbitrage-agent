"""Offline unit tests for the versioned Amazon US fee engine.

Covers the full spec: referral rules (flat / two-rate / price-switch /
progressive / default fallback / $0.30 floor / browse-node match),
FBA fulfillment (size-tier table, 3.5% surcharge split, oversize,
missing inputs), unit costs from env, and the three economics tiers
(estimated / provisional / unavailable). No network: this module imports
test_network_guard like every other test file.
"""

import test_network_guard  # noqa: F401  (blocks real network calls)
import unittest
from unittest.mock import patch

import fee_engine
from fee_engine import (
    calculate_fba_fulfillment_fee,
    calculate_referral_fee,
    calculate_unit_costs,
    calculate_unit_economics,
)
from amazon_us_fee_rules_2026 import (
    FBA_LOGISTICS_SURCHARGE_RATE,
    RULES_VERSION,
)


class ReferralFeeTests(unittest.TestCase):
    def assert_referral(self, price, category, expected_fee, confidence="verified_category"):
        r = calculate_referral_fee(price, amazon_category=category)
        self.assertEqual(r["referral_fee"], expected_fee)
        self.assertEqual(r["referral_fee_category"], category)
        self.assertEqual(r["referral_fee_confidence"], confidence)
        self.assertTrue(r["referral_fee_rule"].startswith(f"REF-{RULES_VERSION}"))
        return r

    def test_home_and_kitchen_flat_15(self):
        r = self.assert_referral(40.0, "Home & Kitchen", 6.00)
        self.assertEqual(r["referral_fee_rate"], 0.15)

    def test_automotive_flat_12(self):
        r = self.assert_referral(40.0, "Automotive & Powersports", 4.80)
        self.assertEqual(r["referral_fee_rate"], 0.12)

    def test_consumer_electronics_flat_8(self):
        self.assert_referral(40.0, "Consumer Electronics", 3.20)

    def test_computers_flat_8(self):
        self.assert_referral(40.0, "Computers", 3.20)

    def test_grocery_low_price_8_percent(self):
        self.assert_referral(12.0, "Grocery & Gourmet Food", 0.96)

    def test_grocery_high_price_15_percent(self):
        self.assert_referral(20.0, "Grocery & Gourmet Food", 3.00)

    def test_beauty_at_10_uses_8_percent(self):
        r = self.assert_referral(10.0, "Beauty", 0.80)
        self.assertEqual(r["referral_fee_rate"], 0.08)

    def test_beauty_above_10_uses_15_percent(self):
        r = self.assert_referral(10.01, "Beauty", 1.50)
        self.assertEqual(r["referral_fee_rate"], round(0.15, 4))

    def test_baby_above_10_uses_15_percent(self):
        self.assert_referral(12.0, "Baby Products", 1.80)

    def test_compact_appliances_tiered_above_300(self):
        # 15% up to $300 + 8% above: 45.00 + 8.00 = 53.00
        self.assert_referral(400.0, "Compact Appliances", 53.00)

    def test_compact_appliances_within_cap(self):
        self.assert_referral(200.0, "Compact Appliances", 30.00)

    def test_electronics_accessories_tiered_above_100(self):
        # 15% up to $100 + 8% above: 15.00 + 4.00 = 19.00
        self.assert_referral(150.0, "Electronics Accessories", 19.00)

    def test_clothing_progressive_30(self):
        # 5% up to $15 (0.75) + 10% $15-20 (0.50) + 17% above $20 (1.70)
        self.assert_referral(30.0, "Clothing & Accessories", 2.95)

    def test_clothing_at_15_boundary(self):
        self.assert_referral(15.0, "Clothing & Accessories", 0.75)

    def test_clothing_at_20_boundary(self):
        self.assert_referral(20.0, "Clothing & Accessories", 1.25)

    def test_device_accessories_45(self):
        self.assert_referral(10.0, "Amazon Device Accessories", 4.50)

    def test_unknown_category_defaults_to_everything_else_with_note(self):
        r = calculate_referral_fee(40.0, amazon_category="Handmade Space Widgets")
        self.assertEqual(r["referral_fee"], 6.00)
        self.assertEqual(r["referral_fee_category"], "Everything Else")
        self.assertEqual(r["referral_fee_confidence"], "default_category")
        self.assertIn("Verify the exact category in Seller Central", r["referral_fee_note"])
        self.assertIn("15%", r["referral_fee_note"])

    def test_no_category_defaults_to_everything_else_with_note(self):
        r = calculate_referral_fee(40.0)
        self.assertEqual(r["referral_fee"], 6.00)
        self.assertEqual(r["referral_fee_confidence"], "default_category")
        self.assertIn("No Amazon category / browse node available", r["referral_fee_note"])

    def test_browse_node_match_is_verified(self):
        r = calculate_referral_fee(12.0, browse_node=11055981)
        self.assertEqual(r["referral_fee_category"], "Beauty")
        self.assertEqual(r["referral_fee_confidence"], "verified_category")
        self.assertIn("browse node", r["referral_fee_note"])
        self.assertEqual(r["browse_node_id"], 11055981)
        self.assertEqual(r["category_resolution_source"], "browse_node")
        self.assertEqual(r["category_resolution_confidence"], "verified")

    def test_browse_node_wins_over_category_alias(self):
        """The browse node is the most specific signal and beats a name or
        alias match when both are present."""
        r = calculate_referral_fee(40.0, amazon_category="Kitchen", browse_node=11055981)
        self.assertEqual(r["referral_fee_category"], "Beauty")
        self.assertEqual(r["referral_fee_confidence"], "verified_category")
        self.assertEqual(r["category_resolution_source"], "browse_node")
        self.assertEqual(r["category_resolution_confidence"], "verified")

    def test_structured_category_resolution_verified(self):
        r = calculate_referral_fee(40.0, amazon_category="Pet Supplies")
        self.assertEqual(r["referral_fee_category"], "Pet Supplies")
        self.assertEqual(r["referral_fee_confidence"], "verified_category")
        self.assertEqual(r["category_resolution_source"], "structured_category")
        self.assertEqual(r["category_resolution_confidence"], "verified")
        self.assertIn("matched exactly", r["referral_fee_note"])

    def test_breadcrumb_resolution_is_inferred(self):
        """A breadcrumb-derived category maps to the right RULE (verified
        rate) but is marked inferred and flagged for Seller Central."""
        r = calculate_referral_fee(
            40.0, amazon_category="Grocery & Gourmet Food", category_source_hint="breadcrumb"
        )
        self.assertEqual(r["referral_fee_category"], "Grocery & Gourmet Food")
        self.assertEqual(r["referral_fee_confidence"], "verified_category")
        self.assertEqual(r["category_resolution_source"], "breadcrumb")
        self.assertEqual(r["category_resolution_confidence"], "inferred")
        self.assertIn("breadcrumbs", r["referral_fee_note"])
        self.assertIn("Seller Central", r["referral_fee_note"])

    def test_breadcrumb_alias_resolution_is_inferred(self):
        r = calculate_referral_fee(
            40.0, amazon_category="Kitchen", category_source_hint="breadcrumb"
        )
        self.assertEqual(r["referral_fee_category"], "Home & Kitchen")
        self.assertEqual(r["category_resolution_confidence"], "inferred")

    def test_default_resolution_metadata(self):
        r = calculate_referral_fee(40.0)
        self.assertEqual(r["referral_fee_category"], "Everything Else")
        self.assertEqual(r["referral_fee_confidence"], "default_category")
        self.assertEqual(r["category_resolution_source"], "default")
        self.assertEqual(r["category_resolution_confidence"], "default")
        self.assertIsNone(r["browse_node_id"])

    def test_missing_price_resolution_metadata_unavailable(self):
        r = calculate_referral_fee(None)
        self.assertEqual(r["category_resolution_source"], "unavailable")
        self.assertEqual(r["category_resolution_confidence"], "unavailable")
        self.assertIsNone(r["category_resolution_note"])
        self.assertIsNone(r["browse_node_id"])

    def test_min_fee_floor_0_30(self):
        r = self.assert_referral(1.0, "Everything Else", 0.30)
        self.assertEqual(r["referral_fee_rate"], 0.30)

    def test_missing_price_never_invents_fee(self):
        r = calculate_referral_fee(None)
        self.assertIsNone(r["referral_fee"])
        self.assertIsNone(r["referral_fee_rate"])
        self.assertEqual(r["referral_fee_confidence"], "unavailable")
        self.assertIsNone(r["referral_fee_category"])

    def test_zero_price_normalized_to_none(self):
        r = calculate_referral_fee(0)
        self.assertIsNone(r["referral_fee"])
        self.assertEqual(r["referral_fee_confidence"], "unavailable")

    def test_alias_match(self):
        r = calculate_referral_fee(40.0, amazon_category="Kitchen")
        self.assertEqual(r["referral_fee_category"], "Home & Kitchen")
        self.assertEqual(r["referral_fee_confidence"], "verified_category")


class FbaFulfillmentFeeTests(unittest.TestCase):
    def test_standard_size_fee_matches_legacy_all_in_total(self):
        f = calculate_fba_fulfillment_fee(3.5, None, 40.0)
        self.assertEqual(f["fba_fee"], 8.20)
        self.assertEqual(f["fba_size_tier"], "standard")
        self.assertEqual(f["fba_fee_status"], "available")
        self.assertEqual(f["fba_fee_confidence"], "table_estimate")
        # base + surcharge == total, surcharge = 3.5% of base
        self.assertEqual(round(f["fba_base_fee"] + f["fba_fuel_logistics_surcharge"], 2), 8.20)
        self.assertAlmostEqual(
            f["fba_fuel_logistics_surcharge"],
            round(f["fba_base_fee"] * FBA_LOGISTICS_SURCHARGE_RATE, 2),
        )

    def test_one_pound_band(self):
        f = calculate_fba_fulfillment_fee(1.0, None, 40.0)
        self.assertEqual(f["fba_fee"], 5.25)

    def test_three_pounds_band(self):
        f = calculate_fba_fulfillment_fee(3.0, None, 40.0)
        self.assertEqual(f["fba_fee"], 7.10)

    def test_three_and_half_pounds_band(self):
        f = calculate_fba_fulfillment_fee(3.5, None, 40.0)
        self.assertEqual(f["fba_fee"], 8.20)

    def test_five_point_two_five_pounds_band(self):
        f = calculate_fba_fulfillment_fee(5.25, None, 40.0)
        self.assertEqual(f["fba_fee"], 9.90)

    def test_dimensions_within_envelope_stays_standard(self):
        f = calculate_fba_fulfillment_fee(10.0, (10.0, 8.0, 5.0), 40.0)
        self.assertEqual(f["fba_fee"], 9.90)
        self.assertEqual(f["fba_size_tier"], "standard")

    def test_oversize_dimensions_need_revenue_calculator(self):
        f = calculate_fba_fulfillment_fee(10.0, (20.0, 10.0, 6.0), 40.0)
        self.assertIsNone(f["fba_fee"])
        self.assertEqual(f["fba_fee_status"], "needs_revenue_calculator_verification")
        self.assertEqual(f["fba_size_tier"], "small_oversize")
        self.assertIn("Revenue Calculator", f["fba_fee_note"])

    def test_heavy_oversize_tier_label(self):
        f = calculate_fba_fulfillment_fee(80.0, (30.0, 20.0, 15.0), 40.0)
        self.assertIsNone(f["fba_fee"])
        self.assertEqual(f["fba_size_tier"], "large_oversize")

    def test_weight_above_standard_limit_without_dims(self):
        f = calculate_fba_fulfillment_fee(25.0, None, 40.0)
        self.assertIsNone(f["fba_fee"])
        self.assertEqual(f["fba_fee_status"], "size_tier_unavailable")

    def test_missing_weight_never_invents_fee(self):
        f = calculate_fba_fulfillment_fee(None, None, 40.0)
        self.assertIsNone(f["fba_fee"])
        self.assertIsNone(f["fba_base_fee"])
        self.assertIsNone(f["fba_fuel_logistics_surcharge"])
        self.assertEqual(f["fba_fee_status"], "weight_unavailable")
        self.assertEqual(f["fba_fee_confidence"], "unavailable")

    def test_missing_dimensions_noted_but_fee_available(self):
        f = calculate_fba_fulfillment_fee(2.0, None, 40.0)
        self.assertEqual(f["fba_fee"], 6.10)
        self.assertEqual(f["fba_fee_status"], "available")
        self.assertIn("assumed standard-size", f["fba_fee_note"])

    def test_rule_label_is_versioned(self):
        f = calculate_fba_fulfillment_fee(2.0, None, 40.0)
        self.assertEqual(f["fba_fee_rule"], f"FBA-{RULES_VERSION}")

    def test_zero_weight_normalized_to_none(self):
        f = calculate_fba_fulfillment_fee(0, None, 40.0)
        self.assertIsNone(f["fba_fee"])

    def test_product_category_lands_in_note(self):
        f = calculate_fba_fulfillment_fee(2.0, None, 40.0, product_category="Pet Supplies")
        self.assertIn("Pet Supplies", f["fba_fee_note"])


class UnitCostTests(unittest.TestCase):
    def test_defaults(self):
        c = calculate_unit_costs()
        self.assertEqual(c["inbound_cost_per_unit"], 0.35)
        self.assertEqual(c["prep_cost_per_unit"], 0.25)
        self.assertEqual(c["packaging_cost_per_unit"], 0.00)
        self.assertEqual(c["return_reserve_rate"], 0.02)

    def test_env_overrides(self):
        with patch.dict("os.environ", {
            "INBOUND_COST_PER_UNIT": "0.50",
            "PREP_COST_PER_UNIT": "0.10",
            "PACKAGING_COST_PER_UNIT": "0.15",
            "RETURN_RESERVE_RATE": "0.03",
        }):
            c = calculate_unit_costs()
        self.assertEqual(c["inbound_cost_per_unit"], 0.50)
        self.assertEqual(c["prep_cost_per_unit"], 0.10)
        self.assertEqual(c["packaging_cost_per_unit"], 0.15)
        self.assertEqual(c["return_reserve_rate"], 0.03)

    def test_invalid_env_falls_back_to_default(self):
        with patch.dict("os.environ", {"INBOUND_COST_PER_UNIT": "banana"}):
            c = calculate_unit_costs()
        self.assertEqual(c["inbound_cost_per_unit"], 0.35)


class EconomicsTests(unittest.TestCase):
    def base_product(self, **overrides):
        product = {
            "amazon_price": 48.87,
            "amazon_category": "Home & Kitchen",
            "package_weight_lbs": 3.5,
            "package_dimensions_in": None,
            "item_weight_lbs": None,
            "listing_fba_fee": None,
            "browse_node": None,
        }
        product.update(overrides)
        return product

    def base_costco(self, costco_cost=15.99, basis="estimated"):
        return {"costco_cost": costco_cost, "costco_cost_basis": basis}

    def test_estimated_full_stack(self):
        e = calculate_unit_economics(self.base_product(), self.base_costco())
        self.assertEqual(e["economics_confidence"], "estimated")
        self.assertEqual(e["economics_status"], "estimated_fee_stack")
        self.assertIsNotNone(e["net_profit"])
        self.assertIsNotNone(e["roi_pct"])
        # referral 15% = 7.33; fba 3.5lb = 8.20 (all-in incl. surcharge)
        self.assertEqual(e["referral_fee"], 7.33)
        self.assertEqual(e["fba_fee"], 8.20)
        # net = 48.87 - 15.99 - 7.33 - 8.20 - 0.35 - 0.25 - 0.00 - 0.98
        self.assertAlmostEqual(e["net_profit"], 15.77, places=2)
        self.assertAlmostEqual(e["roi_pct"], 98.62, places=2)
        self.assertIn("All costs included", e["economics_note"])

    def test_estimated_roi_formula_net_over_cogs(self):
        e = calculate_unit_economics(
            self.base_product(amazon_price=40.0, package_weight_lbs=2.0),
            self.base_costco(costco_cost=10.0),
        )
        # referral 6.00, fba 6.10, inbound .35, prep .25, reserve .80
        net = 40.0 - 10.0 - 6.0 - 6.10 - 0.35 - 0.25 - 0.80
        self.assertAlmostEqual(e["net_profit"], net, places=2)
        self.assertAlmostEqual(e["roi_pct"], net / 10.0 * 100, places=2)

    def test_surcharge_included_in_fba_total(self):
        e = calculate_unit_economics(self.base_product(), self.base_costco())
        self.assertAlmostEqual(
            e["fba_fee"],
            e["fba_base_fee"] + e["fba_fuel_logistics_surcharge"],
            places=2,
        )

    def test_listing_reported_fba_fee_overrides_table(self):
        e = calculate_unit_economics(
            self.base_product(listing_fba_fee=9.25),
            self.base_costco(),
        )
        self.assertEqual(e["fba_fee"], 9.25)
        self.assertEqual(e["fba_fee_confidence"], "listing_reported")
        self.assertEqual(e["fba_fee_status"], "available")
        self.assertEqual(e["economics_confidence"], "estimated")

    def test_provisional_without_fba_fee(self):
        e = calculate_unit_economics(
            self.base_product(package_weight_lbs=None, item_weight_lbs=None),
            self.base_costco(),
        )
        self.assertEqual(e["economics_confidence"], "provisional")
        self.assertEqual(e["economics_status"], "needs_fee_verification")
        self.assertIsNone(e["fba_fee"])
        self.assertIsNotNone(e["net_profit"])
        self.assertIsNotNone(e["roi_pct"])
        # provisional excludes ONLY the FBA fee
        expected = 48.87 - 15.99 - 7.33 - 0.35 - 0.25 - 0.00 - 0.98
        self.assertAlmostEqual(e["net_profit"], expected, places=2)
        note = e["economics_note"]
        self.assertIn("EXCLUDED", note)
        self.assertIn("verify", note.lower())

    def test_missing_price_unavailable(self):
        e = calculate_unit_economics(
            self.base_product(amazon_price=None),
            self.base_costco(),
        )
        self.assertEqual(e["economics_confidence"], "unavailable")
        self.assertEqual(e["economics_status"], "missing_amazon_price")
        self.assertIsNone(e["net_profit"])
        self.assertIsNone(e["roi_pct"])
        self.assertIn("never estimated", e["economics_note"])

    def test_zero_price_normalized_to_null(self):
        e = calculate_unit_economics(self.base_product(amazon_price=0), self.base_costco())
        self.assertEqual(e["economics_status"], "missing_amazon_price")
        self.assertIsNone(e["net_profit"])

    def test_missing_cogs_unavailable(self):
        e = calculate_unit_economics(
            self.base_product(),
            self.base_costco(costco_cost=None),
        )
        self.assertEqual(e["economics_confidence"], "unavailable")
        self.assertEqual(e["economics_status"], "missing_costco_cogs")
        self.assertIsNone(e["net_profit"])
        self.assertIsNone(e["roi_pct"])

    def test_zero_cogs_normalized_to_null(self):
        e = calculate_unit_economics(self.base_product(), self.base_costco(costco_cost=0))
        self.assertEqual(e["economics_status"], "missing_costco_cogs")
        self.assertIsNone(e["net_profit"])

    def test_cogs_basis_passthrough(self):
        e = calculate_unit_economics(
            self.base_product(),
            self.base_costco(costco_cost=12.0, basis="invoice_confirmed"),
        )
        self.assertEqual(e["costco_cost_basis"], "invoice_confirmed")
        self.assertEqual(e["costco_cogs"], 12.0)

    def test_missing_costco_basis_defaults_unavailable(self):
        e = calculate_unit_economics(self.base_product(), {"costco_cost": 15.99})
        self.assertEqual(e["costco_cost_basis"], "unavailable")

    def test_category_default_shows_default_confidence(self):
        e = calculate_unit_economics(
            self.base_product(amazon_category=None),
            self.base_costco(),
        )
        self.assertEqual(e["referral_fee_confidence"], "default_category")
        self.assertEqual(e["referral_fee"], 7.33)

    def test_estimated_tier_unchanged_by_category_resolution(self):
        """Category metadata may change the referral rate/confidence but
        never the economics tier: estimated stays estimated."""
        e = calculate_unit_economics(
            self.base_product(
                amazon_category="Pet Supplies",
                browse_node=2619533011,
                category_source_hint="breadcrumb",
            ),
            self.base_costco(),
        )
        self.assertEqual(e["economics_confidence"], "estimated")
        self.assertEqual(e["economics_status"], "estimated_fee_stack")
        self.assertEqual(e["referral_fee_category"], "Pet Supplies")
        self.assertEqual(e["referral_fee_confidence"], "verified_category")
        self.assertEqual(e["browse_node_id"], 2619533011)
        self.assertEqual(e["category_resolution_source"], "browse_node")
        self.assertEqual(e["category_resolution_confidence"], "verified")
        # 15% Pet Supplies fee == 15% Everything Else fee, so economics
        # are identical to the default case — the tier logic is untouched.
        self.assertAlmostEqual(e["net_profit"], 15.77, places=2)

    def test_provisional_tier_unchanged_by_breadcrumb_category(self):
        """A breadcrumb category sharpens provisional numbers but never
        promotes the row to estimated (FBA fee is still missing)."""
        e = calculate_unit_economics(
            self.base_product(
                amazon_category="Grocery & Gourmet Food",
                category_source_hint="breadcrumb",
                package_weight_lbs=None,
                item_weight_lbs=None,
            ),
            self.base_costco(),
        )
        self.assertEqual(e["economics_confidence"], "provisional")
        self.assertEqual(e["economics_status"], "needs_fee_verification")
        self.assertEqual(e["referral_fee_category"], "Grocery & Gourmet Food")
        self.assertEqual(e["referral_fee_confidence"], "verified_category")
        self.assertEqual(e["category_resolution_confidence"], "inferred")
        self.assertIsNotNone(e["net_profit"])

    def test_item_weight_fallback_used_when_no_package_weight(self):
        e = calculate_unit_economics(
            self.base_product(package_weight_lbs=None, item_weight_lbs=2.0),
            self.base_costco(),
        )
        self.assertEqual(e["fba_fee"], 6.10)

    def test_negative_net_profit_is_a_number_never_null(self):
        e = calculate_unit_economics(
            self.base_product(amazon_price=8.0, package_weight_lbs=3.5),
            self.base_costco(costco_cost=15.99),
        )
        self.assertEqual(e["economics_confidence"], "estimated")
        self.assertLess(e["net_profit"], 0)
        self.assertIsNotNone(e["roi_pct"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
