"""Configurable pipeline settings / thresholds.

PURE / OFFLINE. Centralizes the thresholds referenced by the manual-export
workflow (competition filter, conservative economics, approvals, reports).
Values can be overridden via environment variables (NORTHSTAR_<NAME>) or by
passing a `settings` dict into the functions that consume them.

Unknown is never favorable; thresholds only gate KNOWN values.
"""
from __future__ import annotations

import os
from typing import Any, Dict

DEFAULT_SETTINGS: Dict[str, Any] = {
    # ---- marketplace competition filter (Phase 5) ----
    "minimum_active_mfn_sellers": 3,
    "maximum_active_fba_sellers": 0,
    "maximum_shipping_weight_lb": 3.0,
    "minimum_net_profit": 5.00,
    "minimum_roi_pct": 30.0,
    "qualified_net_profit": 11.00,
    "priority_net_profit": 20.00,
    "market_snapshot_max_age_minutes": 60,
    "source_price_max_age_minutes": 60,
    "price_history_max_age_hours": 24,

    # ---- conservative economics (Phase 6) ----
    "source_sales_tax_rate": 0.0825,
    "prep_cost": 0.50,
    "inbound_shipping_cost": 0.40,
    "storage_allowance": 0.25,
    "returns_allowance_rate": 0.02,
    "other_buy_costs": 0.00,
    "referral_fee_rate": 0.15,
    "fba_fee_unknown_note": "not_reported",
    "historical_price_stability_floor_pct": 0.90,  # conservative floor = 90% of history midpoint

    # ---- scoring (Phase 5 mfn_opportunity_score_v1 weights, sum 100) ----
    "mfn_score_weights": {
        "net_profit": 25,
        "roi": 20,
        "demand_signal": 15,
        "mfn_competition_quality": 15,
        "zero_fba_sellers": 10,
        "low_weight_standard_size": 5,
        "price_stability": 5,
        "source_repeatability": 5,
    },

    # ---- identity / match ----
    "title_similarity_candidate": 0.60,
    "title_similarity_pack": 0.70,

    # ---- approval (Phase 7) ----
    "approval_default_expiry_hours": 72,
    "approval_max_quantity": 200,
}


def env_override(name: str, value: Any) -> Any:
    """Read NORTHSTAR_<NAME> env override for a setting (non-secret)."""
    key = f"NORTHSTAR_{name.upper()}"
    raw = os.getenv(key)
    if raw is None:
        return value
    if isinstance(value, bool):
        return raw.strip().lower() in ("1", "true", "yes", "on")
    if isinstance(value, int):
        try:
            return int(raw)
        except ValueError:
            return value
    if isinstance(value, float):
        try:
            return float(raw)
        except ValueError:
            return value
    return raw


def get_settings(overrides: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """Resolve effective settings (defaults + env + explicit overrides)."""
    out = {}
    for k, v in DEFAULT_SETTINGS.items():
        out[k] = env_override(k, v)
    if overrides:
        for k, v in overrides.items():
            out[k] = v
    return out