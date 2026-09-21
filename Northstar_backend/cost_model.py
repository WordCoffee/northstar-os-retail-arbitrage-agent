"""Cost model + margin invariants (Phase H / H5).

Loads the canonical caps/unit costs from ``shared/usage-caps.json`` and
computes the worst-case cost of a tier (every cap hit) and its margin. The
invariant — worst case ≤ 40% of price (≥60% margin) — is asserted by tests so
the pricing can never silently drift into a loss.

Pure and offline. The unit costs are planning assumptions; they are
recalibrated from real provider invoices before launch (the calibration gate).
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Dict, List, Optional

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_CAPS_PATH = os.path.join(_REPO_ROOT, "shared", "usage-caps.json")

MARGIN_FLOOR = 0.60          # worst case must keep ≥60% margin
MAX_COST_FRACTION = 0.40     # worst-case cost ≤ 40% of price


def load_caps(path: Optional[str] = None) -> Dict:
    with open(path or _CAPS_PATH, "r", encoding="utf-8") as fh:
        return json.load(fh)


@dataclass
class TierCost:
    plan: str
    name: str
    price: float
    worst_case_cost: float
    margin: float
    profit: float
    breakdown: Dict[str, float]


def worst_case(plan: str, data: Optional[Dict] = None) -> TierCost:
    """Compute the worst-case cost of a tier (all caps consumed)."""
    d = data or load_caps()
    tier = d["tiers"][plan]
    caps = tier["caps"]
    images = tier.get("images", {})
    u = d["unit_costs_usd"]

    breakdown: Dict[str, float] = {}

    def add(key: str, amount: float) -> None:
        if amount:
            breakdown[key] = round(breakdown.get(key, 0.0) + amount, 6)

    add("chat_t1", caps.get("chat_t1", 0) * u["chat_t1"])
    add("listing", caps.get("listing", 0) * u["listing"])
    add("post", caps.get("post", 0) * u["post"])
    add("autothink_t2", caps.get("autothink_t2", 0) * u["autothink_t2"])
    add("autothink_t3", caps.get("autothink_t3", 0) * u["autothink_t3"])
    add("rank_snapshot", caps.get("rank_snapshot", 0) * u["rank_snapshot"])
    add("alert", caps.get("alert", 0) * u["alert"])

    gg_scan_cost = (caps.get("gg_scan", 0) * u["gg_scan"]) + (
        caps.get("gg_scan", 0) * caps.get("gg_items_per_scan", 0) * u["gg_item"]
    )
    add("gg_scan", gg_scan_cost)

    add("image_v1", images.get("V1", 0) * u["image_v1"])
    add("image_v2", images.get("V2", 0) * u["image_v2"])
    add("image_v3", images.get("V3", 0) * u["image_v3"])

    add("fixed_infra", u["fixed_infra"])

    cost = round(sum(breakdown.values()), 4)
    price = float(tier["price_usd_month"])
    profit = round(price - cost, 2)
    margin = round(profit / price, 4) if price else 0.0
    return TierCost(plan=plan, name=tier["name"], price=price,
                    worst_case_cost=cost, margin=margin, profit=profit,
                    breakdown=breakdown)


def all_tiers(data: Optional[Dict] = None) -> List[TierCost]:
    d = data or load_caps()
    return [worst_case(plan, d) for plan in d["tiers"]]


def margin_ok(plan: str, data: Optional[Dict] = None,
              floor: float = MARGIN_FLOOR) -> bool:
    return worst_case(plan, data).margin >= floor


def ppc_fee(managed_spend: float, data: Optional[Dict] = None) -> Dict[str, float]:
    """Platform fee on managed ad spend, banded (no fee on the first $10k)."""
    d = data or load_caps()
    bands = d["ppc_fee_bands"]
    remaining = max(0.0, managed_spend)
    prev = 0.0
    total = 0.0
    for band in bands:
        top = band["up_to_usd"]
        ceiling = float("inf") if top is None else float(top)
        band_width = max(0.0, min(remaining, ceiling) - prev)
        total += band_width * (band["fee_pct"] / 100.0)
        prev = ceiling
        if remaining <= ceiling:
            break
    return {"managed_spend": managed_spend, "fee_usd": round(total, 2)}


def refund(paid: float, credits_consumed: int, zero_cost_only: bool = False,
           data: Optional[Dict] = None) -> Dict[str, object]:
    """Partial refund = paid - credits x rate; full when only $0-cost data used."""
    d = data or load_caps()
    policy = d["refund_policy"]
    rate = policy["credit_rate_usd"]
    if zero_cost_only:
        return {"refund_usd": round(paid, 2), "reason": "zero_cost_data_only",
                "window_days": policy["window_days"]}
    amount = max(0.0, paid - credits_consumed * rate)
    return {"refund_usd": round(amount, 2), "reason": "partial_minus_credits",
            "window_days": policy["window_days"],
            "credits_consumed": credits_consumed, "credit_rate_usd": rate}
