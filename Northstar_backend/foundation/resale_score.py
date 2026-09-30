"""Resale Score (Master Plan P5-T1) — pure, versioned, config-driven.

Display name: "Resale Score" (provisional). Code name: ``resale_score``.
Scorer version: ``resale-score-1.0.0``.

Contract:
  * PURE function: same inputs -> same output (no clocks, no randomness).
  * Every component is 0..1; a MISSING component is UNAVAILABLE (``None``), never
    coerced to 0.
  * ``overall_score`` = weighted mean over AVAILABLE components only; ``None`` if
    none are available. Missing components are listed, not counted.
  * Uncertainty is a SEPARATELY labeled penalty (not folded into a component).
  * ROI% is INFORMATIONAL only — never part of the score and never a gate.
  * A score never authorizes a purchase (PURCHASE_READY requires gates+approval).
"""
from __future__ import annotations

from typing import Optional

SCORER_VERSION = "resale-score-1.0.0"
CODE_NAME = "resale_score"
DISPLAY_NAME = "Resale Score"  # provisional (OA-8)

# -- config-driven thresholds/weights (overridable via ``config``) -------------
DEFAULT_CONFIG = {
    "MIN_NET_PER_UNIT": 5.00,       # $ floor for net profit per unit
    "DEMAND_FULL_SALES": 300.0,     # est. monthly sales that saturate demand
    "COMPETITION_MAX_SELLERS": 20.0,
    "REVIEW_FULL": 500.0,
    "WEIGHTS": {
        "net_profit_per_unit": 1.5,
        "demand": 1.2,
        "bsr_stability": 1.0,
        "competition": 1.0,
        "review_rating_plausibility": 0.7,
        "price_stability": 1.0,
        "match_confidence": 1.3,
        "sourcing_ease": 0.8,
    },
}

COMPONENTS = tuple(DEFAULT_CONFIG["WEIGHTS"].keys())


def _clamp01(v) -> Optional[float]:
    if v is None:
        return None
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    if x < 0:
        return 0.0
    if x > 1:
        return 1.0
    return x


def _ratio(num, den) -> Optional[float]:
    try:
        num = float(num)
        den = float(den)
    except (TypeError, ValueError):
        return None
    if den <= 0:
        return None
    return _clamp01(num / den)


def _net_profit_component(net_per_unit, floor) -> Optional[float]:
    if net_per_unit is None:
        return None
    try:
        n = float(net_per_unit)
    except (TypeError, ValueError):
        return None
    if n <= 0:
        return 0.0
    return _clamp01(n / float(floor))


def _competition_component(seller_count, buy_box_type) -> Optional[float]:
    if seller_count is None and buy_box_type is None:
        return None
    score = 1.0
    if seller_count is not None:
        try:
            sc = float(seller_count)
        except (TypeError, ValueError):
            sc = None
        if sc is not None:
            score *= max(0.0, 1.0 - _clamp01(sc / DEFAULT_CONFIG["COMPETITION_MAX_SELLERS"]))
    bbt = (str(buy_box_type or "")).lower()
    if bbt:
        if "amazon" in bbt:
            score *= 0.2
        elif "fba" in bbt:
            score *= 0.85
        else:
            score *= 1.0
    return _clamp01(score)


def _review_component(review_count, rating) -> Optional[float]:
    if review_count is None and rating is None:
        return None
    score = 1.0
    if review_count is not None:
        try:
            rc = float(review_count)
        except (TypeError, ValueError):
            rc = None
        if rc is not None:
            score *= _clamp01(rc / DEFAULT_CONFIG["REVIEW_FULL"]) or 0.0
    if rating is not None:
        try:
            r = float(rating)
        except (TypeError, ValueError):
            r = None
        if r is not None:
            # plausible ratings 3.5-5.0; penalize implausibly low ratings
            score *= _clamp01((r - 3.0) / 2.0) if r < 3.0 else 1.0
    return _clamp01(score)


def score(inputs: dict, *, config: Optional[dict] = None) -> dict:
    """Compute the Resale Score. ``inputs`` keys (all optional):

    net_per_unit, est_monthly_sales, bsr_stability, seller_count, buy_box_type,
    review_count, rating, price_stability, match_confidence, sourcing_ease,
    uncertainty_penalty, roi_pct.
    """
    cfg = dict(DEFAULT_CONFIG)
    if config:
        cfg.update(config)
    weights = dict(cfg.get("WEIGHTS") or DEFAULT_CONFIG["WEIGHTS"])
    inp = inputs or {}

    raw = {
        "net_profit_per_unit": _net_profit_component(inp.get("net_per_unit"), cfg["MIN_NET_PER_UNIT"]),
        "demand": _ratio(inp.get("est_monthly_sales"), cfg["DEMAND_FULL_SALES"]),
        "bsr_stability": _clamp01(inp.get("bsr_stability")),
        "competition": _competition_component(inp.get("seller_count"), inp.get("buy_box_type")),
        "review_rating_plausibility": _review_component(inp.get("review_count"), inp.get("rating")),
        "price_stability": _clamp01(inp.get("price_stability")),
        "match_confidence": _clamp01(inp.get("match_confidence")),
        "sourcing_ease": _clamp01(inp.get("sourcing_ease")),
    }

    available = {k: v for k, v in raw.items() if v is not None}
    missing = sorted(k for k, v in raw.items() if v is None)
    total_w = sum(weights.get(k, 0.0) for k in available)
    overall = None
    if available and total_w > 0:
        overall = round(sum(available[k] * weights.get(k, 0.0) for k in available) / total_w, 4)

    penalty = inp.get("uncertainty_penalty") or 0.0
    try:
        penalty = max(0.0, float(penalty))
    except (TypeError, ValueError):
        penalty = 0.0
    if overall is not None and penalty:
        overall = round(max(0.0, overall - penalty), 4)

    confidence = round(len(available) / len(COMPONENTS), 4)

    return {
        "scorer_version": SCORER_VERSION,
        "code_name": CODE_NAME,
        "display_name": DISPLAY_NAME,
        "component_scores": raw,
        "component_availability": {k: (v is not None) for k, v in raw.items()},
        "component_weights": {k: weights.get(k, 0.0) for k in COMPONENTS},
        "overall_score": overall,
        "overall_confidence": confidence,
        "uncertainty_penalty": penalty,
        "missing_information": missing,
        "informational": {                       # never gates, never scored
            "roi_pct": inp.get("roi_pct"),
            "net_per_unit": inp.get("net_per_unit"),
            "min_net_per_unit": cfg["MIN_NET_PER_UNIT"],
        },
        "purchase_ready": False,                 # a score NEVER authorizes purchase
    }