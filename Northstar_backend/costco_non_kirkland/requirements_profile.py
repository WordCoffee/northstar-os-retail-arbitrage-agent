"""Costco Research Requirements Profile (versioned, offline).

Consolidates resale/research criteria from existing canonical settings and
documented rules into a versioned, machine-readable profile, classified as:
  verified_current_rule | operator_preference | proposed_default |
  unknown_or_needs_operator_decision
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict

from .settings import DEFAULT_SETTINGS

PROFILE_VERSION = "costco-research-requirements-v1"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_requirements_profile() -> Dict[str, Any]:
    s = DEFAULT_SETTINGS
    rules = {
        # source / identity
        "preferred_sources": {"value": ["costco", "costco_business_center"],
                              "class": "verified_current_rule"},
        "alternate_wholesale_leads_allowed": {"value": True, "class": "operator_preference",
                                              "note": "lead is not a verified source"},
        "invoice_readiness_required_for_sourcing": {"value": True, "class": "verified_current_rule"},
        "non_kirkland_required": {"value": True, "class": "verified_current_rule"},
        "identifier_required_for_exact_match": {"value": "upc/ean/gtin OR mpn+brand",
                                                "class": "verified_current_rule"},
        "costco_item_number_is_not_upc_gtin_mpn_asin": {"value": True, "class": "verified_current_rule"},
        "weight_max_lb": {"value": s.get("maximum_shipping_weight_lb", 3.0), "class": "verified_current_rule"},
        "standard_size_preferred": {"value": True, "class": "operator_preference"},
        "unknown_source_weight_allowed": {"value": "provisional_only_no_auto_qualify",
                                          "class": "verified_current_rule"},
        "split_pack_rule": {"value": "approved_split|intact_only|manual_review|prohibited|unknown",
                            "class": "verified_current_rule"},
        "amazon_retail_rule": {"value": "must_be_provider_reported_absent", "class": "verified_current_rule"},
        "brand_seller_rule": {"value": "provider_reported_absent_when_available", "class": "verified_current_rule"},
        "fba_sellers_max": {"value": s.get("maximum_active_fba_sellers", 0), "class": "verified_current_rule"},
        "mfn_sellers_min": {"value": s.get("minimum_active_mfn_sellers", 3), "class": "verified_current_rule"},
        "demand_min_est_monthly_units": {"value": 500, "class": "operator_preference",
                                         "note": "or provider-supported strong BSR signal -> manual review"},
        "min_net_profit": {"value": s.get("minimum_net_profit", 5.0), "class": "verified_current_rule"},
        "min_roi_pct": {"value": s.get("minimum_roi_pct", 30.0), "class": "verified_current_rule"},
        "preferred_net_profit": {"value": s.get("qualified_net_profit", 11.0), "class": "operator_preference"},
        "priority_net_profit": {"value": s.get("priority_net_profit", 20.0), "class": "operator_preference"},
        "margin_min_pct": {"value": 20.0, "class": "proposed_default"},
        "source_freshness_max_minutes": {"value": s.get("source_price_max_age_minutes", 60),
                                         "class": "proposed_default"},
        "provider_freshness_max_minutes": {"value": s.get("market_snapshot_max_age_minutes", 60),
                                           "class": "proposed_default"},
        "purchase_authorization": {"value": "not_authorized_by_default", "class": "verified_current_rule"},
        "evidence_provenance_required": {"value": True, "class": "verified_current_rule"},
        "cosmetics_exception": {"value": "excluded_by_default; no exception in first runs",
                                "class": "operator_preference"},
        "excluded_classes": {"value": ["food", "grocery", "beverage", "supplement", "otc_drug",
                                       "nicotine", "cosmetics", "skincare", "haircare", "fragrance",
                                       "topical_beauty", "collectible", "fine_jewelry", "gift_card",
                                       "hazardous", "meltable", "fragile", "expiry_risk", "oversized",
                                       "restricted_gated", "regulated_medical_or_drug", "alcohol",
                                       "tobacco", "weapons", "animal_or_animal_products"],
                            "class": "verified_current_rule"},
        # unknowns / operator decisions
        "brightdata_field_availability": {"value": None,
                                          "class": "unknown_or_needs_operator_decision",
                                          "note": "validate on approved sample"},
        "brightdata_spend_cap": {"value": None, "class": "unknown_or_needs_operator_decision"},
        "provider_credit_cost": {"value": None, "class": "unknown_or_needs_operator_decision"},
    }
    return {
        "profile_version": PROFILE_VERSION,
        "generated_at": _now(),
        "defaults": {
            "offline_only": True,
            "bright_data_enabled": False,
            "bright_data_approved": False,
            "bright_data_live_calls": 0,
        },
        "rules": rules,
    }


def render_markdown(profile: Dict[str, Any]) -> str:
    lines = [f"# Costco Research Requirements Profile",
             "",
             f"- Version: {profile['profile_version']}",
             f"- Generated: {profile['generated_at']}",
             f"- Defaults: offline_only={profile['defaults']['offline_only']}, "
             f"bright_data_enabled={profile['defaults']['bright_data_enabled']}",
             "",
             "| Rule | Value | Class |",
             "|------|-------|-------|"]
    for k, v in profile["rules"].items():
        val = v["value"]
        lines.append(f"| {k} | {json.dumps(val)} | {v['class']} |")
    return "\n".join(lines)


def main(argv=None) -> int:
    import sys
    from .cli_common import print_json, print_network_confirmation
    profile = build_requirements_profile()
    print_network_confirmation(0)
    if argv and "--markdown" in argv:
        print(render_markdown(profile))
    else:
        print_json(profile)
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main(sys.argv[1:]))
