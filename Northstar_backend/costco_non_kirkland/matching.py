"""Offline Costco -> Amazon match queue.

PURE / OFFLINE. Identity is evaluated SEPARATELY from economics. Matching
priority:

  1. Exact UPC/EAN/GTIN match.
  2. Exact manufacturer part number + brand match.
  3. Brand + normalized title + exact pack/count/size match.
  4. Title/brand candidate matching only -> manual review.

Never treats a similar title as verified when pack count, unit size, case-pack
vs retail unit, uncertain child variation, conflicting UPC, or brand differ.
Never calculates ROI for identity-conflicted or pack-mismatched records
(enforced by `economics.compute_economics` seeing identity_status).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional, Tuple

from .enums import IdentityStatus
from .normalize import normalize_brand, normalize_title

ASSESSMENT_PRIORITY = (
    "upc_exact",
    "mpn_brand_exact",
    "brand_title_pack_exact",
    "title_brand_candidate",
)


@dataclass
class AmazonAttributes:
    """Amazon-side attributes used for matching."""
    asin: Optional[str] = None
    title: Optional[str] = None
    brand: Optional[str] = None
    upc: Optional[str] = None
    ean: Optional[str] = None
    gtin: Optional[str] = None
    manufacturer_part_number: Optional[str] = None
    model_number: Optional[str] = None
    pack_count: Optional[int] = None
    unit_count: Optional[int] = None
    unit_size: Optional[str] = None      # e.g. "12 oz", "1 gal"
    pack_text: Optional[str] = None
    is_variation_child: bool = False
    parent_asin: Optional[str] = None


class MatchMethod:
    UPC_EXACT = "upc_exact"
    MPN_BRAND_EXACT = "manufacturer_part_exact"
    BRAND_TITLE_PACK_EXACT = "brand_title_pack_exact"
    TITLE_BRAND_CANDIDATE = "title_brand_candidate"


def _digit(x: Optional[Any]) -> Optional[str]:
    if x is None:
        return None
    d = "".join(ch for ch in str(x) if ch.isdigit())
    return d or None


def _norm(x: Optional[Any]) -> Optional[str]:
    if x is None:
        return None
    s = " ".join(str(x).strip().lower().split())
    return s or None


def _title_similarity(a: Optional[str], b: Optional[str]) -> float:
    na, nb = normalize_title(a), normalize_title(b)
    if not na or not nb:
        return 0.0
    return round(SequenceMatcher(None, na, nb).ratio(), 4)


def _extract_pack_count(text: Optional[str]) -> Optional[int]:
    if not text:
        return None
    m = re.search(r"(\d+)\s*(?:-|\s)?(?:count|ct|pk|pack|pieces?|tablets?|tabs?|capsules?|rolls?|sheets?|bags?|bottles?)\b", text, re.IGNORECASE)
    if m:
        return int(m.group(1))
    m = re.search(r"(\d+)\s*-?\s*pack\b", text, re.IGNORECASE)
    if m:
        return int(m.group(1))
    return None


def assess_pack_identity(costco_pack: Optional[Any], amazon_pack: Optional[Any],
                         costco_unit_size: Optional[str] = None,
                         amazon_unit_size: Optional[str] = None) -> Tuple[Optional[bool], str]:
    """Evaluate pack identity. Returns (pack_match: True/False/None, note).

    Rules:
      - Both known and equal        -> True (exact pack)
      - Both known and different    -> False (PACK_MISMATCH)
      - One or both unknown         -> None (cannot confirm)
      - case vs single unit         -> False when known and differ
      - unit sizes differ           -> False (SIZE_MISMATCH)
    """
    cp = int(costco_pack) if costco_pack not in (None, "", 0) else None
    ap = int(amazon_pack) if amazon_pack not in (None, "", 0) else None
    if cp is not None and ap is not None:
        if cp == ap:
            return (True, "pack counts match")
        return (False, f"PACK_MISMATCH: Costco {cp} vs Amazon {ap}")

    if costco_unit_size and amazon_unit_size:
        cs, a_s = _norm(costco_unit_size), _norm(amazon_unit_size)
        if cs and a_s and cs != a_s:
            return (False, f"SIZE_MISMATCH: Costco '{costco_unit_size}' vs Amazon '{amazon_unit_size}'")

    return (None, "pack identity not fully confirmed (missing pack on one side)")


@dataclass
class MatchAssessment:
    method: str
    identity_status: str
    match_confidence: float          # 0..1
    title_similarity: float          # 0..1
    brand_match_status: str          # match | conflict | unknown | missing
    pack_match_status: str           # exact | mismatch | unconfirmed | n/a
    size_match_status: str           # match | mismatch | unconfirmed | n/a
    variation_match_status: str      # verified | ambiguous | unknown | n/a
    match_rationale: str
    manual_review_required: bool
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "method": self.method,
            "identity_status": self.identity_status,
            "match_confidence": self.match_confidence,
            "title_similarity": self.title_similarity,
            "brand_match_status": self.brand_match_status,
            "pack_match_status": self.pack_match_status,
            "size_match_status": self.size_match_status,
            "variation_match_status": self.variation_match_status,
            "match_rationale": self.match_rationale,
            "manual_review_required": self.manual_review_required,
            "notes": list(self.notes),
        }


def assess_amazon_match(costco: Dict[str, Any], amazon: AmazonAttributes,
                        *, allow_title_candidate: bool = True) -> MatchAssessment:
    """Assess a single Costco record against one Amazon candidate.

    `costco` is a canonical normalized costco_source_product dict (or a raw
    dict with the same field names).
    """
    c_brand = normalize_brand(costco.get("brand_normalized") or costco.get("brand_raw") or costco.get("brand"))
    a_brand = normalize_brand(amazon.brand)
    c_upc = _digit(costco.get("upc"))
    a_upc = _digit(amazon.upc or amazon.gtin or amazon.ean)
    c_ean = _digit(costco.get("ean"))
    a_ean = _digit(amazon.ean)
    c_gtin = _digit(costco.get("gtin"))
    a_gtin = _digit(amazon.gtin)
    c_mpn = _norm(costco.get("manufacturer_part_number"))
    a_mpn = _norm(amazon.manufacturer_part_number)

    # Brand comparison
    if c_brand and a_brand:
        if c_brand == a_brand:
            brand_status = "match"
        else:
            brand_status = "conflict"
    elif c_brand or a_brand:
        brand_status = "unknown"
    else:
        brand_status = "missing"

    # --- 1. UPC/GTIN exact ---
    g1 = _digit(costco.get("gtin") or costco.get("upc") or costco.get("ean"))
    g2 = _digit(amazon.gtin or amazon.upc or amazon.ean)
    if g1 and g2 and g1 == g2:
        if brand_status == "conflict":
            return MatchAssessment(
                method=MatchMethod.UPC_EXACT, identity_status=IdentityStatus.IDENTITY_CONFLICT.value,
                match_confidence=0.9, title_similarity=_title_similarity(costco.get("title_raw"), amazon.title),
                brand_match_status=brand_status, pack_match_status="unconfirmed",
                size_match_status="unconfirmed", variation_match_status="unknown",
                match_rationale="UPC matches but brand differs -> identity conflict",
                manual_review_required=True, notes=["UPC exact", "brand conflict"],
            )
        return MatchAssessment(
            method=MatchMethod.UPC_EXACT, identity_status=IdentityStatus.UPC_EXACT_CANDIDATE.value,
            match_confidence=0.95, title_similarity=_title_similarity(costco.get("title_raw"), amazon.title),
            brand_match_status=brand_status, pack_match_status="unconfirmed",
            size_match_status="unconfirmed", variation_match_status="unknown",
            match_rationale="Exact UPC/GTIN/EAN match",
            manual_review_required=False,
        )

    # --- 2. MPN + brand exact ---
    if c_mpn and a_mpn and c_brand and a_brand and c_mpn == a_mpn and c_brand == a_brand:
        return MatchAssessment(
            method=MatchMethod.MPN_BRAND_EXACT, identity_status=IdentityStatus.MANUFACTURER_PART_EXACT_CANDIDATE.value,
            match_confidence=0.9, title_similarity=_title_similarity(costco.get("title_raw"), amazon.title),
            brand_match_status=brand_status, pack_match_status="unconfirmed",
            size_match_status="unconfirmed", variation_match_status="unknown",
            match_rationale="Exact manufacturer part number + brand match",
            manual_review_required=False,
        )

    # --- 3. Brand + title + exact pack ---
    pack_match, pack_note = assess_pack_identity(
        costco.get("normalized_unit_count"), amazon.pack_count,
        costco.get("size_or_weight_raw"), amazon.unit_size,
    )
    similarity = _title_similarity(costco.get("title_raw"), amazon.title)
    # Variation child with uncertain identity never advances automatically.
    if amazon.is_variation_child and similarity >= 0.6 and c_brand and a_brand and c_brand == a_brand:
        return MatchAssessment(
            method=MatchMethod.TITLE_BRAND_CANDIDATE, identity_status=IdentityStatus.VARIATION_AMBIGUOUS.value,
            match_confidence=0.4, title_similarity=similarity,
            brand_match_status=brand_status,
            pack_match_status="exact" if pack_match is True else "mismatch" if pack_match is False else "unconfirmed",
            size_match_status="match" if pack_match is True else "unconfirmed",
            variation_match_status="ambiguous",
            match_rationale="Amazon candidate is a child variation with uncertain identity; manual review required",
            manual_review_required=True, notes=["variation child, identity ambiguous"],
        )
    if c_brand and a_brand and c_brand == a_brand and similarity >= 0.70:
        if pack_match is True:
            return MatchAssessment(
                method=MatchMethod.BRAND_TITLE_PACK_EXACT, identity_status=IdentityStatus.TITLE_PACK_CANDIDATE.value,
                match_confidence=0.8, title_similarity=similarity,
                brand_match_status=brand_status, pack_match_status="exact",
                size_match_status="match" if _norm(costco.get("size_or_weight_raw")) and _norm(amazon.unit_size) and _norm(costco.get("size_or_weight_raw")) == _norm(amazon.unit_size) else "unconfirmed",
                variation_match_status="unknown", match_rationale="Brand + normalized title + exact pack count match",
                manual_review_required=False,
            )
        if pack_match is False:
            return MatchAssessment(
                method=MatchMethod.BRAND_TITLE_PACK_EXACT, identity_status=IdentityStatus.PACK_MISMATCH.value,
                match_confidence=0.5, title_similarity=similarity,
                brand_match_status=brand_status, pack_match_status="mismatch",
                size_match_status="mismatch" if "SIZE_MISMATCH" in pack_note else "unconfirmed",
                variation_match_status="unknown", match_rationale=f"Brand+title match but {pack_note}",
                manual_review_required=True, notes=[pack_note],
            )

    # --- 4. Title/brand candidate (manual review) ---
    if allow_title_candidate and similarity >= 0.6 and brand_status in ("match", "unknown"):
        reason = "Title/brand candidate match; requires manual review"
        if pack_match is False:
            return MatchAssessment(
                method=MatchMethod.TITLE_BRAND_CANDIDATE, identity_status=IdentityStatus.PACK_MISMATCH.value,
                match_confidence=0.4, title_similarity=similarity,
                brand_match_status=brand_status, pack_match_status="mismatch",
                size_match_status="mismatch" if "SIZE_MISMATCH" in pack_note else "unconfirmed",
                variation_match_status="unknown", match_rationale=f"{reason}; {pack_note}",
                manual_review_required=True, notes=[pack_note],
            )
        return MatchAssessment(
            method=MatchMethod.TITLE_BRAND_CANDIDATE, identity_status=IdentityStatus.MANUAL_REVIEW_REQUIRED.value,
            match_confidence=0.4, title_similarity=similarity,
            brand_match_status=brand_status, pack_match_status="exact" if pack_match is True else "unconfirmed",
            size_match_status="match" if pack_match is True and _norm(costco.get("size_or_weight_raw")) and _norm(amazon.unit_size) and _norm(costco.get("size_or_weight_raw")) == _norm(amazon.unit_size) else "unconfirmed",
            variation_match_status="ambiguous" if amazon.is_variation_child else "unknown",
            match_rationale=reason, manual_review_required=True,
        )

    return MatchAssessment(
        method="no_match", identity_status=IdentityStatus.UNRESOLVED.value,
        match_confidence=0.0, title_similarity=similarity,
        brand_match_status=brand_status, pack_match_status="unconfirmed",
        size_match_status="unconfirmed", variation_match_status="unknown",
        match_rationale="No strong identifier match found",
        manual_review_required=True,
    )


def build_match_candidate(costco: Dict[str, Any], amazon: AmazonAttributes,
                          *, allow_title_candidate: bool = True) -> Dict[str, Any]:
    """Build a canonical `amazon_match_candidate` record dict."""
    assess = assess_amazon_match(costco, amazon, allow_title_candidate=allow_title_candidate)
    return {
        "costco_source_product_id": costco.get("id"),
        "asin": amazon.asin,
        "marketplace": "US",
        "match_method": assess.method,
        "match_confidence": assess.match_confidence,
        "title_similarity": assess.title_similarity,
        "brand_match_status": assess.brand_match_status,
        "pack_match_status": assess.pack_match_status,
        "size_match_status": assess.size_match_status,
        "variation_match_status": assess.variation_match_status,
        "identity_status": assess.identity_status,
        "match_rationale": assess.match_rationale,
        "manual_review_required": assess.manual_review_required,
        "amazon_title": amazon.title,
        "amazon_brand": amazon.brand,
    }