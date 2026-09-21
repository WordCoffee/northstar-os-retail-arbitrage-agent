"""Word Coffee ad-account analysis (Phase H / H7).

Offline analysis of the operator's real Amazon Ads export, staged as a local
fixture so The Auctioneer (AdPilot) can be exercised end-to-end WITHOUT any
live call. Produces a dry-run change plan with the fixed guardrails applied
(≤20% bid decrease, ≤10% increase, negatives/pause for bleeds).

No network. No Amazon write. The plan is advisory until an operator names a
live execution (§3).
"""

from __future__ import annotations

import json
import os
from typing import Dict, List, Optional

FIXTURE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "data", "word-coffee", "ads-export.json")

# Fixed bid guardrails (adpilot, unchanged).
MAX_DECREASE_PCT = 20.0
MAX_INCREASE_PCT = 10.0
BLEED_ACOS_PCT = 100.0        # at/above this, pause or cut hard
DEFAULT_TARGET_ACOS_PCT = 30.0


def load(path: Optional[str] = None) -> Dict:
    with open(path or FIXTURE, "r", encoding="utf-8") as fh:
        return json.load(fh)


def account_summary(data: Optional[Dict] = None) -> Dict[str, object]:
    d = data or load()
    a = d["account"]
    return {
        "spend": a["spend"],
        "sales": a["sales"],
        "acos_pct": a["acos_pct"],
        "profitable": a["acos_pct"] < 100.0,
        "units": a["units"],
        "implied_asp": a["implied_asp"],
        "note": "Ad-attributed sales only; organic units are separate.",
    }


def breakeven_acos(cogs_per_unit: float, asp: Optional[float] = None,
                   referral_pct: float = 15.0, fba_fee: float = 0.0,
                   data: Optional[Dict] = None) -> Dict[str, float]:
    """Breakeven ACoS = gross margin % (before ad spend).

    margin = (asp - cogs - fba_fee - asp*referral_pct/100) / asp
    """
    d = data or load()
    price = asp if asp is not None else d["account"]["implied_asp"]
    referral = price * referral_pct / 100.0
    contribution = price - cogs_per_unit - fba_fee - referral
    margin = contribution / price if price else 0.0
    return {
        "asp": round(price, 2),
        "cogs_per_unit": cogs_per_unit,
        "referral_fee": round(referral, 2),
        "fba_fee": fba_fee,
        "contribution_per_unit": round(contribution, 2),
        "breakeven_acos_pct": round(margin * 100.0, 1),
    }


def classify(acos_pct: float, target_acos_pct: float = DEFAULT_TARGET_ACOS_PCT) -> str:
    if acos_pct >= BLEED_ACOS_PCT:
        return "pause_or_cut"
    if acos_pct > target_acos_pct:
        return "cut_bid"
    if acos_pct <= target_acos_pct * 0.7:
        return "increase_bid"
    return "hold"


def clamp_delta(action: str) -> float:
    """Guardrail-clamped bid delta % for an action (positive = raise)."""
    if action == "increase_bid":
        return MAX_INCREASE_PCT
    if action in ("cut_bid", "pause_or_cut"):
        return -MAX_DECREASE_PCT
    return 0.0


def change_plan(target_acos_pct: float = DEFAULT_TARGET_ACOS_PCT,
                data: Optional[Dict] = None) -> List[Dict[str, object]]:
    """Dry-run plan over targets: action + guardrail-clamped delta. No write."""
    d = data or load()
    plan = []
    for t in d["targets"]:
        action = classify(t["acos_pct"], target_acos_pct)
        plan.append({
            "target": t["target"],
            "match": t["match"],
            "acos_pct": t["acos_pct"],
            "spend": t["spend"],
            "action": action,
            "bid_delta_pct": clamp_delta(action),
            "note": ("pause/negative — worst bleed" if action == "pause_or_cut"
                     else "lower bid within the ≤20% guardrail" if action == "cut_bid"
                     else "raise bid within the ≤10% guardrail" if action == "increase_bid"
                     else "leave as-is"),
        })
    plan.sort(key=lambda r: r["acos_pct"], reverse=True)
    return plan


def capital_leaks(data: Optional[Dict] = None) -> List[Dict[str, object]]:
    """Targets at/above the bleed threshold, worst first."""
    return [r for r in change_plan(data=data) if r["action"] == "pause_or_cut"]


def summary(data: Optional[Dict] = None,
            cogs_per_unit: Optional[float] = None,
            target_acos_pct: float = DEFAULT_TARGET_ACOS_PCT) -> Dict[str, object]:
    d = data or load()
    out: Dict[str, object] = {
        "account": account_summary(d),
        "campaigns_all_unprofitable": all(c["acos_pct"] >= 100 for c in d["campaigns"]),
        "capital_leaks": capital_leaks(d),
        "plan": change_plan(target_acos_pct, d),
        "target_acos_pct": target_acos_pct,
        "cogs_supplied": cogs_per_unit is not None,
    }
    if cogs_per_unit is not None:
        out["breakeven"] = breakeven_acos(cogs_per_unit, data=d)
    else:
        out["breakeven"] = None
        out["note"] = ("COGS/unit not supplied — provisional target ACoS "
                       "%s%% in use; breakeven computes once COGS is provided."
                       % target_acos_pct)
    return out
