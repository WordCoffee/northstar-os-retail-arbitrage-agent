"""Golden Goose Finder — full breakdown economics engine.

Calculates the FULL economics of a multi-pack breakdown opportunity: buying a
bulk club pack (Costco / Sam's Club) and selling the individual units on
Amazon.

Fee stack (per individual unit):
  unit_cogs          = wholesale_price / pack_count
  + repackaging      = labor ($0.50/unit) + packaging ($0.25/unit) by default
  + referral fee     = versioned fee_engine rule, or 15% flat fallback
  + FBA fulfillment  = versioned fee_engine table, or pricing.estimate_fba_fee
                       fallback, or EXCLUDED (provisional) when no weight data
  + inbound          = $0.35/unit (fee_engine env-aware default)
  + prep             = $0.25/unit (fee_engine env-aware default)
  + return reserve   = 2% of the Amazon sale price
  = total_costs_per_unit  (== breakeven_amazon_price)

``pack_count`` on :class:`WholesalePack` is the number of INDIVIDUAL SELLABLE
UNITS the pack breaks down into (e.g. a 200-count Costco pack broken into 10 x
20-count Amazon listings has pack_count=10), so ``unit_cogs`` is the landed
cost of one Amazon-sellable unit. This mirrors the sibling
``opportunity_scorer`` models while carrying the extra sourcing/fee fields the
scorer does not need.

Honesty rules (mirrored from fee_engine.py):
  - missing values stay None, never 0 or $0.00
  - confidence travels with the data: estimated | provisional | unavailable
  - "provisional" means an FBA fee could not be verified (excluded) or a fee
    came from a fallback estimator — never passed off as exact
  - every assumption / fallback is recorded in economics_notes
"""

from dataclasses import dataclass, field
import math
from typing import List, Optional, Tuple

# ---------------------------------------------------------------------------
# Unit cost / rate defaults (USD per individual unit). These mirror the
# fee_engine defaults in amazon_us_fee_rules_2026.py so the two modules agree
# when env overrides are absent.
# ---------------------------------------------------------------------------

REPACKAGING_LABOR_COST_PER_UNIT = 0.50
REPACKAGING_PACKAGING_COST_PER_UNIT = 0.25
DEFAULT_REPACKAGING_COST_PER_UNIT = (
    REPACKAGING_LABOR_COST_PER_UNIT + REPACKAGING_PACKAGING_COST_PER_UNIT
)
DEFAULT_INBOUND_COST_PER_UNIT = 0.35
DEFAULT_PREP_COST_PER_UNIT = 0.25
DEFAULT_RETURN_RESERVE_RATE = 0.02
DEFAULT_REFERRAL_FALLBACK_RATE = 0.15  # Everything Else / flat planning rate

ECON_ESTIMATED = "estimated"
ECON_PROVISIONAL = "provisional"
ECON_UNAVAILABLE = "unavailable"

# ---------------------------------------------------------------------------
# Optional engine imports — never a hard dependency. fee_engine / pricing live
# at the backend root; when they are missing (or raise at call time) this
# module degrades gracefully to documented fallbacks.
# ---------------------------------------------------------------------------

try:  # pragma: no cover - exercised by whatever environment imports us
    import fee_engine as _fee_engine
except ImportError:  # pragma: no cover
    _fee_engine = None

try:  # pragma: no cover
    import pricing as _pricing
except ImportError:  # pragma: no cover
    _pricing = None


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class WholesalePack:
    """A multi-pack product from Costco / Sam's Club."""

    source_store: str  # "Costco" or "Sam's Club"
    product_title: str
    brand: str
    category_slug: str
    pack_count: int  # number of individual sellable units in the pack
    wholesale_price: float  # total cost of the multi-pack
    pack_weight_lbs: Optional[float] = None
    pack_dimensions_in: Optional[List[float]] = None
    individual_unit_weight_oz: Optional[float] = None

    @property
    def wholesale_pack_title(self) -> str:
        """Backward-compatible alias for ``product_title``.

        Older consumers (goose_report, opportunity_scorer's slim fallback
        model) read ``wholesale_pack_title``; the shared model's canonical
        field is ``product_title``. A property keeps both spellings working
        without a second stored field.
        """
        return self.product_title


@dataclass
class IndividualListing:
    """The individual/small-pack version sold on Amazon."""

    asin: str
    title: str
    brand: str
    category_slug: str
    amazon_price: float  # price of the individual unit on Amazon
    amazon_category: Optional[str] = None
    browse_node: Optional[int] = None
    bsr: Optional[int] = None
    review_rating: Optional[float] = None
    review_count: Optional[int] = None
    fba_sellers: Optional[int] = None
    monthly_sales_estimate: Optional[float] = None  # demand signal (provider/BSR estimate)
    is_prime: bool = False
    weight_oz: Optional[float] = None
    dimensions_in: Optional[List[float]] = None
    listing_fba_fee: Optional[float] = None
    # Seller identity — the "who sells it" gate. is_brand_seller True and
    # is_amazon_seller True are HARD BLOCKS (profile rule); None means the
    # seller analyzer could not verify identity (scorer fails closed).
    seller_name: Optional[str] = None
    is_brand_seller: Optional[bool] = None
    is_amazon_seller: Optional[bool] = None


@dataclass
class BreakdownEconomics:
    """Full economic analysis of a multi-pack breakdown opportunity."""

    wholesale: WholesalePack
    individual: IndividualListing
    unit_cogs: Optional[float]  # wholesale_price / pack_count
    repackaging_cost_per_unit: Optional[float]
    referral_fee: Optional[float]
    fulfillment_fee: Optional[float]
    inbound_cost: Optional[float]
    prep_cost: Optional[float]
    packaging_cost: Optional[float]  # packaging share of the repackaging bundle
    return_reserve: Optional[float]
    total_amazon_fees: Optional[float]
    total_costs_per_unit: Optional[float]  # cogs + repackaging + all fees
    net_profit_per_unit: Optional[float]
    net_profit_per_costco_pack: Optional[float]
    roi_per_unit: Optional[float]
    roi_per_costco_pack: Optional[float]
    profit_margin_pct: Optional[float]
    breakeven_amazon_price: Optional[float]
    economics_confidence: str = ECON_UNAVAILABLE
    economics_notes: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Small pure helpers
# ---------------------------------------------------------------------------


def _is_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _positive(value) -> Optional[float]:
    """Positive numeric value, else None. Never coerces strings."""
    if not _is_number(value) or value <= 0:
        return None
    return float(value)


def _positive_int(value) -> Optional[int]:
    """Positive integer (wholesale pack_count), else None."""
    if isinstance(value, bool) or not isinstance(value, int):
        try:
            value = int(value)
        except (TypeError, ValueError):
            return None
    if value <= 0:
        return None
    return value


def _attr(obj, name, default=None):
    """Duck-typed attribute read — consumers may pass objects, not just the
    module dataclasses (mock matches, provider records, scanner rows)."""
    try:
        return getattr(obj, name, default)
    except (AttributeError, TypeError):
        return default


def _unit_costs() -> dict:
    """Env-aware unit costs from fee_engine when available."""
    if _fee_engine is not None:
        try:
            engine_costs = _fee_engine.calculate_unit_costs()
            return {
                "inbound_cost_per_unit": float(engine_costs["inbound_cost_per_unit"]),
                "prep_cost_per_unit": float(engine_costs["prep_cost_per_unit"]),
                "return_reserve_rate": float(engine_costs["return_reserve_rate"]),
            }
        except Exception:
            pass
    return {
        "inbound_cost_per_unit": DEFAULT_INBOUND_COST_PER_UNIT,
        "prep_cost_per_unit": DEFAULT_PREP_COST_PER_UNIT,
        "return_reserve_rate": DEFAULT_RETURN_RESERVE_RATE,
    }


def _referral_fee(
    price: float,
    individual: IndividualListing,
    notes: List[str],
) -> Tuple[Optional[float], bool]:
    """Referral fee via fee_engine's versioned rule, or the 15% flat fallback.

    Returns (fee, verified); ``verified`` is False when the flat fallback was
    used (fee needs verification in Seller Central).
    """
    if _fee_engine is not None:
        try:
            result = _fee_engine.calculate_referral_fee(
                price,
                _attr(individual, "amazon_category"),
                _attr(individual, "browse_node"),
            )
        except Exception:
            result = None
        if isinstance(result, dict) and result.get("referral_fee") is not None:
            if result.get("referral_fee_confidence") == "default_category":
                note = (
                    f"Referral fee resolved to default category "
                    f"'{result.get('referral_fee_category')}' "
                    f"({result.get('referral_fee_rate', 0):.0%}) — no exact "
                    "category/browse node on record; verify in Seller Central."
                )
                if note not in notes:
                    notes.append(note)
            return float(result["referral_fee"]), True
        if isinstance(result, dict) and result.get("referral_fee_note"):
            note = f"Referral fee note: {result['referral_fee_note']}"
            if note not in notes:
                notes.append(note)
    note = (
        "fee_engine unavailable — referral fee estimated at "
        f"{DEFAULT_REFERRAL_FALLBACK_RATE:.0%} flat (Amazon's Everything Else "
        "rate); verify the exact category in Seller Central."
    )
    if note not in notes:
        notes.append(note)
    return round(price * DEFAULT_REFERRAL_FALLBACK_RATE, 2), False


def _package_weight_lbs(
    wholesale: WholesalePack,
    individual: IndividualListing,
) -> Optional[float]:
    """Shipping weight (lbs) for the individual unit, or None when unknown.

    Never invents a weight: listing weight_oz first, then the wholesale pack's
    per-unit weight. A 0 / negative value is treated as missing.
    """
    listing_oz = _positive(_attr(individual, "weight_oz"))
    if listing_oz is not None:
        return listing_oz / 16.0
    unit_oz = _positive(_attr(wholesale, "individual_unit_weight_oz"))
    if unit_oz is not None:
        return unit_oz / 16.0
    return None


def _fba_fee(
    price: float,
    wholesale: WholesalePack,
    individual: IndividualListing,
    notes: List[str],
) -> Tuple[Optional[float], bool]:
    """FBA fulfillment fee with honest fallback ordering.

    Returns (fee, verified). Resolution order:
      1. listing-reported listing_fba_fee (verified — data provider reported);
      2. fee_engine versioned table from package weight (dimensions used for
         the standard-size/oversize check);
      3. pricing.estimate_fba_fee when fee_engine is unavailable/raises but a
         weight exists (fee_engine's table totals equal pricing's validated
         rates; still flagged as a fallback -> provisional overall);
      4. None when no weight basis exists -> the caller marks the economics
         provisional (fee EXCLUDED, never guessed).
    """
    listing_fee = _positive(_attr(individual, "listing_fba_fee"))
    if listing_fee is not None:
        note = (
            f"FBA fee ${listing_fee:.2f}/unit reported by the listing/offer "
            "data provider; used for unit economics."
        )
        if note not in notes:
            notes.append(note)
        return listing_fee, True

    weight = _package_weight_lbs(wholesale, individual)
    if weight is None:
        note = (
            "No package weight available for the individual unit — FBA "
            "fulfillment fee is EXCLUDED from these numbers. Verify in the "
            "Amazon Revenue Calculator before purchasing."
        )
        if note not in notes:
            notes.append(note)
        return None, False

    if _fee_engine is not None:
        try:
            result = _fee_engine.calculate_fba_fulfillment_fee(
                package_weight_lbs=weight,
                package_dimensions_in=_attr(individual, "dimensions_in"),
                sale_price=price,
                product_category=_attr(individual, "amazon_category"),
            )
        except Exception:
            result = None
        if isinstance(result, dict) and result.get("fba_fee") is not None:
            if result.get("fba_fee_confidence") == "listing_reported":
                note = (
                    f"FBA fee ${result['fba_fee']:.2f}/unit reported by the "
                    "listing/offer data provider; used for unit economics."
                )
                if note not in notes:
                    notes.append(note)
            return float(result["fba_fee"]), True
        if isinstance(result, dict) and result.get("fba_fee_note"):
            note = (
                "FBA fee could not be estimated by fee_engine: "
                f"{result['fba_fee_note']}"
            )
            if note not in notes:
                notes.append(note)
            return None, False

    if _pricing is not None:
        try:
            fallback_fee = float(_pricing.estimate_fba_fee(weight))
        except Exception:
            fallback_fee = None
        if fallback_fee is not None:
            note = (
                "fee_engine FBA estimate unavailable — used "
                f"pricing.estimate_fba_fee({weight:.3f} lb) fallback "
                f"(${fallback_fee:.2f}/unit); verify in the Amazon Revenue "
                "Calculator if this surprises you."
            )
            if note not in notes:
                notes.append(note)
            return fallback_fee, False
        note = (
            "fee_engine unavailable and pricing.estimate_fba_fee failed — FBA "
            "fulfillment fee EXCLUDED from these numbers. Verify in the Amazon "
            "Revenue Calculator before purchasing."
        )
        if note not in notes:
            notes.append(note)
        return None, False

    note = (
        "fee engine unavailable — FBA fulfillment fee EXCLUDED from these "
        "numbers. Verify in the Amazon Revenue Calculator before purchasing."
    )
    if note not in notes:
        notes.append(note)
    return None, False


# ---------------------------------------------------------------------------
# Core calculation
# ---------------------------------------------------------------------------


def calculate_breakdown_economics(
    wholesale: WholesalePack,
    individual: IndividualListing,
    repackaging_cost_per_unit: float = DEFAULT_REPACKAGING_COST_PER_UNIT,
    roi_floor: float = 10.00,
) -> BreakdownEconomics:
    """Full breakdown economics for one wholesale pack -> Amazon listing.

    ``roi_floor`` is a planning threshold (percent ROI on the unit) used only
    for the warning note; the filter decision lives in
    :func:`passes_economics_filter`.
    """
    notes: List[str] = []

    price = _positive(_attr(individual, "amazon_price"))
    wholesale_price = _positive(_attr(wholesale, "wholesale_price"))
    pack_count = _positive_int(_attr(wholesale, "pack_count"))

    # -- sanity guards: no invented economics -------------------------------
    guards = []
    if price is None:
        guards.append("No Amazon sale price available.")
    if wholesale_price is None:
        guards.append("No wholesale (Costco/Sam's Club) price available.")
    if pack_count is None:
        guards.append("pack_count is missing or not a positive integer.")
    if guards:
        notes.extend(guards)
        notes.append(
            "Breakdown economics unavailable — net profit/ROI cannot be "
            "calculated (never estimated)."
        )
        return BreakdownEconomics(
            wholesale=wholesale,
            individual=individual,
            unit_cogs=None,
            repackaging_cost_per_unit=None,
            referral_fee=None,
            fulfillment_fee=None,
            inbound_cost=None,
            prep_cost=None,
            packaging_cost=None,
            return_reserve=None,
            total_amazon_fees=None,
            total_costs_per_unit=None,
            net_profit_per_unit=None,
            net_profit_per_costco_pack=None,
            roi_per_unit=None,
            roi_per_costco_pack=None,
            profit_margin_pct=None,
            breakeven_amazon_price=None,
            economics_confidence=ECON_UNAVAILABLE,
            economics_notes=notes,
        )

    unit_cogs = wholesale_price / pack_count

    # -- repackaging bundle (labor + packaging) -----------------------------
    # 0.00 is an EXPLICIT configured zero (no labor/packaging budget); only a
    # missing/non-numeric/negative/NaN value falls back to the default.
    if (
        not _is_number(repackaging_cost_per_unit)
        or float(repackaging_cost_per_unit) < 0
        or math.isnan(float(repackaging_cost_per_unit))
    ):
        repack = DEFAULT_REPACKAGING_COST_PER_UNIT
        note = (
            f"repackaging_cost_per_unit was not a positive number; used the "
            f"default ${DEFAULT_REPACKAGING_COST_PER_UNIT:.2f}/unit "
            f"(${REPACKAGING_LABOR_COST_PER_UNIT:.2f} labor + "
            f"${REPACKAGING_PACKAGING_COST_PER_UNIT:.2f} packaging)."
        )
        if note not in notes:
            notes.append(note)
    else:
        repack = float(repackaging_cost_per_unit)
    packaging_cost = max(0.0, repack - REPACKAGING_LABOR_COST_PER_UNIT)
    if packaging_cost > REPACKAGING_PACKAGING_COST_PER_UNIT:
        note = (
            "repackaging_cost_per_unit exceeds the default labor + packaging "
            "bundle; the excess is attributed to extra packaging/supplies."
        )
        if note not in notes:
            notes.append(note)

    # -- fee stack ---------------------------------------------------------
    referral, referral_verified = _referral_fee(price, individual, notes)
    fulfillment, fba_verified = _fba_fee(price, wholesale, individual, notes)
    unit = _unit_costs()
    inbound_cost = float(unit["inbound_cost_per_unit"])
    prep_cost = float(unit["prep_cost_per_unit"])
    reserve_rate = float(unit["return_reserve_rate"])
    return_reserve = price * reserve_rate

    # -- totals (raw math; rounded only for storage) ------------------------
    fixed_per_unit = (
        unit_cogs
        + repack
        + referral
        + inbound_cost
        + prep_cost
        + return_reserve
    )
    total_per_unit = (
        fixed_per_unit + fulfillment if fulfillment is not None else fixed_per_unit
    )

    net_per_unit = price - total_per_unit
    net_per_pack = net_per_unit * pack_count

    roi_unit = (net_per_unit / unit_cogs * 100.0) if unit_cogs > 0 else None
    roi_pack = (net_per_pack / wholesale_price * 100.0) if wholesale_price > 0 else None
    margin_pct = (net_per_unit / price * 100.0) if price > 0 else None

    # -- confidence + notes -------------------------------------------------
    if fulfillment is None:
        confidence = ECON_PROVISIONAL
        note = (
            "PROVISIONAL — the FBA fulfillment fee is not verified and is "
            "EXCLUDED from the net profit / breakeven figures above. All other "
            "costs (referral, repackaging, inbound, prep, return reserve) are "
            "included."
        )
        if note not in notes:
            notes.append(note)
    elif not (referral_verified and fba_verified):
        confidence = ECON_PROVISIONAL
        note = (
            "PROVISIONAL — one or more fees came from a fallback estimator "
            "(fee_engine upgrade / flat referral / pricing table); verify the "
            "referral and FBA fees in Seller Central / the Amazon Revenue "
            "Calculator before purchasing."
        )
        if note not in notes:
            notes.append(note)
    else:
        confidence = ECON_ESTIMATED
        note = (
            "All costs included: referral fee, FBA fulfillment, repackaging "
            f"${repack:.2f}/unit, inbound ${inbound_cost:.2f}/unit, prep "
            f"${prep_cost:.2f}/unit, return reserve {reserve_rate:.0%} of the "
            "sale price."
        )
        if note not in notes:
            notes.append(note)

    if pack_count == 1:
        note = (
            "pack_count is 1 — this is a straight resale, not a breakdown; "
            "the repackaging labor/packaging costs may be overstated."
        )
        if note not in notes:
            notes.append(note)
    if roi_unit is not None and roi_unit < roi_floor:
        note = (
            f"ROI {roi_unit:.2f}% is below the {roi_floor:.2f}% roi floor — "
            "reconsider before committing capital."
        )
        if note not in notes:
            notes.append(note)

    return BreakdownEconomics(
        wholesale=wholesale,
        individual=individual,
        unit_cogs=round(unit_cogs, 2),
        repackaging_cost_per_unit=round(repack, 2),
        referral_fee=round(referral, 2),
        fulfillment_fee=round(fulfillment, 2) if fulfillment is not None else None,
        inbound_cost=round(inbound_cost, 2),
        prep_cost=round(prep_cost, 2),
        packaging_cost=round(packaging_cost, 2),
        return_reserve=round(return_reserve, 2),
        total_amazon_fees=round(
            referral + (fulfillment if fulfillment is not None else 0.0) + return_reserve,
            2,
        ),
        total_costs_per_unit=round(total_per_unit, 2),
        net_profit_per_unit=round(net_per_unit, 2),
        net_profit_per_costco_pack=round(net_per_pack, 2),
        roi_per_unit=round(roi_unit, 2) if roi_unit is not None else None,
        roi_per_costco_pack=round(roi_pack, 2) if roi_pack is not None else None,
        profit_margin_pct=round(margin_pct, 2) if margin_pct is not None else None,
        breakeven_amazon_price=round(total_per_unit, 2),
        economics_confidence=confidence,
        economics_notes=notes,
    )


def evaluate_batch(
    opportunities: List[Tuple[WholesalePack, IndividualListing]],
    roi_floor: float = 10.00,
) -> List[BreakdownEconomics]:
    """Evaluate every (wholesale, individual) pair in order."""
    return [
        calculate_breakdown_economics(wholesale, individual, roi_floor=roi_floor)
        for wholesale, individual in opportunities
    ]


# ---------------------------------------------------------------------------
# Filter
# ---------------------------------------------------------------------------


def passes_economics_filter(
    economics: BreakdownEconomics,
    roi_floor: float = 10.00,
    min_margin_pct: float = 0.0,
) -> bool:
    """True when the opportunity clears the economics gates.

    - roi_per_unit (percent ROI on the unit) >= roi_floor
    - profit_margin_pct >= min_margin_pct
    - confidence is not "unavailable" and the money fields are present
      (fails closed on missing data — never lets unknown numbers through).

    ``roi_floor`` is a percent-ROI floor (matches the scanner's
    roi_per_unit column); use ``min_margin_pct`` for a margin gate.
    """
    if economics.economics_confidence == ECON_UNAVAILABLE:
        return False
    roi = economics.roi_per_unit
    margin = economics.profit_margin_pct
    if roi is None or margin is None:
        return False
    return float(roi) >= roi_floor and float(margin) >= min_margin_pct