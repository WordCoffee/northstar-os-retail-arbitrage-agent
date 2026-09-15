"""AdPilot — Amazon PPC Campaign Management Intelligence.

Four-tier campaign structure with automated keyword lifecycle management,
bid optimization, negative keyword detection, and budget allocation.

Campaign tiers:
  1. Auto     — Discovery campaigns (auto-targeting)
  2. Broad    — Broad match harvesting
  3. Phrase   — Phrase match refinement
  4. Exact    — Exact match winners

Keyword lifecycle:
  bench → performer → almost_winner → winner (with auto-promotion/demotion)
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Bid Optimization
# ---------------------------------------------------------------------------

def optimize_bid(
    keyword: str,
    current_bid: float,
    acos: Optional[float] = None,
    target_acos: float = 30.0,
    clicks: int = 0,
    orders: int = 0,
    impressions: int = 0,
    ctr: Optional[float] = None,
    cvr: Optional[float] = None,
    margin_pct: float = 30.0,
) -> Dict[str, Any]:
    """Optimize bid for a keyword based on performance metrics.

    Decision rules:
    - ACoS >45% AND ≥10 clicks: decrease 10-30%
    - ACoS 30-45%: decrease 5-10%
    - ACoS 15-30%: increase 5-15%
    - ACoS <15%: increase 15-30%
    - ≥20 clicks, 0 orders: pause
    - 1-2 orders + ACoS ≤ target: promote tier
    """
    recommended_bid = current_bid
    adjustment_pct = 0.0
    action = "hold"
    reasoning = ""
    confidence = "medium"
    needs_approval = False

    if clicks == 0 and impressions == 0:
        return _bid_result(current_bid, 0, "no_data", "No performance data yet", "low", False)

    if orders == 0 and clicks >= 20:
        adjustment_pct = -100.0
        recommended_bid = 0
        action = "pause"
        reasoning = f"{clicks} clicks with 0 orders — pause to stop wasted spend"
        confidence = "high"
        needs_approval = True
    elif acos is not None:
        if acos > 45 and clicks >= 10:
            # Aggressive decrease
            adjustment_pct = -min(30, max(10, int((acos - target_acos) * 0.5)))
            recommended_bid = current_bid * (1 + adjustment_pct / 100)
            action = "decrease"
            reasoning = f"ACoS {acos:.1f}% significantly above target {target_acos:.0f}% — decreasing bid"
            confidence = "high"
            needs_approval = adjustment_pct < -20
        elif acos > target_acos:
            adjustment_pct = -min(10, max(5, int((acos - target_acos) * 0.3)))
            recommended_bid = current_bid * (1 + adjustment_pct / 100)
            action = "decrease"
            reasoning = f"ACoS {acos:.1f}% above target {target_acos:.0f}% — decreasing bid"
            confidence = "medium"
        elif acos < target_acos * 0.5:
            # Very profitable — increase aggressively
            adjustment_pct = min(30, max(15, int((target_acos - acos) * 0.3)))
            recommended_bid = current_bid * (1 + adjustment_pct / 100)
            action = "increase"
            reasoning = f"ACoS {acos:.1f}% well below target — room to increase bids"
            confidence = "high"
            needs_approval = adjustment_pct > 20
        elif acos < target_acos:
            adjustment_pct = min(15, max(5, int((target_acos - acos) * 0.2)))
            recommended_bid = current_bid * (1 + adjustment_pct / 100)
            action = "increase"
            reasoning = f"ACoS {acos:.1f}% below target {target_acos:.0f}% — slight increase"
            confidence = "medium"
        else:
            reasoning = f"ACoS {acos:.1f}% at target — hold"
            action = "hold"

    # Tier promotion check
    promote_tier = False
    if orders >= 2 and acos is not None and acos <= target_acos:
        promote_tier = True
        reasoning += " | PROMOTE: 2+ orders at target ACoS"

    recommended_bid = max(0.02, round(recommended_bid, 2))

    return {
        "keyword": keyword,
        "current_bid": current_bid,
        "recommended_bid": recommended_bid,
        "adjustment_pct": round(adjustment_pct, 1),
        "action": action,
        "reasoning": reasoning,
        "confidence": confidence,
        "needs_approval": needs_approval,
        "promote_tier": promote_tier,
        "metrics": {
            "acos": acos,
            "target_acos": target_acos,
            "clicks": clicks,
            "orders": orders,
            "impressions": impressions,
        },
    }


def _bid_result(bid, adj_pct, action, reasoning, confidence, approval):
    return {
        "current_bid": bid,
        "recommended_bid": bid,
        "adjustment_pct": adj_pct,
        "action": action,
        "reasoning": reasoning,
        "confidence": confidence,
        "needs_approval": approval,
        "promote_tier": False,
        "metrics": {},
    }


# ---------------------------------------------------------------------------
# Keyword Lifecycle
# ---------------------------------------------------------------------------

TIER_ORDER = {"bench": 4, "performer": 3, "almost_winner": 2, "winner": 1}


def classify_keyword_tier(
    impressions: int = 0,
    clicks: int = 0,
    orders: int = 0,
    acos: Optional[float] = None,
    target_acos: float = 30.0,
) -> str:
    """Classify a keyword into a lifecycle tier based on performance."""
    if orders >= 3 and acos is not None and acos <= target_acos:
        return "winner"
    if orders >= 1 and acos is not None and acos <= target_acos * 1.2:
        return "almost_winner"
    if clicks >= 5 and orders == 0:
        return "bench"  # not performing
    if clicks >= 2 or impressions >= 100:
        return "performer"
    return "bench"


def detect_negative_keyword_candidates(
    keywords: List[Dict[str, Any]],
    min_clicks: int = 15,
    max_orders: int = 0,
) -> List[Dict[str, Any]]:
    """Identify keywords that should be added as negatives.

    Rules:
    - ≥15 clicks with 0 orders → strong negative candidate
    - ≥30 clicks with 0 orders → urgent negative
    """
    candidates = []
    for kw in keywords:
        clicks = kw.get("clicks", 0)
        orders = kw.get("orders", 0)
        if clicks >= min_clicks and orders <= max_orders:
            urgency = "urgent" if clicks >= 30 else "recommended"
            candidates.append({
                "keyword": kw.get("keyword", ""),
                "clicks": clicks,
                "orders": orders,
                "urgency": urgency,
                "action": "add_negative",
                "suggested_match": "broad" if clicks >= 30 else "phrase",
            })
    return candidates


# ---------------------------------------------------------------------------
# Campaign Structure
# ---------------------------------------------------------------------------

def generate_campaign_structure(
    asin: str,
    product_title: str,
    keywords: List[str],
    daily_budget: float = 50.0,
    target_acos: float = 30.0,
) -> Dict[str, Any]:
    """Generate a four-tier campaign structure for an ASIN.

    Returns campaign definitions ready for Amazon Ads API submission.
    """
    campaigns = []

    # Tier 1: Auto (discovery)
    campaigns.append({
        "name": f"Auto-{asin}",
        "type": "SP-AUTO",
        "asin": asin,
        "targeting_type": "auto",
        "daily_budget": round(daily_budget * 0.3, 2),
        "status": "enabled",
        "bid": 0.75,
        "purpose": "Discovery — find converting search terms",
    })

    # Tier 2: Broad (harvesting)
    broad_kws = keywords[:20] if len(keywords) > 20 else keywords
    campaigns.append({
        "name": f"Broad-{asin}",
        "type": "SP-BROAD",
        "asin": asin,
        "targeting_type": "broad",
        "daily_budget": round(daily_budget * 0.25, 2),
        "status": "enabled",
        "keywords": [{"keyword": kw, "bid": 0.65} for kw in broad_kws],
        "purpose": "Harvest converting search terms from broad match",
    })

    # Tier 3: Phrase (refinement)
    phrase_kws = keywords[:10] if len(keywords) > 10 else keywords
    campaigns.append({
        "name": f"Phrase-{asin}",
        "type": "SP-PHRASE",
        "asin": asin,
        "targeting_type": "phrase",
        "daily_budget": round(daily_budget * 0.25, 2),
        "status": "enabled",
        "keywords": [{"keyword": kw, "bid": 0.85} for kw in phrase_kws],
        "purpose": "Refine with phrase match for more control",
    })

    # Tier 4: Exact (winners)
    exact_kws = keywords[:5] if len(keywords) > 5 else keywords
    campaigns.append({
        "name": f"Exact-{asin}",
        "type": "SP-EXACT",
        "asin": asin,
        "targeting_type": "exact",
        "daily_budget": round(daily_budget * 0.20, 2),
        "status": "enabled",
        "keywords": [{"keyword": kw, "bid": 1.00} for kw in exact_kws],
        "purpose": "Winning keywords — maximize conversions",
    })

    return {
        "asin": asin,
        "campaigns": campaigns,
        "total_daily_budget": daily_budget,
        "target_acos": target_acos,
        "structure": "four_tier",
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# Budget Allocation
# ---------------------------------------------------------------------------

def allocate_budget(
    campaigns: List[Dict[str, Any]],
    total_budget: float,
    performance_weight: float = 0.7,
) -> List[Dict[str, Any]]:
    """Reallocate budget across campaigns based on performance.

    Better-performing campaigns get more budget. Uses ACoS as the
    primary performance signal.
    """
    if not campaigns:
        return []

    # Score each campaign
    scored = []
    for c in campaigns:
        acos = c.get("acos")
        revenue = c.get("revenue", 0)
        spend = c.get("spend", 0)

        if acos is not None and acos > 0:
            # Lower ACoS = better performance
            perf_score = max(0.1, 1.0 - (acos / 100))
        elif revenue > 0 and spend > 0:
            perf_score = min(1.0, revenue / spend)
        else:
            perf_score = 0.5  # neutral for no data

        scored.append({**c, "_perf_score": perf_score})

    # Normalize scores
    total_score = sum(c["_perf_score"] for c in scored)
    if total_score == 0:
        total_score = len(scored)
        for c in scored:
            c["_perf_score"] = 1.0

    # Allocate
    for c in scored:
        base_share = 1.0 / len(scored)
        perf_share = c["_perf_score"] / total_score
        blended = base_share * (1 - performance_weight) + perf_share * performance_weight
        c["allocated_budget"] = round(total_budget * blended, 2)
        c["budget_change"] = round(c["allocated_budget"] - c.get("daily_budget", 0), 2)
        del c["_perf_score"]

    return scored


# ---------------------------------------------------------------------------
# ACoS Target Calculator
# ---------------------------------------------------------------------------

def compute_target_acos(
    product_cost: float,
    amazon_price: float,
    referral_fee_pct: float = 15.0,
    fba_fee: float = 0.0,
    desired_profit_margin: float = 20.0,
) -> Dict[str, Any]:
    """Calculate the maximum target ACoS for profitability.

    target_acos = (selling_price - cost - fees) / selling_price * (1 - desired_margin)
    """
    referral_fee = amazon_price * (referral_fee_pct / 100)
    total_fees = referral_fee + fba_fee
    gross_profit = amazon_price - product_cost - total_fees
    max_acos_pct = (gross_profit / amazon_price) * 100 if amazon_price > 0 else 0
    target_acos = max_acos_pct * (1 - desired_profit_margin / 100)
    breakeven_acos = max_acos_pct

    return {
        "amazon_price": amazon_price,
        "product_cost": product_cost,
        "referral_fee": round(referral_fee, 2),
        "fba_fee": round(fba_fee, 2),
        "total_fees": round(total_fees, 2),
        "gross_profit": round(gross_profit, 2),
        "breakeven_acos": round(breakeven_acos, 1),
        "target_acos": round(max(target_acos, 0), 1),
        "desired_margin": desired_profit_margin,
    }
