"""Layer 13 - Unit economics (null-first).

Combines live price/BSR with a wholesale cost basis. The cost basis is flagged
`estimated` whenever it is not invoice-confirmed (never treated as fact). Net
margin and a velocity tier (derived from BSR band) are returned; any missing
input yields null, never 0.
"""

import math


def velocity_tier(bsr_rank):
    if bsr_rank is None:
        return None
    if bsr_rank <= 1000:
        return "hot"
    if bsr_rank <= 10000:
        return "warm"
    if bsr_rank <= 50000:
        return "moderate"
    return "slow"


def compute_economics(snapshot, cost_basis_lookup):
    market = (snapshot.get("facts") or {}).get("market") or {}
    asin = snapshot.get("asin")
    price = market.get("amazon_price")
    bsr = market.get("bsr") or {}
    bsr_rank = bsr.get("bsr_primary_rank") if isinstance(bsr, dict) else None

    cost = cost_basis_lookup.get(asin) if isinstance(cost_basis_lookup, dict) else None
    cost_val = None
    cost_status = "unavailable"
    if isinstance(cost, dict):
        cost_val = cost.get("cost")
        cost_status = cost.get("status", "unavailable")

    net = (price - cost_val) if (price is not None and cost_val is not None) else None
    roi = (net / cost_val) if (net is not None and cost_val) else None
    tier = velocity_tier(bsr_rank)

    if net is not None and roi is not None:
        confidence = "invoice_confirmed" if cost_status == "invoice_confirmed" else "estimated"
    else:
        confidence = "unavailable"

    return {
        "asin": asin,
        "amazon_price": price,
        "cost_basis": cost_val,
        "cost_basis_status": cost_status,
        "cost_basis_flag": "estimated" if cost_status != "invoice_confirmed" else "invoice_confirmed",
        "net_profit": net,
        "roi_pct": round(roi * 100, 2) if roi is not None else None,
        "bsr_primary_rank": bsr_rank,
        "velocity_tier": tier,
        "economics_confidence": confidence,
    }
