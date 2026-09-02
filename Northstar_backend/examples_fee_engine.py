"""Three complete example unit-economics rows for the Scout fee engine.

Offline only: every row is built from MOCKED fixtures (no network, no
live Bright Data calls, no credits spent). Demonstrates the three
economics tiers exactly as they appear in the scanner response:

  1. estimated   — full fee stack (referral + FBA incl. 3.5% surcharge
                   + inbound + prep + packaging + return reserve)
  2. provisional — price + COGS with the FBA fee EXCLUDED (fee not yet
                   verified; never treated as final)
  3. unavailable — missing Costco cost basis -> null economics, never 0

Run: python examples_fee_engine.py
"""

import json

from fee_engine import calculate_unit_economics


def row(asin, name, product, costco):
    economics = calculate_unit_economics(product, costco)
    record = {
        "name": name,
        "asin": asin,
        "amazon_price": product.get("amazon_price"),
        "costco_cost": costco.get("costco_cost"),
        "fba_fee": economics["fba_fee"],
        "net_profit": economics["net_profit"],
        "roi_pct": economics["roi_pct"],
        "economics_confidence": economics["economics_confidence"],
        "economics_status": economics["economics_status"],
        "economics_note": economics["economics_note"],
        "referral_fee": economics["referral_fee"],
        "referral_fee_rate": economics["referral_fee_rate"],
        "referral_fee_category": economics["referral_fee_category"],
        "referral_fee_confidence": economics["referral_fee_confidence"],
        "referral_fee_rule": economics["referral_fee_rule"],
        "fba_base_fee": economics["fba_base_fee"],
        "fba_fuel_logistics_surcharge": economics["fba_fuel_logistics_surcharge"],
        "fba_size_tier": economics["fba_size_tier"],
        "fba_fee_status": economics["fba_fee_status"],
        "fba_fee_confidence": economics["fba_fee_confidence"],
        "fba_fee_rule": economics["fba_fee_rule"],
        "fba_weight_basis_lbs": economics["fba_weight_basis_lbs"],
        "inbound_cost_per_unit": economics["inbound_cost_per_unit"],
        "prep_cost_per_unit": economics["prep_cost_per_unit"],
        "packaging_cost_per_unit": economics["packaging_cost_per_unit"],
        "return_reserve_rate": economics["return_reserve_rate"],
        "costco_cogs": economics["costco_cogs"],
        "costco_cost_basis": economics["costco_cost_basis"],
    }
    return record


def main():
    rows = [
        row(
            "B0MOCK0001",
            "Kirkland Mock Towelettes (fully estimated)",
            {
                "amazon_price": 48.87,
                "amazon_category": "Home & Kitchen",
                "package_weight_lbs": 3.5,
                "package_dimensions_in": None,
                "item_weight_lbs": None,
                "listing_fba_fee": None,
                "browse_node": None,
            },
            {"costco_cost": 15.99, "costco_cost_basis": "estimated"},
        ),
        row(
            "B0MOCK0002",
            "Kirkland Mock Snack Bars (provisional, FBA fee missing)",
            {
                "amazon_price": 48.87,
                "amazon_category": None,
                "package_weight_lbs": None,
                "package_dimensions_in": None,
                "item_weight_lbs": None,
                "listing_fba_fee": None,
                "browse_node": None,
            },
            {"costco_cost": 15.99, "costco_cost_basis": "estimated"},
        ),
        row(
            "B0MOCK0003",
            "Kirkland Mock Water (missing Costco cost)",
            {
                "amazon_price": 48.87,
                "amazon_category": None,
                "package_weight_lbs": 1.06,
                "package_dimensions_in": None,
                "item_weight_lbs": None,
                "listing_fba_fee": None,
                "browse_node": None,
            },
            {"costco_cost": None, "costco_cost_basis": "unavailable"},
        ),
    ]

    print(json.dumps(rows, indent=2))
    print()
    print("Rows:", len(rows), "| tiers:",
          ", ".join(r["economics_confidence"] for r in rows),
          "| all nulls are JSON null, never 0.")


if __name__ == "__main__":
    main()