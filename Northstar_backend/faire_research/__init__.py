"""Northstar Faire-to-Amazon discovery research — OFFLINE (MODE 1) layer.

STATUS / GATES
--------------
This package is a **design + integration contract with the offline research
implementation only**. It is deliberately bounded by the current Northstar
phase gates:

  * Canonical economics engine (Phase 1C 1C-04) — NOT built. This package
    uses a clearly-labeled TEMPORARY research economics adapter
    (`economics.py`). Do not extend it into a second permanent universe.
  * Job worker / scheduler (1C-03) — NOT built. Live research jobs cannot run.
  * Real auth (1C-01) — dev shim only. All records are org-scoped by contract.
  * Keyword module (1C-07) / provider live adapters — NOT built.

Therefore only MODE 1 (OFFLINE) is implemented. MODE 2/3/4 are contracts
(see docs/northstar-faire-discovery/). This package never contacts Faire,
Amazon, or any provider, and never purchases, lists, or contacts suppliers.

COMPLIANCE
----------
Faire is a PRODUCT AND BRAND DISCOVERY SOURCE ONLY. No Faire-sourced
merchandise is approved for Amazon resale. Faire wholesale prices are
DISCOVERY_BENCHMARK_ONLY.
"""

from __future__ import annotations

from .economics import (
    DEFAULT_MIN_CONTRIBUTION_PROFIT,
    DEFAULT_MIN_MARGIN_PCT,
    DEFAULT_MIN_ROI_PCT,
    EconomicsResult,
    FeeConfidence,
    FeeInputs,
    LandedCostInputs,
    contribution_profit,
    downside_scenarios,
    landed_unit_cost,
)
from .enums import (
    BrandRiskState,
    EligibilityState,
    FeeConfidence as FeeConfidenceEnum,
    MatchConfidence,
    MarketplacePermission,
    OpportunityState,
    PackConfiguration,
    ProvenanceClass,
    ResearchMode,
)
from .matching import (
    ProductAttributes,
    assess_match,
    case_break_allowed,
    pack_configuration,
)
from .qualification import (
    FAIRE_SOURCING_LABEL,
    CandidateAssessment,
    can_be_purchase_ready,
    can_be_source_ready,
    derive_state,
    hard_disqualifiers,
    score,
)

__all__ = [
    "ResearchMode", "ProvenanceClass", "MatchConfidence", "EligibilityState",
    "BrandRiskState", "FeeConfidence", "PackConfiguration", "MarketplacePermission",
    "OpportunityState", "FeeInputs", "LandedCostInputs", "EconomicsResult",
    "landed_unit_cost", "contribution_profit", "downside_scenarios",
    "DEFAULT_MIN_CONTRIBUTION_PROFIT", "DEFAULT_MIN_ROI_PCT", "DEFAULT_MIN_MARGIN_PCT",
    "ProductAttributes", "assess_match", "pack_configuration", "case_break_allowed",
    "CandidateAssessment", "hard_disqualifiers", "score", "derive_state",
    "can_be_source_ready", "can_be_purchase_ready", "FAIRE_SOURCING_LABEL",
]
