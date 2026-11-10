"""Source-to-ASIN identity validation (Phase 4).

PURE / OFFLINE / DETERMINISTIC. Links a Costco / approved-source product to a
provider-reported Amazon listing using the evidence priority:

  1. UPC / EAN exact match
  2. MPN + brand exact match
  3. Manufacturer + model + pack/unit equivalence
  4. Brand + normalized title + exact unit/pack equivalence
  5. Title-only candidate — never qualifies automatically

Identity is evaluated SEPARATELY from economics. This module produces the
`IdentityState` state machine and `SplitPackState` decisions.

Title similarity NEVER overrides a pack, UPC, brand, variation, formula, or
manufacturer-bundle mismatch.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional, Tuple

from .enums import IdentityState, SplitPackState
from .normalize import normalize_brand, normalize_title
from .settings import get_settings


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


def _settings_sim_candidate(settings: Optional[Dict[str, Any]]) -> float:
    return float((settings or {}).get("title_similarity_candidate", 0.60))


def _title_similarity(a: Optional[str], b: Optional[str]) -> float:
    na, nb = normalize_title(a), normalize_title(b)
    if not na or not nb:
        return 0.0
    return round(SequenceMatcher(None, na, nb).ratio(), 4)


def _brand_match(source_brand: Optional[str], listing_brand: Optional[str]) -> str:
    sb, lb = normalize_brand(source_brand), normalize_brand(listing_brand)
    if sb and lb:
        return "match" if sb == lb else "conflict"
    if sb or lb:
        return "unknown"
    return "missing"


def _unit_equivalence(source: Dict[str, Any], listing: Dict[str, Any]) -> Tuple[Optional[bool], str]:
    """Compare unit/pack equivalence. Returns (match True/False/None, note)."""
    sp = source.get("normalized_unit_count") or source.get("item_count") or source.get("pack_count")
    lp = listing.get("item_count") or listing.get("pack_count") or listing.get("unit_count")
    if sp is not None and lp is not None:
        if int(sp) == int(lp):
            return (True, "unit/pack counts match")
        return (False, f"unit/pack mismatch: source {sp} vs listing {lp}")
    # unit measure text compare
    sm = _norm(source.get("unit_measure") or source.get("size_or_weight_raw") or source.get("unit_size"))
    lm = _norm(listing.get("unit_measure") or listing.get("unit_size"))
    if sm and lm:
        if sm == lm:
            return (True, "unit measure matches")
        return (False, f"unit measure mismatch: '{sm}' vs '{lm}'")
    return (None, "unit equivalence not confirmed (missing pack/size on one side)")


@dataclass
class IdentityAssessment:
    state: str
    method: str
    match_confidence: float
    title_similarity: float
    brand_match_status: str
    unit_equivalence: Optional[bool]
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "state": self.state,
            "method": self.method,
            "match_confidence": self.match_confidence,
            "title_similarity": self.title_similarity,
            "brand_match_status": self.brand_match_status,
            "unit_equivalence": self.unit_equivalence,
            "notes": list(self.notes),
        }


def assess_identity(source: Dict[str, Any], listing: Dict[str, Any],
                    *, provider_reported: bool = True,
                    settings: Optional[Dict[str, Any]] = None) -> IdentityAssessment:
    """Assess identity between a source product and a provider-reported listing.

    `source` keys: brand_raw, manufacturer_part_number, upc, ean, gtin, model,
    title_raw, normalized_unit_count, unit_measure, pack_count, item_count,
    variation, formula_or_flavor.
    `listing` keys: asin, brand, upc, ean, gtin, mpn, model, title, item_count,
    pack_count, unit_count, unit_measure, variation_theme, selected_variation.
    """
    st = get_settings(settings)
    sim_candidate = st.get("title_similarity_candidate", 0.60)
    sim_pack = st.get("title_similarity_pack", 0.70)

    s_brand = source.get("brand_raw") or source.get("brand")
    l_brand = listing.get("brand")
    brand_status = _brand_match(s_brand, l_brand)

    # --- 1. UPC / EAN exact ------------------------------------------------
    s_gtin = _digit(source.get("gtin") or source.get("upc") or source.get("ean"))
    l_gtin = _digit(listing.get("gtin") or listing.get("upc") or listing.get("ean"))
    if s_gtin and l_gtin and s_gtin == l_gtin:
        if brand_status == "conflict":
            return IdentityAssessment(
                state=IdentityState.IDENTIFIER_MISMATCH.value, method="upc_exact",
                match_confidence=0.4, title_similarity=_title_similarity(source.get("title_raw"), listing.get("title")),
                brand_match_status=brand_status, unit_equivalence=None,
                notes=["UPC/EAN matches but brand conflicts -> identifier mismatch"],
            )
        return IdentityAssessment(
            state=(IdentityState.EXACT_MATCH_PROVIDER_REPORTED.value if provider_reported
                   else IdentityState.EXACT_MATCH_VERIFIED.value),
            method="upc_exact", match_confidence=0.97,
            title_similarity=_title_similarity(source.get("title_raw"), listing.get("title")),
            brand_match_status=brand_status,
            unit_equivalence=None,  # confirmed by identifier, not pack
            notes=["Exact UPC/EAN match to provider-reported listing"],
        )

    # --- 2. MPN + brand exact ----------------------------------------------
    s_mpn = _norm(source.get("manufacturer_part_number") or source.get("mpn") or source.get("model_number"))
    l_mpn = _norm(listing.get("mpn") or listing.get("model"))
    if s_mpn and l_mpn and brand_status == "match" and s_mpn == l_mpn:
        return IdentityAssessment(
            state=(IdentityState.EXACT_MATCH_PROVIDER_REPORTED.value if provider_reported
                   else IdentityState.EXACT_MATCH_VERIFIED.value),
            method="mpn_brand_exact", match_confidence=0.93,
            title_similarity=_title_similarity(source.get("title_raw"), listing.get("title")),
            brand_match_status=brand_status, unit_equivalence=None,
            notes=["Exact MPN + brand match"],
        )

    # --- 3. Manufacturer + model + pack/unit equivalence ---------------------
    s_man = _norm(source.get("manufacturer") or source.get("brand_raw"))
    l_man = _norm(listing.get("manufacturer") or listing.get("brand"))
    s_model = _norm(source.get("model_number") or source.get("model"))
    l_model = _norm(listing.get("model"))
    if s_model and l_model and s_man and l_man and s_man == l_man and s_model == l_model:
        unit_ok, unit_note = _unit_equivalence(source, listing)
        if unit_ok is False:
            return IdentityAssessment(
                state=IdentityState.PACK_MISMATCH.value, method="manuf_model_pack",
                match_confidence=0.5, title_similarity=_title_similarity(source.get("title_raw"), listing.get("title")),
                brand_match_status=brand_status, unit_equivalence=False, notes=[unit_note])
        return IdentityAssessment(
            state=IdentityState.PROBABLE_MATCH.value, method="manuf_model_pack",
            match_confidence=0.85, title_similarity=_title_similarity(source.get("title_raw"), listing.get("title")),
            brand_match_status=brand_status, unit_equivalence=unit_ok, notes=[unit_note])

    # --- variation mismatch detection (before title+pack promotion) ---------
    similarity = _title_similarity(source.get("title_raw"), listing.get("title"))
    s_variation = _norm(source.get("variation") or source.get("selected_variation") or source.get("formula_or_flavor"))
    l_variation = _norm(listing.get("selected_variation") or listing.get("variation_theme"))
    if brand_status == "match" and similarity >= _settings_sim_candidate(settings) and s_variation and l_variation and s_variation != l_variation:
        return IdentityAssessment(
            state=IdentityState.VARIATION_MISMATCH.value, method="variation",
            match_confidence=0.3, title_similarity=similarity,
            brand_match_status=brand_status,
            unit_equivalence=_unit_equivalence(source, listing)[0],
            notes=[f"variation mismatch: '{s_variation}' vs '{l_variation}'"])

    # --- 4. Brand + normalized title + exact unit/pack equivalence ----------
    unit_ok, unit_note = _unit_equivalence(source, listing)
    if brand_status == "match" and similarity >= sim_pack:
        if unit_ok is False:
            return IdentityAssessment(
                state=IdentityState.PACK_MISMATCH.value, method="brand_title_pack",
                match_confidence=0.5, title_similarity=similarity,
                brand_match_status=brand_status, unit_equivalence=False, notes=[unit_note])
        return IdentityAssessment(
            state=(IdentityState.TITLE_PACK_CANDIDATE.value if unit_ok is not True
                   else IdentityState.PROBABLE_MATCH.value),
            method="brand_title_pack", match_confidence=0.8, title_similarity=similarity,
            brand_match_status=brand_status, unit_equivalence=unit_ok, notes=[unit_note])

    # --- brand mismatch ------------------------------------------------------
    if brand_status == "conflict":
        return IdentityAssessment(
            state=IdentityState.BRAND_MISMATCH.value, method="brand",
            match_confidence=0.2, title_similarity=similarity,
            brand_match_status=brand_status, unit_equivalence=unit_ok,
            notes=["Brand conflict between source and listing"])

    # --- 5. Title-only candidate (never qualifies automatically) -------------
    if brand_status == "match" and similarity >= _settings_sim_candidate(settings):
        return IdentityAssessment(
            state=IdentityState.TITLE_PACK_CANDIDATE.value, method="title_candidate",
            match_confidence=0.4, title_similarity=similarity,
            brand_match_status=brand_status, unit_equivalence=unit_ok,
            notes=["Title/brand candidate only; manual review required"])

    return IdentityAssessment(
        state=IdentityState.NO_MATCH.value, method="no_match", match_confidence=0.0,
        title_similarity=similarity, brand_match_status=brand_status,
        unit_equivalence=unit_ok, notes=["No strong identity match found"])


# ---------------------------------------------------------------------------
# Multipack split validation
# ---------------------------------------------------------------------------

def evaluate_split_pack(source: Dict[str, Any], listing: Dict[str, Any],
                        *, settings: Optional[Dict[str, Any]] = None) -> SplitPackState:
    """Decide whether a source multipack may be split for resale.

    Split is approved only when EVERY requirement is met:
      - each inner unit independently sealed
      - each inner unit retail-ready
      - each inner unit has a valid product identifier when required
      - manufacturer does not state "not for individual resale"
      - inner unit exactly matches the provider-reported target listing
      - brand, variation, formulation, size, count, unit basis match
      - not blocked by restriction or compliance flag
    """
    def b(name, default=None):
        v = source.get(name)
        return default if v is None else v

    if b("split_allowed", None) is False:
        return SplitPackState.PROHIBITED_SPLIT
    if b("not_for_individual_resale", False):
        return SplitPackState.PROHIBITED_SPLIT
    if b("restriction_flag") or b("compliance_flag"):
        return SplitPackState.PROHIBITED_SPLIT

    identity = assess_identity(source, listing, settings=settings)
    if identity.state in (IdentityState.PACK_MISMATCH.value,
                          IdentityState.VARIATION_MISMATCH.value,
                          IdentityState.BRAND_MISMATCH.value,
                          IdentityState.IDENTIFIER_MISMATCH.value):
        return SplitPackState.PROHIBITED_SPLIT
    if identity.unit_equivalence is False:
        return SplitPackState.PROHIBITED_SPLIT

    if b("manufacturer_bundle", False):
        # bundle: splitting requires explicit retail-ready per-unit confirmation
        if b("inner_units_sealed", None) is not True or b("inner_units_retail_ready", None) is not True:
            return SplitPackState.MANUAL_REVIEW_REQUIRED
        return SplitPackState.APPROVED_SPLIT if identity.state in (
            IdentityState.EXACT_MATCH_PROVIDER_REPORTED.value,
            IdentityState.EXACT_MATCH_VERIFIED.value,
            IdentityState.PROBABLE_MATCH.value,
        ) else SplitPackState.MANUAL_REVIEW_REQUIRED

    # Non-bundle: source pack count > target listing unit count
    s_count = source.get("normalized_unit_count") or source.get("item_count") or source.get("pack_count")
    l_count = listing.get("item_count") or listing.get("pack_count") or listing.get("unit_count")
    if s_count and l_count and int(s_count) > int(l_count):
        if (b("inner_units_sealed", None) is True and b("inner_units_retail_ready", None) is True
                and b("inner_units_valid_identifier", True)):
            return SplitPackState.APPROVED_SPLIT
        return SplitPackState.MANUAL_REVIEW_REQUIRED

    return SplitPackState.INTACT_ONLY