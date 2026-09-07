from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Any, Dict, List, Optional
import os
import json
import re
from datetime import datetime, timezone

from pricing import compute_profit, estimate_fba_fee, estimate_financial_profile
from product_analysis import analyze_kirkland_products
import amazon_search
import costco_client
import costco_api_client
import offer_enrichment
import live_gate
import completeness_score
from canopy_client import get_canopy_product


class ScanRequest(BaseModel):
    asins: List[str] = []
    source_profile: str = "dfw-costco"
    min_profit: float = 11.0
    min_velocity: int = 2000


class ProductResult(BaseModel):
    name: str
    asin: str
    monthly_sales: int
    costco_cost: float
    amazon_price: float
    weight_lbs: float
    net_profit: float
    roi_pct: float
    logistics_risk: str
    verdict: str
    projected_net_profit: Optional[float] = None
    amazon_fees_total: Optional[float] = None
    amazon_payout_before_inventory_costs: Optional[float] = None
    landed_cost: Optional[float] = None
    projected_roi_pct: Optional[float] = None
    financial_status: Optional[str] = None
    financial_data_gaps: List[str] = []


class ScanResponse(BaseModel):
    products: List[ProductResult]


app = FastAPI(
    title="Northstar Kirkland Scan API",
    description="Backend API for the Northstar Arbitrage OS Kirkland data console.",
    version="0.4.0",
)

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/", include_in_schema=False)
def serve_scout():
    return FileResponse(STATIC_DIR / "index.html")


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


KIRKLAND_CATALOG = [
    {
        "name": "Kirkland Signature Organic K-Cups Variety Pack (120ct)",
        "asin": "B0CS6Z9SRX",
        "monthly_sales": 1500,
        "costco_cost": 15.99,
        "amazon_price": 48.87,
        "weight_lbs": 3.5,
    },
    {
        "name": "Kirkland Minoxidil Foam 6-Month Supply (6ct)",
        "asin": "B01GRGIC9G",
        "monthly_sales": 900,
        "costco_cost": 34.00,
        "amazon_price": 64.22,
        "weight_lbs": 2.0,
    },
    {
        "name": "Kirkland Signature House Decaf K-Cups (120ct)",
        "asin": "B0734BGSKY",
        "monthly_sales": 700,
        "costco_cost": 15.99,
        "amazon_price": 36.37,
        "weight_lbs": 3.5,
    },
    {
        "name": "Kirkland Signature Milk Chocolate Roasted Almonds (2x3lb)",
        "asin": "B075QPSSHD",
        "monthly_sales": 500,
        "costco_cost": 18.99,
        "amazon_price": 39.99,
        "weight_lbs": 6.0,
    },
    {
        "name": "Kirkland Signature Extra Strength Vitamin D3 (2pk 600ct)",
        "asin": "B005D1K7CW",
        "monthly_sales": 400,
        "costco_cost": 13.99,
        "amazon_price": 25.02,
        "weight_lbs": 1.3,
    },
    {
        "name": "Kirkland Signature Whole Almonds (3lb)",
        "asin": "B07BFHBWP2",
        "monthly_sales": 600,
        "costco_cost": 12.99,
        "amazon_price": 24.99,
        "weight_lbs": 3.0,
    },
    {
        "name": "Kirkland Signature Almond Butter",
        "asin": "B01N9SOK2Y",
        "monthly_sales": 350,
        "costco_cost": 11.49,
        "amazon_price": 21.99,
        "weight_lbs": 2.0,
    },
    {
        "name": "Kirkland Signature Vitamin D3 (600 softgels)",
        "asin": "B00EXPV502",
        "monthly_sales": 300,
        "costco_cost": 9.49,
        "amazon_price": 14.99,
        "weight_lbs": 0.9,
    },
]


def build_result(item: dict, min_profit: float, min_velocity: int) -> ProductResult:
    fba_fee = estimate_fba_fee(item["weight_lbs"])
    net_profit, roi_pct = compute_profit(
        amazon_price=item["amazon_price"],
        costco_cost=item["costco_cost"],
        fba_fee=fba_fee,
    )

    if item["weight_lbs"] >= 15:
        logistics_risk = "High bulk, heavy truck/pallet load"
    elif item["weight_lbs"] >= 7:
        logistics_risk = "Moderate bulk, watch truck space"
    else:
        logistics_risk = "Low bulk, good truck density"

    if net_profit >= min_profit and item["monthly_sales"] >= min_velocity:
        verdict = "Pass"
    elif net_profit > 0:
        verdict = "Hold"
    else:
        verdict = "Reject"

    profile = estimate_financial_profile(
        amazon_price=item["amazon_price"],
        weight_lbs=item["weight_lbs"],
        costco_cost=item["costco_cost"],
    )

    return ProductResult(
        name=item["name"],
        asin=item["asin"],
        monthly_sales=item["monthly_sales"],
        costco_cost=item["costco_cost"],
        amazon_price=item["amazon_price"],
        weight_lbs=item["weight_lbs"],
        net_profit=round(net_profit, 2),
        roi_pct=round(roi_pct, 1),
        logistics_risk=logistics_risk,
        verdict=verdict,
        projected_net_profit=profile["projected_net_profit"],
        amazon_fees_total=profile["amazon_fees_total"],
        amazon_payout_before_inventory_costs=profile[
            "amazon_payout_before_inventory_costs"
        ],
        landed_cost=profile["landed_cost"],
        projected_roi_pct=profile["projected_roi_pct"],
        financial_status=profile["financial_status"],
        financial_data_gaps=profile["financial_data_gaps"],
    )


@app.post("/api/kirkland/scan", response_model=ScanResponse)
def scan_kirkland(req: ScanRequest):
    if req.asins:
        wanted = {a.upper() for a in req.asins}
        items = [i for i in KIRKLAND_CATALOG if i["asin"].upper() in wanted]
    else:
        items = KIRKLAND_CATALOG

    results = [build_result(i, req.min_profit, req.min_velocity) for i in items]
    results = [r for r in results if r.verdict == "Pass"]
    results.sort(key=lambda r: -r.net_profit)

    return ScanResponse(products=results)


@app.get("/api/kirkland/live")
def get_kirkland_live():
    """Scanner analysis. Read-only: with SCANNER_LIVE_ALLOWED unset the
    analysis is cache-only (zero provider calls); live data only when the
    operator explicitly enabled the gate and runs an explicit refresh."""
    return analyze_kirkland_products()


@app.post("/api/kirkland/refresh")
def refresh_kirkland_scan():
    """Explicit live refresh — the ONLY route that may trigger live
    provider searches, and only when SCANNER_LIVE_ALLOWED is an explicit
    opt-in. Without the gate this returns 403 and never touches a
    provider. Never called by the UI on page load (the UI reads
    GET /api/kirkland/scanner, which is cache-only by default)."""
    if not live_gate.live_enabled():
        raise HTTPException(
            status_code=403,
            detail=live_gate.live_disabled_note(),
        )
    analysis = analyze_kirkland_products()
    return {
        "status": "ok",
        "live_allowed": True,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "candidates_returned": len(analysis.get("all_results") or []),
    }


SCANNER_ALLOWED_KEYS = (
    "name",
    "asin",
    "product_url",
    "amazon_price",
    "costco_cost",
    "lowest_price",
    "highest_price",
    "fba_fee",
    "net_profit",
    "roi_pct",
    "profit_tier",
    "total_sellers",
    "fba_sellers",
    "monthly_sales_estimate",
    "monthly_sales_estimated",
    "sales_rank",
    "offer_data_provider",
    "enrichment_status",
    "enriched_at",
    "verdict",
    # Versioned fee-engine economics (computed before the UI renders).
    "amazon_category",
    "browse_node_id",
    "category_resolution_source",
    "category_resolution_confidence",
    "category_resolution_note",
    "costco_cogs",
    "costco_cost_basis",
    "pack_match",
    "cost_match_reason",
    "cost_source",
    "cost_is_purchase_authorized",
    "referral_fee",
    "referral_fee_rate",
    "referral_fee_category",
    "referral_fee_confidence",
    "referral_fee_rule",
    "referral_fee_tier",
    "referral_fee_note",
    "fba_base_fee",
    "fba_fuel_logistics_surcharge",
    "fba_size_tier",
    "fba_fee_status",
    "fba_fee_confidence",
    "fba_fee_rule",
    "fba_fee_note",
    "fba_weight_basis_lbs",
    "inbound_cost_per_unit",
    "prep_cost_per_unit",
    "packaging_cost_per_unit",
    "return_reserve_rate",
    "economics_confidence",
    "economics_status",
    "economics_note",
    # Opportunity analytics (cache-only, read-only; display + exports only).
    "match_evidence",
    "verification_tasks",
    "primary_verification_task",
    "match_readiness",
    "data_completeness_score",
    "opportunity_readiness",
    "recommended_next_step",
    "opportunity_score",
    "opportunity_score_reasons",
    "freshness_label",
    "freshness_basis",
    "freshness_as_of",
    # Local market snapshot merge (read-only, cache-only mode only).
    "snapshot_status",
    "snapshot_source",
    "snapshot_fetched_at",
    "snapshot_observed_at",
    "snapshot_freshness",
    "snapshot_offers_complete",
    "snapshot_offers_returned",
    "snapshot_data_gaps",
    "snapshot_fbm_sellers",
    "snapshot_amazon_sellers",
    "snapshot_buy_box_available",
    "snapshot_buy_box_price",
    "snapshot_buy_box_fulfillment",
    "snapshot_buy_box_seller",
    # Offline demand model (Phase 3, read-only, cache-only).
    "estimated_monthly_sales",
    "sales_estimate_low",
    "sales_estimate_high",
    "sales_estimation_method",
    "sales_estimation_source",
    "sales_estimation_confidence",
    "bsr",
    "bsr_category",
    "bsr_observed_at",
    "calibration_model_name",
    "calibration_model_version",
    # Observed seller competition (Phase 3, local snapshots only).
    "observed_total_sellers",
    "observed_fba_sellers",
    "observed_fbm_sellers",
    "observed_amazon_sellers",
    "claimed_offer_count",
    "offers_returned",
    "offers_complete",
    "offer_roster_reason",
    "competition_data_gaps",
    "observed_buy_box_available",
    "observed_buy_box_price",
    "observed_buy_box_shipping",
    "observed_buy_box_landed_price",
    "observed_buy_box_seller",
    "observed_buy_box_fulfillment",
    "observed_buy_box_condition",
    "lowest_returned_offer_price",
    "lowest_returned_landed_price",
    "highest_returned_landed_price",
    "returned_offer_price_spread",
    "returned_offer_landed_spread",
    "prime_offer_count",
    "fulfilled_by_amazon_offer_count",
    "estimated_units_per_observed_fba_seller",
    "estimated_units_per_observed_fbm_seller",
    "estimated_units_per_observed_seller",
    "seller_share_confidence",
    "seller_share_basis",
    "offer_competition_note",
    "seller_share_note",
    # Portfolio planning (Phase 3, read-only).
    "identity_completeness",
    "cost_completeness",
    "economics_completeness",
    "demand_completeness",
    "competition_completeness",
    "freshness_completeness",
    "total_completeness_score",
    "portfolio_readiness",
    "portfolio_next_step",
    "portfolio_category",
    "risk_flags",
    "portfolio_score_reasons",
    "estimated_monthly_revenue",
    "monthly_revenue_basis",
    "monthly_revenue_confidence",
    "estimated_monthly_profit_pool",
    "monthly_profit_pool_basis",
    "monthly_profit_pool_confidence",
    "estimated_fba_seller_monthly_profit",
    "estimated_fbm_seller_monthly_profit",
    "estimated_observed_seller_monthly_profit",
    "seller_profit_basis",
    "monthly_pool_note",
    # ASIN completeness contract (null-first, additive only). Computed by
    # completeness_score.compute_scanner_completeness from the full record.
    "completeness",
)


def _is_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _clean_scanner_product(record: dict) -> dict:
    return {key: record.get(key) for key in SCANNER_ALLOWED_KEYS}


def _economics_group(product: dict) -> int:
    """Scout spec ordering: Estimated first, Provisional second,
    Unavailable last (0/1/2). Unknown/missing confidence is treated as
    Unavailable so it never outranks a real estimate."""
    confidence = product.get("economics_confidence")
    if confidence == "estimated":
        return 0
    if confidence == "provisional":
        return 1
    return 2


def _scanner_sort_key(product: dict) -> tuple:
    """Rank candidates per the Scout spec.

    Grouped by economics tier (Estimated, then Provisional, then
    Unavailable), then: 1. net profit desc, 2. ROI desc, 3. seller count
    asc (less competition), 4. FBA seller count asc, 5. monthly-sales/
    demand desc, 6. Buy Box price stability (narrower high-low spread)
    asc. Nulls always sort last within their group.
    """

    def pair_desc(value):
        if _is_number(value):
            return (0, -float(value))
        return (1, 0.0)

    def pair_asc(value):
        if _is_number(value):
            return (0, float(value))
        return (1, 0.0)

    def price_stability(product):
        low = product.get("lowest_price")
        high = product.get("highest_price")
        if _is_number(low) and _is_number(high) and high >= low:
            return high - low
        return None

    return (
        _economics_group(product),
        *pair_desc(product.get("net_profit")),
        *pair_desc(product.get("roi_pct")),
        *pair_asc(product.get("total_sellers")),
        *pair_asc(product.get("fba_sellers")),
        *pair_desc(product.get("monthly_sales_estimate")),
        *pair_asc(price_stability(product)),
        str(product.get("name") or "").lower(),
        str(product.get("asin") or "").lower(),
    )


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api/kirkland/scanner")
def get_kirkland_scanner():
    """Clean, allowlisted scanner response for the Product Scout UI.

    Products carry only the Scout data contract keys. Sorting is
    net_profit desc, roi_pct desc, monthly_sales_estimate desc with
    nulls last. Status is honest about empty versus unavailable data.
    """
    analysis = analyze_kirkland_products()
    products = []
    for r in (analysis["all_results"] or []):
        p = _clean_scanner_product(r)
        # Null-first completeness contract: score null when nothing is
        # computable; genuine zero only from evaluated evidence; category
        # scores null where category inputs are absent.
        p["completeness"] = completeness_score.compute_scanner_completeness(r)
        products.append(p)
    products.sort(key=_scanner_sort_key)

    if not products:
        status = (
            "upstream_unavailable"
            if amazon_search.LAST_SEARCH_ERROR
            else "no_candidates"
        )
    else:
        status = "ok"
    error = str(amazon_search.LAST_SEARCH_ERROR or "").lower()
    upstream_hint = None
    if status == "upstream_unavailable" and (
        "402" in error or "insufficient credits" in error
    ):
        billing_url = amazon_search.provider_billing_url()
        upstream_hint = (
            f"{amazon_search.provider_label()} is out of credits. "
            "Top up at " + (billing_url or "the provider dashboard") + " and try again."
        )
    elif status == "upstream_unavailable" and (
        "502" in error or "target_unreachable" in error
    ):
        upstream_hint = (
            f"Amazon is temporarily blocking searches for {amazon_search.provider_label()}. "
            "You were not charged — wait ~10 seconds and retry."
        )
    elif status == "upstream_unavailable" and amazon_search.active_search_source() == "BRIGHTDATA":
        upstream_hint = (
            "Bright Data search failed (" + str(amazon_search.LAST_SEARCH_ERROR) + "). "
            "Switch SCANNER_SEARCH_SOURCE=CHOCODATA or SCAVIO in .env, "
            "or check the Bright Data dashboard at https://www.brightdata.com."
        )

    cache_meta = amazon_search.cache_meta()
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "summary": {
            "candidates_returned": len(products),
            "tier_found": analysis.get("tier_found"),
            "costco_catalog": costco_client.catalog_state(),
            "costco_discovery": costco_api_client.last_run_status(),
            "search_source": amazon_search.active_search_source(),
            "enrichment_source": offer_enrichment._enrichment_mode(),
            # Backward-compatible diagnostics: cache_only mode reads only
            # the local candidate cache + Costco CSV — zero outbound calls.
            # Missing/corrupt/stale cache is honest (cache_status) and
            # never triggers a live fallback. status stays within the
            # permitted ok|no_candidates|upstream_unavailable set.
            "scanner_mode": (
                "cache_only"
                if offer_enrichment._enrichment_mode() == "OFF"
                else "live"
            ),
            "live_allowed": live_gate.live_enabled(),
            "cache_status": cache_meta.get("cache_status"),
            "cache_fetched_at": cache_meta.get("cache_fetched_at"),
            "cache_source": cache_meta.get("cache_source"),
            "upstream_hint": upstream_hint,
            # Null-first completeness contract version (additive).
            "completeness_contract_version": 1,
        },
        "products": products,
    }


# ---------------------------------------------------------------------------
# Kirkland Discovery API — high-velocity product discovery with BSR-based
# sales estimation, category filtering, and Costco cross-reference.
# ---------------------------------------------------------------------------

import kirkland_discovery as kd

DISCOVERY_CACHE = os.path.join(BASE_DIR, "data", "kirkland-discovery.json")
DISCOVERY_META_CACHE = os.path.join(BASE_DIR, "data", "kirkland-discovery-meta.json")


class DiscoveryFilters(BaseModel):
    min_monthly_sales: int = 500
    categories: List[str] = []  # empty = all non-food
    exclude_categories: List[str] = []
    match_quality: List[str] = ["exact", "invoice_confirmed", "high_confidence", "candidate"]
    cost_basis: List[str] = ["invoice_confirmed", "costco_online", "estimated", "candidate_match"]
    min_profit: Optional[float] = None
    min_roi: Optional[float] = None
    max_price: Optional[float] = None


@app.get("/api/kirkland/discovery")
def get_kirkland_discovery(
    min_monthly_sales: int = 500,
    category: Optional[str] = None,
    match_quality: Optional[str] = None,
    cost_basis: Optional[str] = None,
    min_profit: Optional[float] = None,
    min_roi: Optional[float] = None,
    max_price: Optional[float] = None,
):
    """
    Get Kirkland product discovery results with filtering.
    
    All data is from cached discovery runs — zero live API calls.
    Results auto-load from local JSON cache on server start.
    """
    # Load cached discovery
    if not os.path.exists(DISCOVERY_CACHE):
        raise HTTPException(
            status_code=404,
            detail="Discovery cache not found. Run discovery pipeline first (python kirkland_discovery.py)."
        )
    
    with open(DISCOVERY_CACHE, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    products = data.get("qualified_products", [])
    all_products = data.get("all_kirkland_products", [])
    
    # Apply filters
    filtered = []
    for p in all_products:
        # Monthly sales filter
        sales = p.get("monthly_sales_estimate")
        if sales is None or sales < min_monthly_sales:
            continue
        
        # Category filter
        if category:
            p_cat = p.get("normalized_category") or p.get("category")
            if not p_cat or p_cat != category:
                continue
        
        # Match quality filter
        if match_quality:
            qualities = [q.strip() for q in match_quality.split(",")]
            if p.get("match_quality") not in qualities:
                continue
        
        # Cost basis filter
        if cost_basis:
            bases = [b.strip() for b in cost_basis.split(",")]
            if p.get("costco_cost_basis") not in bases:
                continue
        
        # Profit filter
        if min_profit is not None:
            profit = p.get("net_profit") or p.get("projected_net_profit")
            if profit is None or profit < min_profit:
                continue
        
        # ROI filter
        if min_roi is not None:
            roi = p.get("roi_pct") or p.get("projected_roi_pct")
            if roi is None or roi < min_roi:
                continue
        
        # Max price filter
        if max_price is not None:
            price = p.get("amazon_price")
            if price is None or price > max_price:
                continue
        
        filtered.append(p)
    
    # Sort by monthly sales desc
    filtered.sort(key=lambda x: x.get("monthly_sales_estimate") or 0, reverse=True)
    
    # Get unique categories for filter UI
    categories = sorted(set(
        c for c in (
            p.get("normalized_category") or p.get("category")
            for p in all_products
            if p.get("monthly_sales_estimate") and p.get("monthly_sales_estimate") >= min_monthly_sales
            and not kd.is_food_category(p.get("category")) and not kd.is_food_by_title(p.get("name"))
        )
        if c
    ))
    
    return {
        "meta": data.get("meta", {}),
        "filters_applied": {
            "min_monthly_sales": min_monthly_sales,
            "category": category,
            "match_quality": match_quality,
            "cost_basis": cost_basis,
            "min_profit": min_profit,
            "min_roi": min_roi,
            "max_price": max_price,
        },
        "categories": categories,
        "products": filtered,
        "total_available": len(all_products),
        "total_filtered": len(filtered),
    }


@app.post("/api/kirkland/discovery/run")
def run_kirkland_discovery(filters: DiscoveryFilters):
    """
    Trigger a fresh discovery run with custom filters.
    Uses cached scanner data only (zero live calls unless explicitly enabled).
    """
    result = kd.run_discovery(
        use_cache_only=True,
        min_sales=filters.min_monthly_sales,
        excluded_cats=filters.exclude_categories,
        included_cats=filters.categories,
    )
    return {
        "status": "ok" if result.get("qualified_count", 0) > 0 else "completed",
        "summary": result.get("meta", {}),
    }


@app.get("/api/kirkland/discovery/categories")
def get_discovery_categories():
    """Get all available categories from discovery cache for filter UI."""
    if not os.path.exists(DISCOVERY_CACHE):
        return {"categories": []}
    
    with open(DISCOVERY_CACHE, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    all_products = data.get("all_kirkland_products", [])
    categories = {}
    
    for p in all_products:
        sales = p.get("monthly_sales_estimate")
        if not sales or sales < 500:
            continue
        if kd.is_food_category(p.get("category")) or kd.is_food_by_title(p.get("name")):
            continue
        cat = p.get("normalized_category") or p.get("category") or "Unknown"
        if cat not in categories:
            categories[cat] = 0
        categories[cat] += 1
    
    return {
        "categories": [
            {"name": cat, "count": count}
            for cat, count in sorted(categories.items(), key=lambda x: -x[1])
        ]
    }


@app.get("/api/kirkland/discovery/meta")
def get_discovery_meta():
    """Get discovery metadata (timestamp, counts, etc.) without full product list."""
    if not os.path.exists(DISCOVERY_META_CACHE):
        return {"status": "not_found"}
    
    with open(DISCOVERY_META_CACHE, "r", encoding="utf-8") as f:
        return json.load(f)


@app.get("/api/products/{asin}/canopy")
def get_product_canopy(asin: str) -> dict:
    if not re.fullmatch(r"[A-Za-z0-9]{10}", asin):
        raise HTTPException(
            status_code=400,
            detail="Invalid ASIN. Expected a 10-character alphanumeric Amazon ASIN.",
        )

    product = get_canopy_product(asin)

    product["enrichment_source"] = "canopy"
    product["enrichment_scope"] = "one_explicit_asin"
    price = product.get("amazon_price")
    product["live_price_verified"] = isinstance(price, (int, float)) and price > 0

    return product


@app.get("/api/products/{asin}/offers")
def get_product_offers(asin: str) -> dict:
    """On-demand seller/Buy Box detail for exactly one ASIN.

    Called only when the user explicitly opens the Sellers & Buy Box panel
    for one ASIN — never by the scanner, row rendering, filtering, sorting,
    or page load. One provider request maximum per cache miss (Easyparser
    OFFER), cached separately from the scanner enrichment cache. Invalid
    ASINs are rejected before any provider call.
    """
    if not re.fullmatch(r"[A-Za-z0-9]{10}", asin):
        raise HTTPException(
            status_code=400,
            detail="Invalid ASIN. Expected a 10-character alphanumeric Amazon ASIN.",
        )

    payload = offer_enrichment.get_seller_offer_contract(asin)
    payload["enrichment_source"] = payload.get("offer_data_source") or "easyparser"
    payload["enrichment_scope"] = "one_explicit_asin"

    return payload


# ---------------------------------------------------------------------------
# DataForSEO Amazon Merchant secondary-validation adapter (offline by default)
# ---------------------------------------------------------------------------

from pydantic import BaseModel as _BaseModel

import dataforseo_adapter as _df
from proof_batch_contracts import GuardError as _GuardError


class DataForSEOValidateRequest(_BaseModel):
    asin: str = ""
    marketplace: str = ""
    bd_snapshot_ref: Optional[str] = None
    bd_record_id: Optional[str] = None
    approval_run_id: str = ""
    approval_token: Optional[str] = None
    task_types: Optional[List[str]] = None


@app.post("/api/dataforseo/validate")
def post_dataforseo_validate(req: DataForSEOValidateRequest):
    """Guarded single-ASIN DataForSEO Standard-queue cross-check.

    This is the ONLY route that may touch the DataForSEO adapter, and it
    is fail-closed:

    - DATAFORSEO_ENABLED must be an explicit opt-in (feature flag, false
      by default). Otherwise returns 403 and never touches a provider.
    - An explicit one-run approval token must be supplied in the POST body
      (never a GET, never a UI toggle, never a page load). The token must
      equal the approval_run_id exactly.
    - The candidate must have passed the internal shortlist logic; the
      contract rejects batches/lists/wildcards/keyword searches.
    - The live transport is armed only by an explicit runtime opt-in:
      DATAFORSEO_TRANSPORT_ENABLED exactly "true" plus configured
      DATAFORSEO_LOGIN/DATAFORSEO_PASSWORD credentials. Without the arm,
      even a fully authorized request refuses before any network call
      (LIVE_CALLS_MADE=0); with the arm, the guarded Standard-queue
      submission runs with the budget ledger enforced.

    GET routes and normal page loads never invoke this adapter.
    """
    cfg = _df.load_config()
    if not cfg.get("enabled"):
        raise HTTPException(
            status_code=403,
            detail=(
                "DataForSEO validation is disabled (DATAFORSEO_ENABLED not set "
                "to an explicit opt-in). Returning no provider call."
            ),
        )
    body: Dict[str, Any] = {
        "asin": req.asin,
        "marketplace": req.marketplace,
        "bd_snapshot_ref": req.bd_snapshot_ref,
        "bd_record_id": req.bd_record_id,
        "approval_run_id": req.approval_run_id,
        "approval_token": req.approval_token,
    }
    if req.task_types is not None:
        body["task_types"] = req.task_types
    try:
        result = _df.execute_validation(
            body, operator_token=req.approval_token)
    except _GuardError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return result
