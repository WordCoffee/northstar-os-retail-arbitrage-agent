"""Replenishment Intelligence — stockout prediction and restock timing.

Analyzes BSR velocity, current inventory levels, and sales history
to predict when a product will go out of stock and recommend reorder
timing and quantities.

Signals:
- Days of stock remaining based on current inventory / daily sales rate
- BSR velocity trend (accelerating vs decelerating demand)
- Historical Costco restock patterns
- Recommended reorder date and quantity
"""

import math
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional


def estimate_stockout(
    current_inventory: int,
    daily_sales_rate: Optional[float] = None,
    monthly_sales_estimate: Optional[int] = None,
    bsr_velocity_trend: str = "stable",
    safety_stock_days: int = 7,
) -> Dict[str, Any]:
    """Estimate when stock will run out and recommend reorder.

    Args:
        current_inventory: Units currently in stock (FBA + inbound).
        daily_sales_rate: Known daily sales rate (preferred).
        monthly_sales_estimate: Monthly sales estimate (used to derive daily rate).
        bsr_velocity_trend: "accelerating", "stable", or "decelerating".
        safety_stock_days: Days of buffer to maintain.

    Returns:
        Stockout estimate with days_remaining, reorder_date, recommended_qty.
    """
    if current_inventory <= 0:
        return {
            "status": "out_of_stock",
            "days_remaining": 0,
            "reorder_urgent": True,
            "recommended_action": "RESTOCK IMMEDIATELY",
        }

    # Derive daily rate
    if daily_sales_rate and daily_sales_rate > 0:
        daily_rate = daily_sales_rate
        rate_source = "provided"
    elif monthly_sales_estimate and monthly_sales_estimate > 0:
        daily_rate = monthly_sales_estimate / 30.0
        rate_source = "monthly_estimate"
    else:
        return {
            "status": "insufficient_data",
            "days_remaining": None,
            "reorder_urgent": False,
            "recommended_action": "Need sales data to estimate stockout",
        }

    # Adjust rate based on velocity trend
    rate_multiplier = {"accelerating": 1.15, "stable": 1.0, "decelerating": 0.85}
    adjusted_rate = daily_rate * rate_multiplier.get(bsr_velocity_trend, 1.0)

    if adjusted_rate <= 0:
        return {
            "status": "no_sales",
            "days_remaining": None,
            "reorder_urgent": False,
            "recommended_action": "No sales detected — review pricing and listing",
        }

    # Calculate days remaining
    days_remaining = current_inventory / adjusted_rate
    days_until_reorder = max(0, days_remaining - safety_stock_days)

    # Urgency
    if days_remaining <= safety_stock_days:
        urgency = "critical"
        action = "REORDER NOW — stock critically low"
    elif days_until_reorder <= 7:
        urgency = "high"
        action = "REORDER THIS WEEK"
    elif days_until_reorder <= 14:
        urgency = "medium"
        action = "Plan reorder within 2 weeks"
    elif days_until_reorder <= 30:
        urgency = "low"
        action = "Reorder within month"
    else:
        urgency = "none"
        action = "No reorder needed yet"

    # Recommended reorder date
    reorder_date = (datetime.now(timezone.utc) + timedelta(days=days_until_reorder)).strftime("%Y-%m-%d")
    stockout_date = (datetime.now(timezone.utc) + timedelta(days=days_remaining)).strftime("%Y-%m-%d")

    # Recommended quantity (aim for 60-day supply)
    target_days = 60
    recommended_qty = math.ceil(adjusted_rate * target_days)

    return {
        "status": "calculated",
        "current_inventory": current_inventory,
        "daily_sales_rate": round(adjusted_rate, 2),
        "rate_source": rate_source,
        "velocity_trend": bsr_velocity_trend,
        "days_remaining": round(days_remaining, 1),
        "days_until_reorder": round(days_until_reorder, 1),
        "stockout_date": stockout_date,
        "reorder_date": reorder_date,
        "urgency": urgency,
        "recommended_action": action,
        "recommended_qty": recommended_qty,
        "target_days_supply": target_days,
        "safety_stock_days": safety_stock_days,
    }


def cycle_scaling_plan(
    current_units: int = 50,
    profit_per_unit: float = 15.0,
    reinvestment_pct: float = 0.7,
    cycles: int = 5,
) -> List[Dict[str, Any]]:
    """Project compound growth across purchase cycles.

    Models the Northstar 50-unit Cycle 1 → compound growth strategy.
    Each cycle reinvests a percentage of profit into more inventory.

    Returns a list of cycle projections.
    """
    plan = []
    units = current_units
    cumulative_profit = 0
    cumulative_investment = 0

    for cycle in range(1, cycles + 1):
        revenue = units * (profit_per_unit + 10)  # assume ~$10 cost, ~$15 profit
        cost = units * 10  # COGS
        profit = units * profit_per_unit
        cumulative_profit += profit
        cumulative_investment += cost

        reinvest_amount = profit * reinvestment_pct
        additional_units = int(reinvest_amount / 10) if reinvest_amount > 0 else 0

        plan.append({
            "cycle": cycle,
            "units_purchased": units,
            "total_cost": round(cost, 2),
            "revenue": round(revenue, 2),
            "profit": round(profit, 2),
            "reinvestment": round(reinvest_amount, 2),
            "additional_units": additional_units,
            "cumulative_profit": round(cumulative_profit, 2),
            "cumulative_investment": round(cumulative_investment, 2),
        })

        units += additional_units

    return plan
