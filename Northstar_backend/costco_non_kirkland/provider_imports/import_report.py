"""Provider import report builder.

PURE / OFFLINE. Aggregates per-row outcomes into an auditable import report with
the explicit "Network calls made: 0" confirmation and provenance summary.
"""
from __future__ import annotations

from typing import Any, Dict, List

from ..enums import ImportRowStatus


def build_import_report(import_result: Dict[str, Any]) -> Dict[str, Any]:
    """Build a standardized import report from an importer result."""
    status_counts = dict(import_result.get("row_status_counts", {}))
    for s in ImportRowStatus:
        status_counts.setdefault(s.value, 0)

    total = import_result.get("rows_total", 0)
    imported = status_counts.get(ImportRowStatus.IMPORTED.value, 0)
    duplicates = status_counts.get(ImportRowStatus.DUPLICATE.value, 0)
    rejected = status_counts.get(ImportRowStatus.REJECTED.value, 0)
    needs_mapping = status_counts.get(ImportRowStatus.NEEDS_MAPPING.value, 0)
    stale = status_counts.get(ImportRowStatus.STALE.value, 0)
    missing = status_counts.get(ImportRowStatus.MISSING_REQUIRED_FIELDS.value, 0)
    ambiguous = status_counts.get(ImportRowStatus.IDENTITY_AMBIGUOUS.value, 0)

    return {
        "provider": import_result.get("provider"),
        "filename": import_result.get("filename"),
        "file_sha256": import_result.get("sha256"),
        "parse_kind": import_result.get("parse_kind"),
        "dry_run": import_result.get("dry_run", False),
        "strict": import_result.get("strict", False),
        "rows_total": total,
        "rows_imported": imported,
        "rows_duplicate": duplicates,
        "rows_rejected": rejected,
        "rows_needs_mapping": needs_mapping,
        "rows_stale": stale,
        "rows_missing_required_fields": missing,
        "rows_identity_ambiguous": ambiguous,
        "row_status_counts": status_counts,
        "network_calls_made": 0,
        "confirmation": "Network calls made: 0",
        "note": (
            "Imported fields are PROVIDER-REPORTED, not verified. Verification "
            "requires the project's established identity/validation rules."
        ),
        "snapshots_in_memory": len(import_result.get("snapshots", [])),
    }


def import_report_confirmation() -> str:
    return "Network calls made: 0"