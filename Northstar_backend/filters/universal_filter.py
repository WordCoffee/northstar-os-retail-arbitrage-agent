"""Universal Product Filter — Golden Goose Finder thresholds, applied to ANY
product across all un-gated Amazon categories.

This engine extracts the retail-arbitrage filters that the Golden Goose
Finder profile applies to national-brand Costco/Sam's products and makes
them available as a reusable, category-agnostic filter. Any product dict
carrying the right fields can be filtered and scored with the SAME rules:

  - MIN ROI per unit       >= $10.00 net profit after all Amazon fees
  - Min monthly sales      >= 1,000 units/mo demand floor
  - Preferred weight       <= 32 oz (2 lbs); hard ceiling 80 oz (5 lbs)
  - Max FBA sellers        <= 2 (0 = gold; 1-2 OK if undercut headroom)
  - Brand exclusions       store/private labels always rejected
  - Dynamic brand blacklist  cron-updated gating list (see brand_policy.json)

Design notes:
  * ``defaults`` are instance attributes, so callers can construct a filter
    with overrides (e.g. a user profile that raises the ROI floor).
  * ``apply()`` never raises: a product missing a field simply fails that
    gate with an explanatory reason. Unknown fields are ignored.
  * ``explain_rejection()`` returns the full ordered list of failed gates so
    the UI can show *why* a product was filtered out.
  * Brand checks are case-insensitive substring matches (title contains the
    store-brand token) PLUS an exact/fuzzy brand-name match — matching the
    Golden Goose ``is_brand_allowed`` semantics.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Canonical defaults — keep in sync with
# agents/golden_goose_finder/category_config.py
# ---------------------------------------------------------------------------

DEFAULT_MIN_ROI_PER_UNIT: float = 10.00
DEFAULT_MIN_MONTHLY_SALES: int = 1000
DEFAULT_PREFERRED_MAX_WEIGHT_OZ: float = 32.0   # 2 lbs
DEFAULT_ABS_MAX_WEIGHT_OZ: float = 80.0          # 5 lbs hard ceiling
DEFAULT_MAX_FBA_SELLERS: int = 2
DEFAULT_WEIGHT_LBS_TO_OZ: float = 16.0

# Static store/private-label exclusions (mirrors BRAND_EXCLUSION_LIST).
DEFAULT_BRAND_EXCLUSIONS: List[str] = [
    "Kirkland Signature",
    "Member's Mark",
    "Great Value",
    "Equate",
    "store brand",
    "private label",
]

# Key names the filter reads from a product dict. A product may carry any
# subset; missing keys fail their gate with an explicit reason.
ROI_KEY = "net_profit_per_unit"
PROFIT_KEY = "net_profit"
SALES_KEY = "monthly_sales_estimate"
SALES_KEY_ALT = "monthly_sales"
WEIGHT_KEY = "weight_lbs"
WEIGHT_OZ_KEY = "weight_oz"
FBA_KEY = "fba_sellers"
FBA_KEY_ALT = "competition_fba_sellers"
BRAND_KEY = "brand"
TITLE_KEY = "name"
TITLE_KEY_ALT = "product_title"
TITLE_KEY_ALT2 = "title"
CATEGORY_KEY = "category_slug"
CATEGORY_KEY_ALT = "category"


@dataclass
class FilterResult:
    """Outcome of applying the universal filter to one product."""

    passed: bool
    reasons: List[str] = field(default_factory=list)   # reject reasons (ordered)
    passed_gates: List[str] = field(default_factory=list)
    unknown_gates: List[str] = field(default_factory=list)


def _first(*values: Any) -> Any:
    """Return the first non-None value."""
    for v in values:
        if v is not None:
            return v
    return None


def _to_float(v: Any) -> Optional[float]:
    """Coerce a numeric-ish value to float; None/blank -> None."""
    if v is None:
        return None
    if isinstance(v, bool):
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f


def _to_int(v: Any) -> Optional[int]:
    f = _to_float(v)
    if f is None:
        return None
    return int(f)


def _normalize_brand(brand: Any) -> str:
    if not brand:
        return ""
    return str(brand).strip().lower()


class UniversalProductFilter:
    """Category-agnostic retail-arbitrage filter using Golden Goose rules.

    Example:
        filt = UniversalProductFilter()
        result = filt.apply(product_dict)
        if result.passed:
            ...
        else:
            for reason in result.reasons:
                print(reason)
    """

    def __init__(
        self,
        min_roi_per_unit: float = DEFAULT_MIN_ROI_PER_UNIT,
        min_monthly_sales: int = DEFAULT_MIN_MONTHLY_SALES,
        preferred_max_weight_oz: float = DEFAULT_PREFERRED_MAX_WEIGHT_OZ,
        abs_max_weight_oz: float = DEFAULT_ABS_MAX_WEIGHT_OZ,
        max_fba_sellers: int = DEFAULT_MAX_FBA_SELLERS,
        brand_exclusions: Optional[List[str]] = None,
        brand_blacklist: Optional[List[str]] = None,
        enforce_weight: bool = True,
        enforce_sales: bool = True,
        enforce_roi: bool = True,
        enforce_competition: bool = True,
    ) -> None:
        self.min_roi_per_unit = min_roi_per_unit
        self.min_monthly_sales = min_monthly_sales
        self.preferred_max_weight_oz = preferred_max_weight_oz
        self.abs_max_weight_oz = abs_max_weight_oz
        self.max_fba_sellers = max_fba_sellers
        self.brand_exclusions = list(
            brand_exclusions if brand_exclusions is not None else DEFAULT_BRAND_EXCLUSIONS
        )
        self.brand_blacklist = list(brand_blacklist or [])
        self.enforce_weight = enforce_weight
        self.enforce_sales = enforce_sales
        self.enforce_roi = enforce_roi
        self.enforce_competition = enforce_competition

    # -- field extraction --------------------------------------------------

    def _roi(self, product: Dict[str, Any]) -> Optional[float]:
        """Return net profit per unit (ROI metric is $/unit in this profile).

        The Golden Goose profile's "ROI floor" is a *dollar* floor
        (>= $10 net per unit). ``roi_per_unit`` is a percentage; this gate
        uses the dollar fields so semantics stay identical to the scanner.
        """
        return _to_float(_first(product.get(ROI_KEY), product.get(PROFIT_KEY)))

    def _sales(self, product: Dict[str, Any]) -> Optional[int]:
        return _to_int(_first(product.get(SALES_KEY), product.get(SALES_KEY_ALT)))

    def _weight_oz(self, product: Dict[str, Any]) -> Optional[float]:
        oz = _to_float(_first(product.get(WEIGHT_OZ_KEY)))
        if oz is not None:
            return oz
        lbs = _to_float(product.get(WEIGHT_KEY))
        if lbs is not None:
            return lbs * DEFAULT_WEIGHT_LBS_TO_OZ
        return None

    def _fba_sellers(self, product: Dict[str, Any]) -> Optional[int]:
        return _to_int(_first(product.get(FBA_KEY), product.get(FBA_KEY_ALT)))

    def _brand_value(self, product: Dict[str, Any]) -> str:
        return _normalize_brand(product.get(BRAND_KEY))

    def _title_value(self, product: Dict[str, Any]) -> str:
        raw = _first(
            product.get(TITLE_KEY),
            product.get(TITLE_KEY_ALT),
            product.get(TITLE_KEY_ALT2),
        )
        if not raw:
            return ""
        return str(raw).strip().lower()

    # -- gates -------------------------------------------------------------

    def _gate_brand(self, product: Dict[str, Any]) -> Optional[str]:
        """Return a rejection reason when the product is a blocked brand.

        Checks (in order):
          1. static exclusions (store/private-label tokens in brand OR title)
          2. dynamic blacklist (cron-updated gating list)
        """
        brand = self._brand_value(product)
        title = self._title_value(product)
        haystacks = [b for b in (brand, title) if b]

        for token in self.brand_exclusions:
            t = token.strip().lower()
            if not t:
                continue
            if any(t in h for h in haystacks):
                return f"Brand excluded (store/private label): {token}"
        for token in self.brand_blacklist:
            t = token.strip().lower()
            if not t:
                continue
            if any(t in h for h in haystacks):
                return f"Brand blacklisted (gated): {token}"
        return None

    def _gate_roi(self, product: Dict[str, Any]) -> Optional[str]:
        if not self.enforce_roi:
            return None
        roi = self._roi(product)
        if roi is None:
            return "Net profit per unit unknown"
        if roi < self.min_roi_per_unit:
            return (
                f"Net profit ${roi:.2f}/unit below ${self.min_roi_per_unit:.2f} floor"
            )
        return None

    def _gate_sales(self, product: Dict[str, Any]) -> Optional[str]:
        if not self.enforce_sales:
            return None
        sales = self._sales(product)
        if sales is None:
            return "Monthly sales estimate unknown"
        if sales < self.min_monthly_sales:
            return (
                f"Monthly sales {sales:,} below {self.min_monthly_sales:,} demand floor"
            )
        return None

    def _gate_weight(self, product: Dict[str, Any]) -> Optional[str]:
        if not self.enforce_weight:
            return None
        oz = self._weight_oz(product)
        if oz is None:
            return "Weight unknown"
        if oz > self.abs_max_weight_oz:
            return (
                f"Weight {oz:.0f} oz exceeds {self.abs_max_weight_oz:.0f} oz (5 lbs) hard ceiling"
            )
        if oz > self.preferred_max_weight_oz:
            return (
                f"Weight {oz:.0f} oz above preferred {self.preferred_max_weight_oz:.0f} oz (2 lbs)"
            )
        return None

    def _gate_competition(self, product: Dict[str, Any]) -> Optional[str]:
        if not self.enforce_competition:
            return None
        fba = self._fba_sellers(product)
        if fba is None:
            return "FBA seller count unknown"
        if fba > self.max_fba_sellers:
            return (
                f"{fba} FBA sellers exceed {self.max_fba_sellers} seller limit"
            )
        return None

    # -- public API ---------------------------------------------------------

    def gates(self) -> List[str]:
        """Ordered gate names, for reporting."""
        return ["ROI", "Demand", "Weight", "Competition", "Brand"]

    def gates_blocked(self) -> List[str]:
        """Gates that have been disabled via constructor flags."""
        blocked = []
        if not self.enforce_roi:
            blocked.append("ROI")
        if not self.enforce_sales:
            blocked.append("Demand")
        if not self.enforce_weight:
            blocked.append("Weight")
        if not self.enforce_competition:
            blocked.append("Competition")
        return blocked

    def apply(self, product: Dict[str, Any]) -> FilterResult:
        """Evaluate one product against every enabled gate.

        Returns a FilterResult with passed=True only when NO gate fails.
        A missing field is treated as a failed gate with an explanatory
        reason (fail-closed, matching the scorer's policy).
        """
        if not isinstance(product, dict):
            return FilterResult(passed=False, reasons=["Product is not a dict"])

        brand_reason = self._gate_brand(product)
        if brand_reason is not None:
            return FilterResult(passed=False, reasons=[brand_reason])

        order = [
            ("ROI", self._gate_roi),
            ("Demand", self._gate_sales),
            ("Weight", self._gate_weight),
            ("Competition", self._gate_competition),
        ]
        reasons: List[str] = []
        passed_gates: List[str] = []
        for name, gate in order:
            reason = gate(product)
            if reason is None:
                passed_gates.append(name)
            else:
                reasons.append(reason)

        if not reasons:
            return FilterResult(passed=True, passed_gates=passed_gates)
        return FilterResult(passed=False, reasons=reasons, passed_gates=passed_gates)

    def explain_rejection(self, product: Dict[str, Any]) -> List[str]:
        """Return the ordered list of rejection reasons (empty when passed)."""
        return self.apply(product).reasons

    def filter_all(
        self,
        products: List[Dict[str, Any]],
        keep_rejected: bool = False,
    ) -> List[Dict[str, Any]]:
        """Filter a batch of products.

        Passing products are returned annotated with
        ``universal_filter_passed=True`` and their passed gates under
        ``universal_filter_gates``. When ``keep_rejected`` is True rejected
        products are included annotated with their rejection reasons.
        """
        out: List[Dict[str, Any]] = []
        for p in products:
            result = self.apply(p)
            if result.passed:
                annotated = dict(p)
                annotated["universal_filter_passed"] = True
                annotated["universal_filter_gates"] = result.passed_gates
                annotated.pop("universal_filter_reasons", None)
                out.append(annotated)
            elif keep_rejected:
                annotated = dict(p)
                annotated["universal_filter_passed"] = False
                annotated["universal_filter_reasons"] = result.reasons
                out.append(annotated)
        return out


def default_filter() -> UniversalProductFilter:
    """Construct the canonical filter with Golden Goose defaults."""
    return UniversalProductFilter()


def apply_universal_filter(
    product: Dict[str, Any],
    **overrides: Any,
) -> FilterResult:
    """Convenience one-shot: build a filter from overrides and apply it."""
    return UniversalProductFilter(**overrides).apply(product)