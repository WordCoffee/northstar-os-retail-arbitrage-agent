"""Faire<->Amazon identity matching, exact-match safety, and pack normalization.

PURE / OFFLINE. Implements the matching contract in
docs/northstar-faire-discovery/05-amazon-matching-contract.md and
06-pack-and-case-normalization.md.

Matching priority (strongest identifier first):
  1. Exact GTIN/UPC/EAN.
  2. Exact MPN + brand.
  3. Exact model + brand.
  4. Exact title/size/color/material/package quantity.
  5. High-confidence fuzzy -> manual approval required.

Only EXACT_IDENTIFIER_MATCH / EXACT_ATTRIBUTE_MATCH may advance automatically.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from .enums import MatchConfidence, PackConfiguration


@dataclass
class ProductAttributes:
    brand: Optional[str] = None
    title: Optional[str] = None
    mpn: Optional[str] = None
    model: Optional[str] = None
    gtin: Optional[str] = None
    upc: Optional[str] = None
    ean: Optional[str] = None
    color: Optional[str] = None
    size: Optional[str] = None
    material: Optional[str] = None
    unit_count: Optional[int] = None
    item_package_quantity: Optional[int] = None
    included_accessories: Optional[str] = None


def _norm(s: Optional[str]) -> Optional[str]:
    if s is None:
        return None
    return " ".join(str(s).strip().lower().split())


def _digit(s: Optional[str]) -> Optional[str]:
    if s is None:
        return None
    d = "".join(ch for ch in str(s) if ch.isdigit())
    return d or None


def _gtin(a: ProductAttributes) -> Optional[str]:
    return _digit(a.gtin or a.upc or a.ean)


def _agree(x: Optional[str], y: Optional[str]) -> Optional[bool]:
    """True/False/None(unknown) for a normalized attribute comparison."""
    nx, ny = _norm(x), _norm(y)
    if nx is None or ny is None:
        return None
    return nx == ny


def assess_match(faire: ProductAttributes, amazon: ProductAttributes,
                 *, fuzzy_score: Optional[float] = None) -> Tuple[MatchConfidence, List[str]]:
    """Classify a Faire->Amazon match. Returns (confidence, reasons)."""
    reasons: List[str] = []

    # 1. GTIN
    g1, g2 = _gtin(faire), _gtin(amazon)
    if g1 and g2:
        if g1 == g2:
            if _norm(faire.brand) and _norm(amazon.brand) and _norm(faire.brand) != _norm(amazon.brand):
                return MatchConfidence.MISMATCH, ["GTIN matches but brand differs"]
            return MatchConfidence.EXACT_IDENTIFIER_MATCH, ["exact GTIN/UPC/EAN match"]

    # 2. MPN + brand
    if _norm(faire.mpn) and _norm(amazon.mpn) and _norm(faire.brand) and _norm(amazon.brand):
        if _norm(faire.mpn) == _norm(amazon.mpn) and _norm(faire.brand) == _norm(amazon.brand):
            return MatchConfidence.EXACT_IDENTIFIER_MATCH, ["exact MPN + brand match"]

    # 3. model + brand
    if _norm(faire.model) and _norm(amazon.model) and _norm(faire.brand) and _norm(amazon.brand):
        if _norm(faire.model) == _norm(amazon.model) and _norm(faire.brand) == _norm(amazon.brand):
            return MatchConfidence.EXACT_IDENTIFIER_MATCH, ["exact model + brand match"]

    # 4. attribute agreement
    checks = {
        "brand": _agree(faire.brand, amazon.brand),
        "color": _agree(faire.color, amazon.color),
        "size": _agree(faire.size, amazon.size),
        "material": _agree(faire.material, amazon.material),
        "included_accessories": _agree(faire.included_accessories, amazon.included_accessories),
    }
    for name, ok in checks.items():
        if ok is False:
            return MatchConfidence.MISMATCH, ["%s differs" % name]

    if faire.unit_count is not None and amazon.unit_count is not None:
        if faire.unit_count != amazon.unit_count:
            return MatchConfidence.MISMATCH, ["unit_count differs (%s vs %s)" % (faire.unit_count, amazon.unit_count)]
    if faire.item_package_quantity is not None and amazon.item_package_quantity is not None:
        if faire.item_package_quantity != amazon.item_package_quantity:
            return MatchConfidence.MISMATCH, ["item_package_quantity differs"]

    known = [v for v in checks.values() if v is True]
    if _norm(faire.brand) and _norm(amazon.brand) and checks["brand"] and len(known) >= 3:
        return MatchConfidence.EXACT_ATTRIBUTE_MATCH, ["brand+%d attributes agree; no GTIN evidence" % (len(known) - 1)]
    if _norm(faire.brand) and _norm(amazon.brand) and checks["brand"]:
        if fuzzy_score is not None and fuzzy_score >= 0.6:
            return MatchConfidence.PROBABLE_MATCH_REVIEW_REQUIRED, ["brand agrees, partial attributes, fuzzy %.2f" % fuzzy_score]
        return MatchConfidence.AMBIGUOUS, ["brand agrees but attributes incomplete"]
    return MatchConfidence.INSUFFICIENT_DATA, ["insufficient identifiers"]


def pack_configuration(units_per_case: Optional[int], inner_units: Optional[int],
                       *, manufacturer_multipack: bool = False,
                       seller_created: bool = False,
                       bundle_of_different: bool = False,
                       display_pack: bool = False,
                       retail_ready_singles: bool = False) -> PackConfiguration:
    if bundle_of_different:
        return PackConfiguration.BUNDLE_OF_DIFFERENT_PRODUCTS
    if seller_created:
        return PackConfiguration.SELLER_CREATED_MULTIPACK
    if manufacturer_multipack:
        return PackConfiguration.MANUFACTURER_MULTIPACK
    if display_pack:
        return PackConfiguration.DISPLAY_PACK
    if inner_units and units_per_case and inner_units < units_per_case:
        return PackConfiguration.INNER_PACK
    if units_per_case and units_per_case > 1 and retail_ready_singles:
        return PackConfiguration.MANUFACTURER_SINGLE_UNITS_INSIDE_CASE
    if units_per_case and units_per_case > 1:
        return PackConfiguration.WHOLESALE_SHIPPING_CASE
    return PackConfiguration.PACK_CONFIGURATION_UNKNOWN


def case_break_allowed(*, retail_ready_unit: bool, matches_single_asin: bool,
                       correct_label: bool, no_not_for_individual_sale: bool,
                       brand_terms_allow: bool, no_sealed_packaging_required: bool,
                       undamaged_by_separation: bool, amazon_condition_met: bool,
                       direct_supplier_permits_amazon: bool) -> Tuple[bool, List[str]]:
    """Case-break singles are allowed only if EVERY condition holds."""
    checks = {
        "retail_ready_unit": retail_ready_unit,
        "matches_single_asin": matches_single_asin,
        "correct_label": correct_label,
        "no_not_for_individual_sale": no_not_for_individual_sale,
        "brand_terms_allow": brand_terms_allow,
        "no_sealed_packaging_required": no_sealed_packaging_required,
        "undamaged_by_separation": undamaged_by_separation,
        "amazon_condition_met": amazon_condition_met,
        "direct_supplier_permits_amazon": direct_supplier_permits_amazon,
    }
    failed = [k for k, v in checks.items() if not v]
    return (not failed), failed
