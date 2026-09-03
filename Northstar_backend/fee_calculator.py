"""Standalone Amazon US FBA fee calculator for the Northstar Scout.

This is a self-contained, dependency-light module (stdlib only — no imports
from fee_engine / amazon_us_fee_rules_2026, no network) intended for quick
per-item fee and net-profit estimates. It mirrors the numbers already
validated elsewhere in this repo (fee_engine.py +
amazon_us_fee_rules_2026.py) so a standalone caller gets consistent results
without pulling the whole pricing engine.

Primary entry point:
    calculate_fba_fees(category, weight_oz, dimensions_in, sale_price,
                       landed_cost=None)

Returns a breakdown dict with referral_fee, fulfillment_fee,
storage_fee_estimate, total_fees, and — when a landed_cost is supplied —
net_profit and net_margin_pct.

Honesty / scope rules:
  * Money is always rounded to 2 decimals; missing values stay None, never 0.
  * storage_fee_estimate defaults to 0 (out of scope: monthly storage is not a
    per-unit landed cost and this calculator deliberately does not estimate it).
  * Fulfillment fees come from the weight-tier table below and are marked
    APPROXIMATE — verify against Amazon Seller Central before relying on this
    for real pricing decisions.
"""

from typing import Dict, Optional, Tuple, Union

# --------------------------------------------------------------------------
# Referral fee table (flat % of sale price by category).
# Source: Amazon Seller Central — US referral fee schedule (2026), transcribed
# in this repo at amazon_us_fee_rules_2026.py (REFERRAL_RULES).
# --------------------------------------------------------------------------
REFERRAL_RATES: Dict[str, float] = {
    # Primary case — this project's actual product category.
    "Health & Personal Care": 0.15,
    "Beauty": 0.15,
    "Home & Kitchen": 0.15,
    "Tools & Home Improvement": 0.15,
    "Sports & Outdoors": 0.15,
    "Pet Supplies": 0.15,
    "Toys & Games": 0.15,
    "Everything Else": 0.15,  # Amazon's catch-all bucket.
    "Grocery & Gourmet Food": 0.15,
    "Automotive & Powersports": 0.12,
    "Business, Industrial & Scientific": 0.12,
    "Consumer Electronics": 0.08,
    "Computers": 0.08,
    "Baby Products": 0.15,
}

# Health & Personal Care (and Beauty) use a price switch: 8% at/below $10,
# 15% above. Only categories in this set get the low-price tier. This is the
# project's actual product category, so it is modeled faithfully.
PRICE_SWITCH_CATEGORIES: Dict[str, float] = {
    "Health & Personal Care": 10.0,
    "Beauty": 10.0,
}

# --------------------------------------------------------------------------
# FBA fulfillment fee schedule (US, standard-size, all-in published rates).
# APPROXIMATE — verify against Amazon Seller Central before relying on this
# for real pricing decisions.
#
# Source: Amazon Seller Central — US FBA fulfillment fees (2026), transcribed
# in this repo at amazon_us_fee_rules_2026.py (FBA_SIZE_TIER_TABLE). Rates
# are all-in (base + fuel/logistics surcharge). Standard-size envelope is
# weight <= 20 lb and every side within 18 x 14 x 8 in; anything else is
# oversize and falls outside this table (fulfillment_fee None, never a guess).
# --------------------------------------------------------------------------
FBA_LOGISTICS_SURCHARGE_RATE = 0.035
STANDARD_MAX_WEIGHT_LBS = 20.0
STANDARD_MAX_DIMENSIONS_IN = (18.0, 14.0, 8.0)

# (max_weight_lbs, all_in_fee_usd) ascending; final entry uses inf.
FBA_STANDARD_SIZE_TIER_TABLE: Tuple[Tuple[float, float], ...] = (
    (0.5, 4.75),
    (1.0, 5.25),
    (2.0, 6.10),
    (3.0, 7.10),
    (5.0, 8.20),
    (10.0, 9.90),
    (20.0, 12.50),
    (float("inf"), 15.00),
)

REFERRAL_FEE_SOURCE = "Amazon Seller Central US referral fee schedule (2026); see amazon_us_fee_rules_2026.py"
FULFILLMENT_FEE_SOURCE = (
    "Amazon Seller Central US FBA fulfillment fee schedule (2026); "
    "APPROXIMATE - verify against Seller Central before real pricing decisions."
)

DEFAULT_CATEGORY = "Everything Else"


def _is_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _as_price(value: object) -> Optional[float]:
    """Positive numeric value, else None. Never coerces strings."""
    if not _is_number(value) or value <= 0:
        return None
    return float(value)


def _resolve_category(category: Optional[str]) -> str:
    """Resolve a category label to a canonical key with alias fallbacks."""
    raw = str(category or "").strip()
    if not raw:
        return DEFAULT_CATEGORY
    folded = " ".join(raw.lower().split())
    for name in REFERRAL_RATES:
        if folded == " ".join(name.lower().split()):
            return name
    alias_map = {
        "health": "Health & Personal Care",
        "health & personal care": "Health & Personal Care",
        "personal care": "Health & Personal Care",
        "electronics": "Consumer Electronics",
        "consumer electronics": "Consumer Electronics",
        "toys": "Toys & Games",
        "toys & games": "Toys & Games",
        "kitchen": "Home & Kitchen",
        "home & kitchen": "Home & Kitchen",
    }
    return alias_map.get(folded, DEFAULT_CATEGORY)


def calculate_referral_fee(
    sale_price: Union[int, float],
    category: Optional[str] = None,
) -> Dict[str, object]:
    """Referral fee for a sale price and category.

    Applies the Health & Personal Care / Beauty refinement (8% at/below $10,
    15% above). Missing price -> referral_fee None (never invented).
    """
    price = _as_price(sale_price)
    resolved = _resolve_category(category)
    if price is None:
        return {"referral_fee": None, "referral_fee_rate": None,
                "referral_fee_category": resolved, "referral_fee_source": None,
                "referral_fee_note": "No sale price; referral fee unavailable."}
    rate = REFERRAL_RATES[resolved]
    threshold = PRICE_SWITCH_CATEGORIES.get(resolved)
    if threshold is not None and price <= threshold:
        effective = 0.08
        note = f"{resolved}: 8% at/below ${threshold:.2f}."
    else:
        effective = rate
        note = f"{resolved}: {rate:.0%} of sale price."
    return {
        "referral_fee": round(price * effective, 2),
        "referral_fee_rate": round(effective, 4),
        "referral_fee_category": resolved,
        "referral_fee_source": REFERRAL_FEE_SOURCE,
        "referral_fee_note": note,
    }


def _normalize_dimensions(
    dimensions_in: Optional[Union[Tuple[object, object, object], list]],
) -> Optional[Tuple[float, float, float]]:
    if dimensions_in is None:
        return None
    try:
        dims = tuple(float(d) for d in dimensions_in)
    except (TypeError, ValueError):
        return None
    if len(dims) != 3 or any(d <= 0 for d in dims):
        return None
    return tuple(sorted(dims))  # type: ignore[return-value]


def calculate_fulfillment_fee(
    weight_oz: Union[int, float],
    dimensions_in: Optional[Union[Tuple[object, object, object], list]] = None,
) -> Dict[str, object]:
    """Standard-size FBA fulfillment fee from the weight tier table.

    APPROXIMATE — verify against Amazon Seller Central before using for real
    pricing decisions. Oversize packages (outside the standard-size envelope)
    or missing weight return fulfillment_fee None with an explanatory note.
    """
    as_lb = _as_price(weight_oz) / 16.0 if _as_price(weight_oz) is not None else None
    if as_lb is None:
        return {"fulfillment_fee": None, "size_tier": None,
                "weight_basis_lbs": None, "fulfillment_fee_source": FULFILLMENT_FEE_SOURCE,
                "fulfillment_fee_note": "No weight; fulfillment fee unavailable."}
    dims = _normalize_dimensions(dimensions_in)
    if dims is not None and any(d > m for d, m in zip(dims, tuple(sorted(STANDARD_MAX_DIMENSIONS_IN)))):
        return {"fulfillment_fee": None, "size_tier": "oversize",
                "weight_basis_lbs": round(as_lb, 2),
                "fulfillment_fee_source": FULFILLMENT_FEE_SOURCE,
                "fulfillment_fee_note": "Package is oversize (outside standard-size envelope); fee unavailable."}
    if as_lb > STANDARD_MAX_WEIGHT_LBS:
        return {"fulfillment_fee": None, "size_tier": "oversize",
                "weight_basis_lbs": round(as_lb, 2),
                "fulfillment_fee_source": FULFILLMENT_FEE_SOURCE,
                "fulfillment_fee_note": "Weight exceeds standard-size limit; fee unavailable."}
    fee = None
    for max_weight, band_fee in FBA_STANDARD_SIZE_TIER_TABLE:
        if as_lb <= max_weight:
            fee = band_fee
            break
    return {
        "fulfillment_fee": round(fee, 2) if fee is not None else None,
        "size_tier": "standard",
        "weight_basis_lbs": round(as_lb, 2),
        "fulfillment_fee_source": FULFILLMENT_FEE_SOURCE,
        "fulfillment_fee_note": (
            "Standard-size all-in published rate incl. "
            f"{FBA_LOGISTICS_SURCHARGE_RATE:.1%} fuel/logistics surcharge. "
            "APPROXIMATE - verify against Seller Central."
        ),
    }


def calculate_fba_fees(
    category: Optional[str],
    weight_oz: Union[int, float],
    dimensions_in: Optional[Union[Tuple[object, object, object], list]],
    sale_price: Union[int, float],
    landed_cost: Optional[Union[int, float]] = None,
) -> Dict[str, object]:
    """Full FBA fee + net-profit breakdown for one unit.

    Returns referral_fee, fulfillment_fee, storage_fee_estimate (0 by
    default — out of scope), total_fees, and — when a landed_cost (unit
    COGS) is provided — net_profit and net_margin_pct:

        net_profit       = sale_price - landed_cost - total_fees
        net_margin_pct   = net_profit / sale_price * 100

    Provenance fields (referral_fee_source, fulfillment_fee_source, notes)
    are included so callers know what the numbers are based on. Missing
    values stay None and are explained in the notes — never invented.
    """
    price = _as_price(sale_price)
    referral = calculate_referral_fee(sale_price if price is not None else None, category)
    fulfillment = calculate_fulfillment_fee(weight_oz, dimensions_in)

    storage = 0.0  # Out of scope: monthly storage is not a per-unit landed cost.

    total_fees = None
    if price is not None and referral["referral_fee"] is not None and fulfillment["fulfillment_fee"] is not None:
        total_fees = round(referral["referral_fee"] + fulfillment["fulfillment_fee"] + storage, 2)

    net_profit = None
    net_margin_pct = None
    cost = _as_price(landed_cost)
    if price is not None and cost is not None and total_fees is not None:
        net_profit = round(price - cost - total_fees, 2)
        net_margin_pct = round(net_profit / price * 100.0, 2) if price else None

    return {
        "sale_price": round(price, 2) if price is not None else None,
        "referral_fee": referral["referral_fee"],
        "referral_fee_rate": referral["referral_fee_rate"],
        "referral_fee_category": referral["referral_fee_category"],
        "referral_fee_source": referral["referral_fee_source"],
        "fulfillment_fee": fulfillment["fulfillment_fee"],
        "size_tier": fulfillment["size_tier"],
        "weight_basis_lbs": fulfillment["weight_basis_lbs"],
        "fulfillment_fee_source": fulfillment["fulfillment_fee_source"],
        "storage_fee_estimate": storage,
        "total_fees": total_fees,
        "net_profit": net_profit,
        "net_margin_pct": net_margin_pct,
        "referral_fee_note": referral["referral_fee_note"],
        "fulfillment_fee_note": fulfillment["fulfillment_fee_note"],
    }
