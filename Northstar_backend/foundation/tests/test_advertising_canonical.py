"""Batch C — advertising economics/policy separation (Phase 1C-03R)."""
from __future__ import annotations

import os
import sys
from decimal import Decimal

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))  # Northstar_backend

from Northstar_backend.foundation.economics.advertising import (  # noqa: E402
    break_even_acos, target_acos_policy, maximum_cpc, ADVERTISING_POLICY_VERSION,
)
from Northstar_backend.foundation.economics.versions import FORMULA_VERSION  # noqa: E402


def test_break_even_acos_canonical():
    r = break_even_acos(pre_ad_contribution="12.16", ad_attributed_revenue="42.00")
    assert r["break_even_acos"] == Decimal("0.2895")
    assert r["denominator_label"] == "ad_attributed_revenue"


def test_break_even_acos_unknown_inputs_none():
    assert break_even_acos(pre_ad_contribution=None, ad_attributed_revenue="42")["break_even_acos"] is None
    assert break_even_acos(pre_ad_contribution="1", ad_attributed_revenue="0")["break_even_acos"] is None


def test_target_policy_break_even_equals_be():
    r = target_acos_policy(break_even_acos="0.30", policy="break_even")
    assert r["target_acos"] == Decimal("0.3000")
    assert r["policy_version"] == ADVERTISING_POLICY_VERSION


def test_target_policy_retained_below_be():
    r = target_acos_policy(break_even_acos="0.30", policy="retained_contribution",
                           retained_contribution_pct=0.2)
    assert r["target_acos"] == Decimal("0.2400")


def test_target_policy_no_hidden_default():
    # unknown policy, no explicit selection -> unavailable (never 70% of break-even)
    r = target_acos_policy(break_even_acos="0.30")
    # default mode is break_even (explicit), so target == be; ensure no 0.21 magic
    assert r["target_acos"] != Decimal("0.2100")


def test_loss_leading_requires_explicit_flag():
    blocked = target_acos_policy(break_even_acos="0.30", policy="loss_leading",
                                 allow_loss_leading=False)
    assert blocked["target_acos"] is None
    assert blocked["warnings"]
    allowed = target_acos_policy(break_even_acos="0.30", policy="loss_leading",
                                 allow_loss_leading=True)
    assert allowed["target_acos"] > Decimal("0.30")


def test_maximum_cpc_requires_cvr():
    assert maximum_cpc(pre_ad_contribution_per_order="10", cvr=None) is None
    assert maximum_cpc(pre_ad_contribution_per_order="10", cvr="0.10") == Decimal("1.00")


# --- ad_pilot integration ----------------------------------------------------

def test_ad_pilot_compute_target_acos_canonical():
    import ad_pilot
    out = ad_pilot.compute_target_acos(12.5, 24.99, referral_fee_pct=15, fba_fee=5.55,
                                       desired_profit_margin=20)
    assert out["economics_formula_version"] == FORMULA_VERSION
    assert out["advertising_policy_version"] == ADVERTISING_POLICY_VERSION
    assert out["break_even_acos"] is not None
    assert out["policy_name"] == "retained_contribution"
    # legacy keys preserved
    assert "breakeven_acos" in out and "target_acos" in out


def test_ad_pilot_unknown_price_break_even_none():
    import ad_pilot
    out = ad_pilot.compute_target_acos(12.5, 0.0)
    assert out["break_even_acos"] is None  # never fabricated from zero revenue


def test_word_coffee_breakeven_canonical():
    import word_coffee
    out = word_coffee.breakeven_acos(cogs_per_unit=12.0, asp=42.0)
    assert out["economics_formula_version"] == FORMULA_VERSION
    assert out["break_even_acos"] is not None
    assert "breakeven_acos_pct" in out  # legacy preserved