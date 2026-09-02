import os
from dotenv import load_dotenv
from typing import Dict, List, Optional

import amazon_search
from amazon_search import search_kirkland_products
import costco_client
from costco_client import get_costco_price as _csv_get_costco_price
from costco_api_client import resolve_costco_cost
import market_snapshot_store
import opportunity_analytics
import offer_enrichment
import competition_analytics
import demand_estimator
import portfolio_analytics
from pricing import estimate_fba_fee, screen_by_profit_tier, estimate_financial_profile
from fee_engine import (
    calculate_unit_economics,
    ECON_ESTIMATED,
    ECON_UNAVAILABLE,
    ECON_STATUS_NEEDS_FEE_VERIFICATION,
)

load_dotenv()

MIN_PROFIT_MARGIN_PERCENT = float(os.getenv("MIN_PROFIT_MARGIN_PERCENT", "0"))
MIN_ROI_PERCENT = float(os.getenv("MIN_ROI_PERCENT", "0"))

# Mirrors the existing server-side catalog-screen rule in main.build_result
# (ScanRequest defaults: min_profit 11.0, min_velocity 2000).
CATALOG_SCREEN_MIN_PROFIT = 11.0
CATALOG_SCREEN_MIN_VELOCITY = 2000

# Pack/Variant match gate (purchase-analysis policy): estimated economics
# require a hard product-equivalence fingerprint. invoice_confirmed rows
# (real paid COGS) and exact fingerprints pass; high_confidence (strong
# normalized title identity, no known conflict) also passes the economics
# gate but is never a purchase authorization by itself — only
# invoice_confirmed rows carry cost_is_purchase_authorized=True.
PURCHASE_GATE_MATCH_QUALITIES = ("exact", "invoice_confirmed", "high_confidence")


def _catalog_verdict_or_none(net_profit, monthly_sales, monthly_sales_estimated):
    """Pass/Hold/Reject only when every verified catalog-screen input is
    present; otherwise None because the existing rule cannot be evaluated."""
    if not isinstance(net_profit, (int, float)) or isinstance(net_profit, bool):
        return None
    if not isinstance(monthly_sales, (int, float)) or isinstance(monthly_sales, bool):
        return None
    if monthly_sales_estimated is not False:
        return None
    if net_profit >= CATALOG_SCREEN_MIN_PROFIT and monthly_sales >= CATALOG_SCREEN_MIN_VELOCITY:
        return "Pass"
    if net_profit > 0:
        return "Hold"
    return "Reject"


NEEDS_FEE_VERIFICATION = "Needs Fee Verification"


def get_costco_price(item_name: str, amazon_asin: Optional[str] = None,
                     amazon_upc: Optional[str] = None,
                     amazon_brand: Optional[str] = None) -> Dict:
    """Resolve the strongest Costco cost basis for an Amazon product name
    across the three catalog layers (invoice_confirmed > product_detail >
    CSV legacy), preceded by the verified ASIN ledger. The ASIN/UPC/brand
    strengthen (or honestly conflict) the fingerprint on every layer.
    Never invents costs; returns {} when no layer matches."""
    return (
        resolve_costco_cost(item_name, amazon_asin=amazon_asin,
                            amazon_upc=amazon_upc, amazon_brand=amazon_brand)
        or _csv_get_costco_price(item_name, amazon_upc=amazon_upc, amazon_brand=amazon_brand)
        or {}
    )


def _verified_fba_fee(offer, costco):
    """Verified FBA fee for the ASIN, or None.

    Priority: an FBA fee reported by the Amazon/listing data provider
    (offer.fba_fee), then the weight-based estimate for legacy Costco rows
    that still carry weight_lbs. Never invented: when neither exists the
    fee is None and the product moves to the Needs Fee Verification state.
    """
    listing_fee = offer.get("fba_fee")
    if _is_number(listing_fee) and listing_fee > 0:
        return listing_fee
    weight_lbs = costco.get("weight_lbs")
    if _is_number(weight_lbs) and weight_lbs > 0:
        return estimate_fba_fee(weight_lbs)
    return None


def _is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _dedupe_candidates(candidates: List[Dict]) -> List[Dict]:
    """Drop duplicate candidates by ASIN (fallback: product URL), keeping
    the first occurrence from the search results."""
    seen = set()
    out: List[Dict] = []
    for c in candidates:
        key = c.get("asin") or c.get("product_url")
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(c)
    return out


def _apply_market_intelligence(results: List[Dict], snapshots: Dict, candidate_prices: Dict):
    """Phase 3 offline demand/competition/portfolio enrichment.

    Runs only for rows with a local market snapshot (merge enabled) and
    overlays the honest field sets from demand_estimator,
    competition_analytics, and portfolio_analytics. Candidate-record
    amazon_price is passed separately so monthly revenue may fall back
    to the documented listing price only — never an arbitrary
    seller-offer price. Read-only: no writes, no providers.
    """
    for r in results:
        asin = r.get("asin")
        snap = snapshots.get(asin) if asin else None
        if not isinstance(snap, dict):
            continue
        demand = demand_estimator.estimate_demand(
            listing_bought_past_month=r.get("listing_bought_past_month"),
            provider_monthly_sales_estimate=r.get("monthly_sales_estimate"),
            bsr=r.get("sales_rank"),
            bsr_category=r.get("amazon_category"),
            bsr_observed_at=r.get("snapshot_observed_at") or r.get("enriched_at"),
        )
        competition = competition_analytics.competition_fields(
            snap, demand.get("estimated_monthly_sales")
        )
        r.update(demand)
        r.update(competition)
        r.update(
            portfolio_analytics.portfolio_fields(
                r,
                demand,
                competition,
                snap,
                candidate_amazon_price=candidate_prices.get(asin),
                portfolio_size=len(results),
            )
        )


def _candidates_for_mode() -> List[Dict]:
    """Candidate source selected by the enrichment flag.

    Disabled (cache-only): the local search cache only — zero outbound or
    provider calls. Enabled: live search; the cache is written only after
    a fully successful result, and a failed/partial live search falls
    back to the prior cache instead of overwriting it.
    """
    if offer_enrichment._enrichment_mode() == "OFF":
        return _dedupe_candidates(amazon_search.load_cached_candidates())

    candidates = _dedupe_candidates(search_kirkland_products())
    if amazon_search.LAST_SEARCH_ERROR:
        cached = _dedupe_candidates(amazon_search.load_cached_candidates())
        if cached:
            return cached
    else:
        amazon_search.save_cached_candidates(candidates)
    return candidates


def analyze_kirkland_products() -> Dict:
    candidates = _candidates_for_mode()
    results: List[Dict] = []
    _snapshots = (
        market_snapshot_store.load_snapshots()
        if offer_enrichment._snapshot_merge_enabled()
        else {}
    )

    for c in candidates:
        identifier = c.get("product_url") or c.get("asin")
        if not identifier:
            continue

        costco = get_costco_price(
            c["name"],
            amazon_asin=c.get("asin"),
            amazon_upc=c.get("upc") or c.get("ean"),
            amazon_brand=c.get("brand"),
        ) or {}
        costco_cost = costco.get("costco_cost")

        # Display-only match evidence: same fingerprints and classifier as
        # the decision, structured for the Scout drawer. Never gates
        # economics or purchases — it only explains the decision.
        match_evidence = costco_client.equivalence_evidence(
            c["name"],
            costco.get("item_name"),
            amazon_upc=c.get("upc") or c.get("ean"),
            costco_upc=costco.get("upc_or_ean"),
            amazon_brand=c.get("brand"),
        )

        # Per-ASIN enrichment (BRIGHTDATA Web Unlocker per-request, CHOCODATA
        # 5 credits, UNWRANGLE 1 credit) is billed per request: only spend
        # credits where the row can actually be scored — a Costco cost exists
        # AND the Pack/Variant fingerprint passes the purchase-analysis gate
        # (exact, invoice-confirmed, or high-confidence title identity),
        # since Net Profit / ROI can only be computed for those rows.
        # Candidate/mismatch/unknown matches are research view only: they
        # get the offline placeholder at zero cost.
        enrichable = (
            costco_cost is not None
            and costco.get("match_quality") in PURCHASE_GATE_MATCH_QUALITIES
        )
        if offer_enrichment._enrichment_mode() == "OFF" or not enrichable:
            offer = offer_enrichment._offline_offer_merged(
                identifier, c, _snapshots.get(c.get("asin"))
            )
        else:
            offer = offer_enrichment.get_scanner_offer(identifier)
        if not offer:
            continue

        # Amazon price: the per-ASIN offer/Buy Box price first, then the
        # search candidate's own price. Missing (None or non-positive) at
        # both levels stays None — the row renders Unavailable, never $0.
        offer_price = offer.get("amazon_price")
        candidate_price = c.get("amazon_price")
        if _is_number(offer_price) and offer_price > 0:
            amazon_price = offer_price
        elif _is_number(candidate_price) and candidate_price > 0:
            amazon_price = candidate_price
        else:
            amazon_price = None

        # Verified FBA fee for this ASIN: listing/offer data first, then the
        # weight-based estimate for legacy Costco rows that carry weight_lbs.
        # Missing weight never disqualifies a product: without a fee the
        # candidate stays visible in the Needs Fee Verification state with
        # Unavailable labels — never $0, never fabricated.
        fba_fee = _verified_fba_fee(offer, costco)

        # Versioned fee-engine economics. Category / browse-node metadata
        # (parsed from the Bright Data product page, zero extra requests)
        # feeds the referral rule: a breadcrumb-derived category maps to the
        # matching rule with inferred resolution confidence; without it the
        # referral defaults to Everything Else 15% (default_category, with
        # an explicit note). Provisional rows (no FBA fee) still get price
        # + COGS economics with the fee excluded and the note marked for
        # verification before purchasing.
        economics = calculate_unit_economics(
            product={
                "amazon_price": amazon_price,
                "amazon_category": offer.get("amazon_category"),
                "browse_node": offer.get("browse_node_id"),
                "category_source_hint": offer.get("category_source_hint"),
                "package_weight_lbs": costco.get("weight_lbs"),
                "item_weight_lbs": None,
                "package_dimensions_in": None,
                "listing_fba_fee": fba_fee,
            },
            costco={
                "costco_cost": costco_cost,
                "costco_cost_basis": costco.get("costco_cost_basis", "unavailable"),
            },
        )

        # Pack/Variant match gate (purchase-analysis policy): a hard
        # product-equivalence fingerprint match (brand, formula/flavor,
        # net weight, pack/count, UPC when available) is required before
        # estimated ROI is allowed. Invoice-confirmed rows (real paid
        # COGS from a Business Center invoice) pass the same way an exact
        # fingerprint does, and high_confidence rows (strong title
        # identity, no known conflict) pass with the research cost.
        # Candidate/fuzzy matches may still surface as research candidates
        # but are downgraded to unavailable economics (status
        # mapping_verification_required) with the candidate cost basis —
        # no Tier, no Pass/Scale eligibility. A row with no Costco cost at
        # all keeps its honest missing_costco_cogs status instead of the
        # mapping-verification label.
        match_quality = costco.get("match_quality") or "unknown"
        if match_quality not in PURCHASE_GATE_MATCH_QUALITIES and costco_cost is not None:
            match_reason = costco.get("match_reason") or (
                "Exact product equivalence (weight/pack/flavor) unverified."
            )
            economics["economics_confidence"] = ECON_UNAVAILABLE
            economics["economics_status"] = "mapping_verification_required"
            economics["economics_note"] = (
                "COGS is a candidate match only — " + match_reason
                + " Verify the exact item (weight, pack, flavor) at Costco "
                "before purchase."
            )
            economics["net_profit"] = None
            economics["roi_pct"] = None

        # Manual-import provenance: high-confidence rows from a manual
        # import stay visible and scoreable research candidates, with the
        # import-verification warning appended to the allowlisted
        # economics note — never hidden, never treated as a mismatch.
        if (
            isinstance(c.get("imported_at"), str)
            and match_quality == "high_confidence"
            and costco_cost is not None
        ):
            warning = "Verify UPC, pack size, and variant before buying."
            note = economics.get("economics_note")
            economics["economics_note"] = ((note + " ") if note else "") + warning
        net_profit = economics["net_profit"]
        roi_pct = economics["roi_pct"]

        profit_margin_pct = (
            (net_profit / costco_cost) * 100
            if _is_number(net_profit) and _is_number(costco_cost) and costco_cost > 0
            else None
        )

        # ROI / margin gating applies to estimated economics only:
        # provisional rows are already flagged for fee verification and must
        # never be dropped by a threshold they cannot truthfully satisfy.
        if (
            economics["economics_confidence"] == ECON_ESTIMATED
            and _is_number(roi_pct)
            and (
                roi_pct < MIN_ROI_PERCENT
                or (profit_margin_pct is not None and profit_margin_pct < MIN_PROFIT_MARGIN_PERCENT)
            )
        ):
            continue

        profile = estimate_financial_profile(
            amazon_price=amazon_price,
            weight_lbs=costco.get("weight_lbs"),
            costco_cost=costco_cost,
        )

        fba_sellers = offer.get("fba_sellers")
        if fba_sellers == 0:
            fba_seller_preference = "Best (0 FBA sellers)"
        elif fba_sellers in (1, 2):
            fba_seller_preference = "Good (1-2 FBA sellers)"
        elif fba_sellers is not None and fba_sellers >= 3:
            fba_seller_preference = "Crowded (3+ FBA sellers)"
        else:
            fba_seller_preference = "Unknown"

        results.append(
            {
                "name": c["name"],
                "asin": c.get("asin"),
                "product_url": c.get("product_url"),
                "costco_cost": costco_cost,
                "pack_match": match_quality,
                "cost_match_reason": costco.get("match_reason"),
                "cost_source": costco.get("source"),
                # Only an invoice-confirmed row authorizes a purchase; exact
                # and high_confidence matches are research costs.
                "cost_is_purchase_authorized": match_quality == "invoice_confirmed",
                "amazon_price": amazon_price,
                "lowest_price": offer.get("lowest_price"),
                "highest_price": offer.get("highest_price"),
                "total_sellers": offer.get("total_sellers"),
                "fba_sellers": fba_sellers,
                "fba_sellers_estimated": offer.get("fba_sellers_estimated", False),
                "fba_seller_preference": fba_seller_preference,
                "lowest_price_seller_type": offer.get("lowest_price_seller_type", "unknown"),
                "highest_price_seller_type": offer.get("highest_price_seller_type", "unknown"),
                "monthly_sales_estimate": (
                    offer.get("monthly_sales_estimate")
                    if offer.get("monthly_sales_estimate") is not None
                    else c.get("monthly_sales_estimate")
                ),
                "monthly_sales_estimated": (
                    offer.get("monthly_sales_estimated", True)
                    if offer.get("monthly_sales_estimate") is not None
                    else bool(c.get("monthly_sales_estimated", False))
                ),
                "sales_rank": offer.get("sales_rank") or c.get("sales_rank"),
                "fba_fee": fba_fee,
                "net_profit": net_profit,
                "roi_pct": roi_pct,
                **economics,
                "projected_net_profit": profile["projected_net_profit"],
                "amazon_fees_total": profile["amazon_fees_total"],
                "amazon_payout_before_inventory_costs": profile["amazon_payout_before_inventory_costs"],
                "cogs": profile["cogs"],
                "prep_cost": profile["prep_cost"],
                "inbound_shipping_cost": profile["inbound_shipping_cost"],
                "landed_cost": profile["landed_cost"],
                "projected_roi_pct": profile["projected_roi_pct"],
                "financial_status": profile["financial_status"],
                "financial_decision_status": profile["financial_status"],
                "offer_data_provider": offer.get("offer_data_provider"),
                "enrichment_status": offer.get("enrichment_status"),
                "enriched_at": offer.get("enriched_at"),
                # Local market snapshot provenance (read-only merge).
                "snapshot_status": offer.get("snapshot_status"),
                "snapshot_source": offer.get("snapshot_source"),
                "snapshot_fetched_at": offer.get("snapshot_fetched_at"),
                "snapshot_observed_at": offer.get("snapshot_observed_at"),
                "snapshot_freshness": offer.get("snapshot_freshness"),
                "snapshot_offers_complete": offer.get("snapshot_offers_complete"),
                "snapshot_offers_returned": offer.get("snapshot_offers_returned"),
                "snapshot_data_gaps": offer.get("snapshot_data_gaps"),
                "snapshot_fbm_sellers": offer.get("snapshot_fbm_sellers"),
                "snapshot_amazon_sellers": offer.get("snapshot_amazon_sellers"),
                "snapshot_buy_box_available": offer.get("snapshot_buy_box_available"),
                "snapshot_buy_box_price": offer.get("snapshot_buy_box_price"),
                "snapshot_buy_box_fulfillment": offer.get("snapshot_buy_box_fulfillment"),
                "snapshot_buy_box_seller": offer.get("snapshot_buy_box_seller"),
                "verdict": (
                    None
                    if match_quality not in PURCHASE_GATE_MATCH_QUALITIES
                    else (
                        NEEDS_FEE_VERIFICATION
                        if fba_fee is None
                        else _catalog_verdict_or_none(
                            net_profit,
                            offer.get("monthly_sales_estimate"),
                            offer.get("monthly_sales_estimated", True),
                        )
                    )
                ),
                "financial_data_gaps": profile["financial_data_gaps"],
                "match_evidence": match_evidence,
                **opportunity_analytics.opportunity_fields(
                    {
                        "name": c["name"],
                        "asin": c.get("asin"),
                        "product_url": c.get("product_url"),
                        "amazon_price": amazon_price,
                        "costco_cost": costco_cost,
                        "match_quality": match_quality,
                        "match_reason": costco.get("match_reason"),
                        "cost_match_reason": costco.get("match_reason"),
                        "economics_confidence": economics["economics_confidence"],
                        "economics_status": economics.get("economics_status"),
                        "economics_note": economics.get("economics_note"),
                        "net_profit": net_profit,
                        "roi_pct": roi_pct,
                        "fba_fee": fba_fee,
                        "monthly_sales_estimate": (
                            offer.get("monthly_sales_estimate")
                            if offer.get("monthly_sales_estimate") is not None
                            else c.get("monthly_sales_estimate")
                        ),
                        "total_sellers": offer.get("total_sellers"),
                        "fba_sellers": fba_sellers,
                        "enriched_at": offer.get("enriched_at"),
                        "observed_at": c.get("observed_at"),
                        "imported_at": c.get("imported_at"),
                    },
                    cache_meta=amazon_search.cache_meta(),
                ),
            }
        )

    # Phase 3 offline market intelligence (demand, competition,
    # portfolio) for rows with a local market snapshot. Read-only and
    # cache-only: runs only when SCANNER_LOCAL_SNAPSHOT_MERGE is enabled.
    if offer_enrichment._snapshot_merge_enabled():
        _apply_market_intelligence(
            results,
            _snapshots,
            {c.get("asin"): c.get("amazon_price") for c in candidates if c.get("asin")},
        )

    estimated_only = [
        r for r in results if r.get("economics_confidence") == ECON_ESTIMATED
    ]
    tier, matches = screen_by_profit_tier(estimated_only, tiers=(11, 9, 7))

    for r in results:
        if r.get("economics_confidence") != ECON_ESTIMATED:
            r["profit_tier"] = None
        elif _is_number(r["net_profit"]) and r["net_profit"] >= 11:
            r["profit_tier"] = 11
        elif _is_number(r["net_profit"]) and r["net_profit"] >= 9:
            r["profit_tier"] = 9
        elif _is_number(r["net_profit"]) and r["net_profit"] >= 7:
            r["profit_tier"] = 7
        else:
            r["profit_tier"] = None

    by_monthly_sales = sorted(
        [r for r in results if r.get("monthly_sales_estimate") is not None],
        key=lambda x: x["monthly_sales_estimate"],
        reverse=True,
    )

    return {
        "tier_found": tier,
        "best_tier_matches": matches,
        "all_results": sorted(
            results,
            key=lambda x: x["net_profit"] if _is_number(x["net_profit"]) else float("-inf"),
            reverse=True,
        ),
        "by_monthly_sales": by_monthly_sales,
    }