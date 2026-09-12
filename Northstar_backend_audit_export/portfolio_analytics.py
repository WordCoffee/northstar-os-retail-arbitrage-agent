"""Offline portfolio analytics for the Product Scout (read-only).

Pure, deterministic helpers that turn one scored row plus its demand and
competition fields into portfolio-planning outputs: monthly revenue and
profit pools, completeness dimensions, portfolio readiness, next step,
category recommendation, risk flags, and enriched score reasons.

Rules of honesty (mirrored from the scanner contracts):
  - estimated_monthly_revenue = estimated_monthly_sales x Buy Box
    LANDED price, and ONLY when the Buy Box landed price is explicitly
    supplied. If it is unknown, revenue may fall back to the separately
    documented amazon_price already present in the candidate record —
    never to an arbitrary seller-offer price. Without either, monthly
    revenue stays Unknown.
  - Pools use only existing unit-economics outputs (net_profit per
    unit) and modeled demand; they are labeled estimates with the
    modeled-sales disclaimer — never a forecast of actual Buy Box share
    or earnings.
  - Unknown seller data never improves scoring: an unknown/absent
    offer roster leaves competition completeness at 0, readiness below
    complete_opportunity, category at watchlist/research, and share
    fields null. Only an explicit complete zero-offer set counts as
    real (empty-competition) data.
  - Unknown stays Unknown (null), never 0, never a fabricated value.
  - This module writes nothing and never calls a provider.
"""

from typing import Any, Dict, List, Optional

import market_snapshot_store

REVENUE_BASIS_BUY_BOX = "observed_buy_box_landed_price"
REVENUE_BASIS_CANDIDATE = "candidate_amazon_price"
POOL_BASIS = "est_sales_x_net_profit"
SELLER_PROFIT_BASIS = "est_units_per_observed_seller_x_net_profit"

REVENUE_DISCLAIMER = (
    "Estimated from modeled monthly sales and the observed Buy Box "
    "landed price (or the listing price already in the candidate "
    "record); not a forecast."
)
POOL_DISCLAIMER = (
    "Estimated from modeled total sales and observed seller "
    "competition; not a forecast of your actual Buy Box share or "
    "earnings."
)
MODELED_DISCLAIMER = REVENUE_DISCLAIMER + " " + POOL_DISCLAIMER

# Completeness weights (identity, cost, economics, demand, competition,
# freshness) for the total score.
_COMPLETENESS_DIMS = (
    "identity_completeness",
    "cost_completeness",
    "economics_completeness",
    "demand_completeness",
    "competition_completeness",
    "freshness_completeness",
)

_VERIFIED_MATCHES = ("exact", "invoice_confirmed", "high_confidence")

# Portfolio readiness states (display/planning only; never alters
# match_quality, economics, or the purchase gate).
READY_COMPLETE = "complete_opportunity"
READY_ECON_READY = "economics_ready"
READY_INSUFFICIENT = "insufficient_data"
READY_STALE = "stale_market_data"
READY_NEEDS_SELLERS = "needs_seller_data"
READY_NEEDS_SNAPSHOT = "needs_offer_snapshot"
READY_NEEDS_BSR = "needs_bsr_category"
READY_NEEDS_PRICE_COST = "needs_price_or_cost"
READY_NEEDS_FEE = "needs_fee_verification"
READY_NEEDS_IDENTITY = "needs_identity_verification"
READY_NEEDS_COSTCO = "needs_costco_mapping"
READY_BLOCKED = "blocked_mismatch"

_NEXT_STEP = {
    READY_BLOCKED: "reject_mismatch",
    READY_NEEDS_COSTCO: "find_costco_match",
    READY_NEEDS_IDENTITY: "verify_upc_and_variant",
    READY_NEEDS_FEE: "get_fba_fee_preview",
    READY_NEEDS_PRICE_COST: "verify_costco_pack_and_price",
    READY_NEEDS_BSR: "gather_bsr_category",
    READY_NEEDS_SNAPSHOT: "run_offer_snapshot",
    READY_NEEDS_SELLERS: "enrich_sellers",
    READY_STALE: "refresh_market_data",
    READY_ECON_READY: "await_data",
    READY_COMPLETE: "review_top_opportunity",
    READY_INSUFFICIENT: "await_data",
}

_CATEGORY_BLOCKED = "avoid_mismatch"
_CATEGORY_CORE = "core_replenishable"
_CATEGORY_TEST = "test_buy_candidate"
_CATEGORY_WATCH = "watchlist"
_CATEGORY_RESEARCH = "research_queue"

# Risk flag vocabulary.
RISK_WEAK_MATCH = "weak_match"
RISK_COST_CANDIDATE = "cost_basis_candidate"
RISK_UNKNOWN_FBA_FEE = "unknown_fba_fee"
RISK_THIN_MARGIN = "thin_margin"
RISK_LOW_DEMAND = "low_est_demand"
RISK_HIGH_COMPETITION = "high_observed_competition"
RISK_LOW_SHARE = "low_est_seller_share"
RISK_PARTIAL_SAMPLE = "partial_offer_sample"
RISK_ROSTER_UNAVAILABLE = "offer_roster_unavailable"
RISK_STALE = "stale_market_data"
RISK_SINGLE_ASIN = "single_asin_concentration"

CORE_MIN_NET_PROFIT = 9.0
CORE_MIN_EST_SALES = 500.0
LOW_DEMAND_THRESHOLD = 100.0
HIGH_COMPETITION_THRESHOLD = 10
LOW_SHARE_THRESHOLD = 30.0
THIN_MARGIN_THRESHOLD = 5.0


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _positive(value: Any) -> Optional[float]:
    if not _is_number(value) or value <= 0:
        return None
    return float(value)


def _round2(value: Optional[float]) -> Optional[float]:
    return round(value, 2) if value is not None else None


def completeness_dimensions(
    row: Dict,
    demand: Dict,
    competition: Dict,
    snapshot: Dict,
) -> Dict:
    """Six 0.0-1.0 completeness dimensions plus a 0-100 total.

    Unknown seller data never scores: only an explicit complete
    zero-offer set (roster state "zero") or actual returned rows give
    competition completeness credit; unknown rosters score 0.
    """
    pack_match = row.get("pack_match")
    identity = 1.0 if pack_match in _VERIFIED_MATCHES else (0.5 if pack_match == "candidate" else 0.0)

    cost = row.get("costco_cost")
    basis = row.get("costco_cost_basis")
    if _is_number(cost) and basis not in ("candidate_match", "unavailable"):
        cost_dim = 1.0
    elif _is_number(cost):
        cost_dim = 0.5
    else:
        cost_dim = 0.0

    econ_conf = row.get("economics_confidence")
    economics_dim = 1.0 if econ_conf == "estimated" else (0.5 if econ_conf == "provisional" else 0.0)

    demand_dim = 1.0 if demand.get("estimated_monthly_sales") is not None else 0.0

    roster_state = competition.get("roster_state") or _roster_state_from(competition)
    if roster_state == "zero" or (
        roster_state == "rows" and competition.get("offers_complete") is True
    ):
        competition_dim = 1.0
    elif roster_state == "rows":
        competition_dim = 0.5
    else:
        competition_dim = 0.0

    if snapshot is None:
        freshness_dim = 0.0
    else:
        status = market_snapshot_store.snapshot_freshness_status(snapshot, stage="offers")
        freshness_dim = 1.0 if status == "fresh" else 0.5

    dims = {
        "identity_completeness": identity,
        "cost_completeness": cost_dim,
        "economics_completeness": economics_dim,
        "demand_completeness": demand_dim,
        "competition_completeness": competition_dim,
        "freshness_completeness": freshness_dim,
    }
    total = int(round(100 * sum(dims.values()) / len(_COMPLETENESS_DIMS)))
    dims["total_completeness_score"] = total
    return dims


def _roster_state_from(competition: Dict) -> Optional[str]:
    counts = competition.get("observed_total_sellers")
    if _is_number(counts):
        return "zero" if counts == 0 else "rows"
    return None


def monthly_pool_fields(
    row: Dict,
    demand: Dict,
    competition: Dict,
    candidate_amazon_price: Any = None,
) -> Dict:
    """Estimated monthly revenue and profit pools.

    Revenue basis priority (never an arbitrary offer price):
      1. estimated_monthly_sales x observed_buy_box_landed_price —
         only when the Buy Box landed price is explicitly supplied.
      2. estimated_monthly_sales x candidate_amazon_price — the
         separately documented listing price already in the candidate
         record.
      3. Unknown (basis None) — never filled from any seller-offer
         price, lowest/highest, or Buy Box price without a landed
         price.
    Profit pools use only existing unit economics (net_profit per
    unit). Everything is labeled estimated with the modeled-sales
    disclaimer.
    """
    est = demand.get("estimated_monthly_sales")
    confidence = demand.get("sales_estimation_confidence")
    net_profit = row.get("net_profit")
    net = _positive(net_profit)

    fields: Dict = {
        "estimated_monthly_revenue": None,
        "monthly_revenue_basis": None,
        "monthly_revenue_confidence": None,
        "estimated_monthly_profit_pool": None,
        "monthly_profit_pool_basis": None,
        "monthly_profit_pool_confidence": None,
        "estimated_fba_seller_monthly_profit": None,
        "estimated_fbm_seller_monthly_profit": None,
        "estimated_observed_seller_monthly_profit": None,
        "seller_profit_basis": None,
        "monthly_pool_note": None,
    }
    if est is None:
        return fields

    landed = _positive(competition.get("observed_buy_box_landed_price"))
    cand_price = _positive(candidate_amazon_price)
    if landed is not None:
        revenue = est * landed
        basis = REVENUE_BASIS_BUY_BOX
    elif cand_price is not None:
        revenue = est * cand_price
        basis = REVENUE_BASIS_CANDIDATE
    else:
        revenue = None
        basis = None
    fields["estimated_monthly_revenue"] = _round2(revenue)
    fields["monthly_revenue_basis"] = basis
    fields["monthly_revenue_confidence"] = confidence if revenue is not None else None

    if net is not None:
        pool = est * net
        fields["estimated_monthly_profit_pool"] = _round2(pool)
        fields["monthly_profit_pool_basis"] = POOL_BASIS
        fields["monthly_profit_pool_confidence"] = confidence
        fields["estimated_fba_seller_monthly_profit"] = _round2(
            _positive(competition.get("estimated_units_per_observed_fba_seller")) * net
            if competition.get("estimated_units_per_observed_fba_seller") is not None
            else None
        )
        fields["estimated_fbm_seller_monthly_profit"] = _round2(
            _positive(competition.get("estimated_units_per_observed_fbm_seller")) * net
            if competition.get("estimated_units_per_observed_fbm_seller") is not None
            else None
        )
        fields["estimated_observed_seller_monthly_profit"] = _round2(
            _positive(competition.get("estimated_units_per_observed_seller")) * net
            if competition.get("estimated_units_per_observed_seller") is not None
            else None
        )
        if any(
            fields[k] is not None
            for k in (
                "estimated_fba_seller_monthly_profit",
                "estimated_fbm_seller_monthly_profit",
                "estimated_observed_seller_monthly_profit",
            )
        ):
            fields["seller_profit_basis"] = SELLER_PROFIT_BASIS

    if any(
        fields[k] is not None
        for k in ("estimated_monthly_revenue", "estimated_monthly_profit_pool")
    ):
        fields["monthly_pool_note"] = MODELED_DISCLAIMER
    return fields


def portfolio_readiness(
    row: Dict,
    demand: Dict,
    competition: Dict,
    snapshot: Dict,
) -> str:
    """Readiness state for one row (display/planning only).

    Unknown seller data never unlocks complete_opportunity: an unknown
    roster (empty/partial-zero/failed/unavailable/malformed/absent)
    keeps readiness at needs_seller_data (or stale/needs_offer_snapshot
    when the snapshot itself is absent or stale).
    """
    pack_match = row.get("pack_match")
    if pack_match == "mismatch":
        return READY_BLOCKED

    if not _is_number(row.get("costco_cost")):
        return READY_NEEDS_COSTCO

    if pack_match == "candidate" or row.get("costco_cost_basis") == "candidate_match":
        return READY_NEEDS_IDENTITY

    econ_conf = row.get("economics_confidence")
    if econ_conf == "provisional" or (
        econ_conf == "estimated" and not _is_number(row.get("fba_fee"))
    ):
        return READY_NEEDS_FEE
    if econ_conf == "unavailable" or econ_conf is None:
        return READY_NEEDS_PRICE_COST

    if demand.get("estimated_monthly_sales") is None:
        return READY_NEEDS_BSR

    if snapshot is None:
        return READY_NEEDS_SNAPSHOT

    state, _ = _roster_state(snapshot)
    if state is None:
        return READY_NEEDS_SELLERS

    if market_snapshot_store.snapshot_freshness_status(snapshot, stage="offers") != "fresh":
        return READY_STALE

    if econ_conf == "estimated":
        return READY_COMPLETE
    return READY_ECON_READY


def _roster_state(snapshot: Dict) -> tuple:
    """Mirror competition_analytics.roster_state without importing it
    (keeps this module dependency-light and testable in isolation)."""
    offers = [o for o in (snapshot.get("offers") or []) if isinstance(o, dict)]
    if snapshot.get("data_status") not in ("available", "partial"):
        return None, "offer_roster_unavailable"
    if offers:
        return "rows", None
    stored = snapshot.get("seller_counts") or {}
    if (
        snapshot.get("data_status") == "available"
        and snapshot.get("offers_complete") is True
        and _is_number(stored.get("claimed_total"))
        and stored.get("claimed_total") == 0
        and _is_number(snapshot.get("offers_returned"))
        and snapshot.get("offers_returned") == 0
    ):
        return "zero", None
    if snapshot.get("data_status") == "partial":
        return None, "partial_offer_roster"
    return None, "no_explicit_zero_offer_evidence"


def portfolio_next_step(readiness: str) -> str:
    return _NEXT_STEP.get(readiness, "await_data")


def portfolio_category(readiness: str, row: Dict, demand: Dict) -> str:
    """Portfolio category recommendation.

    A proven complete zero-offer set is real (empty-competition) data;
    unknown seller data never upgrades the category. Only a complete,
    fresh, estimated row with a strong margin can reach
    core_replenishable.
    """
    if readiness == READY_BLOCKED:
        return _CATEGORY_BLOCKED
    if readiness in (READY_NEEDS_COSTCO, READY_NEEDS_IDENTITY, READY_NEEDS_PRICE_COST):
        return _CATEGORY_RESEARCH
    if readiness == READY_NEEDS_FEE:
        return _CATEGORY_TEST
    if readiness in (
        READY_NEEDS_BSR,
        READY_NEEDS_SNAPSHOT,
        READY_NEEDS_SELLERS,
        READY_STALE,
        READY_ECON_READY,
    ):
        return _CATEGORY_WATCH
    if readiness == READY_COMPLETE:
        net = row.get("net_profit")
        est = demand.get("estimated_monthly_sales")
        if (
            _is_number(net)
            and net >= CORE_MIN_NET_PROFIT
            and _is_number(est)
            and est >= CORE_MIN_EST_SALES
        ):
            return _CATEGORY_CORE
        return _CATEGORY_TEST
    return _CATEGORY_RESEARCH


def risk_flags(
    row: Dict,
    demand: Dict,
    competition: Dict,
    snapshot: Optional[Dict] = None,
    portfolio_size: Optional[int] = None,
) -> List[str]:
    """Risk flags for one row (stable order, deduped).

    Flags are honesty signals, not penalties fabricated for missing
    data: they only appear when the underlying fact (or absence of a
    fact) is real.
    """
    flags: List[str] = []
    pack_match = row.get("pack_match")
    if pack_match in ("candidate", "unknown"):
        flags.append(RISK_WEAK_MATCH)
    if row.get("costco_cost_basis") == "candidate_match":
        flags.append(RISK_COST_CANDIDATE)
    if row.get("economics_confidence") == "provisional":
        flags.append(RISK_UNKNOWN_FBA_FEE)
    net = row.get("net_profit")
    if _is_number(net) and net < THIN_MARGIN_THRESHOLD:
        flags.append(RISK_THIN_MARGIN)
    est = demand.get("estimated_monthly_sales")
    if _is_number(est) and est < LOW_DEMAND_THRESHOLD:
        flags.append(RISK_LOW_DEMAND)
    observed = competition.get("observed_total_sellers")
    if _is_number(observed) and observed >= HIGH_COMPETITION_THRESHOLD:
        flags.append(RISK_HIGH_COMPETITION)
    share = competition.get("estimated_units_per_observed_seller")
    if _is_number(share) and share < LOW_SHARE_THRESHOLD:
        flags.append(RISK_LOW_SHARE)
    if competition.get("offers_complete") is False and competition.get("observed_total_sellers") is not None:
        flags.append(RISK_PARTIAL_SAMPLE)
    if competition.get("offer_roster_reason"):
        flags.append(RISK_ROSTER_UNAVAILABLE)
    if snapshot is not None and market_snapshot_store.snapshot_freshness_status(
        snapshot, stage="offers"
    ) != "fresh":
        flags.append(RISK_STALE)
    if portfolio_size is not None and portfolio_size <= 1:
        flags.append(RISK_SINGLE_ASIN)
    return flags


def enriched_score_reasons(existing_reasons: Any, risk_flags: List[str]) -> Optional[List[str]]:
    """Existing opportunity score reasons plus risk penalties.

    None when there is no existing score (a row without a score never
    gains one from risk flags alone); missing-data exclusions in the
    existing reasons are preserved untouched.
    """
    if not existing_reasons:
        return None
    if not risk_flags:
        return list(existing_reasons)
    return list(existing_reasons) + ["risk: " + flag for flag in risk_flags]


def portfolio_fields(
    row: Dict,
    demand: Dict,
    competition: Dict,
    snapshot: Optional[Dict],
    candidate_amazon_price: Any = None,
    portfolio_size: Optional[int] = None,
) -> Dict:
    """Complete portfolio field set for one row.

    Never modifies the input row; returns the new fields so callers can
    merge them (e.g. row.update(...)). All values stay None/Unknown
    when their inputs are missing.
    """
    fields = completeness_dimensions(row, demand, competition, snapshot)
    fields.update(monthly_pool_fields(row, demand, competition, candidate_amazon_price))
    readiness = portfolio_readiness(row, demand, competition, snapshot)
    fields["portfolio_readiness"] = readiness
    fields["portfolio_next_step"] = portfolio_next_step(readiness)
    fields["portfolio_category"] = portfolio_category(readiness, row, demand)
    flags = risk_flags(row, demand, competition, snapshot, portfolio_size)
    fields["risk_flags"] = flags
    fields["portfolio_score_reasons"] = enriched_score_reasons(
        row.get("opportunity_score_reasons"), flags
    )
    return fields