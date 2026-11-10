"""Candidate qualification: hard disqualifiers, scoring, and opportunity state.

PURE / OFFLINE. Implements docs/northstar-faire-discovery/09-scoring-model.md
and the compliance posture in 01-policy-and-compliance.md.

Core compliance rule: **Faire is a DISCOVERY source only.** A candidate can
never be SOURCE_READY on a Faire route, and Faire wholesale pricing is a
DISCOVERY_BENCHMARK_ONLY — never a compliant Amazon sourcing price.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import List, Optional, Tuple

from .enums import (
    BrandRiskState,
    EligibilityState,
    MatchConfidence,
    MarketplacePermission,
    OpportunityState,
    PackConfiguration,
    ProvenanceClass,
)
from .economics import EconomicsResult

FAIRE_SOURCING_LABEL = "DISCOVERY_BENCHMARK_ONLY — AMAZON RESALE THROUGH FAIRE NOT AUTHORIZED"


@dataclass
class CandidateAssessment:
    org_id: str = ""
    source: str = "faire"
    provenance: ProvenanceClass = ProvenanceClass.UNKNOWN
    captured_at: Optional[str] = None
    confidence: Optional[float] = None
    stale: bool = False

    # identity / match
    match_confidence: MatchConfidence = MatchConfidence.INSUFFICIENT_DATA
    pack_mismatch_unresolved: bool = False
    pack_configuration: PackConfiguration = PackConfiguration.PACK_CONFIGURATION_UNKNOWN

    # economics
    economics: Optional[EconomicsResult] = None

    # risk / authorization
    faire_is_only_sourcing_route: bool = True
    brand_permission: MarketplacePermission = MarketplacePermission.UNKNOWN
    eligibility: EligibilityState = EligibilityState.ELIGIBILITY_UNKNOWN
    brand_risk: BrandRiskState = BrandRiskState.UNKNOWN
    direct_supplier_verified: bool = False
    invoice_path_ready: bool = False

    # operational
    exceeds_weight_or_dimensions: bool = False
    hazmat_expiration_meltable_over_tolerance: bool = False
    amazon_retail_or_brand_dominance: bool = False
    ip_enforcement_vulnerable: bool = False
    case_break_terms_violation: bool = False

    notes: List[str] = field(default_factory=list)


HARD_DISQUALIFIER_LABELS = [
    "faire_is_only_sourcing_route",
    "brand_prohibits_amazon",
    "direct_supplier_prohibits_amazon",
    "amazon_eligibility_restricted_or_not_eligible",
    "exact_match_failed",
    "pack_mismatch_unresolved",
    "invoice_path_absent",
    "product_authenticity_uncertain",
    "required_cost_or_fee_missing",
    "contribution_profit_non_positive",
    "exceeds_weight_or_dimensions",
    "hazmat_expiration_meltable_over_tolerance",
    "amazon_retail_or_brand_dominance",
    "ip_enforcement_or_detail_page_mismatch",
    "case_break_terms_violation",
]


def hard_disqualifiers(a: CandidateAssessment) -> List[str]:
    """Return the list of triggered hard disqualifiers. Empty == not disqualified."""
    d: List[str] = []
    if a.faire_is_only_sourcing_route:
        d.append("faire_is_only_sourcing_route")
    if a.brand_permission == MarketplacePermission.NO:
        d.append("brand_prohibits_amazon")
    if a.brand_risk in (BrandRiskState.BRAND_POLICY_RESTRICTS_MARKETPLACES,):
        d.append("direct_supplier_prohibits_amazon")
    if a.eligibility in (EligibilityState.RESTRICTED, EligibilityState.NOT_ELIGIBLE):
        d.append("amazon_eligibility_restricted_or_not_eligible")
    if a.match_confidence in (MatchConfidence.MISMATCH, MatchConfidence.INSUFFICIENT_DATA,
                              MatchConfidence.AMBIGUOUS):
        d.append("exact_match_failed")
    if a.pack_mismatch_unresolved:
        d.append("pack_mismatch_unresolved")
    if not a.invoice_path_ready:
        d.append("invoice_path_absent")
    # economics None == not-yet-computed (routes to ECONOMICS_INCOMPLETE, not a
    # hard reject). economics present but unresolved (missing required inputs)
    # and non-positive profit are hard disqualifiers.
    if a.economics is not None and not a.economics.resolved:
        d.append("required_cost_or_fee_missing")
    if a.economics is not None and a.economics.resolved and a.economics.contribution_profit is not None and a.economics.contribution_profit <= 0:
        d.append("contribution_profit_non_positive")
    if a.exceeds_weight_or_dimensions:
        d.append("exceeds_weight_or_dimensions")
    if a.hazmat_expiration_meltable_over_tolerance:
        d.append("hazmat_expiration_meltable_over_tolerance")
    if a.amazon_retail_or_brand_dominance:
        d.append("amazon_retail_or_brand_dominance")
    if a.ip_enforcement_vulnerable:
        d.append("ip_enforcement_or_detail_page_mismatch")
    if a.case_break_terms_violation:
        d.append("case_break_terms_violation")
    return d


# score components (must sum to 100)
SCORE_COMPONENTS = {
    "verified_profit_and_roi": 20,
    "size_weight_fba_burden": 15,
    "marketplace_eligibility_authorization": 15,
    "direct_supplier_invoice_readiness": 15,
    "demand_evidence": 10,
    "competition_quality": 10,
    "price_stability": 5,
    "replenishment_quality": 5,
    "operational_simplicity": 5,
}


def score(a: CandidateAssessment, *, components: Optional[dict] = None) -> Tuple[int, dict]:
    """Transparent 0-100 score. `components` supplies earned fractions [0..1]
    per component; missing components earn 0 (never assumed)."""
    comps = components or {}
    earned = {}
    total = 0
    for name, weight in SCORE_COMPONENTS.items():
        frac = comps.get(name)
        frac = 0.0 if frac is None else max(0.0, min(1.0, float(frac)))
        pts = int(round(weight * frac))
        earned[name] = {"weight": weight, "fraction": frac, "points": pts}
        total += pts
    return total, earned


def derive_state(a: CandidateAssessment, score_value: Optional[int] = None) -> OpportunityState:
    """State machine. Hard disqualifiers first; never jumps to purchase."""
    if hard_disqualifiers(a):
        return OpportunityState.REJECTED
    if a.match_confidence in (MatchConfidence.PROBABLE_MATCH_REVIEW_REQUIRED,):
        return OpportunityState.MATCH_REVIEW
    if a.economics is None or not a.economics.resolved:
        return OpportunityState.ECONOMICS_INCOMPLETE
    if a.brand_permission != MarketplacePermission.YES:
        return OpportunityState.AUTHORIZATION_REQUIRED
    if a.eligibility != EligibilityState.ELIGIBLE_CONFIRMED:
        return OpportunityState.ELIGIBILITY_CHECK_REQUIRED
    if not a.direct_supplier_verified:
        return OpportunityState.DIRECT_SUPPLIER_RESEARCH
    # Direct supplier verified + authorization + eligibility + economics ok
    return OpportunityState.QUALIFIED_FOR_MANUAL_REVIEW


def can_be_source_ready(a: CandidateAssessment) -> Tuple[bool, List[str]]:
    """SOURCE_READY requires a verified direct supplier and no disqualifiers."""
    reasons = hard_disqualifiers(a)
    if a.economics is None or not a.economics.resolved:
        reasons.append("economics_incomplete")
    if not a.direct_supplier_verified:
        reasons.append("direct_supplier_not_verified")
    return (not reasons), reasons


def can_be_purchase_ready(a: CandidateAssessment) -> Tuple[bool, List[str]]:
    """PURCHASE_READY requires everything in SOURCE_READY plus eligibility,
    authorization, exact pack match, complete fees/costs and operator approval."""
    reasons = hard_disqualifiers(a)
    if a.economics is None or not a.economics.resolved:
        reasons.append("economics_incomplete")
    if a.eligibility != EligibilityState.ELIGIBLE_CONFIRMED:
        reasons.append("eligibility_not_confirmed")
    if a.brand_permission != MarketplacePermission.YES:
        reasons.append("brand_authorization_not_confirmed")
    if not a.direct_supplier_verified:
        reasons.append("direct_supplier_not_verified")
    if a.pack_mismatch_unresolved:
        reasons.append("pack_mismatch_unresolved")
    return (not reasons), reasons
