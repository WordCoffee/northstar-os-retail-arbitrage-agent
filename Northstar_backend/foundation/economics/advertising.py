"""Advertising economics bridge + policy (Phase 1C-03R Batch C1/C2).

Separates three things the legacy modules conflated:
  * OBJECTIVE economics  -> break-even ACoS (from canonical economics inputs).
  * ADVERTISING MATH      -> maximum CPC (needs CVR + economics boundary).
  * OPERATOR POLICY       -> target ACoS (explicitly selected, versioned).

No hidden 15% referral, no fixed FBA fee, no universal "70% of break-even".
Unknown inputs return None. No provider calls.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Optional

from .money import to_decimal, safe_div, quantize_rate, quantize_money

ADVERTISING_POLICY_VERSION = "advertising-policy-1.0.0"
POLICY_MODES = ("break_even", "retained_contribution", "loss_leading")


def break_even_acos(*, pre_ad_contribution, ad_attributed_revenue) -> dict:
    """Objective break-even ACoS = pre-ad contribution / ad-attributed revenue."""
    num = to_decimal(pre_ad_contribution)
    den = to_decimal(ad_attributed_revenue)
    val = safe_div(num, den)
    return {
        "break_even_acos": quantize_rate(val) if val is not None else None,
        "numerator_label": "pre_ad_contribution",
        "denominator_label": "ad_attributed_revenue",
    }


def target_acos_policy(*, break_even_acos, policy: str = "break_even",
                       retained_contribution_pct=None,
                       allow_loss_leading: bool = False) -> dict:
    """Target ACoS is POLICY, never a universal constant.

    - break_even: target == break-even (no retained margin).
    - retained_contribution: keep retained_contribution_pct of break-even
      (retained_contribution_pct is a fraction, e.g. 0.2 = keep 20%).
    - loss_leading: only with explicit allow_loss_leading -> may exceed break-even.
    """
    be = to_decimal(break_even_acos)
    warnings: list[str] = []
    if be is None:
        return {"target_acos": None, "policy_name": policy,
                "policy_version": ADVERTISING_POLICY_VERSION,
                "warnings": ["break_even_acos unavailable"]}
    t: Optional[Decimal]
    if policy == "break_even":
        t = be
    elif policy == "retained_contribution" and retained_contribution_pct is not None:
        keep = to_decimal(retained_contribution_pct)
        t = None if keep is None else be * (Decimal("1") - keep)
    elif policy == "loss_leading" and allow_loss_leading:
        t = be * Decimal("1.2")  # explicit, labeled loss-leading; never default
        warnings.append("loss_leading policy selected explicitly; target exceeds break-even")
    else:
        t = None
        warnings.append("no applicable policy; target unavailable")
    if t is not None and t > be and not (policy == "loss_leading" and allow_loss_leading):
        t = None
        warnings.append("target exceeds break-even without explicit loss-leading policy")
    return {"target_acos": quantize_rate(t) if t is not None else None,
            "policy_name": policy, "policy_version": ADVERTISING_POLICY_VERSION,
            "warnings": warnings}


def maximum_cpc(*, pre_ad_contribution_per_order, cvr,
                required_post_ad_profit="0") -> Optional[Decimal]:
    """Max CPC = (pre-ad contribution per order - required post-ad profit) * CVR.
    Requires a valid CVR; missing CVR -> None (never fabricated)."""
    contrib = to_decimal(pre_ad_contribution_per_order)
    c = to_decimal(cvr)
    req = to_decimal(required_post_ad_profit) or Decimal("0")
    if contrib is None or c is None:
        return None
    return quantize_money((contrib - req) * c)