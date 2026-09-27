"""Kirkland Signature exclusion for the Costco Non-Kirkland pipeline.

PURE / OFFLINE / DETERMINISTIC. Marks (never deletes) records whose identity
contains Kirkland Signature or a known alias. Missing brand is never presumed
non-Kirkland when the title/metadata hints at Kirkland — those are flagged for
review.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

EXCLUSION_REASON = "kirkland_signature_out_of_scope"
ELIGIBLE_FIELD = "eligible_for_costco_non_kirkland_workflow"

# Configurable alias list. Documented in docs/costco-non-kirkland-pipeline.md.
# Substring matching is case-insensitive. "kirkland signature" is checked first
# (so a title "Kirkland Signature ..." is caught), then "kirkland", then aliases.
KIRKLAND_ALIASES: tuple = (
    "kirkland signature",
    "kirkland",
    "k-sig",
    "ksig",
    "costco signature",
    "costco brand",
    "member's mark",   # defensive: Sam's Club private label, never Costco
    "signature select",
)

# Fields inspected, in priority order. `description`, `manufacturer`, `url`,
# and `notes` are optional (only inspected when present).
_INSPECT_FIELDS = (
    "brand_normalized",
    "brand_raw",
    "brand",
    "title_normalized",
    "title_raw",
    "product_name",
    "item_name",
    "name",
    "description",
    "manufacturer",
    "source_url",
    "url",
    "notes",
)

_KIRKLAND_CORE = re.compile(r"kirkland", re.IGNORECASE)
_KIRKLAND_SIGNATURE = re.compile(r"kirkland\s+signature", re.IGNORECASE)


def _as_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def _contains_kirkland(record: Dict[str, Any]) -> bool:
    """Scan all inspectable fields for any Kirkland marker (core or alias)."""
    for fld in _INSPECT_FIELDS:
        if fld not in record:
            continue
        text = _as_text(record.get(fld)).lower()
        if not text:
            continue
        if _KIRKLAND_CORE.search(text):
            return True
        for alias in KIRKLAND_ALIASES:
            if alias and alias in text:
                return True
    return False


def is_kirkland(record: Optional[Dict[str, Any]]) -> bool:
    """Deterministic Kirkland detection.

    Returns True when any inspected field contains a Kirkland marker.
    A missing/empty record is never Kirkland.
    """
    if not record or not isinstance(record, dict):
        return False
    return _contains_kirkland(record)


def _brand_text(record: Dict[str, Any]) -> str:
    for fld in ("brand_normalized", "brand_raw", "brand"):
        if fld in record and _as_text(record.get(fld)).strip():
            return _as_text(record.get(fld))
    return ""


def _title_text(record: Dict[str, Any]) -> str:
    for fld in ("title_normalized", "title_raw", "product_name", "item_name", "name"):
        if fld in record and _as_text(record.get(fld)).strip():
            return _as_text(record.get(fld))
    return ""


@dataclass
class ExclusionResult:
    excluded: bool
    exclusion_reason: Optional[str]
    eligible_for_costco_non_kirkland_workflow: bool
    manual_review_required: bool
    reason_code: str  # machine-readable
    notes: str = ""

    def to_record(self, base: Dict[str, Any]) -> Dict[str, Any]:
        """Merge the exclusion decision into a record (mark, never delete)."""
        out = dict(base)
        out[ELIGIBLE_FIELD] = self.eligible_for_costco_non_kirkland_workflow
        out["exclusion_reason"] = self.exclusion_reason
        out["manual_review_required"] = bool(self.manual_review_required or base.get("manual_review_required"))
        return out


def evaluate_exclusion(record: Optional[Dict[str, Any]]) -> ExclusionResult:
    """Evaluate ONE record against the Kirkland exclusion rule.

    Deterministic outcomes (priority order):
      1. Brand field is Kirkland (or contains a marker)   -> excluded
      2. Title/metadata contains a Kirkland marker        -> excluded
      3. Brand missing AND title hints at Kirkland        -> manual_review_required
         (never presumed non-Kirkland when title suggests Kirkland)
      4. Brand missing AND no Kirkland hint               -> manual_review_required
         (missing brand is ambiguous; flagged for review)
      5. Brand present, non-Kirkland, no marker           -> eligible
    """
    if not record or not isinstance(record, dict):
        return ExclusionResult(
            excluded=False, exclusion_reason=None,
            eligible_for_costco_non_kirkland_workflow=False,
            manual_review_required=True, reason_code="missing_record",
            notes="Empty or missing record; flagged for review.",
        )

    brand = _brand_text(record)
    title = _title_text(record)
    has_brand = bool(brand)
    brand_is_kirkland = bool(brand) and _KIRKLAND_CORE.search(brand.lower())
    brand_alias_hit = any(a for a in KIRKLAND_ALIASES if a and a in brand.lower())

    if brand_is_kirkland or brand_alias_hit:
        return ExclusionResult(
            excluded=True, exclusion_reason=EXCLUSION_REASON,
            eligible_for_costco_non_kirkland_workflow=False,
            manual_review_required=False, reason_code="brand_kirkland",
            notes=f"Brand field identifies Kirkland Signature: '{brand}'.",
        )

    # Missing brand + title/metadata suggests Kirkland -> excluded AND review.
    title_hints_kirkland = bool(title) and bool(_KIRKLAND_CORE.search(title.lower()))
    if not has_brand and title_hints_kirkland:
        return ExclusionResult(
            excluded=True, exclusion_reason=EXCLUSION_REASON,
            eligible_for_costco_non_kirkland_workflow=False,
            manual_review_required=True, reason_code="missing_brand_title_hints_kirkland",
            notes="Brand missing and title suggests Kirkland; excluded and flagged for review.",
        )

    if _contains_kirkland(record):
        return ExclusionResult(
            excluded=True, exclusion_reason=EXCLUSION_REASON,
            eligible_for_costco_non_kirkland_workflow=False,
            manual_review_required=False, reason_code="metadata_kirkland",
            notes=f"Title/metadata contains a Kirkland marker: '{title or ''}'.",
        )

    title_hints_kirkland = _KIRKLAND_CORE.search(title.lower()) if title else False
    if not has_brand and not title_hints_kirkland:
        return ExclusionResult(
            excluded=False, exclusion_reason=None,
            eligible_for_costco_non_kirkland_workflow=False,
            manual_review_required=True, reason_code="missing_brand",
            notes="Brand missing; ambiguity cannot be presumed non-Kirkland. Manual review required.",
        )

    return ExclusionResult(
        excluded=False, exclusion_reason=None,
        eligible_for_costco_non_kirkland_workflow=True,
        manual_review_required=False, reason_code="eligible",
        notes="Non-Kirkland brand with no Kirkland marker.",
    )


@dataclass
class ExclusionAudit:
    total_discovered: int = 0
    excluded_kirkland: int = 0
    non_kirkland_eligible: int = 0
    missing_brand: int = 0
    ambiguous_brand: int = 0
    manual_review_required: int = 0
    by_reason_code: Dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_discovered": self.total_discovered,
            "excluded_kirkland": self.excluded_kirkland,
            "non_kirkland_eligible": self.non_kirkland_eligible,
            "missing_brand": self.missing_brand,
            "ambiguous_brand": self.ambiguous_brand,
            "manual_review_required": self.manual_review_required,
            "by_reason_code": dict(self.by_reason_code),
        }


def audit_exclusion(records: List[Dict[str, Any]]) -> ExclusionAudit:
    """Apply exclusion to a list and produce an auditable summary.

    Does NOT delete. Does NOT mutate inputs. Returns the audit; callers that
    need the marked records should call evaluate_exclusion per row.
    """
    audit = ExclusionAudit()
    for rec in records:
        audit.total_discovered += 1
        res = evaluate_exclusion(rec)
        audit.by_reason_code[res.reason_code] = audit.by_reason_code.get(res.reason_code, 0) + 1
        if res.excluded:
            audit.excluded_kirkland += 1
        elif res.eligible_for_costco_non_kirkland_workflow:
            audit.non_kirkland_eligible += 1
        if res.reason_code == "missing_brand":
            audit.missing_brand += 1
        if res.reason_code in ("missing_brand", "missing_brand_title_hints_kirkland"):
            audit.ambiguous_brand += 1
        if res.manual_review_required:
            audit.manual_review_required += 1
    return audit