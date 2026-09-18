"""Supplier cost-benefit analysis — pre-account profitability engine.

Computes full unit economics for a wholesale supplier product (from a public
catalog or a business-center price list) matched against an Amazon listing,
reusing the shared pricing/finance engines so the numbers match the rest of
Northstar OS (SourceScout, Golden Goose).

Decision flags (mirrors the supplier_cost_analysis table CHECK constraint):
    viable             — meets ROI % + profit margin % + $/unit floors
    marginal           — clears the $/unit floor but misses a % floor
    reject             — fails the $/unit floor (or negative profit)
    needs_manual_review — missing critical inputs; cannot compute honestly

Thresholds (config-driven via config/supplier_intelligence.json):
    min_roi_pct              20.0
    min_profit_margin_pct    15.0
    min_net_profit_per_unit  5.0

Inputs are name-keyed dicts (the shapes used by SuppliersDB / catalog
ingestion / Amazon matcher), so this engine has no hard dependency on any
dataclass.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# Graceful import: pricing.py is the canonical shared engine; fall back to
# local math only if it is somehow unavailable (never crash the module).
try:
    from pricing import estimate_financial_profile, estimate_fba_fee, compute_profit
except ImportError:  # pragma: no cover - defensive
    estimate_financial_profile = None
    estimate_fba_fee = None
    compute_profit = None

# ---------------------------------------------------------------------------
# Decision vocabulary
# ---------------------------------------------------------------------------

VIABLE = "viable"
MARGINAL = "marginal"
REJECT = "reject"
MANUAL_REVIEW = "needs_manual_review"
DECISION_FLAGS = (VIABLE, MARGINAL, REJECT, MANUAL_REVIEW)

# ---------------------------------------------------------------------------
# Default thresholds (mirror config/supplier_intelligence.json analysis)
# ---------------------------------------------------------------------------

DEFAULT_MIN_ROI_PCT = 20.0
DEFAULT_MIN_PROFIT_MARGIN_PCT = 15.0
DEFAULT_MIN_NET_PROFIT_PER_UNIT = 5.0


def _load_thresholds() -> Dict[str, float]:
    """Read analysis thresholds from config when present."""
    cfg = Path(__file__).resolve().parent.parent / "config" / "supplier_intelligence.json"
    try:
        with open(cfg, "r", encoding="utf-8") as f:
            data = json.load(f)
        analysis = data.get("analysis", {})
        return {
            "min_roi_pct": float(analysis.get("min_roi_pct", DEFAULT_MIN_ROI_PCT)),
            "min_profit_margin_pct": float(analysis.get("min_profit_margin_pct", DEFAULT_MIN_PROFIT_MARGIN_PCT)),
            "min_net_profit_per_unit": float(analysis.get("min_net_profit_per_unit", DEFAULT_MIN_NET_PROFIT_PER_UNIT)),
        }
    except (OSError, ValueError, TypeError, AttributeError):
        return {
            "min_roi_pct": DEFAULT_MIN_ROI_PCT,
            "min_profit_margin_pct": DEFAULT_MIN_PROFIT_MARGIN_PCT,
            "min_net_profit_per_unit": DEFAULT_MIN_NET_PROFIT_PER_UNIT,
        }


def _is_number(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _first(*values: Any) -> Any:
    for v in values:
        if v is not None:
            return v
    return None


@dataclass
class CostBenefitResult:
    """Full pre-account cost-benefit output for one supplier product."""

    supplier_product_id: Optional[str] = None
    amazon_asin: Optional[str] = None
    product_name: Optional[str] = None

    # economics
    wholesale_price: Optional[float] = None
    unit_count: Optional[int] = None
    unit_cogs: Optional[float] = None
    amazon_price: Optional[float] = None
    fba_fee_estimate: Optional[float] = None
    referral_fee_estimate: Optional[float] = None
    inbound_cost_estimate: Optional[float] = None
    prep_cost_estimate: Optional[float] = None
    landed_cost: Optional[float] = None
    estimated_net_profit: Optional[float] = None
    estimated_roi_pct: Optional[float] = None
    profit_margin_pct: Optional[float] = None

    # decision
    min_roi_threshold: float = DEFAULT_MIN_ROI_PCT
    meets_threshold: bool = False
    decision_flag: str = MANUAL_REVIEW
    notes: List[str] = field(default_factory=list)
    analysis_date: Optional[str] = None

    def as_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "supplier_product_id": self.supplier_product_id,
            "amazon_asin": self.amazon_asin,
            "product_name": self.product_name,
            "wholesale_price": self.wholesale_price,
            "unit_count": self.unit_count,
            "unit_cogs": self.unit_cogs,
            "amazon_price": self.amazon_price,
            "fba_fee_estimate": self.fba_fee_estimate,
            "referral_fee_estimate": self.referral_fee_estimate,
            "inbound_cost_estimate": self.inbound_cost_estimate,
            "prep_cost_estimate": self.prep_cost_estimate,
            "landed_cost": self.landed_cost,
            "estimated_net_profit": self.estimated_net_profit,
            "estimated_roi_pct": self.estimated_roi_pct,
            "profit_margin_pct": self.profit_margin_pct,
            "min_roi_threshold": self.min_roi_threshold,
            "meets_threshold": self.meets_threshold,
            "decision_flag": self.decision_flag,
            "notes": self.notes,
            "analysis_date": self.analysis_date,
        }
        return d


def decision_flag(
    net_profit: Optional[float],
    roi_pct: Optional[float],
    margin_pct: Optional[float],
    min_net_profit: float,
    min_roi_pct: float,
    min_margin_pct: float,
) -> str:
    """Classify an opportunity using the universal decision matrix.

    Order of evaluation (documented, deterministic):
      1. net_profit is None or <= 0           -> reject (no profit to chase)
      2. net_profit < min_net_profit          -> reject
      3. roi_pct is None or margin_pct is None -> needs_manual_review
         (profit exists but a % floor is uncomputable — operator review)
      4. roi_pct < min_roi_pct or margin_pct < min_margin_pct -> marginal
      5. otherwise                            -> viable
    """
    if net_profit is None or net_profit <= 0:
        return REJECT
    if net_profit < min_net_profit:
        return REJECT
    if roi_pct is None or margin_pct is None:
        return MANUAL_REVIEW
    if roi_pct < min_roi_pct or margin_pct < min_margin_pct:
        return MARGINAL
    return VIABLE


class SupplierCostBenefitAnalyzer:
    """Analyze one wholesale supplier product against one Amazon listing.

    Input shapes (dicts, to stay binding-agnostic):

        supplier_product = {
            "id": "...", "product_name": "...", "brand": "...",
            "wholesale_price": 18.50, "pack_size": "360 ct",
            "unit_count": 360, "moq": 12, "currency": "USD",
            "weight_lbs": 1.5, ...   (weight optional)
        }

        amazon_match = {
            "asin": "B0...", "title": "...", "brand": "...",
            "amazon_price": 34.99, "monthly_sales_estimate": 2500,
            "fba_sellers": 1, "browse_node": 3760901, ... (optional)
        }
    """

    def __init__(
        self,
        min_roi_pct: Optional[float] = None,
        min_profit_margin_pct: Optional[float] = None,
        min_net_profit_per_unit: Optional[float] = None,
        referral_rate: float = 0.15,
        inbound_cost_per_unit: float = 0.35,
        prep_cost_per_unit: Optional[float] = None,
    ) -> None:
        t = _load_thresholds()
        self.min_roi_pct = min_roi_pct if min_roi_pct is not None else t["min_roi_pct"]
        self.min_profit_margin_pct = (
            min_profit_margin_pct if min_profit_margin_pct is not None else t["min_profit_margin_pct"]
        )
        self.min_net_profit_per_unit = (
            min_net_profit_per_unit if min_net_profit_per_unit is not None else t["min_net_profit_per_unit"]
        )
        self.referral_rate = referral_rate
        self.inbound_cost_per_unit = inbound_cost_per_unit
        self.prep_cost_per_unit = prep_cost_per_unit

    # -- helpers ------------------------------------------------------------

    def _unit_cogs(self, product: Dict[str, Any]) -> Optional[float]:
        """Wholesale price per sellable unit."""
        price = _first(product.get("wholesale_price"), product.get("price"))
        if not _is_number(price) or price <= 0:
            return None
        units = _first(product.get("unit_count"), product.get("pack_count"))
        if _is_number(units) and units > 0:
            return price / float(units)
        return price  # single-unit items: wholesale price IS unit cogs

    def _weight_lbs(self, product: Dict[str, Any]) -> Optional[float]:
        w = product.get("weight_lbs")
        if _is_number(w) and w > 0:
            return float(w)
        return None

    def _amazon_price(self, match: Dict[str, Any]) -> Optional[float]:
        p = _first(
            match.get("amazon_price"),
            match.get("buy_box_price"),
            match.get("price"),
        )
        if _is_number(p) and p > 0:
            return float(p)
        return None

    # -- main entry ---------------------------------------------------------

    def analyze(
        self,
        supplier_product: Dict[str, Any],
        amazon_match: Optional[Dict[str, Any]] = None,
        weight_lbs: Optional[float] = None,
    ) -> CostBenefitResult:
        notes: List[str] = []
        now = datetime.now(timezone.utc).isoformat()

        result = CostBenefitResult(
            supplier_product_id=supplier_product.get("id"),
            amazon_asin=amazon_match.get("asin") if amazon_match else None,
            product_name=_first(
                supplier_product.get("product_name"),
                amazon_match.get("title") if amazon_match else None,
            ),
            wholesale_price=_first(supplier_product.get("wholesale_price"), supplier_product.get("price")),
            unit_count=_first(supplier_product.get("unit_count"), supplier_product.get("pack_count")),
            analysis_date=now,
            min_roi_threshold=self.min_roi_pct,
        )

        unit_cogs = self._unit_cogs(supplier_product)
        if unit_cogs is None:
            result.decision_flag = MANUAL_REVIEW
            result.notes.append("Missing wholesale price — cannot compute economics.")
            return result
        result.unit_cogs = round(unit_cogs, 4)

        w = weight_lbs if weight_lbs is not None else self._weight_lbs(supplier_product)
        result.fba_fee_estimate = estimate_fba_fee(w) if w is not None and estimate_fba_fee else None

        mp = self._amazon_price(amazon_match or {})
        if mp is None:
            result.decision_flag = MANUAL_REVIEW
            result.notes.append("Missing Amazon price — cannot compute net profit.")
            return result
        result.amazon_price = mp

        # Referral fee: use a browse-node-derived category if provided, else
        # the analyzer default rate (15% Everything Else).
        referral = round(self.referral_rate * mp, 2)
        result.referral_fee_estimate = referral

        fba = result.fba_fee_estimate
        inbound = self.inbound_cost_per_unit
        prep = self.prep_cost_per_unit

        # Landed cost = unit COGS + per-unit inbound + per-unit prep.
        landed = unit_cogs + inbound + (prep or 0.0)
        result.inbound_cost_estimate = inbound
        result.prep_cost_estimate = prep
        result.landed_cost = round(landed, 4)

        net_profit = mp - landed - referral - (fba or 0.0)
        result.estimated_net_profit = round(net_profit, 4)

        roi_pct = (net_profit / landed * 100) if landed > 0 else None
        result.estimated_roi_pct = round(roi_pct, 2) if roi_pct is not None else None

        margin_pct = (net_profit / mp * 100) if mp > 0 else None
        result.profit_margin_pct = round(margin_pct, 2) if margin_pct is not None else None

        if fba is None:
            notes.append("FBA fee unknown (no weight) — fee excluded from net profit; verify before purchase.")

        result.decision_flag = decision_flag(
            net_profit=result.estimated_net_profit,
            roi_pct=result.estimated_roi_pct,
            margin_pct=result.profit_margin_pct,
            min_net_profit=self.min_net_profit_per_unit,
            min_roi_pct=self.min_roi_pct,
            min_margin_pct=self.min_profit_margin_pct,
        )
        result.meets_threshold = result.decision_flag == VIABLE

        if result.decision_flag == VIABLE:
            notes.append(
                f"Meets thresholds: ${result.estimated_net_profit:.2f}/unit, "
                f"{result.estimated_roi_pct:.0f}% ROI, {result.profit_margin_pct:.0f}% margin."
            )
        elif result.decision_flag == MARGINAL:
            notes.append(
                f"Marginal: ${result.estimated_net_profit:.2f}/unit profit but below "
                f"{self.min_roi_pct:.0f}% ROI / {self.min_profit_margin_pct:.0f}% margin floor."
            )
        elif result.decision_flag == REJECT:
            notes.append(
                f"Rejected: ${result.estimated_net_profit:.2f}/unit below "
                f"${self.min_net_profit_per_unit:.2f} floor."
            )

        result.notes = notes
        return result


def analyze_supplier_product(
    supplier_product: Dict[str, Any],
    amazon_match: Optional[Dict[str, Any]] = None,
    **kwargs: Any,
) -> CostBenefitResult:
    """Module-level convenience wrapper."""
    return SupplierCostBenefitAnalyzer(**kwargs).analyze(supplier_product, amazon_match)