"""scanner_data.py — schema normalization + field-level provenance.

This is a NARROW normalization module. It does not call providers, does not
edit core engines, and does not write the primary cache. It turns raw
waterfall artifacts + existing engine outputs into a stable, namespaced,
provenance-rich ASIN record where every field carries:

    value, status, source, observed_at, confidence, verification_level,
    missing_reason

Source labels (from the Master Brain spec):
    live_dataforseo, live_rapidapi, cached, benchmark_reference,
    costco_discovery, derived_existing_engine, manual_verified, unavailable

Status vocabulary:
    VERIFIED, AVAILABLE_UNVERIFIED, MISSING, STALE, BENCHMARK_ONLY,
    NOT_APPLICABLE, BLOCKED_BY_POLICY

Missing data is never invented: it stays null with an explicit
missing_reason (or status MISSING / BLOCKED_BY_POLICY).
"""

import os
from datetime import datetime, timezone

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))

SOURCE_LIVE_DATAFORSEO = "live_dataforseo"
SOURCE_LIVE_RAPIDAPI = "live_rapidapi"
SOURCE_CACHED = "cached"
SOURCE_BENCHMARK_REFERENCE = "benchmark_reference"
SOURCE_COSTCO_DISCOVERY = "costco_discovery"
SOURCE_DERIVED_ENGINE = "derived_existing_engine"
SOURCE_MANUAL_VERIFIED = "manual_verified"
SOURCE_UNAVAILABLE = "unavailable"

STATUS_VERIFIED = "VERIFIED"
STATUS_AVAILABLE_UNVERIFIED = "AVAILABLE_UNVERIFIED"
STATUS_MISSING = "MISSING"
STATUS_STALE = "STALE"
STATUS_BENCHMARK_ONLY = "BENCHMARK_ONLY"
STATUS_NOT_APPLICABLE = "NOT_APPLICABLE"
STATUS_BLOCKED_BY_POLICY = "BLOCKED_BY_POLICY"

VALID_STATUSES = frozenset({
    STATUS_VERIFIED, STATUS_AVAILABLE_UNVERIFIED, STATUS_MISSING, STATUS_STALE,
    STATUS_BENCHMARK_ONLY, STATUS_NOT_APPLICABLE, STATUS_BLOCKED_BY_POLICY,
})


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def as_field(value=None, status=STATUS_MISSING, source=SOURCE_UNAVAILABLE,
             observed_at=None, confidence=None, verification_level=None,
             missing_reason=None):
    """Build a single provenance-bearing field record."""
    if status not in VALID_STATUSES:
        raise ValueError(f"invalid field status: {status!r}")
    return {
        "value": value,
        "status": status,
        "source": source,
        "observed_at": observed_at,
        "confidence": confidence,
        "verification_level": verification_level,
        "missing_reason": missing_reason,
    }


def normalize_asin_record(asin: str, extracted: dict, engines: dict,
                          policy: dict, observed_at: str = None) -> dict:
    """Compose a full namespaced ASIN record.

    extracted: raw artifact fields
        { title, brand, price, rating_value, reviews_count, seller_count,
          sellers, tier3_status, run_observed_at, image_url }
    engines: existing-engine outputs
        { economics, demand, costco } from fee_engine / demand_estimator /
        product_analysis respectively.
    """
    observed_at = observed_at or extracted.get("run_observed_at") or _utc_now()
    econ = engines.get("economics") or {}
    demand = engines.get("demand") or {}
    costco = engines.get("costco") or {}

    live_src = SOURCE_LIVE_DATAFORSEO
    price = extracted.get("price")
    title = extracted.get("title")
    rating = extracted.get("rating_value")
    reviews = extracted.get("reviews_count")
    seller_count = extracted.get("seller_count")

    # ---- Identity & matching ----
    identity = {
        "asin": as_field(asin, STATUS_VERIFIED, SOURCE_CACHED, observed_at,
                         verification_level="verified"),
        "amazon_title": as_field(
            title, STATUS_AVAILABLE_UNVERIFIED if title is not None else STATUS_MISSING,
            live_src, observed_at,
            missing_reason=None if title is not None else "DataForSEO asin task missing title"),
        "brand": as_field(
            extracted.get("brand"), STATUS_MISSING, live_src, observed_at,
            missing_reason="DataForSEO asin task does not return brand"),
        "product_image": as_field(
            extracted.get("image_url"), STATUS_MISSING, live_src, observed_at,
            missing_reason="image not carried from artifact"),
        "pack_count": as_field(
            None, STATUS_MISSING, SOURCE_UNAVAILABLE, observed_at,
            missing_reason="not derived (must not infer from title)"),
        "unit_count": as_field(
            None, STATUS_MISSING, SOURCE_UNAVAILABLE, observed_at,
            missing_reason="not derived (must not infer from title)"),
        "size_or_volume": as_field(
            None, STATUS_MISSING, SOURCE_UNAVAILABLE, observed_at,
            missing_reason="not derived (must not infer from title)"),
        "variation_match_status": as_field(
            "UNKNOWN", STATUS_MISSING, SOURCE_UNAVAILABLE, observed_at,
            missing_reason="variation/pack equivalence not established"),
        "match_confidence": as_field(
            costco.get("match_quality") if costco else None,
            STATUS_AVAILABLE_UNVERIFIED if costco else STATUS_MISSING,
            SOURCE_COSTCO_DISCOVERY if costco else SOURCE_UNAVAILABLE, observed_at,
            missing_reason=None if costco else "no Costco catalog match"),
        "title_match_status": as_field(
            "UNKNOWN", STATUS_MISSING, SOURCE_UNAVAILABLE, observed_at,
            missing_reason="title cross-file match not recomputed here"),
    }

    # ---- Amazon market data ----
    amazon_market = {
        "amazon_price": as_field(
            price, STATUS_AVAILABLE_UNVERIFIED if price is not None else STATUS_MISSING,
            live_src, observed_at,
            missing_reason=None if price is not None else "DataForSEO asin task missing price"),
        "buybox_price": as_field(
            None, STATUS_MISSING, live_src, observed_at,
            missing_reason="DataForSEO asin task does not return Buy Box price"),
        "buybox_seller_name": as_field(
            None, STATUS_MISSING, live_src, observed_at,
            missing_reason="seller roster did not expose Buy Box winner"),
        "buybox_winner_status": as_field(
            "Unavailable", STATUS_MISSING, live_src, observed_at,
            missing_reason="provider did not flag a Buy Box winner"),
        "buybox_fulfillment_channel": None,
        "buybox_fulfillment_channel_status": as_field(
            None, STATUS_MISSING, live_src, observed_at,
            missing_reason="fulfillment channel not exposed by provider"),
        "is_fba": as_field(
            None, STATUS_MISSING, live_src, observed_at,
            missing_reason="FBA flag not exposed by DataForSEO sellers task"),
        "is_fbm": as_field(
            None, STATUS_MISSING, live_src, observed_at,
            missing_reason="FBM flag not exposed by DataForSEO sellers task"),
        "seller_count": as_field(
            seller_count, STATUS_AVAILABLE_UNVERIFIED if seller_count is not None else STATUS_MISSING,
            live_src, observed_at,
            missing_reason=None if seller_count is not None else "sellers task missing"),
        "fba_seller_count": as_field(
            None, STATUS_MISSING, live_src, observed_at,
            missing_reason="per-fulfillment seller split not provided"),
        "fbm_seller_count": as_field(
            None, STATUS_MISSING, live_src, observed_at,
            missing_reason="per-fulfillment seller split not provided"),
        "rating": as_field(
            rating, STATUS_AVAILABLE_UNVERIFIED if rating is not None else STATUS_MISSING,
            live_src, observed_at,
            missing_reason=None if rating is not None else "rating not in artifact"),
        "review_count": as_field(
            reviews, STATUS_AVAILABLE_UNVERIFIED if reviews is not None else STATUS_MISSING,
            live_src, observed_at,
            missing_reason=None if reviews is not None else "review count not in artifact"),
        "category": as_field(
            None, STATUS_MISSING, live_src, observed_at,
            missing_reason="category not returned by DataForSEO asin task"),
        "bsr": as_field(
            None, STATUS_MISSING, live_src, observed_at,
            missing_reason="BSR not returned by DataForSEO asin task"),
        "bsr_category": as_field(
            None, STATUS_MISSING, live_src, observed_at,
            missing_reason="BSR category not returned by DataForSEO asin task"),
        "observed_at": as_field(observed_at, STATUS_VERIFIED, live_src, observed_at,
                                verification_level="verified"),
    }
    # (buybox_fulfillment_channel placeholder removed below)
    amazon_market.pop("buybox_fulfillment_channel", None)

    # ---- Costco / supply-side ----
    costco_matched = bool(costco and costco.get("costco_cost") is not None)
    costco_src = SOURCE_COSTCO_DISCOVERY if costco_matched else SOURCE_UNAVAILABLE
    costco_status = STATUS_AVAILABLE_UNVERIFIED if costco_matched else STATUS_MISSING
    costco = costco or {}
    costco_section = {
        "costco_product_id": as_field(
            costco.get("costco_item_id"), costco_status, costco_src, observed_at,
            missing_reason=None if costco_matched else "no Costco catalog match"),
        "costco_title": as_field(
            costco.get("item_name"), costco_status, costco_src, observed_at,
            missing_reason=None if costco_matched else "no Costco catalog match"),
        "costco_price": as_field(
            costco.get("costco_cost"), costco_status, costco_src, observed_at,
            missing_reason=None if costco_matched else "no Costco catalog match"),
        "costco_price_type": as_field(
            "discovery_only" if costco_matched else None,
            costco_status, costco_src, observed_at,
            missing_reason="Costco retail/online pricing is discovery-only"),
        "costco_pack_count": as_field(
            costco.get("pack_count"), costco_status, costco_src, observed_at,
            missing_reason=None if costco_matched else "no Costco catalog match"),
        "costco_unit_cost": as_field(
            costco.get("unit_cost"), costco_status, costco_src, observed_at,
            missing_reason=None if costco_matched else "no Costco catalog match"),
        "costco_availability": as_field(
            "discovery_only" if costco_matched else None,
            costco_status, costco_src, observed_at),
        "costco_observed_at": as_field(
            costco.get("last_seen_at"), costco_status, costco_src, observed_at),
        "costco_match_status": as_field(
            costco.get("match_quality") if costco else "no_match",
            costco_status, costco_src, observed_at,
            missing_reason=None if costco_matched else "no Costco catalog match"),
        "costco_match_confidence": as_field(
            costco.get("match_confidence") if costco else None,
            costco_status, costco_src, observed_at),
        # Retail receipts / discovery data are NEVER invoice-backed.
        "source_invoice_status": as_field(
            "discovery_only", STATUS_AVAILABLE_UNVERIFIED, costco_src, observed_at,
            missing_reason="discovery-only; not invoice-confirmed"),
        "supplier_legitimacy_status": as_field(
            "discovery_only" if costco_matched else "unverified",
            costco_status, costco_src, observed_at,
            missing_reason="requires explicit invoice review for purchase authorization"),
    }

    # ---- Fee / profit / ROI ----
    fba_fee = econ.get("fba_fee")
    referral_fee = econ.get("referral_fee")
    requires_verified_fee = bool(policy.get("require_verified_fee_inputs", True))
    fee_ok = (fba_fee is not None) and (referral_fee is not None)
    fee_status = (STATUS_VERIFIED if (fee_ok and not requires_verified_fee)
                  else STATUS_AVAILABLE_UNVERIFIED if fee_ok
                  else STATUS_MISSING)
    if fba_fee is None:
        fee_verification_status = "needs_fee_verification"
    elif requires_verified_fee:
        fee_verification_status = "needs_fee_verification"
    else:
        fee_verification_status = "verified"

    net_profit = econ.get("net_profit")
    roi_pct = econ.get("roi_pct")
    cogs = econ.get("costco_cogs")
    unit = econ  # fee_engine returns unit costs inside economics dict
    prep = unit.get("prep_cost_per_unit")
    inbound = unit.get("inbound_cost_per_unit")
    landed_cogs = None
    if isinstance(cogs, (int, float)) and isinstance(prep, (int, float)) and isinstance(inbound, (int, float)):
        landed_cogs = round(cogs + prep + inbound, 2)

    price_spread = None
    if isinstance(price, (int, float)) and isinstance(costco.get("costco_cost"), (int, float)):
        price_spread = round(price - float(costco.get("costco_cost")), 2)

    net_margin_pct = None
    if isinstance(net_profit, (int, float)) and isinstance(price, (int, float)) and price > 0:
        net_margin_pct = round(net_profit / price * 100.0, 2)

    fees_economics = {
        "referral_fee": as_field(
            referral_fee, STATUS_AVAILABLE_UNVERIFIED if referral_fee is not None else STATUS_MISSING,
            SOURCE_DERIVED_ENGINE, observed_at,
            missing_reason=None if referral_fee is not None else "referral fee not computed"),
        "fba_fee": as_field(
            fba_fee, fee_status if fba_fee is not None else STATUS_MISSING,
            SOURCE_DERIVED_ENGINE, observed_at,
            missing_reason=None if fba_fee is not None else "FBA fee unavailable (no weight/dimensions)"),
        "amazon_fees_total": as_field(
            (round(referral_fee + fba_fee, 2) if fee_ok else None),
            STATUS_AVAILABLE_UNVERIFIED if fee_ok else STATUS_MISSING,
            SOURCE_DERIVED_ENGINE, observed_at,
            missing_reason=None if fee_ok else "fee inputs incomplete"),
        "amazon_payout": as_field(
            (round(price - (referral_fee + fba_fee), 2) if fee_ok and isinstance(price, (int, float)) else None),
            STATUS_AVAILABLE_UNVERIFIED if fee_ok else STATUS_MISSING,
            SOURCE_DERIVED_ENGINE, observed_at,
            missing_reason=None if fee_ok else "fee inputs incomplete"),
        "prep_cost": as_field(
            prep, STATUS_AVAILABLE_UNVERIFIED if prep is not None else STATUS_MISSING,
            SOURCE_DERIVED_ENGINE, observed_at),
        "inbound_shipping_cost": as_field(
            inbound, STATUS_AVAILABLE_UNVERIFIED if inbound is not None else STATUS_MISSING,
            SOURCE_DERIVED_ENGINE, observed_at),
        "landed_cogs": as_field(
            landed_cogs, STATUS_AVAILABLE_UNVERIFIED if landed_cogs is not None else STATUS_MISSING,
            SOURCE_DERIVED_ENGINE, observed_at,
            missing_reason=None if landed_cogs is not None else "landed COGS incomplete"),
        "price_spread": as_field(
            price_spread, STATUS_AVAILABLE_UNVERIFIED if price_spread is not None else STATUS_MISSING,
            SOURCE_DERIVED_ENGINE, observed_at,
            missing_reason=None if price_spread is not None else "matched Amazon+Costco price required"),
        "net_profit": as_field(
            net_profit, STATUS_AVAILABLE_UNVERIFIED if net_profit is not None else STATUS_MISSING,
            SOURCE_DERIVED_ENGINE, observed_at,
            missing_reason=None if net_profit is not None else "economics incomplete (fee/COGS gap)"),
        "net_margin_pct": as_field(
            net_margin_pct, STATUS_AVAILABLE_UNVERIFIED if net_margin_pct is not None else STATUS_MISSING,
            SOURCE_DERIVED_ENGINE, observed_at,
            missing_reason=None if net_margin_pct is not None else "net profit incomplete"),
        "roi_pct": as_field(
            roi_pct, STATUS_AVAILABLE_UNVERIFIED if roi_pct is not None else STATUS_MISSING,
            SOURCE_DERIVED_ENGINE, observed_at,
            missing_reason=None if roi_pct is not None else "ROI requires verified landed COGS"),
        "economics_status": as_field(
            econ.get("economics_status") or ("needs_fee_verification" if fba_fee is None else "unknown"),
            STATUS_AVAILABLE_UNVERIFIED, SOURCE_DERIVED_ENGINE, observed_at),
        "fee_verification_status": as_field(
            fee_verification_status, STATUS_AVAILABLE_UNVERIFIED, SOURCE_DERIVED_ENGINE, observed_at),
    }

    # ---- Demand / velocity ----
    demand_section = {
        "bsr": as_field(
            None, STATUS_MISSING, live_src, observed_at,
            missing_reason="BSR not available (Tier-2 provider unsubscribed)"),
        "bsr_category": as_field(
            None, STATUS_MISSING, live_src, observed_at,
            missing_reason="BSR category not available"),
        "estimated_monthly_sales": as_field(
            demand.get("estimated_monthly_sales") if isinstance(demand, dict) else None,
            STATUS_MISSING, SOURCE_DERIVED_ENGINE, observed_at,
            missing_reason="BSR required for demand estimate; BSR unavailable"),
        "velocity_status": as_field(
            "needs_verified_bsr", STATUS_MISSING, SOURCE_DERIVED_ENGINE, observed_at,
            missing_reason="no verified BSR"),
        "demand_model_source": as_field(
            demand.get("sales_estimation_source") if isinstance(demand, dict) else None,
            STATUS_AVAILABLE_UNVERIFIED if demand else STATUS_MISSING,
            SOURCE_DERIVED_ENGINE, observed_at),
        "days_of_cover": as_field(
            None, STATUS_NOT_APPLICABLE, SOURCE_UNAVAILABLE, observed_at,
            missing_reason="no inventory inputs"),
        "reorder_signal": as_field(
            None, STATUS_NOT_APPLICABLE, SOURCE_UNAVAILABLE, observed_at,
            missing_reason="requires valid demand + inventory inputs"),
    }

    record = {
        "asin": asin,
        "enrichment_meta": {
            "generated_at": _utc_now(),
            "source": "brain_orchestrator",
            "policy": "config/brain_policy.json",
        },
        "identity": identity,
        "amazon_market": amazon_market,
        "costco": costco_section,
        "fees_economics": fees_economics,
        "demand": demand_section,
    }
    return record


FIELD_SECTIONS = ("identity", "amazon_market", "costco",
                   "fees_economics", "demand")


def completeness_matrix(record: dict) -> dict:
    """Flatten every field to its status for the completeness matrix."""
    matrix = {}
    for section in FIELD_SECTIONS:
        fields = record.get(section, {})
        if not isinstance(fields, dict):
            continue
        for fname, fobj in fields.items():
            if isinstance(fobj, dict) and "status" in fobj:
                matrix[f"{section}.{fname}"] = fobj["status"]
    return matrix


def data_completeness_pct(record: dict) -> float:
    """Percent of required fields that are VERIFIED or AVAILABLE_UNVERIFIED."""
    matrix = completeness_matrix(record)
    if not matrix:
        return 0.0
    filled = sum(1 for s in matrix.values()
                 if s in (STATUS_VERIFIED, STATUS_AVAILABLE_UNVERIFIED))
    return round(100.0 * filled / len(matrix), 1)
