"""Golden Goose scoring for eligible non-Kirkland Costco candidates.

PURE / OFFLINE / VERSIONED / EXPLAINABLE. Scores ONLY candidates that are:
  * eligible for the Costco non-Kirkland workflow (not Kirkland-excluded), AND
  * have an Amazon match candidate.

A numeric score NEVER authorizes purchasing. `purchase_authorization_status`
is always `not_authorized`; no automated path can change that.

The scoring model is a weighted composite with hard blockers and penalties,
mirroring the existing Golden Goose scorer conventions in this repo but
scoped to the Costco non-Kirkland pipeline.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .enums import (
    RecommendationStatus,
    PURCHASE_AUTHORIZATION_NOT_AUTHORIZED,
    RiskFlag,
)

GG_SCORER_VERSION = "golden-goose-costco-nonkirkland-1.0.0"

# Weighted positive signals (defaults). Sum = 1.0.
DEFAULT_WEIGHTS = {
    "demand": 0.25,
    "bsr_stability": 0.15,
    "price_stability": 0.10,
    "margin": 0.25,
    "roi": 0.10,
    "competition": 0.05,
    "pack_identity": 0.05,
    "replenishment": 0.05,
}

# Default positive-signal thresholds (documented).
DEFAULT_THRESHOLDS = {
    "min_monthly_sales": 5000.0,
    "min_net_margin_percent": 20.0,
    "min_roi_percent": 25.0,
    "competition_max_sellers": 10,
    "confidence_threshold": 0.7,
}


@dataclass
class GoldenGooseScore:
    score: Optional[float] = None
    score_version: str = GG_SCORER_VERSION
    score_components: Dict[str, Any] = field(default_factory=dict)
    positive_evidence: List[str] = field(default_factory=list)
    penalties: List[str] = field(default_factory=list)
    risk_flags: List[str] = field(default_factory=list)
    missing_evidence: List[str] = field(default_factory=list)
    confidence_level: str = "low"
    recommendation_status: str = RecommendationStatus.RESEARCH_REQUIRED.value
    purchase_authorization_status: str = PURCHASE_AUTHORIZATION_NOT_AUTHORIZED
    manual_review_required: bool = True
    evidence_summary: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "score": self.score,
            "score_version": self.score_version,
            "score_components": dict(self.score_components),
            "positive_evidence": list(self.positive_evidence),
            "penalties": list(self.penalties),
            "risk_flags": list(self.risk_flags),
            "missing_evidence": list(self.missing_evidence),
            "confidence_level": self.confidence_level,
            "recommendation_status": self.recommendation_status,
            "purchase_authorization_status": self.purchase_authorization_status,
            "manual_review_required": bool(self.manual_review_required),
            "evidence_summary": self.evidence_summary,
        }


# ---------------------------------------------------------------------------
# Hard blockers
# ---------------------------------------------------------------------------

def _hard_blockers(*, eligible: bool, identity_status: str, pack_verified: Optional[bool],
                   economics_completeness: str, stale: bool) -> List[str]:
    blockers: List[str] = []
    if not eligible:
        blockers.append("KIRKLAND_SOURCE")
    if identity_status in ("identity_conflict", "pack_mismatch", "size_mismatch"):
        blockers.append("IDENTITY_MISMATCH")
    if identity_status == "variation_ambiguous":
        blockers.append("VARIATION_AMBIGUITY")
    if stale:
        blockers.append("STALE_DATA")
    if economics_completeness in ("not_calculated", "blocked_identity_mismatch"):
        blockers.append("MISSING_ECONOMICS")
    if pack_verified is not True:
        blockers.append("PACK_UNVERIFIED")
    return blockers


def _blocked_status(blockers: List[str]) -> str:
    if "IDENTITY_MISMATCH" in blockers or "VARIATION_AMBIGUITY" in blockers:
        return RecommendationStatus.BLOCKED_IDENTITY_MISMATCH.value
    if "MISSING_ECONOMICS" in blockers:
        return RecommendationStatus.BLOCKED_INCOMPLETE_ECONOMICS.value
    return RecommendationStatus.BLOCKED_COMPLIANCE_RISK.value


# ---------------------------------------------------------------------------
# Positive signal scoring (0..1 each)
# ---------------------------------------------------------------------------

def _demand_score(est_monthly_sales: Optional[float], thresholds) -> float:
    if est_monthly_sales is None:
        return 0.0
    t = thresholds["min_monthly_sales"]
    if est_monthly_sales <= 0:
        return 0.0
    # log-interpolate: 0 -> 0, target -> 0.5, 5x target -> 1.0
    import math
    if est_monthly_sales >= 5 * t:
        return 1.0
    if est_monthly_sales >= t:
        return 0.5 + 0.5 * (est_monthly_sales - t) / (4 * t)
    return 0.5 * (est_monthly_sales / t)


def _margin_score(net_margin_percent: Optional[float], thresholds) -> float:
    if net_margin_percent is None:
        return 0.0
    t = thresholds["min_net_margin_percent"]
    if net_margin_percent <= 0:
        return 0.0
    if net_margin_percent >= 2 * t:
        return 1.0
    if net_margin_percent >= t:
        return 0.5 + 0.5 * (net_margin_percent - t) / t
    return 0.5 * (net_margin_percent / t)


def _roi_score(roi_percent: Optional[float], thresholds) -> float:
    if roi_percent is None:
        return 0.0
    t = thresholds["min_roi_percent"]
    if roi_percent >= 3 * t:
        return 1.0
    if roi_percent >= t:
        return 0.5 + 0.5 * (roi_percent - t) / (2 * t)
    if roi_percent > 0:
        return 0.5 * (roi_percent / t)
    return 0.0


def _competition_score(seller_count: Optional[int], thresholds) -> float:
    if seller_count is None:
        return 0.0
    if seller_count <= 0:
        return 1.0
    if seller_count == 1:
        return 0.9
    if seller_count <= 3:
        return 0.7
    if seller_count <= 6:
        return 0.5
    if seller_count <= thresholds.get("competition_max_sellers", 10):
        return 0.3
    return 0.1


def _bsr_stability_score(bsr_trend: Optional[str]) -> float:
    """bsr_trend: 'improving' | 'stable' | 'declining' | None."""
    if bsr_trend is None:
        return 0.0
    return {"improving": 1.0, "stable": 0.8, "declining": 0.2}.get(bsr_trend, 0.0)


def _price_stability_score(price_trend: Optional[str]) -> float:
    """price_trend: 'improving' | 'stable' | 'declining' | None."""
    if price_trend is None:
        return 0.0
    return {"improving": 1.0, "stable": 0.8, "declining": 0.3}.get(price_trend, 0.0)


def _pack_identity_score(identity_status: str, pack_verified: Optional[bool]) -> float:
    if pack_verified is True or identity_status == "verified_exact_pack_match":
        return 1.0
    if identity_status in ("upc_exact_candidate", "manufacturer_part_exact_candidate"):
        return 0.7
    return 0.0


def _replenishment_score(est_monthly_sales: Optional[float]) -> float:
    if est_monthly_sales is None:
        return 0.0
    return 1.0 if est_monthly_sales >= 5000 else 0.5 if est_monthly_sales >= 1000 else 0.2


# ---------------------------------------------------------------------------
# Penalties
# ---------------------------------------------------------------------------

_PENALTY_RULES = {
    "BUY_BOX_RISK": ("buy_box_risk_observed", 0.15, RiskFlag.BUY_BOX_RISK.value),
    "EXCESSIVE_COMPETITION": ("excessive_competition", 0.10, RiskFlag.EXCESSIVE_COMPETITION.value),
    "HAZARDOUS": ("hazardous", 0.30, RiskFlag.HAZARDOUS.value),
    "MELTABLE": ("meltable", 0.15, RiskFlag.MELTABLE.value),
    "FRAGILE": ("fragile", 0.10, RiskFlag.FRAGILE.value),
    "EXPIRY": ("expiry_risk", 0.25, RiskFlag.EXPIRY.value),
    "OVERSIZED": ("oversized", 0.15, RiskFlag.OVERSIZED.value),
    "GATED_UNKNOWN": ("gated_uncertainty", 0.20, RiskFlag.GATED_UNKNOWN.value),
    "INVOICE_READINESS_UNKNOWN": ("invoice_readiness_unknown", 0.15, RiskFlag.INVOICE_READINESS_UNKNOWN.value),
    "RETAIL_RECEIPT_ONLY": ("costco_retail_receipt_only", 0.20, RiskFlag.RETAIL_RECEIPT_ONLY.value),
    "SUPPLY_BOTTLENECK": ("supply_bottleneck", 0.20, RiskFlag.SUPPLY_BOTTLENECK.value),
    "SINGLE_ASIN_CONCENTRATION": ("single_asin_concentration", 0.15, RiskFlag.SINGLE_ASIN_CONCENTRATION.value),
    "ONE_SOURCE_ONLY": ("one_source_only_evidence", 0.10, RiskFlag.ONE_SOURCE_ONLY.value),
}


def score_golden_goose(
    *,
    eligible: bool,
    identity_status: str,
    pack_verified: Optional[bool],
    economics_completeness: str,
    economics: Optional[Dict[str, Any]] = None,
    selleramp: Optional[Dict[str, Any]] = None,
    stale: bool = False,
    bsr_trend: Optional[str] = None,
    price_trend: Optional[str] = None,
    seller_count: Optional[int] = None,
    risk_hints: Optional[Dict[str, bool]] = None,
    weights: Optional[Dict[str, float]] = None,
    thresholds: Optional[Dict[str, float]] = None,
) -> GoldenGooseScore:
    """Score one eligible candidate. Always `purchase_authorization_status=not_authorized`."""
    weights = dict(DEFAULT_WEIGHTS if weights is None else weights)
    thresholds = dict(DEFAULT_THRESHOLDS if thresholds is None else thresholds)
    risk_hints = risk_hints or {}

    est_sales = None
    if selleramp and selleramp.get("estimated_monthly_sales") is not None:
        est_sales = float(selleramp["estimated_monthly_sales"])

    econ = economics or {}
    net_margin_pct = econ.get("net_margin_percent")
    roi_pct = econ.get("roi_percent")

    # --- blockers ---------------------------------------------------------
    blockers = _hard_blockers(
        eligible=eligible, identity_status=identity_status,
        pack_verified=pack_verified, economics_completeness=economics_completeness,
        stale=stale,
    )
    if blockers:
        return GoldenGooseScore(
            score=None, score_components={},
            positive_evidence=[], penalties=[], risk_flags=blockers,
            missing_evidence=[],
            confidence_level="low",
            recommendation_status=_blocked_status(blockers),
            manual_review_required=True,
            evidence_summary=f"Blocked: {', '.join(blockers)}. No score computed.",
        )

    # --- components ---------------------------------------------------------
    comps = {
        "demand": _demand_score(est_sales, thresholds),
        "bsr_stability": _bsr_stability_score(bsr_trend),
        "price_stability": _price_stability_score(price_trend),
        "margin": _margin_score(net_margin_pct, thresholds),
        "roi": _roi_score(roi_pct, thresholds),
        "competition": _competition_score(seller_count, thresholds),
        "pack_identity": _pack_identity_score(identity_status, pack_verified),
        "replenishment": _replenishment_score(est_sales),
    }
    total_w = sum(weights.values()) or 1.0
    base = sum(comps[k] * weights.get(k, 0.0) for k in comps) / total_w

    # --- penalties ---------------------------------------------------------
    penalties: List[str] = []
    risk_flags: List[str] = []
    penalty_total = 0.0
    for key, (hint_key, penalty, flag) in _PENALTY_RULES.items():
        if risk_hints.get(hint_key):
            penalties.append(f"{key}: {penalty:.2f}")
            risk_flags.append(flag)
            penalty_total += penalty
    score = max(0.0, min(1.0, round(base - penalty_total, 4)))

    # --- positive evidence / missing --------------------------------------
    positive: List[str] = []
    missing: List[str] = []
    if est_sales is not None and est_sales >= thresholds["min_monthly_sales"]:
        positive.append(f"provider-estimated demand {est_sales:.0f}/mo >= {thresholds['min_monthly_sales']:.0f}")
    else:
        missing.append("credible demand estimate (5k+/mo)")
    if net_margin_pct is not None and net_margin_pct >= thresholds["min_net_margin_percent"]:
        positive.append(f"net margin {net_margin_pct:.1f}% >= {thresholds['min_net_margin_percent']:.0f}%")
    else:
        missing.append("fully modeled net margin >= 20%")
    if roi_pct is not None and econ.get("economics_completeness") == "complete":
        positive.append(f"ROI {roi_pct:.1f}% with complete economics")
    else:
        missing.append("ROI with complete economics")
    if bsr_trend in ("stable", "improving"):
        positive.append(f"BSR {bsr_trend}")
    else:
        missing.append("stable/improving BSR")
    if price_trend in ("stable", "improving"):
        positive.append(f"price {price_trend}")
    else:
        missing.append("stable/improving price history")
    if identity_status == "verified_exact_pack_match" or pack_verified is True:
        positive.append("exact pack identity")
    else:
        missing.append("verified exact pack identity")

    # --- confidence / recommendation --------------------------------------
    avail_count = sum(1 for k in comps if comps[k] > 0 or k in ("competition",))
    confidence = round(avail_count / max(1, len(comps)), 2)
    confidence_level = "high" if confidence >= thresholds.get("confidence_threshold", 0.7) else "medium" if confidence >= 0.4 else "low"

    if score >= 0.6 and confidence >= 0.6:
        rec = RecommendationStatus.HIGH_PRIORITY_REVIEW.value
    elif score >= 0.45:
        rec = RecommendationStatus.WATCHLIST.value
    elif score >= 0.25:
        rec = RecommendationStatus.CANDIDATE.value
    else:
        rec = RecommendationStatus.REJECTED.value

    return GoldenGooseScore(
        score=score, score_components=comps,
        positive_evidence=positive, penalties=penalties, risk_flags=risk_flags,
        missing_evidence=missing, confidence_level=confidence_level,
        recommendation_status=rec,
        purchase_authorization_status=PURCHASE_AUTHORIZATION_NOT_AUTHORIZED,
        manual_review_required=True,
        evidence_summary=("Score computed from cached/estimate evidence only. "
                          "Not purchase authorization."),
    )