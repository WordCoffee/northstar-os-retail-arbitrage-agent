"""Evidence-first extraction (P6-T4).

Every extracted field stores source_url, observed_at, selector_version, confidence.
Extraction failure produces UNKNOWN with a reason, never a guess.

Provenance: In-house implementation based on NORTHSTAROS_MASTER_BUILD_PLAN.md P6-T4.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass
class FieldEvidence:
    field_name: str
    value: Any
    source_url: str
    observed_at: str
    selector_version: str
    confidence: float
    status: str = "OK"  # OK | UNKNOWN | DEGRADED
    extraction_method: str = "selector"  # selector | adaptive | ai | vision
    screenshot_hash: Optional[str] = None
    error_reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ExtractionEvidence:
    job_id: str
    url: str
    observed_at: str
    fields: List[FieldEvidence] = field(default_factory=list)
    screenshot_sha256: Optional[str] = None
    status: str = "OK"  # OK | PARTIAL | FAILED | DEGRADED
    selector_version: str = "1.0.0"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "job_id": self.job_id,
            "url": self.url,
            "observed_at": self.observed_at,
            "fields": [f.to_dict() for f in self.fields],
            "screenshot_sha256": self.screenshot_sha256,
            "status": self.status,
            "selector_version": self.selector_version,
        }

    @property
    def all_ok(self) -> bool:
        return all(f.status == "OK" for f in self.fields)

    @property
    def has_unknown(self) -> bool:
        return any(f.status == "UNKNOWN" for f in self.fields)


def make_field_evidence(
    field_name: str,
    value: Any,
    source_url: str,
    selector_version: str = "1.0.0",
    confidence: float = 1.0,
    method: str = "selector",
    error_reason: Optional[str] = None,
) -> FieldEvidence:
    """Create a field evidence record."""
    if value is None:
        status = "UNKNOWN"
    else:
        status = "OK"
    if error_reason:
        status = "DEGRADED"
    return FieldEvidence(
        field_name=field_name,
        value=value,
        source_url=source_url,
        observed_at=datetime.now(timezone.utc).isoformat(),
        selector_version=selector_version,
        confidence=confidence,
        status=status,
        extraction_method=method,
        error_reason=error_reason,
    )


def make_extraction_evidence(
    job_id: str,
    url: str,
    fields: List[FieldEvidence],
    screenshot_hash: Optional[str] = None,
    selector_version: str = "1.0.0",
) -> ExtractionEvidence:
    """Create an extraction evidence record."""
    if all(f.status == "OK" for f in fields):
        status = "OK"
    elif any(f.status == "UNKNOWN" for f in fields):
        status = "PARTIAL" if any(f.status == "OK" for f in fields) else "FAILED"
    else:
        status = "DEGRADED"
    return ExtractionEvidence(
        job_id=job_id,
        url=url,
        observed_at=datetime.now(timezone.utc).isoformat(),
        fields=fields,
        screenshot_sha256=screenshot_hash,
        status=status,
        selector_version=selector_version,
    )


def sha256_hash(data: bytes) -> str:
    """Compute SHA-256 hash of data (for screenshot hashes)."""
    return hashlib.sha256(data).hexdigest()
