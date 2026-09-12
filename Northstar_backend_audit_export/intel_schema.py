"""Offline schema validation for the proposed normalized per-ASIN market
snapshot (plan: docs/asin-market-data-completeness-plan.md, Phase 2).

PURE VALIDATION ONLY — no network, no file IO, no writes, no imports of
provider clients. This module is planning scaffolding: nothing in the
server imports it yet. It defines the field-level contract the shortlist
workflow must satisfy, so fixtures and dry-run planning can be tested
before any live provider decision is approved.

Rules enforced here (honesty invariants):
  - Unknown numbers are null (None); 0 is never a substitute for unknown
    in market/economic fields (explicitly configured zero costs such as a
    0.00 prep cost are legitimate and allowed).
  - Raw provider responses and normalized facts are separate top-level
    sections.
  - Observed market facts, derived economics, and estimates are separate
    sections.
  - Every populated value field carries provenance (source, fetched_at).
  - seller-offer coverage metadata is always present and honest
    (available | partial | unknown coverage).
"""

import re
from typing import Any, Dict, List

SCHEMA_VERSION = 1

ASIN_PATTERN = re.compile(r"^[A-Za-z0-9]{10}$")

COST_STATUSES = (
    "costco_online_discovery",
    "business_center_invoice_confirmed",
    "distributor_invoice_confirmed",
    "manual_assumption",
    "unavailable",
)

FEE_STATUSES = ("verified_seller_central", "estimated", "unavailable")

DEMAND_STATUSES = ("provider_verified", "internal_estimate", "unavailable")

COVERAGE_STATUSES = ("full", "partial", "unknown")

SELLER_STATUSES = ("available", "partial", "provider_error", "unavailable")

REQUIRED_TOP_LEVEL = ("schema_version", "asin", "ingested_at", "sources", "facts")

# Numeric fields where 0 can never mean "unknown" or "none" — a missing
# value MUST be null. Configured zero costs (prep/inbound/packaging/
# reserve) stay outside this set because 0.00 is a legitimate explicit
# value there.
ZERO_FORBIDDEN = {
    "amazon_price",
    "costco_cost",
    "paid_cost_invoice",
    "referral_fee",
    "fba_fee",
    "net_profit",
    "roi_pct",
    "estimated_monthly_sales",
}

# Keys that describe provenance/metadata/status themselves and therefore
# need no separate provenance entry.
PROVENANCE_EXEMPT_SUBSTRINGS = (
    "status",
    "confidence",
    "method",
    "match",
    "source",
    "available",
    "_at",
    "count",
    "coverage",
    "reason",
    "is_",
    "fulfillment",
    "condition",
    "note",
    "pack_size",
)


def validate_snapshot(snapshot: Dict[str, Any]) -> List[str]:
    """Return a list of contract violations ([] = valid).

    Nulls are allowed wherever a value is unknown; forbidden zeros are
    rejected; populated value fields must carry provenance.
    """
    errors: List[str] = []
    if not isinstance(snapshot, dict):
        return ["snapshot must be a dict"]

    for key in REQUIRED_TOP_LEVEL:
        if key not in snapshot:
            errors.append(f"missing top-level key: {key}")

    if snapshot.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"schema_version must be {SCHEMA_VERSION}")

    asin = snapshot.get("asin")
    if not isinstance(asin, str) or not ASIN_PATTERN.fullmatch(asin):
        errors.append("asin must be a 10-character alphanumeric string")

    ingested_at = snapshot.get("ingested_at")
    if not isinstance(ingested_at, str) or not ingested_at:
        errors.append("ingested_at must be a non-empty ISO timestamp")

    sources = snapshot.get("sources")
    if not isinstance(sources, dict):
        errors.append("sources must be a dict of raw provider responses")
    else:
        for source_name, raw in sources.items():
            if not isinstance(raw, dict):
                errors.append(f"sources.{source_name} must be a dict")

    facts = snapshot.get("facts")
    if not isinstance(facts, dict):
        errors.append("facts must be a dict")
        return errors

    _validate_fact_section(errors, facts, "identity")
    _validate_fact_section(errors, facts, "cost")
    _validate_fact_section(errors, facts, "fees")
    _validate_fact_section(errors, facts, "demand")

    market = facts.get("market")
    if not isinstance(market, dict):
        errors.append("facts.market must be a dict")
    else:
        _validate_market(errors, market, facts.get("provenance") or {})

    economics = facts.get("economics")
    if not isinstance(economics, dict):
        errors.append("facts.economics must be a dict")
    else:
        _validate_economics(errors, economics)

    provenance = facts.get("provenance")
    if not isinstance(provenance, dict):
        errors.append("facts.provenance must be a dict")

    return errors


def _is_provenance_exempt(field: str) -> bool:
    return any(sub in field for sub in PROVENANCE_EXEMPT_SUBSTRINGS)


def _validate_fact_section(
    errors: List[str],
    facts: Dict[str, Any],
    name: str,
) -> None:
    section = facts.get(name)
    if not isinstance(section, dict):
        errors.append(f"facts.{name} must be a dict")
        return
    provenance = facts.get("provenance") or {}
    for field, value in section.items():
        if value == 0 and field in ZERO_FORBIDDEN:
            errors.append(f"facts.{name}.{field} is 0; unknown numbers must be null (None)")
        if value is not None and not _is_provenance_exempt(field):
            if f"{name}.{field}" not in provenance:
                errors.append(f"facts.{name}.{field} has no provenance entry")


def _validate_market(
    errors: List[str],
    market: Dict[str, Any],
    provenance: Dict[str, Any],
) -> None:
    if market.get("amazon_price") == 0:
        errors.append("facts.market.amazon_price is 0; unknown numbers must be null (None)")
    if market.get("amazon_price") is not None and "market.amazon_price" not in provenance:
        errors.append("facts.market.amazon_price has no provenance entry")

    coverage = market.get("coverage")
    if not isinstance(coverage, dict):
        errors.append("facts.market.coverage must be a dict")
    else:
        if coverage.get("offer_list_available") not in (True, False):
            errors.append("facts.market.coverage.offer_list_available must be a bool")
        status = coverage.get("offers_complete_status")
        if status not in COVERAGE_STATUSES:
            errors.append(
                f"facts.market.coverage.offers_complete_status must be one of {COVERAGE_STATUSES}"
            )
        if status != "full" and not coverage.get("coverage_reason"):
            errors.append("facts.market.coverage.coverage_reason required unless coverage is full")

    buy_box = market.get("buy_box")
    if not isinstance(buy_box, dict):
        errors.append("facts.market.buy_box must be a dict")
    elif buy_box.get("available") is True:
        if buy_box.get("price") is None:
            errors.append("buy_box.available is true but price is null")
        if not buy_box.get("source"):
            errors.append("buy_box.source required when available")
        if buy_box.get("price") == 0:
            errors.append("buy_box.price is 0; unknown numbers must be null (None)")

    offers = market.get("offers")
    if not isinstance(offers, list):
        errors.append("facts.market.offers must be a list")
        return
    for idx, offer in enumerate(offers):
        if not isinstance(offer, dict):
            errors.append(f"facts.market.offers[{idx}] must be a dict")
            continue
        if offer.get("price") == 0:
            errors.append(f"facts.market.offers[{idx}].price is 0; unknown must be null")
        if "fulfillment" in offer and offer["fulfillment"] not in (
            None,
            "FBA",
            "FBM",
            "AMAZON",
            "Unknown",
        ):
            errors.append(
                f"facts.market.offers[{idx}].fulfillment invalid: {offer['fulfillment']!r}"
            )
        if "is_buy_box_winner" in offer and not isinstance(offer["is_buy_box_winner"], bool):
            errors.append(f"facts.market.offers[{idx}].is_buy_box_winner must be a bool or absent")


def _validate_economics(errors: List[str], economics: Dict[str, Any]) -> None:
    for field in ("net_profit", "roi_pct"):
        if economics.get(field) == 0:
            errors.append(f"facts.economics.{field} is 0; unknown must be null (None)")
    confidence = economics.get("economics_confidence")
    if confidence not in (None, "estimated", "provisional", "unavailable"):
        errors.append("facts.economics.economics_confidence invalid")
    if economics.get("net_profit") is not None and economics.get("roi_pct") is None:
        errors.append("net_profit present without roi_pct is inconsistent for the plan contract")


def snapshot_from_fixture(fixture: Dict[str, Any]) -> Dict[str, Any]:
    """Copy a fixture and stamp schema_version/asin placeholders if absent."""
    import copy

    snap = copy.deepcopy(fixture)
    snap.setdefault("schema_version", SCHEMA_VERSION)
    snap.setdefault("asin", "B0PLACEH01")
    return snap


def fixture_minimal() -> Dict[str, Any]:
    """A valid all-null placeholder snapshot (never invented real data)."""
    return {
        "schema_version": SCHEMA_VERSION,
        "asin": "B0PLACEH01",
        "ingested_at": "2026-08-17T12:00:00+00:00",
        "sources": {},
        "facts": {
            "identity": {
                "name": None,
                "pack_match": None,
                "upc_or_ean": None,
                "net_weight_lbs": None,
            },
            "cost": {
                "costco_cost": None,
                "cost_status": "unavailable",
                "source": None,
                "paid_cost_invoice": None,
            },
            "fees": {
                "referral_fee": None,
                "referral_fee_confidence": "unavailable",
                "fba_fee": None,
                "fba_fee_status": "unavailable",
                "prep_cost_per_unit": None,
                "inbound_cost_per_unit": None,
                "packaging_cost_per_unit": None,
                "return_reserve_rate": None,
            },
            "demand": {
                "estimated_monthly_sales": None,
                "sales_estimation_method": "unknown",
                "sales_estimation_confidence": "unknown",
            },
            "market": {
                "amazon_price": None,
                "buy_box": {
                    "available": False,
                    "price": None,
                    "seller_name": None,
                    "seller_id": None,
                    "fulfillment": None,
                    "source": None,
                    "observed_at": None,
                },
                "seller_counts": {
                    "total_observed": None,
                    "fba_observed": None,
                    "fbm_observed": None,
                    "amazon_observed": None,
                    "claimed_total": None,
                },
                "coverage": {
                    "offer_list_available": False,
                    "offers_complete_status": "unknown",
                    "coverage_reason": "no provider roster requested",
                },
                "offers": [],
            },
            "economics": {
                "net_profit": None,
                "roi_pct": None,
                "economics_confidence": "unavailable",
                "economics_status": "missing_market_or_cost_inputs",
            },
            "provenance": {},
        },
    }