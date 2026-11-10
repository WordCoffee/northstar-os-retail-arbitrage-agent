"""Normalized market snapshot + provenance envelope.

PURE / OFFLINE. Mirrors the existing `intel_schema` / `normalized_snapshot`
patterns but scoped to provider-enriched (or fixture) market data with
field-level provenance, capture status, freshness, and limitations.
BSR is first-class and never inferred; unknown BSR is never zero.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .enums import CaptureStatus, SnapshotEvidenceClass

SCHEMA_VERSION = 1

# Evidence classes required by the pipeline contract.
EVIDENCE_CLASSES = tuple(e.value for e in SnapshotEvidenceClass)

# Capture statuses required by the pipeline contract.
CAPTURE_STATUSES = tuple(e.value for e in CaptureStatus)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean_text(x: Optional[Any]) -> Optional[str]:
    if x is None:
        return None
    s = str(x).strip()
    return s or None


def _to_number(x: Optional[Any]) -> Optional[float]:
    if x is None or x == "":
        return None
    try:
        return float(str(x).replace("$", "").replace(",", ""))
    except (ValueError, TypeError):
        return None


@dataclass
class ProvenanceField:
    """Field-level provenance envelope."""
    value: Any = None
    source: Optional[str] = None
    captured_at: Optional[str] = None
    freshness: Optional[str] = None
    evidence_class: Optional[str] = None
    capture_status: Optional[str] = None
    limitations: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "value": self.value,
            "source": self.source,
            "captured_at": self.captured_at,
            "freshness": self.freshness,
            "evidence_class": self.evidence_class,
            "capture_status": self.capture_status,
            "limitations": self.limitations,
        }


@dataclass
class BsrFact:
    bsr_raw: Optional[str] = None
    bsr_primary_rank: Optional[int] = None
    bsr_primary_category: Optional[str] = None
    bsr_secondary_rank: Optional[int] = None
    bsr_secondary_category: Optional[str] = None
    bsr_capture_status: str = CaptureStatus.NOT_REQUESTED.value
    bsr_source: Optional[str] = None
    bsr_captured_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "bsr_raw": self.bsr_raw,
            "bsr_primary_rank": self.bsr_primary_rank,
            "bsr_primary_category": self.bsr_primary_category,
            "bsr_secondary_rank": self.bsr_secondary_rank,
            "bsr_secondary_category": self.bsr_secondary_category,
            "bsr_capture_status": self.bsr_capture_status,
            "bsr_source": self.bsr_source,
            "bsr_captured_at": self.bsr_captured_at,
        }


def parse_bsr(bsr_raw: Optional[str], *, source: Optional[str] = None,
              captured_at: Optional[str] = None) -> BsrFact:
    """Parse a '#N in Category' BSR string into first-class fields.

    Unknown/blank/unsupported input -> capture_status 'unavailable' (NOT zero).
    """
    if not bsr_raw:
        return BsrFact(
            bsr_raw=None, bsr_capture_status=CaptureStatus.UNAVAILABLE.value,
            bsr_source=source, bsr_captured_at=captured_at or _now(),
        )
    import re
    fact = BsrFact(bsr_raw=_clean_text(bsr_raw), bsr_source=source,
                   bsr_captured_at=captured_at or _now())
    matches = re.findall(r"#([\d,]+)\s+in\s+([^#]+?)(?:\s*#|$)", bsr_raw, re.IGNORECASE)
    if not matches:
        # fallback: single rank
        single = re.match(r"#?\s*([\d,]+)\s+(?:in\s+)?(.+)$", bsr_raw, re.IGNORECASE)
        if single:
            fact.bsr_primary_rank = int(single.group(1).replace(",", ""))
            fact.bsr_primary_category = single.group(2).strip()
            fact.bsr_capture_status = CaptureStatus.CAPTURED.value
        else:
            fact.bsr_capture_status = CaptureStatus.PARSE_ERROR.value
        return fact
    rank, cat = matches[0]
    fact.bsr_primary_rank = int(rank.replace(",", ""))
    fact.bsr_primary_category = cat.strip()
    fact.bsr_capture_status = CaptureStatus.CAPTURED.value
    if len(matches) > 1:
        rank2, cat2 = matches[1]
        fact.bsr_secondary_rank = int(rank2.replace(",", ""))
        fact.bsr_secondary_category = cat2.strip()
    return fact


def build_market_snapshot(
    *,
    asin: str,
    title: Optional[str] = None,
    brand: Optional[str] = None,
    price: Optional[Any] = None,
    price_source: Optional[str] = None,
    price_captured_at: Optional[str] = None,
    buy_box: Optional[Dict[str, Any]] = None,
    seller_counts: Optional[Dict[str, Any]] = None,
    bsr: Optional[BsrFact] = None,
    estimated_monthly_sales: Optional[Any] = None,
    review_count: Optional[Any] = None,
    rating: Optional[Any] = None,
    provider: Optional[str] = None,
    evidence_class: str = SnapshotEvidenceClass.CACHED_PROVIDER_SNAPSHOT.value,
    limitations: Optional[str] = None,
) -> Dict[str, Any]:
    """Build a normalized market snapshot with full provenance.

    Every present field gets a provenance entry; missing fields get capture_status
    'unavailable' (never zero). Sales/revenue are ALWAYS provider estimates.
    """
    now = _now()
    bsr_fact = bsr or BsrFact(bsr_capture_status=CaptureStatus.NOT_REQUESTED.value,
                              bsr_source=provider, bsr_captured_at=now)

    fields: Dict[str, ProvenanceField] = {
        "asin": ProvenanceField(asin, source=provider, captured_at=now, evidence_class=evidence_class,
                                capture_status=CaptureStatus.CAPTURED.value, limitations=limitations),
        "title": ProvenanceField(_clean_text(title), source=provider, captured_at=now, evidence_class=evidence_class,
                                 capture_status=CaptureStatus.CAPTURED.value if title else CaptureStatus.UNAVAILABLE.value,
                                 limitations=limitations),
        "brand": ProvenanceField(_clean_text(brand), source=provider, captured_at=now, evidence_class=evidence_class,
                                 capture_status=CaptureStatus.CAPTURED.value if brand else CaptureStatus.UNAVAILABLE.value,
                                 limitations=limitations),
        "price": ProvenanceField(_to_number(price), source=price_source or provider, captured_at=price_captured_at or now,
                                 evidence_class=evidence_class,
                                 capture_status=CaptureStatus.CAPTURED.value if price is not None else CaptureStatus.UNAVAILABLE.value,
                                 limitations=limitations or "Provider estimate unless explicitly live_verified."),
        "estimated_monthly_sales": ProvenanceField(
            _to_number(estimated_monthly_sales), source=provider, captured_at=now,
            evidence_class=SnapshotEvidenceClass.PROVIDER_ESTIMATE.value,
            capture_status=CaptureStatus.CAPTURED.value if estimated_monthly_sales is not None else CaptureStatus.UNAVAILABLE.value,
            limitations="Provider estimate, not a verified Amazon sales figure."),
        "review_count": ProvenanceField(_to_number(review_count), source=provider, captured_at=now,
                                        evidence_class=evidence_class,
                                        capture_status=CaptureStatus.CAPTURED.value if review_count is not None else CaptureStatus.UNAVAILABLE.value,
                                        limitations=limitations),
        "rating": ProvenanceField(_to_number(rating), source=provider, captured_at=now, evidence_class=evidence_class,
                                  capture_status=CaptureStatus.CAPTURED.value if rating is not None else CaptureStatus.UNAVAILABLE.value,
                                  limitations=limitations),
    }

    snapshot = {
        "schema_version": SCHEMA_VERSION,
        "asin": asin,
        "provider": provider,
        "observed_at": now,
        "evidence_class": evidence_class,
        "capture_statuses": {k: v.to_dict()["capture_status"] for k, v in fields.items()},
        "fields": {k: v.to_dict() for k, v in fields.items()},
        "bsr": bsr_fact.to_dict(),
        "buy_box": buy_box or {"available": False, "capture_status": CaptureStatus.UNAVAILABLE.value},
        "seller_counts": seller_counts or {"capture_status": CaptureStatus.UNAVAILABLE.value},
    }
    return snapshot