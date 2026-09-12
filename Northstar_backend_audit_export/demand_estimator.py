"""Offline BSR/Category demand model for the Product Scout (read-only).

Pure, deterministic, zero-network helpers that turn listing-published
signals, provider sales estimates, or a Best Sellers Rank + category
into an estimated monthly sales figure with an honest confidence tier
and range. This module never writes anything and never calls a provider.

Model (v1.0):
  - Six supported categories, each with BSR->monthly-sales band values
    anchored at the band's lower bound. Values between anchors are
    interpolated in log-log space (no abrupt band jumps); ranks below
    the first anchor take the top value; ranks past the last anchor
    clamp to the floor value.
  - Signal priority: (1) listing-published bought-past-month signal
    (higher confidence, +/- 15%), (2) provider monthly-sales estimate
    (medium, +/- 30%), (3) BSR + supported category model
    (medium +/- 30% for BSR <= 50,000; low +/- 50% for 50,001-100,000;
    very_low +/- 70% above 100,000), (4) Unknown.
  - NEVER estimated from price, title, reviews, seller counts, Costco
    cost, weight, an assumed category, or a missing BSR: every missing
    input keeps the corresponding field None/Unknown/False.

Rules of honesty (mirrored from the scanner contracts):
  - Unknown is never 0. `monthly_sales_estimated` is False (never None)
    when there is no basis; it is True only when an estimate exists.
  - Confidence and range travel together; a range is only emitted with
    its matching confidence tier.
"""

import math
from typing import Any, Dict, Optional

CALIBRATION_MODEL_NAME = "Northstar BSR/Category Demand Model"
CALIBRATION_MODEL_VERSION = "1.0"

# BSR -> monthly-sales anchors, one (bsr, units_per_month) pair per band
# boundary (band start), ascending. Log-space interpolation runs between
# them; the final entry is the floor for any rank beyond it.
CATEGORY_CURVES = {
    "Home & Kitchen": [
        (1, 20000),
        (101, 8000),
        (1001, 2500),
        (5001, 600),
        (25001, 120),
        (100001, 20),
    ],
    "Beauty & Personal Care": [
        (1, 15000),
        (101, 5500),
        (1001, 1800),
        (5001, 450),
        (25001, 90),
        (100001, 15),
    ],
    "Health & Household": [
        (1, 18000),
        (101, 6500),
        (1001, 2000),
        (5001, 500),
        (25001, 100),
        (100001, 20),
    ],
    "Toys & Games": [
        (1, 12000),
        (101, 4500),
        (1001, 1500),
        (5001, 350),
        (25001, 70),
        (100001, 15),
    ],
    "Electronics": [
        (1, 10000),
        (101, 3500),
        (1001, 1100),
        (5001, 260),
        (25001, 55),
        (100001, 10),
    ],
    "Books": [
        (1, 3500),
        (101, 1200),
        (1001, 400),
        (5001, 90),
        (25001, 20),
        (100001, 5),
    ],
}

# Confidence -> +/- range fraction applied to the point estimate.
CONFIDENCE_RANGES = {
    "higher": 0.15,
    "medium": 0.30,
    "low": 0.50,
    "very_low": 0.70,
}

_MEDIUM_BSR_MAX = 50000
_LOW_BSR_MAX = 100000


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _positive(value: Any) -> Optional[float]:
    if not _is_number(value) or value <= 0:
        return None
    return float(value)


def _interpolate_curve(anchors, bsr: float) -> float:
    """Log-log interpolation between (bsr, sales) anchors.

    Returns the top band value for ranks at/below the first anchor,
    smooth interpolation between anchors, and the floor value for ranks
    at/beyond the final anchor. Pure math — never extrapolates above the
    floor band.
    """
    if bsr <= anchors[0][0]:
        return float(anchors[0][1])
    for i in range(len(anchors) - 1):
        r1, s1 = anchors[i]
        r2, s2 = anchors[i + 1]
        if bsr <= r2:
            if s1 == s2:
                return float(s1)
            if bsr <= r1:
                return float(s1)
            log_r = math.log10(max(bsr, 1))
            log_r1 = math.log10(max(r1, 1))
            log_r2 = math.log10(max(r2, 1))
            if log_r2 == log_r1:
                return float(s1)
            t = (log_r - log_r1) / (log_r2 - log_r1)
            return float(10 ** (math.log10(s1) + t * (math.log10(s2) - math.log10(s1))))
    return float(anchors[-1][1])


def model_estimate(bsr: Any, category: Optional[str]) -> Optional[float]:
    """BSR/category model point estimate, or None when unsupported.

    A missing/unknown category or a missing BSR is never replaced by an
    assumed category or a placeholder rank.
    """
    bsr = _positive(bsr)
    if bsr is None or not category or category not in CATEGORY_CURVES:
        return None
    return _interpolate_curve(CATEGORY_CURVES[category], bsr)


def bsr_confidence(bsr: Any, category: Optional[str]) -> str:
    """Confidence tier for the BSR/category path only.

    Supported category + valid BSR <= 50,000 -> medium; 50,001-100,000
    -> low; > 100,000 -> very_low; unsupported category or missing BSR
    -> unknown.
    """
    bsr = _positive(bsr)
    if bsr is None or not category or category not in CATEGORY_CURVES:
        return "unknown"
    if bsr <= _MEDIUM_BSR_MAX:
        return "medium"
    if bsr <= _LOW_BSR_MAX:
        return "low"
    return "very_low"


def _range_values(estimate: float, confidence: str) -> Optional[tuple]:
    """(low, high) rounded conservatively (floor/ceil) for a confidence
    tier, or None when the tier carries no range."""
    spread = CONFIDENCE_RANGES.get(confidence)
    if spread is None:
        return None
    low = math.floor(estimate * (1 - spread))
    high = math.ceil(estimate * (1 + spread))
    return (max(0, low), high)


def estimate_demand(
    listing_bought_past_month: Any = None,
    provider_monthly_sales_estimate: Any = None,
    bsr: Any = None,
    bsr_category: Optional[str] = None,
    bsr_observed_at: Optional[str] = None,
) -> Dict:
    """Estimate monthly demand with honest provenance.

    Priority: listing-published bought-past-month signal, then provider
    monthly-sales estimate, then the BSR/category model, then Unknown.

    Returns the full demand field set (all values None/False/Unknown when
    there is no basis). This function is pure: it never writes, never
    calls out, and never invents an estimate.
    """
    listing = _positive(listing_bought_past_month)
    provider = _positive(provider_monthly_sales_estimate)
    rank = _positive(bsr)

    bsr_category_clean = bsr_category if isinstance(bsr_category, str) and bsr_category else None

    if listing is not None:
        estimate = listing
        method = "listing_bought_past_month"
        source = "listing_published_signal"
        confidence = "higher"
    elif provider is not None:
        estimate = provider
        method = "provider_monthly_sales_estimate"
        source = "provider_estimate"
        confidence = "medium"
    else:
        estimate = model_estimate(rank, bsr_category_clean)
        method = "bsr_category_model" if estimate is not None else "unknown"
        source = "bsr_category_model" if estimate is not None else "unknown"
        confidence = bsr_confidence(rank, bsr_category_clean) if estimate is not None else "unknown"

    fields: Dict = {
        "estimated_monthly_sales": None,
        "sales_estimate_low": None,
        "sales_estimate_high": None,
        "sales_estimation_method": method,
        "sales_estimation_source": source,
        "sales_estimation_confidence": confidence,
        "monthly_sales_estimated": estimate is not None,
        "bsr": int(rank) if rank is not None else None,
        "bsr_category": bsr_category_clean,
        "bsr_observed_at": bsr_observed_at if isinstance(bsr_observed_at, str) and bsr_observed_at else None,
        "calibration_model_name": CALIBRATION_MODEL_NAME if estimate is not None else None,
        "calibration_model_version": CALIBRATION_MODEL_VERSION if estimate is not None else None,
    }
    if estimate is not None:
        rounded = int(round(estimate))
        fields["estimated_monthly_sales"] = rounded
        span = _range_values(estimate, confidence)
        if span is not None:
            fields["sales_estimate_low"] = span[0]
            fields["sales_estimate_high"] = span[1]
    return fields


SUPPORTED_CATEGORIES = tuple(sorted(CATEGORY_CURVES.keys()))