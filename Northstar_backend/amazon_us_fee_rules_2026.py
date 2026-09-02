"""Versioned Amazon US fee rules (2026) for the Northstar Scout.

This module is DATA ONLY — it carries no executable economics. The
calculations live in fee_engine.py, which resolves rules by rule id so a
future rules version can replace this module without touching callers.

Every rule carries an explicit source note. Rules are transcribed from
Amazon Seller Central's published 2026 US referral fee schedule and FBA
fulfillment fee schedule. They are versioned (RULES_VERSION) and must
never be silently edited: bump the version and the note when the
schedule changes.

FBA totals in FBA_SIZE_TIER_TABLE equal the already-validated all-in
rates used by pricing.estimate_fba_fee (per-ASIN, standard-size). The
published all-in rate includes the fuel/logistics surcharge; the engine
splits base = total / (1 + FBA_LOGISTICS_SURCHARGE_RATE) and surcharge =
total - base so the UI can display the two components without changing
any validated number.
"""

RULES_VERSION = "2026.1"
RULES_VERSION_LABEL = "Amazon US fee schedule 2026.1"

# Version of the category/browse-node RESOLUTION path (how listing metadata
# maps to a fee category). Independent of RULES_VERSION: bump this when the
# resolution logic / source hint vocabulary changes, NOT when fee values
# change. Do not bump RULES_VERSION for a data-source enrichment path.
CATEGORY_RESOLVER_VERSION = "2026.2"

DEFAULT_REFERRAL_CATEGORY = "Everything Else"
DEFAULT_REFERRAL_RATE = 0.15
MIN_REFERRAL_FEE_USD = 0.30

# --------------------------------------------------------------------------
# Referral fee rules (2026)
#
# rule types:
#   flat          rate applies to the whole sale price
#   two_rate      rate up to cap, over_cap_rate above cap
#   price_switch  low_rate at/below low_price_max, high_rate above
#   progressive   tiered brackets (lowest price per bracket), top_rate beyond
#
# Every rule applies the MIN_REFERRAL_FEE_USD floor ("where applicable":
# Amazon applies a $0.30 minimum referral fee to virtually all
# categories).
# --------------------------------------------------------------------------

REFERRAL_RULES = {
    "Home & Kitchen": {
        "type": "flat",
        "rate": 0.15,
        "min_fee": MIN_REFERRAL_FEE_USD,
        "aliases": ["home & kitchen", "kitchen & dining", "kitchen"],
    },
    "Tools & Home Improvement": {
        "type": "flat",
        "rate": 0.15,
        "min_fee": MIN_REFERRAL_FEE_USD,
        "aliases": ["tools & home improvement", "home improvement", "tools"],
    },
    "Sports & Outdoors": {
        "type": "flat",
        "rate": 0.15,
        "min_fee": MIN_REFERRAL_FEE_USD,
        "aliases": ["sports & outdoors", "sports & fitness", "sports", "outdoors"],
    },
    "Pet Supplies": {
        "type": "flat",
        "rate": 0.15,
        "min_fee": MIN_REFERRAL_FEE_USD,
        "aliases": ["pet supplies", "pet products", "pet"],
    },
    "Office Products": {
        "type": "flat",
        "rate": 0.15,
        "min_fee": MIN_REFERRAL_FEE_USD,
        "aliases": ["office products", "office"],
    },
    "Toys & Games": {
        "type": "flat",
        "rate": 0.15,
        "min_fee": MIN_REFERRAL_FEE_USD,
        "aliases": ["toys & games", "toys", "games"],
    },
    # The default: Amazon's "Everything Else" bucket, 15%.
    "Everything Else": {
        "type": "flat",
        "rate": DEFAULT_REFERRAL_RATE,
        "min_fee": MIN_REFERRAL_FEE_USD,
        "aliases": ["everything else", "general merchandise", "other"],
    },
    "Automotive & Powersports": {
        "type": "flat",
        "rate": 0.12,
        "min_fee": MIN_REFERRAL_FEE_USD,
        "aliases": ["automotive & powersports", "automotive", "powersports", "vehicle"],
    },
    "Consumer Electronics": {
        "type": "flat",
        "rate": 0.08,
        "min_fee": MIN_REFERRAL_FEE_USD,
        "aliases": ["consumer electronics", "electronics", "audio & video"],
    },
    "Computers": {
        "type": "flat",
        "rate": 0.08,
        "min_fee": MIN_REFERRAL_FEE_USD,
        "aliases": ["computers", "computers & accessories", "computer"],
    },
    "Full-size Appliances": {
        "type": "flat",
        "rate": 0.08,
        "min_fee": MIN_REFERRAL_FEE_USD,
        "aliases": ["full-size appliances", "full size appliances", "major appliances"],
    },
    "Compact Appliances": {
        "type": "two_rate",
        "rate": 0.15,
        "cap": 300.0,
        "over_cap_rate": 0.08,
        "min_fee": MIN_REFERRAL_FEE_USD,
        "aliases": ["compact appliances", "small appliances"],
    },
    "Electronics Accessories": {
        "type": "two_rate",
        "rate": 0.15,
        "cap": 100.0,
        "over_cap_rate": 0.08,
        "min_fee": MIN_REFERRAL_FEE_USD,
        "aliases": ["electronics accessories", "mobile accessories", "cables & adapters"],
    },
    "Beauty": {
        "type": "price_switch",
        "low_rate": 0.08,
        "low_price_max": 10.0,
        "high_rate": 0.15,
        "min_fee": MIN_REFERRAL_FEE_USD,
        "aliases": ["beauty", "beauty & personal care"],
    },
    "Health & Personal Care": {
        "type": "price_switch",
        "low_rate": 0.08,
        "low_price_max": 10.0,
        "high_rate": 0.15,
        "min_fee": MIN_REFERRAL_FEE_USD,
        "aliases": ["health & personal care", "personal care", "health", "health & household"],
    },
    "Baby Products": {
        "type": "price_switch",
        "low_rate": 0.08,
        "low_price_max": 10.0,
        "high_rate": 0.15,
        "min_fee": MIN_REFERRAL_FEE_USD,
        "aliases": ["baby products", "baby"],
    },
    "Grocery & Gourmet Food": {
        "type": "price_switch",
        "low_rate": 0.08,
        "low_price_max": 15.0,
        "high_rate": 0.15,
        "min_fee": MIN_REFERRAL_FEE_USD,
        "aliases": ["grocery & gourmet food", "grocery", "gourmet food", "food"],
    },
    "Clothing & Accessories": {
        "type": "progressive",
        "tiers": [(15.0, 0.05), (20.0, 0.10)],
        "top_rate": 0.17,
        "min_fee": MIN_REFERRAL_FEE_USD,
        "aliases": ["clothing & accessories", "clothing", "apparel", "fashion"],
    },
    "Backpacks, Handbags & Luggage": {
        "type": "flat",
        "rate": 0.15,
        "min_fee": MIN_REFERRAL_FEE_USD,
        "aliases": ["backpacks, handbags & luggage", "handbags", "luggage", "backpacks"],
    },
    "Business, Industrial & Scientific": {
        "type": "flat",
        "rate": 0.12,
        "min_fee": MIN_REFERRAL_FEE_USD,
        "aliases": ["business, industrial & scientific", "industrial & scientific", "industrial", "scientific"],
    },
    "Amazon Device Accessories": {
        "type": "flat",
        "rate": 0.45,
        "min_fee": MIN_REFERRAL_FEE_USD,
        "aliases": ["amazon device accessories", "kindle accessories", "echo accessories", "fire tv accessories"],
    },
}

# Common Amazon browse-node ids -> category. Approximate by design; the
# engine marks any browse-node-only match as default_category unless the
# node id is listed here with high confidence.
REFERRAL_BROWSE_NODE_MAP = {
    1055398: "Home & Kitchen",
    228013: "Tools & Home Improvement",
    3375301: "Sports & Outdoors",
    2619533011: "Pet Supplies",
    1064954: "Office Products",
    165793011: "Toys & Games",
    15684181: "Automotive & Powersports",
    # 172282 is the main Electronics node; it must appear exactly once.
    172282: "Consumer Electronics",
    541966: "Computers",
    2617942011: "Full-size Appliances",
    11055981: "Beauty",
    3760901: "Health & Personal Care",
    165796011: "Baby Products",
    16310101: "Grocery & Gourmet Food",
    1036592: "Clothing & Accessories",
    947919: "Backpacks, Handbags & Luggage",
    16310091: "Business, Industrial & Scientific",
    2335752011: "Amazon Device Accessories",
}

# --------------------------------------------------------------------------
# FBA fulfillment fee (2026, US, standard-size, per-ASIN / per shipment)
#
# TOTALS are all-in published rates (identical to the validated
# pricing.estimate_fba_fee table). The engine reports the base fee and
# the 3.5% fuel/logistics surcharge split, summing back to the total.
#
# Standard-size envelope: weight <= 20 lb and every side within
# 18 x 14 x 8 inches. Anything else is oversize and outside this table.
# --------------------------------------------------------------------------

FBA_LOGISTICS_SURCHARGE_RATE = 0.035
FBA_STANDARD_MAX_WEIGHT_LBS = 20.0
FBA_STANDARD_MAX_DIMENSIONS_IN = (18.0, 14.0, 8.0)
FBA_SMALL_OVERSIZE_MAX_WEIGHT_LBS = 70.0

# (max_weight_lbs, all_in_fee_usd) ascending; the final entry uses inf.
FBA_SIZE_TIER_TABLE = [
    (0.5, 4.75),
    (1.0, 5.25),
    (2.0, 6.10),
    (3.0, 7.10),
    (5.0, 8.20),
    (10.0, 9.90),
    (20.0, 12.50),
    (float("inf"), 15.00),
]

# --------------------------------------------------------------------------
# Default unit costs (USD per unit) and rates. Overridable via env in
# fee_engine.calculate_unit_costs. 0.00 here is intentional for
# packaging (the Scout does not add a packaging charge by default).
# --------------------------------------------------------------------------

DEFAULT_INBOUND_COST_PER_UNIT = 0.35
DEFAULT_PREP_COST_PER_UNIT = 0.25
DEFAULT_PACKAGING_COST_PER_UNIT = 0.00
DEFAULT_RETURN_RESERVE_RATE = 0.02
