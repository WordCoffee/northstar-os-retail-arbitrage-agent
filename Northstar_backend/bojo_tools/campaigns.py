"""Campaign tools for Bojo — AdPilot's ads plan and cost maths.

``plan_campaign`` wraps ``ad_pilot``: ``generate_campaign_structure`` builds the
four-tier plan (auto / broad / phrase / exact) and allocates the daily budget
across the tiers; ``compute_target_acos`` derives the break-even and target
ACoS from the seller's own price, cost and fees (and then cross-checks the
break-even against ``foundation.economics.advertising``). Both are pure
arithmetic from production code — no Ads API call, no spend, no upload.

Nothing is re-implemented: the tier weights, the bid floors, the budget split
and the ACoS formula all come from ``ad_pilot``.

Contract::

    {"ok": True,  "tool": "<name>", "data": {...}}
    {"ok": False, "tool": "<name>", "reason": "<reason string>"}

Business failures — no keywords to target, a non-positive budget, an ACoS
target outside 0-100% — return ``ok=False``. Programmer errors in the argument
contract raise ``TypeError``.
"""

from __future__ import annotations

import os
import sys
from functools import lru_cache
from typing import Any, Dict, List, Mapping, Optional

from ._coerce import jsonable, num, text

TOOL_PLAN_CAMPAIGN = "plan_campaign"


def _backend_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _ensure_backend_on_path() -> None:
    root = _backend_root()
    if root not in sys.path:
        sys.path.insert(0, root)


@lru_cache(maxsize=1)
def _default_planner() -> Any:
    """The real AdPilot plan/cost maths (pure, offline)."""
    _ensure_backend_on_path()
    import ad_pilot

    return ad_pilot


def _bad(reason: str) -> Dict[str, Any]:
    return {"ok": False, "tool": TOOL_PLAN_CAMPAIGN, "reason": reason}


def _keywords(value: Any) -> List[str]:
    if not isinstance(value, (list, tuple)):
        raise TypeError("keywords must be a list of strings")
    out: List[str] = []
    for item in value:
        if not isinstance(item, str):
            raise TypeError("keywords entries must be strings")
        written = item.strip()
        if written and written not in out:
            out.append(written)
    return out


def plan_campaign(
    asin: str,
    keywords: Any,
    product_title: str = "",
    daily_budget: Any = 50.0,
    target_acos: Any = 30.0,
    product_cost: Any = None,
    amazon_price: Any = None,
    referral_fee_pct: Any = 15.0,
    fba_fee: Any = 0.0,
    desired_profit_margin: Any = 20.0,
    planner: Optional[Any] = None,
) -> Dict[str, Any]:
    """Plan a four-tier Sponsored Products campaign. Nothing is spent.

    ``asin`` identifies the product; ``keywords`` are the terms to target.
    ``daily_budget`` is divided across the four tiers by the production
    function; ``target_acos`` is a percentage (30.0 == 30%).

    Pass both ``product_cost`` and ``amazon_price`` to also get the ACoS cost
    maths from ``compute_target_acos`` (break-even, target, canonical
    cross-check and the fee breakdown). Those two are optional because the
    campaign structure itself does not need them.

    ``planner`` is an injectable dependency: anything exposing
    ``generate_campaign_structure(...)`` and ``compute_target_acos(...)``. It
    defaults to the real ``ad_pilot`` module.
    """
    if not isinstance(asin, str):
        raise TypeError("asin must be a string")
    if not isinstance(product_title, str):
        raise TypeError("product_title must be a string")

    written_asin = asin.strip()
    if not written_asin:
        return _bad("asin is empty")

    terms = _keywords(keywords)
    if not terms:
        return _bad("no keywords supplied to target")

    budget = num(daily_budget)
    if budget is None:
        raise TypeError("daily_budget must be a number")
    if budget <= 0:
        return _bad("daily_budget must be greater than zero")

    acos_target = num(target_acos)
    if acos_target is None:
        raise TypeError("target_acos must be a number")
    if not 0 < acos_target <= 100:
        return _bad("target_acos must be a percentage in (0, 100]")

    cost = None if product_cost is None else num(product_cost)
    if product_cost is not None and cost is None:
        raise TypeError("product_cost must be a number or None")
    price = None if amazon_price is None else num(amazon_price)
    if amazon_price is not None and price is None:
        raise TypeError("amazon_price must be a number or None")
    referral = num(referral_fee_pct)
    if referral is None:
        raise TypeError("referral_fee_pct must be a number")
    fulfilment = num(fba_fee)
    if fulfilment is None:
        raise TypeError("fba_fee must be a number")
    margin = num(desired_profit_margin)
    if margin is None:
        raise TypeError("desired_profit_margin must be a number")

    engine = planner if planner is not None else _default_planner()
    try:
        structure = engine.generate_campaign_structure(
            asin=written_asin,
            product_title=product_title,
            keywords=terms,
            daily_budget=float(budget),
            target_acos=float(acos_target),
        )
    except Exception as exc:  # noqa: BLE001 - planner failure, surfaced honestly
        return _bad(
            "campaign planning failed: %s: %s" % (type(exc).__name__, exc)
        )
    if not isinstance(structure, Mapping):
        return _bad(
            "planner returned %s, expected a mapping" % type(structure).__name__
        )
    campaigns = structure.get("campaigns")
    if not isinstance(campaigns, list) or not campaigns:
        return _bad("the planner produced no campaigns")

    acos_math: Optional[Dict[str, Any]] = None
    acos_note = (
        "Pass product_cost and amazon_price to get the ACoS cost maths."
    )
    if cost is not None and price is not None:
        if price <= 0:
            return _bad("amazon_price must be greater than zero")
        try:
            acos_math = dict(
                engine.compute_target_acos(
                    product_cost=float(cost),
                    amazon_price=float(price),
                    referral_fee_pct=float(referral),
                    fba_fee=float(fulfilment),
                    desired_profit_margin=float(margin),
                )
            )
        except Exception as exc:  # noqa: BLE001
            return _bad("ACoS cost maths failed: %s: %s" % (type(exc).__name__, exc))
        # The canonical advertising module returns Decimal rates; the tool
        # contract is JSON-serialisable, so they leave as decimal strings.
        acos_math = jsonable(acos_math)
        acos_note = None

    return {
        "ok": True,
        "tool": TOOL_PLAN_CAMPAIGN,
        "data": {
            "asin": written_asin,
            "product_title": text(product_title) or None,
            "keywords": terms,
            "structure": structure.get("structure"),
            "campaigns": [dict(c) for c in campaigns if isinstance(c, Mapping)],
            "total_daily_budget": structure.get("total_daily_budget"),
            "target_acos_pct": structure.get("target_acos"),
            "acos_math": acos_math,
            "acos_note": acos_note,
            "no_spend": True,
            "note": (
                "A plan only. Nothing was uploaded to an ads platform and no "
                "money was spent."
            ),
        },
    }


TOOLS = {TOOL_PLAN_CAMPAIGN: plan_campaign}
