"""Golden Goose Finder — opportunity scoring and ranking engine.

Scores one retail-arbitrage result (:class:`BreakdownEconomics`) into a 0-1
composite with four weighted components, hard filters, a tier label,
human-readable notes, and opportunity tags. Pure and
deterministic: no network calls, no writes, no invented values.

The shared data models (:class:`WholesalePack`, :class:`IndividualListing`,
:class:`BreakdownEconomics`) live here until the sibling economics module
lands; it should import them from this module (they are also re-exported
from the package ``__init__``).

Scoring model (v1.0)::

    composite = 0.35*profit + 0.25*demand + 0.25*competition + 0.15*health

    profit      log-interpolated anchors ($0->0.0, $10->0.5, $20->0.75, $30+->1.0)
    demand      log-interpolated anchors (0->0.0, 1000->0.5, 2000->0.75, 5000+->1.0)
                using demand_estimator.estimate_demand(); unknown -> 0.30
    competition stepwise by FBA seller count (0->1.0 ... 6+->0.1); unknown -> 0.30
    health      rating anchors + review-count bonus; no rating -> 0.40

Hard filters (all fail closed on missing data):
    profit       net_profit_per_unit >= $10
    demand       1,000+ monthly sales, or rating >= 4.0 near baseline (>= 80%)
    competition  0 FBA sellers; 1-2 only if undercutting 2% still clears the
                 profit floor; 3+ rejected
    seller       brand-owner seller or Amazon.com as a seller = HARD BLOCK;
                 unverifiable seller identity fails closed
    size         weight <= 5 lbs (2 lbs preferred); unknown weight fails closed
    health       rating >= 3.5

    tiers       >= 0.60 and all hard filters -> HIGH
                >= 0.40 and profit floor      -> MEDIUM
                >= 0.20                       -> LOW
                else                          -> REJECT

Unknown is never 0: a missing value scores its documented fallback and
records a note, and its hard filter fails closed (fail-closed, matching
the Northstar "null-first" honesty rules).

ROI percentage convention: the sibling economics module stores ROIs /
margins as percentages (e.g. 125.0 = 125%). Values that are positive and
<= 1.0 are treated as ratios and converted (0.45 -> 45.0) so unit tests
and ratio-style callers still behave. See :func:`_as_pct`.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Data models (shared with the sibling economics module).
#
# Preferred source: the sibling module `breakdown_economics` (main.py already
# imports from it). Until that module lands, identical local fallback
# definitions keep this scorer importable and testable standalone. Both
# shapes follow the documented `BreakdownEconomics` contract; consumers only
# read attributes (duck-typed), so either class works at runtime.
# ---------------------------------------------------------------------------

try:  # pragma: no cover - sibling may not be present on this import path
    from .breakdown_economics import BreakdownEconomics, IndividualListing, WholesalePack

    _MODELS_FROM_SIBLING = True
except ImportError:  # pragma: no cover
    try:
        from breakdown_economics import BreakdownEconomics, IndividualListing, WholesalePack

        _MODELS_FROM_SIBLING = True
    except ImportError:

        @dataclass
        class WholesalePack:
            """The multi-pack wholesale unit bought at Costco / Sam's Club."""

            wholesale_price: float
            pack_count: int
            brand: str
            category_slug: Optional[str]
            # Optional reporting enrichments filled by the sourcing module when known.
            source_store: Optional[str] = None
            wholesale_pack_title: Optional[str] = None

        @dataclass
        class IndividualListing:
            """The Amazon listing the pack breaks down into."""

            asin: str
            title: str
            amazon_price: Optional[float]
            bsr: Optional[int] = None
            review_rating: Optional[float] = None
            review_count: Optional[int] = None
            fba_sellers: Optional[int] = None
            monthly_sales_estimate: Optional[float] = None
            weight_oz: Optional[float] = None
            seller_name: Optional[str] = None
            is_brand_seller: Optional[bool] = None
            is_amazon_seller: Optional[bool] = None

        @dataclass
        class BreakdownEconomics:
            """Full breakdown economics for one wholesale pack -> individual listing."""

            wholesale: WholesalePack
            individual: IndividualListing
            unit_cogs: Optional[float]
            net_profit_per_unit: Optional[float]
            net_profit_per_costco_pack: Optional[float]
            roi_per_unit: Optional[float]
            roi_per_costco_pack: Optional[float]
            profit_margin_pct: Optional[float]
            total_amazon_fees: Optional[float]
            economics_confidence: str = "unavailable"  # estimated | provisional | unavailable
            economics_notes: List[str] = field(default_factory=list)

        _MODELS_FROM_SIBLING = False


# ---------------------------------------------------------------------------
# Scoring weights (must sum to 1.0).
# ---------------------------------------------------------------------------

WEIGHT_PROFIT = 0.35
WEIGHT_DEMAND = 0.20
WEIGHT_COMPETITION = 0.15
WEIGHT_LISTING_HEALTH = 0.10
WEIGHT_PRICE_GAP = 0.10
WEIGHT_AD_FEASIBILITY = 0.10
_WEIGHTS_SUM = (
    WEIGHT_PROFIT + WEIGHT_DEMAND + WEIGHT_COMPETITION
    + WEIGHT_LISTING_HEALTH + WEIGHT_PRICE_GAP + WEIGHT_AD_FEASIBILITY
)

# Thresholds
DEFAULT_ROI_FLOOR = 10.00  # $10 min net profit per unit
DEFAULT_MIN_MONTHLY_SALES = 1000  # proven demand: 1K+ units/mo
DEFAULT_MIN_RATING = 4.0  # used when sales are near baseline
BASELINE_MONTHLY_SALES = 1000  # threshold for the rating requirement

# Score tiers
TIER_HIGH = "HIGH"
TIER_MEDIUM = "MEDIUM"
TIER_LOW = "LOW"
TIER_REJECT = "REJECT"

# Hard-filter ceilings / floors
# Competition: 0 FBA sellers is gold; 1-2 FBA sellers pass ONLY when their
# Buy Box price is high enough that undercutting by 2% still clears the
# profit floor; 3+ FBA sellers are rejected outright (profile rule).
COMPETITION_CEILING = 2  # FBA sellers allowed before rejection
LISTING_HEALTH_MIN_RATING = 3.5
NEAR_BASELINE_FRACTION = 0.80  # sales within 80% of the floor count as "near baseline"
UNDERCUT_DISCOUNT = 0.02  # price 2% below the buy box for the undercut check

# Size filter — preferred max 2 lbs, hard ceiling 5 lbs (trash bags are the
# largest acceptable item; most are already too heavy).
PREFERRED_MAX_WEIGHT_LBS = 2.0   # preferred band (cheap small-standard FBA fee)
ABS_MAX_WEIGHT_LBS = 5.0         # hard ceiling
PREFERRED_MAX_WEIGHT_OZ = PREFERRED_MAX_WEIGHT_LBS * 16.0
ABS_MAX_WEIGHT_OZ = ABS_MAX_WEIGHT_LBS * 16.0

# Score curve anchors: (value, score) pairs, log-interpolated between them.
PROFIT_ANCHORS = [(0.0, 0.0), (10.0, 0.5), (20.0, 0.75), (30.0, 1.0)]
DEMAND_ANCHORS = [(0.0, 0.0), (1000.0, 0.5), (2000.0, 0.75), (5000.0, 1.0)]

# Slug spellings -> canonical demand-curve category names. Ranges over the
# common slug variants emitted by sourcing pipelines; anything not listed
# falls through to demand_estimator's own alias table.
_SLUG_ALIASES = {
    "home-kitchen": "Home & Kitchen",
    "home-and-kitchen": "Home & Kitchen",
    "beauty-personal-care": "Beauty & Personal Care",
    "beauty-and-personal-care": "Beauty & Personal Care",
    "health-household": "Health & Household",
    "health-and-household": "Health & Household",
    "toys-games": "Toys & Games",
    "toys-and-games": "Toys & Games",
    "consumer-electronics": "Electronics",
    "electronics": "Electronics",
    "books": "Books",
}

# ---------------------------------------------------------------------------
# Optional dependency: demand_estimator (backend root). Never a hard import,
# so this module stays importable even when the backend root is not on the
# path; scoring then falls back to "demand unavailable" (score 0.30, filter
# fails closed) and records an honest note.
# ---------------------------------------------------------------------------

try:  # pragma: no cover - exercised by whatever environment imports us
    import demand_estimator as _demand
except ImportError:  # pragma: no cover
    _demand = None


# ---------------------------------------------------------------------------
# Small pure helpers.
# ---------------------------------------------------------------------------


def _number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def _as_pct(value: Optional[float]) -> Optional[float]:
    """Normalize a ratio to a percentage; pass percentages through.

    Values in (0, 1.0] are treated as ratios (0.45 -> 45.0); anything
    larger is assumed to already be a percentage (125.0 stays 125.0).
    None stays None. Documented heuristic — percentages are preferred.
    """
    if value is None:
        return None
    if 0.0 < value <= 1.0:
        return float(value) * 100.0
    return float(value)


def _log_interp(anchors: List[tuple], value: float) -> float:
    """Smooth log-space interpolation between (value, score) anchors.

    Values at/below the first anchor take its score, values at/beyond the
    last anchor take the last score, and values in between are interpolated
    in log space (+1 offset so log(0) is never evaluated). Clamped to zero
    for negative inputs.  Falls back to linear interpolation when the
    log-space denominator would be non-positive (negative anchor values).
    """
    if value < 0:
        value = 0.0
    if value <= anchors[0][0]:
        return float(anchors[0][1])
    for (r1, s1), (r2, s2) in zip(anchors, anchors[1:]):
        if value <= r2:
            if s1 == s2:
                return float(s1)
            # Check if log space is valid before calling math.log
            shifted_r1 = r1 + 1.0
            shifted_r2 = r2 + 1.0
            if shifted_r1 <= 0 or shifted_r2 <= 0 or shifted_r2 / shifted_r1 <= 0:
                # Linear fallback when log space is invalid
                t = (value - r1) / (r2 - r1) if r2 != r1 else 0.0
                return s1 + max(0.0, min(1.0, t)) * (s2 - s1)
            t = math.log(shifted_r2 / shifted_r1)
            if t == 0:
                return float(s1)
            t = math.log((value + 1.0) / shifted_r1) / t
            return s1 + t * (s2 - s1)
    return float(anchors[-1][1])


# ---------------------------------------------------------------------------
# Component scores (0-1 each).
# ---------------------------------------------------------------------------


def _profit_score(net_profit_per_unit: Optional[float]) -> float:
    """$0 -> 0.0, $10 (floor) -> 0.5, $20 -> 0.75, $30+ -> 1.0 (log curve)."""
    if net_profit_per_unit is None:
        return 0.0
    return _log_interp(PROFIT_ANCHORS, float(net_profit_per_unit))


def _demand_score(monthly_sales: Optional[float]) -> float:
    """0 -> 0.0, 1000 (baseline) -> 0.5, 2000 -> 0.75, 5000+ -> 1.0.

    Unknown (None) scores 0.30 — the caller records the note.
    """
    if monthly_sales is None:
        return 0.3
    return _log_interp(DEMAND_ANCHORS, float(monthly_sales))


def _competition_score(fba_sellers: Optional[int]) -> float:
    """0 -> 1.0, 1 -> 0.75, 2 -> 0.5, 3-5 -> 0.25, 6+ -> 0.1, unknown -> 0.3.

    The spec lists both "3-5 -> 0.25" and "5+ -> 0.1"; 5 belongs to the
    3-5 band, so 6+ is where the 0.1 band begins.
    """
    if fba_sellers is None:
        return 0.3
    if fba_sellers == 0:
        return 1.0
    if fba_sellers == 1:
        return 0.75
    if fba_sellers == 2:
        return 0.5
    if fba_sellers <= 5:
        return 0.25
    return 0.1


def _rating_component(rating: Optional[float]) -> float:
    """4.8+ -> 1.0, 4.5 -> 0.8, 4.0 -> 0.5, <4.0 -> 0.2, no data -> 0.4."""
    if rating is None:
        return 0.4
    if rating >= 4.8:
        return 1.0
    if rating >= 4.5:
        return 0.8 + (rating - 4.5) / 0.3 * 0.2
    if rating >= 4.0:
        return 0.5 + (rating - 4.0) / 0.5 * 0.3
    return 0.2


def _review_bonus(review_count: Optional[int]) -> float:
    """1000+ -> +0.2, 500+ -> +0.1, <50 -> -0.2, else 0."""
    if review_count is None:
        return 0.0
    if review_count >= 1000:
        return 0.2
    if review_count >= 500:
        return 0.1
    if review_count < 50:
        return -0.2
    return 0.0


def _listing_health_score(rating: Optional[float], review_count: Optional[int]) -> float:
    """Rating anchors combined with the review-count bonus, clamped 0-1."""
    return _clamp01(_rating_component(rating) + _review_bonus(review_count))


# ---------------------------------------------------------------------------
# Price gap scoring.
# ---------------------------------------------------------------------------

PRICE_GAP_ANCHORS = [(-5.0, 0.0), (0.0, 0.2), (5.0, 0.6), (10.0, 0.85), (15.0, 1.0)]


def _price_gap_score(undercut_headroom: Optional[float]) -> float:
    """Score the price gap headroom (how much we can undercut and still profit).

    Negative headroom = can't compete -> 0.0
    $0 = exactly at the floor -> 0.2 (marginal)
    $5 = good room -> 0.6
    $10 = strong position -> 0.85
    $15+ = dominant -> 1.0
    Unknown = 0.3 (fallback, fail closed in hard filter)
    """
    if undercut_headroom is None:
        return 0.3
    return _log_interp(PRICE_GAP_ANCHORS, float(undercut_headroom))


# ---------------------------------------------------------------------------
# Ad feasibility scoring (proxy signals).
# ---------------------------------------------------------------------------

def _ad_feasibility_score(
    review_count: Optional[int],
    bsr: Optional[int],
    monthly_sales: Optional[float],
    brand: Optional[str],
) -> tuple[float, dict]:
    """Score ad feasibility using proxy signals.

    Returns (score, breakdown_dict) where breakdown_dict has the individual
    component scores (0-25 each, total 0-100 -> normalized to 0-1).

    Components:
      - Review count (demand signal): >500=25, >100=15, >20=5, else 0
      - BSR rank (velocity): <1K=25, <10K=15, <50K=5, else 0
      - Sales velocity: >5K=25, >2K=15, >1K=5, else 0
      - Brand recognition: known brand=25, unknown=10, none=0
    """
    breakdown = {}

    # Review count — more reviews = proven demand = ads convert better
    if review_count is not None and review_count >= 500:
        breakdown["review_pts"] = 25
    elif review_count is not None and review_count >= 100:
        breakdown["review_pts"] = 15
    elif review_count is not None and review_count >= 20:
        breakdown["review_pts"] = 5
    else:
        breakdown["review_pts"] = 0

    # BSR rank — lower = higher velocity = ads amplify momentum
    if bsr is not None and bsr < 1000:
        breakdown["bsr_pts"] = 25
    elif bsr is not None and bsr < 10000:
        breakdown["bsr_pts"] = 15
    elif bsr is not None and bsr < 50000:
        breakdown["bsr_pts"] = 5
    else:
        breakdown["bsr_pts"] = 0

    # Sales velocity — proven sales = ads will compound
    if monthly_sales is not None and monthly_sales >= 5000:
        breakdown["velocity_pts"] = 25
    elif monthly_sales is not None and monthly_sales >= 2000:
        breakdown["velocity_pts"] = 15
    elif monthly_sales is not None and monthly_sales >= 1000:
        breakdown["velocity_pts"] = 5
    else:
        breakdown["velocity_pts"] = 0

    # Brand recognition — known brands have search demand for branded ads
    if brand:
        brand_lower = brand.lower()
        # Check against the brand allowlist for recognition
        try:
            from .wholesale_scanner import _BRAND_ALLOWLIST_LOWER
        except ImportError:
            try:
                from wholesale_scanner import _BRAND_ALLOWLIST_LOWER
            except ImportError:
                _BRAND_ALLOWLIST_LOWER = {}
        if brand_lower in _BRAND_ALLOWLIST_LOWER:
            breakdown["brand_pts"] = 25
        else:
            breakdown["brand_pts"] = 10
    else:
        breakdown["brand_pts"] = 0

    total_pts = sum(breakdown.values())
    score = total_pts / 100.0  # normalize to 0-1
    breakdown["total_pts"] = total_pts
    return _clamp01(score), breakdown


# ---------------------------------------------------------------------------
# Seller-identity and size hard filters.
# ---------------------------------------------------------------------------


def _seller_identity_blocked(
    seller_name: Optional[str],
    is_brand_seller: Optional[bool],
    is_amazon_seller: Optional[bool],
    product_brand: Optional[str],
) -> bool:
    """Delegate to amazon_matcher.seller_identity_blocked when available."""
    try:  # pragma: no cover - sibling resolution
        from .amazon_matcher import seller_identity_blocked as _sib
    except ImportError:  # pragma: no cover
        try:
            from amazon_matcher import seller_identity_blocked as _sib  # type: ignore[import-not-found]
        except ImportError:
            _sib = None  # type: ignore[assignment]
    if _sib is not None:
        return _sib(seller_name, is_brand_seller, is_amazon_seller, product_brand)
    return bool(is_brand_seller or is_amazon_seller)  # pragma: no cover


def _verify_seller_identity(ind: Any, ws_brand: Optional[str]) -> tuple:
    """(passes, note) for the seller-identity hard filter — FAILS CLOSED.

    Unverifiable identity (no seller data at all) is a block: a listing whose
    sellers we could not identify cannot be certified as safe to enter.
    """
    observed = (
        ind.seller_name is not None
        or ind.is_brand_seller is not None
        or ind.is_amazon_seller is not None
    )
    if not observed:
        return False, "FAIL (unverifiable — no seller identity data)"
    blocked = _seller_identity_blocked(
        ind.seller_name, ind.is_brand_seller, ind.is_amazon_seller, ws_brand
    )
    if blocked:
        who = ind.seller_name or (
            "brand owner" if ind.is_brand_seller else "Amazon.com"
        )
        return False, "FAIL (seller blocked: %s)" % who
    return True, "PASS (verified third-party seller)"


def _check_size(ind: Any) -> tuple:
    """(passes, note) for the size hard filter — FAILS CLOSED on unknown weight.

    Small/light is the strategy: <= 2 lbs is preferred, 5 lbs is the hard
    ceiling (trash bags are the largest acceptable item). Unknown weight
    cannot be certified small and fails closed.
    """
    w = ind.weight_oz
    if w is None:
        return False, "FAIL (unknown weight — cannot certify small/light)"
    if float(w) > ABS_MAX_WEIGHT_OZ:
        return False, "FAIL (%.1f oz > %.0f oz / 5 lbs ceiling)" % (w, ABS_MAX_WEIGHT_OZ)
    if float(w) > PREFERRED_MAX_WEIGHT_OZ:
        return True, "PASS (%.1f oz — over preferred 2 lbs, under 5 lbs ceiling)" % w
    return True, "PASS (%.1f oz — preferred <= 2 lbs)" % w


def _assign_tier(
    composite: float,
    passes_profit_floor: bool,
    passes_all_filters: bool,
) -> str:
    """Tier assignment per the documented rules."""
    if composite >= 0.6 and passes_all_filters:
        return TIER_HIGH
    if composite >= 0.4 and passes_profit_floor:
        return TIER_MEDIUM
    if composite >= 0.2:
        return TIER_LOW
    return TIER_REJECT


# ---------------------------------------------------------------------------
# Demand estimation (via the demand_estimator backend module).
# ---------------------------------------------------------------------------


def _resolve_bsr_category(category_slug: Optional[str]) -> Optional[str]:
    """Map a category slug onto a supported demand-curve category name."""
    if not category_slug:
        return None
    slug = str(category_slug).strip().lower()
    if not slug:
        return None
    norm = slug.replace("&", "and").replace("_", "-").replace(" ", "-")
    if norm in _SLUG_ALIASES:
        return _SLUG_ALIASES[norm]
    if _demand is not None:
        return _demand._canonical_category(slug)  # noqa: SLF001 - documented bridge
    return None


def estimate_demand_fields(economics: BreakdownEconomics) -> Optional[Dict[str, Any]]:
    """Run demand_estimator.estimate_demand for this economics breakdown.

    Returns the demand field set (which may itself report "unknown" when
    there is no BSR or sales basis), or None when the estimator module is
    unavailable. Pure and read-only.
    """
    if _demand is None:
        return None
    ind = economics.individual
    category = _resolve_bsr_category(economics.wholesale.category_slug)
    try:
        return _demand.estimate_demand(
            provider_monthly_sales_estimate=ind.monthly_sales_estimate,
            bsr=ind.bsr,
            bsr_category=category,
        )
    except Exception:  # pragma: no cover - defensive against estimator breakage
        return None


def _estimated_sales(economics: BreakdownEconomics) -> Optional[int]:
    fields = estimate_demand_fields(economics)
    if not fields:
        return None
    return fields.get("estimated_monthly_sales")


# ---------------------------------------------------------------------------
# Tags.
# ---------------------------------------------------------------------------


def _apply_tags(economics: BreakdownEconomics) -> List[str]:
    """Apply every matching opportunity tag, in a stable order."""
    ind = economics.individual
    ws = economics.wholesale
    tags: List[str] = []
    if ind.fba_sellers == 0:
        tags.append("no_fba_competition")
    elif ind.fba_sellers == 1:
        tags.append("low_competition")
    # 1-2 FBA sellers whose Buy Box price we can undercut by ~2% and still
    # clear the $10 profit floor -> winnable competition.
    if ind.fba_sellers is not None and 1 <= ind.fba_sellers <= 2:
        undercut = _undercut_allows_competition(
            economics.net_profit_per_unit, ind.amazon_price, DEFAULT_ROI_FLOOR
        )
        if undercut:
            tags.append("undercut_opportunity")
    # Seller-identity blockers (these entries end up REJECT, but tagging the
    # discarded list makes the reason visible in the report).
    if ind.is_brand_seller:
        tags.append("brand_owner_seller")
    if ind.is_amazon_seller or (
        ind.seller_name and "amazon.com" in str(ind.seller_name).lower()
    ):
        tags.append("amazon_seller_present")
    margin = _as_pct(economics.profit_margin_pct)
    if margin is not None and margin > 40:
        tags.append("high_margin")
    if ind.amazon_price is not None and ind.amazon_price > 25:
        tags.append("premium_product")
    sales = _estimated_sales(economics)
    if sales is not None and sales > 2000:
        tags.append("high_velocity")
    if ind.bsr is not None and ind.bsr < 10000:
        tags.append("trending_up")
    pack_roi = _as_pct(economics.roi_per_costco_pack)
    if pack_roi is not None and pack_roi > 100:
        tags.append("bulk_goldmine")
    return tags


# ---------------------------------------------------------------------------
# Public scoring API.
# ---------------------------------------------------------------------------


@dataclass
class ScoredOpportunity:
    """A Golden Goose opportunity with full scoring breakdown."""

    # Source data
    economics: BreakdownEconomics
    # Individual scores (0.0 - 1.0 each)
    profit_score: float
    demand_score: float
    competition_score: float
    listing_health_score: float
    # Composite
    composite_score: float  # weighted average
    tier: str  # HIGH / MEDIUM / LOW / REJECT
    # Hard filter results
    passes_profit_floor: bool
    passes_demand_floor: bool
    passes_competition_ceiling: bool
    passes_listing_health: bool
    passes_seller_identity: bool
    passes_size_filter: bool
    passes_all_filters: bool
    # Human-readable
    scoring_notes: List[str] = field(default_factory=list)
    opportunity_tags: List[str] = field(default_factory=list)  # e.g. ["low_competition", ...]
    # New scoring fields (price gap + ad feasibility)
    price_gap_score: float = 0.0
    ad_feasibility_score: float = 0.0
    ad_feasibility_breakdown: Dict[str, Any] = field(default_factory=dict)

    @property
    def asin(self) -> str:
        return self.economics.individual.asin


def _undercut_allows_competition(
    net_profit_per_unit: Optional[float],
    amazon_price: Optional[float],
    roi_floor: float,
) -> Optional[bool]:
    """Return True/False for the 1-2-seller undercut check, or None when the
    check cannot be evaluated (missing net or price).

    We would price 2% below the Buy Box to win it; the check confirms the
    undercut price still clears the profit floor (i.e. the incumbent sellers
    are priced HIGH enough that we can undercut and stay profitable).
    """
    if net_profit_per_unit is None or amazon_price is None or amazon_price <= 0:
        return None
    cut = amazon_price * UNDERCUT_DISCOUNT
    return (net_profit_per_unit - cut) >= roi_floor


def score_opportunity(
    economics: BreakdownEconomics,
    roi_floor: float = DEFAULT_ROI_FLOOR,
    min_monthly_sales: int = DEFAULT_MIN_MONTHLY_SALES,
    min_rating: float = DEFAULT_MIN_RATING,
) -> ScoredOpportunity:
    """Score a single breakdown economics result.

    See the module docstring for the full methodology. Hard filters:

      - profit:      net_profit_per_unit >= roi_floor
      - demand:      est monthly sales >= min_monthly_sales, or rating >=
                     min_rating when sales are near baseline (>= 80% of the
                     floor)
      - competition: 0 FBA sellers (gold); 1-2 FBA sellers pass only when
                     undercutting 2% below the Buy Box still clears the
                     profit floor; 3+ rejected
      - seller:      brand-owner seller or Amazon.com as a seller = HARD
                     BLOCK; unverifiable seller identity fails closed
      - size:        weight <= 5 lbs (2 lbs preferred); unknown weight fails
                     closed
      - listing_health: review_rating >= 3.5

    All hard filters fail closed on missing data (with a note).
    """
    ind = economics.individual
    ws = economics.wholesale
    notes: List[str] = []

    # 1. Profit ------------------------------------------------------------
    net = economics.net_profit_per_unit
    profit_score = _profit_score(net)
    passes_profit = net is not None and net >= roi_floor
    if net is None:
        notes.append("Profit: no net profit data -> score 0.00")
    else:
        notes.append(
            "Profit: $%.2f/unit -> %.2f (floor $%.2f)" % (net, profit_score, roi_floor)
        )

    # 2. Demand ------------------------------------------------------------
    demand_fields = estimate_demand_fields(economics)
    sales = demand_fields.get("estimated_monthly_sales") if demand_fields else None
    confidence = (demand_fields or {}).get("sales_estimation_confidence")
    if sales is None:
        demand_score = _demand_score(None)
        notes.append("Demand: no BSR/sales data -> score 0.30")
    else:
        demand_score = _demand_score(sales)
        notes.append("Demand: ~%d/mo -> %.2f (%s confidence)" % (sales, demand_score, confidence or "unknown"))

    rating = ind.review_rating
    if sales is None:
        passes_demand = False
        notes.append("Demand floor: FAIL (no monthly sales estimate)")
    elif sales >= min_monthly_sales:
        passes_demand = True
    elif sales >= NEAR_BASELINE_FRACTION * min_monthly_sales and rating is not None and rating >= min_rating:
        passes_demand = True
        notes.append(
            "Demand floor: PASS via rating %.1f while near baseline (%d/mo < %d)"
            % (rating, sales, min_monthly_sales)
        )
    else:
        passes_demand = False
        if rating is None:
            notes.append("Demand floor: FAIL (%d/mo < %d, no rating to fall back on)" % (sales, min_monthly_sales))
        else:
            notes.append("Demand floor: FAIL (%d/mo < %d, rating %.1f below %.1f)" % (sales, min_monthly_sales, rating, min_rating))

    # 3. Competition ---------------------------------------------------------
    fba = ind.fba_sellers
    competition_score = _competition_score(fba)
    if fba is None:
        passes_competition = False
        notes.append("Competition: unknown seller data -> score 0.30")
        notes.append("Competition floor: FAIL (no FBA seller data)")
    else:
        notes.append("Competition: %d FBA seller%s -> %.2f" % (fba, "" if fba == 1 else "s", competition_score))
        if fba == 0:
            passes_competition = True
            notes.append("Competition floor: PASS (0 FBA sellers — uncontested)")
        elif fba <= COMPETITION_CEILING:
            # 1-2 FBA sellers: only winnable if their Buy Box price is high
            # enough that undercutting by 2% still clears the profit floor.
            undercut = _undercut_allows_competition(net, ind.amazon_price, roi_floor)
            passes_competition = bool(undercut)
            notes.append(
                "Competition floor: %d FBA sellers (<= %d); undercut check -> %s"
                % (fba, COMPETITION_CEILING, "PASS" if undercut else "FAIL")
            )
        else:
            passes_competition = False
            notes.append(
                "Competition floor: FAIL (%d FBA sellers > %d ceiling)"
                % (fba, COMPETITION_CEILING)
            )

    # 4. Listing health -------------------------------------------------------
    health_score = _listing_health_score(rating, ind.review_count)
    if rating is None:
        passes_health = False
        notes.append("Listing health: no rating data -> score 0.40")
        notes.append("Listing health floor: FAIL (no rating data)")
    else:
        passes_health = rating >= LISTING_HEALTH_MIN_RATING
        notes.append(
            "Listing health: rating %s, %s reviews -> %.2f"
            % (rating, "?" if ind.review_count is None else ind.review_count, health_score)
        )

    # 4b. Seller identity -----------------------------------------------------
    passes_seller, seller_note = _verify_seller_identity(ind, ws.brand)
    notes.append("Seller identity: %s" % seller_note)

    # 4c. Size (small & light) ------------------------------------------------
    passes_size, size_note = _check_size(ind)
    notes.append("Size: %s" % size_note)

    # 4d. Price gap headroom --------------------------------------------------
    eco = economics
    price_gap = _price_gap_score(eco.undercut_headroom)
    if eco.undercut_headroom is not None:
        notes.append(
            "Price gap: $%.2f headroom -> %.2f (max undercut price $%.2f)"
            % (eco.undercut_headroom, price_gap, eco.max_undercut_price or 0)
        )
    else:
        notes.append("Price gap: no buy box data -> score 0.30")

    # 4e. Ad feasibility (proxy signals) --------------------------------------
    ad_score, ad_breakdown = _ad_feasibility_score(
        ind.review_count, ind.bsr, ind.monthly_sales_estimate, ws.brand
    )
    notes.append(
        "Ad feasibility: %d/100 pts (reviews=%d, BSR=%d, velocity=%d, brand=%d)"
        % (
            ad_breakdown.get("total_pts", 0),
            ad_breakdown.get("review_pts", 0),
            ad_breakdown.get("bsr_pts", 0),
            ad_breakdown.get("velocity_pts", 0),
            ad_breakdown.get("brand_pts", 0),
        )
    )

    passes_all = (
        passes_profit
        and passes_demand
        and passes_competition
        and passes_health
        and passes_seller
        and passes_size
    )

    # 5. Composite + tier -----------------------------------------------------
    # Updated weights: profit 35%, demand 20%, competition 15%, health 10%,
    # price gap 10%, ad feasibility 10%
    composite = round(
        WEIGHT_PROFIT * profit_score
        + WEIGHT_DEMAND * demand_score
        + WEIGHT_COMPETITION * competition_score
        + WEIGHT_LISTING_HEALTH * health_score
        + WEIGHT_PRICE_GAP * price_gap
        + WEIGHT_AD_FEASIBILITY * ad_score,
        4,
    )
    tier = _assign_tier(composite, passes_profit, passes_all)
    notes.append("Composite: %.4f -> %s" % (composite, tier))

    # 6. Tags ------------------------------------------------------------------
    tags = _apply_tags(economics)
    if not tags:
        notes.append("Tags: none matched")

    return ScoredOpportunity(
        economics=economics,
        profit_score=profit_score,
        demand_score=demand_score,
        competition_score=competition_score,
        listing_health_score=health_score,
        composite_score=composite,
        tier=tier,
        passes_profit_floor=passes_profit,
        passes_demand_floor=passes_demand,
        passes_competition_ceiling=passes_competition,
        passes_listing_health=passes_health,
        passes_seller_identity=passes_seller,
        passes_size_filter=passes_size,
        passes_all_filters=passes_all,
        scoring_notes=notes,
        opportunity_tags=tags,
        price_gap_score=price_gap,
        ad_feasibility_score=ad_score,
        ad_feasibility_breakdown=ad_breakdown,
    )


def score_batch(
    economics_list: List[BreakdownEconomics],
    roi_floor: float = DEFAULT_ROI_FLOOR,
    min_monthly_sales: int = DEFAULT_MIN_MONTHLY_SALES,
    include_rejected: bool = False,
) -> List[ScoredOpportunity]:
    """Score a batch of opportunities, sorted by composite score descending.

    REJECT-tier results are filtered out by default; pass include_rejected
    to keep them (e.g. so the report can populate its ``discarded`` list).
    """
    scored = [
        score_opportunity(e, roi_floor=roi_floor, min_monthly_sales=min_monthly_sales)
        for e in economics_list
    ]
    if not include_rejected:
        scored = [s for s in scored if s.tier != TIER_REJECT]
    scored.sort(key=lambda s: s.composite_score, reverse=True)
    return scored


def get_scoring_summary(scored: List[ScoredOpportunity]) -> Dict[str, Any]:
    """Return summary statistics over a list of scored opportunities."""
    profits = [s.economics.net_profit_per_unit for s in scored if _number(s.economics.net_profit_per_unit)]
    rois = [v for v in (_as_pct(s.economics.roi_per_unit) for s in scored) if v is not None]

    top_tags: Dict[str, int] = {}
    for s in scored:
        for tag in s.opportunity_tags:
            top_tags[tag] = top_tags.get(tag, 0) + 1

    best = max(scored, key=lambda s: s.composite_score, default=None)

    return {
        "total_evaluated": len(scored),
        "high": sum(1 for s in scored if s.tier == TIER_HIGH),
        "medium": sum(1 for s in scored if s.tier == TIER_MEDIUM),
        "low": sum(1 for s in scored if s.tier == TIER_LOW),
        "rejected": sum(1 for s in scored if s.tier == TIER_REJECT),
        "avg_profit": round(sum(profits) / len(profits), 2) if profits else 0.0,
        "avg_roi": round(sum(rois) / len(rois), 2) if rois else 0.0,
        "best_opportunity": best,
        "top_tags": top_tags,
    }