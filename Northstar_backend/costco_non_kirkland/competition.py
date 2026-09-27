"""Marketplace competition filter (Phase 5) — provider-only seller composition.

PURE / OFFLINE. A candidate may only enter qualified/test-buy recommendation
state if all required marketplace conditions are provider-reported, fresh, and
complete. All unknowns block qualification and produce needs_enrichment or
manual_review_required.

Default required rules:
  Amazon Retail active:              must be explicitly false
  Brand owner seller active:         must be explicitly false when identifiable
  Active FBA seller count:           must be explicitly 0
  Active MFN seller count:           must be explicitly >= minimum_active_mfn_sellers
  Buy Box / expected sale price:     required
  Seller count evidence freshness:   required
  Exact listing identity:            required
  ASIN sellability status:           must be eligible / sellable
  Restriction status:                must be unrestricted

Scoring: mfn_opportunity_score_v1 — applied only after hard blockers pass.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .enums import OperationalRecommendation
from .settings import get_settings

SCORE_VERSION = "mfn_opportunity_score_v1"

# Competition state outcomes
COMPETITION_PASS = "pass"
COMPETITION_BLOCK = "block"
COMPETITION_NEEDS_ENRICHMENT = "needs_enrichment"
COMPETITION_MANUAL_REVIEW = "manual_review_required"

UNKNOWN = "unknown"
NOT_REPORTED = "not_reported"
NOT_AVAILABLE = "not_available_in_export"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _is_unknown(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and value.strip().lower() in ("unknown", "not_reported",
                                                            "not_available_in_export", "requires_manual_review"):
        return True
    return False


def _age_minutes(observed_at: Optional[str]) -> Optional[float]:
    if not observed_at:
        return None
    try:
        dt = datetime.fromisoformat(str(observed_at).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - dt).total_seconds() / 60.0
    except (ValueError, TypeError):
        return None


def _sellable(status: Optional[str]) -> bool:
    if status is None:
        return False
    return str(status).strip().lower() in ("eligible", "sellable", "active", "ok")


def _unrestricted(value: Optional[str]) -> bool:
    if value is None:
        return False
    return str(value).strip().lower() in ("no", "none", "false", "unrestricted", "not restricted", "eligible")


@dataclass
class CompetitionAssessment:
    state: str
    reason_codes: List[str] = field(default_factory=list)
    missing_fields: List[str] = field(default_factory=list)
    blocked_flags: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)
    amazon_retail_active: Optional[bool] = None
    brand_owner_seller_active: Optional[bool] = None
    active_fba_sellers: Optional[int] = None
    active_mfn_sellers: Optional[int] = None
    buy_box_price: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "state": self.state,
            "reason_codes": list(self.reason_codes),
            "missing_fields": list(self.missing_fields),
            "blocked_flags": list(self.blocked_flags),
            "notes": list(self.notes),
            "amazon_retail_active": self.amazon_retail_active,
            "brand_owner_seller_active": self.brand_owner_seller_active,
            "active_fba_sellers": self.active_fba_sellers,
            "active_mfn_sellers": self.active_mfn_sellers,
            "buy_box_price": self.buy_box_price,
        }


def assess_competition(market: Dict[str, Any], *, identity_state: str,
                       settings: Optional[Dict[str, Any]] = None) -> CompetitionAssessment:
    """Evaluate provider-only seller composition for a market snapshot.

    `market` is the canonical market snapshot (identity/marketplace/demand/...).
    Identity state is supplied separately (validated upstream).
    """
    st = get_settings(settings)
    min_mfn = int(st.get("minimum_active_mfn_sellers", 3))
    max_fba = int(st.get("maximum_active_fba_sellers", 0))
    snapshot_max_age = float(st.get("market_snapshot_max_age_minutes", 60))

    marketplace = market.get("marketplace", {})
    risk = market.get("risk", {})
    observed_at = market.get("fields", {}).get("asin", {}).get("observed_at") or market.get("observed_at")

    missing: List[str] = []
    blocked: List[str] = []

    amazon_retail = marketplace.get("amazon_retail_active")
    if _is_unknown(amazon_retail):
        missing.append("amazon_retail_active")
    elif amazon_retail is True:
        blocked.append("amazon_retail_active")

    brand_seller = marketplace.get("brand_owner_seller_active")
    if _is_unknown(brand_seller):
        missing.append("brand_owner_seller_active")
    elif brand_seller is True:
        blocked.append("brand_owner_seller_active")

    fba = marketplace.get("active_fba_seller_count")
    if _is_unknown(fba):
        missing.append("active_fba_seller_count")
    elif int(fba) > max_fba:
        blocked.append(f"active_fba_sellers({fba})>max({max_fba})")

    mfn = marketplace.get("active_mfn_seller_count")
    if _is_unknown(mfn):
        missing.append("active_mfn_seller_count")
    elif int(mfn) < min_mfn:
        blocked.append(f"active_mfn_sellers({mfn})<min({min_mfn})")

    buy_box = marketplace.get("buy_box_price")
    if _is_unknown(buy_box):
        missing.append("buy_box_price")

    # seller-count evidence freshness
    offer_observed = marketplace.get("offer_count_observed_at") or observed_at
    age = _age_minutes(offer_observed)
    if age is None:
        missing.append("seller_count_evidence_freshness")
    elif age > snapshot_max_age:
        blocked.append(f"seller_count_evidence_stale({age:.0f}m>{snapshot_max_age}m)")

    # exact listing identity
    if identity_state not in ("exact_match_verified", "exact_match_provider_reported",
                              "probable_match"):
        missing.append("exact_listing_identity")

    sellability = risk.get("asin_sellability_status")
    if _is_unknown(sellability):
        missing.append("asin_sellability_status")
    elif not _sellable(sellability):
        blocked.append(f"not_sellable({sellability})")

    restriction = risk.get("category_restriction_status") or risk.get("product_restriction_status") \
        or risk.get("brand_restriction_status")
    if _is_unknown(restriction):
        missing.append("restriction_status")
    elif not _unrestricted(restriction):
        blocked.append(f"restricted({restriction})")

    if blocked:
        return CompetitionAssessment(
            state=COMPETITION_BLOCK, reason_codes=["blocked_competition"],
            missing_fields=missing, blocked_flags=blocked,
            amazon_retail_active=amazon_retail if not _is_unknown(amazon_retail) else None,
            brand_owner_seller_active=brand_seller if not _is_unknown(brand_seller) else None,
            active_fba_sellers=fba if not _is_unknown(fba) else None,
            active_mfn_sellers=mfn if not _is_unknown(mfn) else None,
            buy_box_price=buy_box if not _is_unknown(buy_box) else None,
            notes=["Competition hard-blocked on provider-reported fields."],
        )
    if missing:
        return CompetitionAssessment(
            state=COMPETITION_NEEDS_ENRICHMENT, reason_codes=["needs_enrichment"],
            missing_fields=missing, blocked_flags=[],
            amazon_retail_active=amazon_retail if not _is_unknown(amazon_retail) else None,
            brand_owner_seller_active=brand_seller if not _is_unknown(brand_seller) else None,
            active_fba_sellers=fba if not _is_unknown(fba) else None,
            active_mfn_sellers=mfn if not _is_unknown(mfn) else None,
            buy_box_price=buy_box if not _is_unknown(buy_box) else None,
            notes=["Competition incomplete; needs enrichment (unknowns are never favorable)."],
        )
    return CompetitionAssessment(
        state=COMPETITION_PASS, reason_codes=["competition_pass"],
        amazon_retail_active=False, brand_owner_seller_active=False,
        active_fba_sellers=0, active_mfn_sellers=int(mfn),
        buy_box_price=buy_box,
        notes=["Competition requirements met (provider-reported, fresh, complete)."],
    )


# ---------------------------------------------------------------------------
# mfn_opportunity_score_v1
# ---------------------------------------------------------------------------

def mfn_opportunity_score(
    *,
    net_profit: Optional[float],
    roi_pct: Optional[float],
    demand_signal: Optional[float],
    mfn_competition_quality: Optional[float],
    zero_fba: bool,
    low_weight_standard_size: bool,
    price_stability: Optional[float],
    source_repeatability: float,
    settings: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Compute mfn_opportunity_score_v1 (0-100).

    Weights (sum 100): net_profit 25, roi 20, demand 15, mfn quality 15,
    zero_fba 10, low_weight 5, price_stability 5, source_repeatability 5.

    Unknown inputs score 0 for that component (never favorable). A high MFN
    seller count is NOT automatically rewarded.
    """
    st = get_settings(settings)
    weights = dict(st.get("mfn_score_weights", {}))

    def comp(value, target):
        if value is None:
            return 0.0
        if target <= 0:
            return 1.0 if value > 0 else 0.0
        return max(0.0, min(1.0, value / target))

    profit_score = comp(net_profit, st.get("qualified_net_profit", 11.0)) * 100
    roi_score = comp(roi_pct, st.get("minimum_roi_pct", 30.0)) * 100
    demand_score = comp(demand_signal, 5000.0) * 100 if demand_signal is not None else 0.0
    mfn_score = (mfn_competition_quality if mfn_competition_quality is not None else 0.0) * 100
    zero_fba_score = 100 if zero_fba else 0
    weight_score = 100 if low_weight_standard_size else 0
    price_score = (price_stability if price_stability is not None else 0.0) * 100
    repeat_score = (source_repeatability if source_repeatability is not None else 0.0) * 100

    total_w = sum(weights.values()) or 100.0
    score = (
        profit_score * weights.get("net_profit", 25) +
        roi_score * weights.get("roi", 20) +
        demand_score * weights.get("demand_signal", 15) +
        mfn_score * weights.get("mfn_competition_quality", 15) +
        zero_fba_score * weights.get("zero_fba_sellers", 10) +
        weight_score * weights.get("low_weight_standard_size", 5) +
        price_score * weights.get("price_stability", 5) +
        repeat_score * weights.get("source_repeatability", 5)
    ) / total_w

    return {
        "score": round(score, 2),
        "score_version": SCORE_VERSION,
        "components": {
            "net_profit": round(profit_score, 2),
            "roi": round(roi_score, 2),
            "demand_signal": round(demand_score, 2),
            "mfn_competition_quality": round(mfn_score, 2),
            "zero_fba_sellers": round(zero_fba_score, 2),
            "low_weight_standard_size": round(weight_score, 2),
            "price_stability": round(price_score, 2),
            "source_repeatability": round(repeat_score, 2),
        },
        "weights": dict(weights),
    }