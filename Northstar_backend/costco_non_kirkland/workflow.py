"""Operational candidate decision engine (Phase 6).

PURE / OFFLINE. Combines a source product (Costco/wholesale) with a
provider-reported market snapshot into a deterministic, evidence-based
recommendation:

  identity -> split-pack -> competition filter -> conservative economics
  -> recommendation status (+ reason codes) -> mfn_opportunity_score_v1

No scorer, importer, or CLI may produce `purchase_authorized` without the
separate explicit approval record (see approvals.py).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .enums import (
    OperationalRecommendation,
    PURCHASE_AUTHORIZATION_NOT_AUTHORIZED,
)
from .settings import get_settings
from .identity import assess_identity, evaluate_split_pack, IdentityState, SplitPackState
from .competition import assess_competition, mfn_opportunity_score, COMPETITION_PASS
from .economics import (
    conservative_sale_price,
    compute_economics,
    maximum_buy_cost,
)
from .store import PipelineStore


@dataclass
class CandidateDecision:
    candidate_id: str
    asin: Optional[str] = None
    costco_source_product_id: Optional[str] = None
    identity_state: str = IdentityState.UNKNOWN.value
    split_pack_state: str = SplitPackState.UNKNOWN.value
    competition_state: str = "needs_enrichment"
    recommendation_status: str = OperationalRecommendation.NEEDS_ENRICHMENT.value
    reason_codes: List[str] = field(default_factory=list)
    risk_flags: List[str] = field(default_factory=list)
    economics: Dict[str, Any] = field(default_factory=dict)
    market_snapshot: Dict[str, Any] = field(default_factory=dict)
    mfn_score: Optional[float] = None
    mfn_score_version: Optional[str] = None
    evidence_summary: str = ""
    purchase_authorization_status: str = PURCHASE_AUTHORIZATION_NOT_AUTHORIZED
    source_name: Optional[str] = None
    source_sku: Optional[str] = None
    source_url: Optional[str] = None
    source_price: Optional[float] = None
    source_price_observed_at: Optional[str] = None
    source_pack_text: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "asin": self.asin,
            "costco_source_product_id": self.costco_source_product_id,
            "identity_state": self.identity_state,
            "split_pack_state": self.split_pack_state,
            "competition_state": self.competition_state,
            "recommendation_status": self.recommendation_status,
            "reason_codes": list(self.reason_codes),
            "risk_flags": list(self.risk_flags),
            "economics": dict(self.economics),
            "market_snapshot": self.market_snapshot,
            "mfn_score": self.mfn_score,
            "mfn_score_version": self.mfn_score_version,
            "evidence_summary": self.evidence_summary,
            "purchase_authorization_status": self.purchase_authorization_status,
            "source_name": self.source_name,
            "source_sku": self.source_sku,
            "source_url": self.source_url,
            "source_price": self.source_price,
            "source_price_observed_at": self.source_price_observed_at,
            "source_pack_text": self.source_pack_text,
        }


# ---------------------------------------------------------------------------
# Recommendation decision
# ---------------------------------------------------------------------------

def decide_candidate(
    *,
    candidate_id: str,
    asin: str,
    source: Dict[str, Any],
    market_snapshot: Dict[str, Any],
    settings: Optional[Dict[str, Any]] = None,
    source_repeatability: float = 0.8,
) -> CandidateDecision:
    """Produce a deterministic candidate decision.

    `source` is a normalized costco_source_product dict.
    `market_snapshot` is a canonical provider market-snapshot dict.
    """
    st = get_settings(settings)
    min_net_profit = float(st.get("minimum_net_profit", 5.00))
    min_roi = float(st.get("minimum_roi_pct", 30.0))
    qualified_profit = float(st.get("qualified_net_profit", 11.00))
    priority_profit = float(st.get("priority_net_profit", 20.00))

    # --- identity -----------------------------------------------------------
    identity = assess_identity(source, _listing_from_snapshot(market_snapshot),
                               provider_reported=True, settings=settings)

    # --- split-pack ---------------------------------------------------------
    split = evaluate_split_pack(source, _listing_from_snapshot(market_snapshot), settings=settings)

    # --- competition --------------------------------------------------------
    competition = assess_competition(market_snapshot, identity_state=identity.state,
                                      settings=settings)

    decision = CandidateDecision(
        candidate_id=candidate_id,
        asin=asin,
        costco_source_product_id=source.get("id"),
        identity_state=identity.state,
        split_pack_state=split.value,
        competition_state=competition.state,
        market_snapshot=market_snapshot,
        source_name=source.get("source_name"),
        source_sku=source.get("costco_item_number") or source.get("source_record_id"),
        source_url=source.get("source_url"),
        source_price=source.get("costco_price"),
        source_price_observed_at=source.get("observed_at"),
        source_pack_text=source.get("costco_pack_raw"),
    )

    # --- hard blockers -------------------------------------------------------
    if identity.state in (IdentityState.PACK_MISMATCH.value,
                          IdentityState.VARIATION_MISMATCH.value,
                          IdentityState.BRAND_MISMATCH.value,
                          IdentityState.IDENTIFIER_MISMATCH.value,
                          IdentityState.NO_MATCH.value):
        decision.recommendation_status = OperationalRecommendation.BLOCKED.value
        decision.reason_codes = ["blocked_identity"]
        decision.risk_flags = [f"identity_{identity.state}"]
        decision.evidence_summary = f"Blocked: identity {identity.state}."
        return decision

    if identity.state in (IdentityState.MANUAL_REVIEW_REQUIRED.value,
                          IdentityState.TITLE_PACK_CANDIDATE.value):
        decision.recommendation_status = OperationalRecommendation.MANUAL_REVIEW_REQUIRED.value
        decision.reason_codes = ["manual_review"]
        decision.risk_flags = [f"identity_{identity.state}"]
        decision.evidence_summary = "Identity requires manual review (not exact)."
        return decision

    if split.value == SplitPackState.PROHIBITED_SPLIT.value:
        decision.recommendation_status = OperationalRecommendation.BLOCKED.value
        decision.reason_codes = ["blocked_split_pack"]
        decision.risk_flags = ["prohibited_split"]
        decision.evidence_summary = "Blocked: prohibited split-pack."
        return decision
    if split.value == SplitPackState.MANUAL_REVIEW_REQUIRED.value:
        decision.recommendation_status = OperationalRecommendation.MANUAL_REVIEW_REQUIRED.value
        decision.reason_codes = ["manual_review_split"]
        decision.evidence_summary = "Split-pack requires manual review."
        return decision

    # --- competition --------------------------------------------------------
    if competition.state == COMPETITION_PASS:
        pass
    elif competition.state == "block":
        decision.recommendation_status = OperationalRecommendation.BLOCKED.value
        decision.reason_codes = list(competition.reason_codes)
        decision.risk_flags = list(competition.blocked_flags)
        decision.evidence_summary = "Blocked: competition requirements not met."
        return decision
    else:  # needs_enrichment / manual_review
        decision.recommendation_status = OperationalRecommendation.NEEDS_ENRICHMENT.value
        decision.reason_codes = list(competition.reason_codes) or ["needs_enrichment"]
        decision.risk_flags = list(competition.missing_fields)
        decision.evidence_summary = "Needs enrichment: unknown/incomplete marketplace fields."
        return decision

    # --- conservative economics ----------------------------------------------
    econ = _compute_conservative(source, market_snapshot, settings=st)
    decision.economics = econ

    if econ.get("economics_completeness") != "complete":
        decision.recommendation_status = OperationalRecommendation.NEEDS_ENRICHMENT.value
        decision.reason_codes = ["needs_enrichment_economics"]
        decision.risk_flags = list(econ.get("missing_inputs", []))
        decision.evidence_summary = "Needs enrichment: incomplete economics."
        return decision

    net_profit = econ.get("net_profit")
    roi = econ.get("roi_percent")
    if net_profit is None or roi is None:
        decision.recommendation_status = OperationalRecommendation.NEEDS_ENRICHMENT.value
        decision.reason_codes = ["needs_enrichment_economics"]
        decision.evidence_summary = "Needs enrichment: missing net profit/ROI."
        return decision

    # --- mfn opportunity score ----------------------------------------------
    demand = market_snapshot.get("demand", {})
    est_sales = demand.get("estimated_monthly_sales")
    price_stability = market_snapshot.get("marketplace", {}).get("price_stability")
    weight = market_snapshot.get("size", {}).get("shipping_weight_lb")
    std_size = market_snapshot.get("size", {}).get("standard_size_status")
    low_weight = (weight is not None and weight <= float(st.get("maximum_shipping_weight_lb", 3.0)))
    std_ok = (std_size is True) or (weight is not None and low_weight)

    score_result = mfn_opportunity_score(
        net_profit=net_profit, roi_pct=roi,
        demand_signal=est_sales if est_sales is not None else None,
        mfn_competition_quality=0.9,  # pass-state: provider-confirmed composition
        zero_fba=True,
        low_weight_standard_size=bool(std_ok),
        price_stability=price_stability if isinstance(price_stability, (int, float)) else None,
        source_repeatability=source_repeatability,
        settings=settings,
    )
    decision.mfn_score = score_result["score"]
    decision.mfn_score_version = score_result["score_version"]

    # --- recommendation ------------------------------------------------------
    if net_profit >= priority_profit and roi >= min_roi:
        decision.recommendation_status = OperationalRecommendation.PRIORITY_CANDIDATE.value
        decision.reason_codes = ["priority"]
    elif net_profit >= qualified_profit and roi >= min_roi:
        decision.recommendation_status = OperationalRecommendation.QUALIFIED_CANDIDATE.value
        decision.reason_codes = ["qualified"]
    elif net_profit >= min_net_profit and roi >= min_roi:
        decision.recommendation_status = OperationalRecommendation.TEST_BUY_CANDIDATE.value
        decision.reason_codes = ["test_buy"]
    else:
        decision.recommendation_status = OperationalRecommendation.WATCHLIST.value
        decision.reason_codes = ["watchlist_below_threshold"]

    decision.evidence_summary = (
        f"Identity {decision.identity_state}; split {decision.split_pack_state}; "
        f"net profit ${net_profit:.2f}; ROI {roi:.1f}%."
    )
    return decision


def _compute_conservative(source: Dict[str, Any], market: Dict[str, Any], settings: Dict[str, Any]) -> Dict[str, Any]:
    """Conservative economics using the canonical engine."""
    marketplace = market.get("marketplace", {})
    fees = market.get("fees", {})
    size = market.get("size", {})

    price_result = conservative_sale_price(
        buy_box_price=marketplace.get("buy_box_price"),
        price_history_midpoint=marketplace.get("price_history_midpoint"),
        price_history_observed_at=marketplace.get("price_history_observed_at"),
        market_snapshot_max_age_minutes=int(settings.get("market_snapshot_max_age_minutes", 60)),
        price_history_max_age_hours=int(settings.get("price_history_max_age_hours", 24)),
        stability_floor_pct=float(settings.get("historical_price_stability_floor_pct", 0.90)),
        settings=settings,
    )
    sale_price = price_result.get("price")

    source_cost = source.get("costco_price")
    referral_rate = fees.get("referral_fee_rate") or settings.get("referral_fee_rate")
    fba_fee = fees.get("fba_fulfillment_fee")

    econ = compute_economics(
        cost_basis=source_cost,
        cost_basis_source="costco_discovery",
        cost_basis_status="discovery_only",
        sale_price=sale_price,
        sale_price_source=price_result.get("source"),
        identity_status="upc_exact_candidate",
        pack_verified=True,
        sales_tax_rate=settings.get("source_sales_tax_rate"),
        prep_cost=settings.get("prep_cost"),
        inbound_shipping_cost=settings.get("inbound_shipping_cost"),
        referral_fee_rate=referral_rate,
        fba_fee=fba_fee,
        storage_allowance=settings.get("storage_allowance"),
        returns_reserve_rate=settings.get("returns_allowance_rate"),
        fee_source="provider_export",
        fee_status="provider_reported" if (referral_rate is not None and fba_fee is not None) else "incomplete",
        assumptions=[] if (referral_rate is not None and fba_fee is not None) else ["missing provider fee inputs"],
    )
    out = econ.to_dict()
    out["conservative_sale_price_result"] = price_result
    out["maximum_buy_cost"] = maximum_buy_cost(
        sale_price=sale_price,
        target_roi=float(settings.get("minimum_roi_pct", 30.0)) / 100,
        settings=settings,
        referral_fee_rate=referral_rate,
        fba_fee=fba_fee,
    )
    return out


def _listing_from_snapshot(market: Dict[str, Any]) -> Dict[str, Any]:
    """Extract Amazon listing attributes from a canonical market snapshot."""
    identity = market.get("identity", {})
    size = market.get("size", {})
    return {
        "asin": market.get("asin") or identity.get("asin"),
        "brand": identity.get("brand"),
        "title": identity.get("title"),
        "upc": identity.get("upc"),
        "ean": identity.get("ean"),
        "gtin": None,
        "mpn": identity.get("mpn"),
        "model": identity.get("model"),
        "manufacturer": identity.get("manufacturer"),
        "item_count": identity.get("item_count"),
        "pack_count": identity.get("pack_count"),
        "unit_count": identity.get("unit_count"),
        "unit_measure": identity.get("unit_measure"),
        "variation_theme": identity.get("variation_theme"),
        "selected_variation": identity.get("selected_variation"),
        "unit_size": None,
        "shipping_weight_lb": size.get("shipping_weight_lb"),
    }


def persist_decision(decision: CandidateDecision, store: Optional[PipelineStore] = None) -> str:
    store = store or PipelineStore()
    return store.upsert_candidate_decision(decision.to_dict())