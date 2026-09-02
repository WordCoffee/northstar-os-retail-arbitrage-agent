"""Finance calculations for the Northstar arbitrage pipeline.

Pure, reusable, null-safe financial functions only. No requests, no API
client imports, no environment reads, no UI code.

Business definitions:
    amazon_payout_before_inventory_costs =
        amazon_sale_price - referral_fee - fba_fulfillment_fee
    landed_cost =
        cogs + prep_cost + inbound_shipping_cost
    projected_net_profit =
        amazon_sale_price
        - referral_fee
        - fba_fulfillment_fee
        - cogs
        - prep_cost
        - inbound_shipping_cost
    projected_roi_pct (optional, secondary) =
        (projected_net_profit / landed_cost) * 100

The dollar result is named projected_net_profit; there is no
dollar-denominated ROI metric — ROI is a percentage only.

Data-integrity rules enforced here:
    1. Missing values are never treated as $0.00.
    2. Zero is valid only as a real, explicit cost value.
    3. Negative values for sale price, fees, COGS, prep, and inbound are
       rejected as invalid_financial_data.
    4. Inputs are never rounded before calculation.
    5. Display rounding is left to the UI boundary.
    6. Numeric results stay numeric (no float string-sorting problems).
    7. Unknown values stay null.
    8. Projected profit is an estimate, not a sourcing approval.
    9. Retail price is never used as COGS here.
    10. COGS, prep, and inbound are each subtracted exactly once.
"""

import math
import numbers
from typing import Any, Dict, List, Tuple

DISPLAY_FIELD_NAME = "Projected Net Profit ($)"
DEFAULT_SORT_LABEL = "Projected Net Profit: High to Low"
DEFAULT_SORT_FIELD = "projected_net_profit"

STATUS_SCORED = "scored"
STATUS_NEED_COST_DATA = "need_cost_data"
STATUS_NEED_FEE_DATA = "need_fee_data"
STATUS_INVALID_FINANCIAL_DATA = "invalid_financial_data"
STATUS_UNPROFITABLE = "unprofitable"

_FEE_FIELDS = ("amazon_sale_price", "referral_fee", "fba_fulfillment_fee")
_COST_FIELDS = ("cogs", "prep_cost", "inbound_shipping_cost")


def _is_number(value: Any) -> bool:
    return isinstance(value, numbers.Number) and not isinstance(value, bool)


def _is_negative(value: Any) -> bool:
    return _is_number(value) and value < 0


def amazon_payout_before_inventory_costs(
    amazon_sale_price: Any,
    referral_fee: Any,
    fba_fulfillment_fee: Any,
) -> Any:
    """amazon_sale_price - referral_fee - fba_fulfillment_fee, or None."""
    if not all(_is_number(v) for v in (amazon_sale_price, referral_fee, fba_fulfillment_fee)):
        return None
    if any(v < 0 for v in (amazon_sale_price, referral_fee, fba_fulfillment_fee)):
        return None
    return amazon_sale_price - referral_fee - fba_fulfillment_fee


def landed_cost(cogs: Any, prep_cost: Any, inbound_shipping_cost: Any) -> Any:
    """cogs + prep_cost + inbound_shipping_cost, or None."""
    if not all(_is_number(v) for v in (cogs, prep_cost, inbound_shipping_cost)):
        return None
    if any(v < 0 for v in (cogs, prep_cost, inbound_shipping_cost)):
        return None
    return cogs + prep_cost + inbound_shipping_cost


def projected_net_profit(
    amazon_sale_price: Any,
    referral_fee: Any,
    fba_fulfillment_fee: Any,
    cogs: Any,
    prep_cost: Any,
    inbound_shipping_cost: Any,
) -> Any:
    """Full projected profit formula, or None when any input is unusable."""
    if not all(
        _is_number(v)
        for v in (
            amazon_sale_price,
            referral_fee,
            fba_fulfillment_fee,
            cogs,
            prep_cost,
            inbound_shipping_cost,
        )
    ):
        return None
    if any(
        v < 0
        for v in (
            amazon_sale_price,
            referral_fee,
            fba_fulfillment_fee,
            cogs,
            prep_cost,
            inbound_shipping_cost,
        )
    ):
        return None
    return (
        amazon_sale_price
        - referral_fee
        - fba_fulfillment_fee
        - cogs
        - prep_cost
        - inbound_shipping_cost
    )


def projected_roi_pct(profit: Any, landed: Any) -> Any:
    """(projected_net_profit / landed_cost) * 100, or None.

    Returns None when profit or landed is unusable, or when landed_cost is
    zero (no divide-by-zero).
    """
    if not _is_number(profit) or not _is_number(landed):
        return None
    if landed == 0:
        return None
    return (profit / landed) * 100


def project_finances(
    *,
    amazon_sale_price: Any,
    referral_fee: Any,
    fba_fulfillment_fee: Any,
    cogs: Any,
    prep_cost: Any,
    inbound_shipping_cost: Any,
) -> Dict[str, Any]:
    """Compute the full projected-finances record for one candidate.

    Stable return shape (financial_status values):
        - "scored":                 all inputs valid and profit > 0
        - "unprofitable":           all inputs valid and profit <= 0
        - "need_cost_data":         COGS, prep, or inbound missing/invalid
        - "need_fee_data":          sale price, referral, or FBA fee
                                    missing/invalid (checked after costs)
        - "invalid_financial_data": numeric inputs present but negative
    Missing inputs yield null metrics. Explicit zeroes are valid values.
    Inputs are never rounded here; results are full-precision numbers.
    """
    cost_values = (cogs, prep_cost, inbound_shipping_cost)
    fee_values = (amazon_sale_price, referral_fee, fba_fulfillment_fee)

    gap = []
    for name, value in zip(_COST_FIELDS + _FEE_FIELDS, cost_values + fee_values):
        if value is None:
            gap.append(f"{name} is missing")
        elif not _is_number(value):
            gap.append(f"{name} is invalid (not a number)")
        elif not math.isfinite(float(value)):
            gap.append(f"{name} is invalid (not finite)")
        elif value < 0:
            gap.append(f"{name} is negative")

    empty = {
        "amazon_sale_price": None,
        "referral_fee": None,
        "fba_fulfillment_fee": None,
        "amazon_fees_total": None,
        "amazon_payout_before_inventory_costs": None,
        "cogs": None,
        "prep_cost": None,
        "inbound_shipping_cost": None,
        "landed_cost": None,
        "projected_net_profit": None,
        "projected_roi_pct": None,
        "financial_status": STATUS_INVALID_FINANCIAL_DATA,
        "financial_data_gaps": gap,
    }

    if any(
        v is not None
        and _is_number(v)
        and (not math.isfinite(float(v)) or v < 0)
        for v in cost_values + fee_values
    ):
        return empty

    if not all(_is_number(v) for v in cost_values):
        empty["financial_status"] = STATUS_NEED_COST_DATA
        return empty

    if not all(_is_number(v) for v in fee_values):
        empty["financial_status"] = STATUS_NEED_FEE_DATA
        return empty

    payout = amazon_payout_before_inventory_costs(
        amazon_sale_price, referral_fee, fba_fulfillment_fee
    )
    landed = landed_cost(cogs, prep_cost, inbound_shipping_cost)
    profit = projected_net_profit(
        amazon_sale_price,
        referral_fee,
        fba_fulfillment_fee,
        cogs,
        prep_cost,
        inbound_shipping_cost,
    )
    roi_pct = projected_roi_pct(profit, landed)

    return {
        "amazon_sale_price": amazon_sale_price,
        "referral_fee": referral_fee,
        "fba_fulfillment_fee": fba_fulfillment_fee,
        "amazon_fees_total": referral_fee + fba_fulfillment_fee,
        "amazon_payout_before_inventory_costs": payout,
        "cogs": cogs,
        "prep_cost": prep_cost,
        "inbound_shipping_cost": inbound_shipping_cost,
        "landed_cost": landed,
        "projected_net_profit": profit,
        "projected_roi_pct": roi_pct,
        "financial_status": STATUS_SCORED if profit > 0 else STATUS_UNPROFITABLE,
        "financial_data_gaps": [],
    }


def projected_net_profit_sort_key(result: Dict[str, Any]) -> Tuple[int, float]:
    """Default sort key: rows without a valid projected_net_profit sort last.

    Numeric sort on the raw float; deterministic tie-breakers (title
    ascending, then ASIN ascending) are applied by the caller.
    """
    profit = result.get("projected_net_profit")
    if profit is None:
        return (1, 0.0)
    return (0, -float(profit))


def projected_roi_pct_sort_key(result: Dict[str, Any]) -> Tuple[int, float]:
    """ROI sort key: rows with null ROI always sort last."""
    roi = result.get("projected_roi_pct")
    if roi is None:
        return (1, 0.0)
    return (0, -float(roi))


def sort_by_projected_net_profit(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Default ordering: 'Projected Net Profit: High to Low'."""
    return sorted(records, key=lambda r: (projected_net_profit_sort_key(r), _title(r), _asin(r)))


def _title(record: Dict[str, Any]) -> str:
    value = record.get("title")
    if value is None:
        value = record.get("name") or ""
    return str(value).lower()


def _asin(record: Dict[str, Any]) -> str:
    value = record.get("asin")
    return str(value).lower() if value is not None else ""