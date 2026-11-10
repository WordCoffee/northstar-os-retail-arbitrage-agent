"""SellerAmp / Seller Assistant manual export importer (CSV + JSON).

PURE / OFFLINE. Parses a local SellerAmp export, maps columns via schemas, and
normalizes each row into the canonical market-snapshot contract with full
provenance. Idempotent by source-file SHA-256 + row number. No network access.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from .common import sha256_file
from .mapping import map_row_to_canonical
from .schemas import schema_version_for
from .validators import valid_asin
from ..enums import ImportRowStatus
from ..amazon_guard import assert_no_amazon_direct_scan

PROVIDER = "selleramp"


class SellerAmpImporter:
    """Import a SellerAmp/Seller Assistant CSV/JSON export file."""

    def __init__(self, *, store=None, settings: Optional[Dict[str, Any]] = None):
        self.store = store
        self.settings = settings or {}

    def import_file(self, path: str, *, kind: str = "auto", dry_run: bool = False,
                    strict: bool = False, allow_partial: bool = False,
                    schema_version: Optional[str] = None,
                    observed_at: Optional[str] = None) -> Dict[str, Any]:
        lower = path.lower()
        if kind == "auto":
            if lower.endswith(".csv"):
                kind = "csv"
            elif lower.endswith(".json"):
                kind = "json"
            else:
                return self._error_report(path, "unsupported_file",
                                          "Unsupported file type (expected .csv or .json).")
        if kind not in ("csv", "json"):
            return self._error_report(path, "unsupported_file", f"Unknown kind {kind!r}")

        from .common import parse_provider_file
        try:
            parsed = parse_provider_file(path, explicit_provider=PROVIDER,
                                         schema_version=schema_version or schema_version_for(PROVIDER, kind))
        except Exception as e:  # pragma: no cover
            return self._error_report(path, "parse_error", str(e))

        provider = parsed["provider"]
        if provider != PROVIDER:
            return self._error_report(path, "ambiguous_provider",
                                      f"Expected {PROVIDER} but detected {provider}.")

        sha256 = parsed["sha256"]
        snapshots: List[Dict[str, Any]] = []
        rows_status: Dict[str, int] = {}
        imported = 0

        for idx, raw_row in enumerate(parsed["rows"]):
            row_number = idx + 1
            if not isinstance(raw_row, dict):
                rows_status[ImportRowStatus.REJECTED.value] = rows_status.get(ImportRowStatus.REJECTED.value, 0) + 1
                continue

            assert_no_amazon_direct_scan(asin=raw_row.get("asin"))

            snapshot = map_row_to_canonical(
                raw_row, provider=PROVIDER, kind=kind,
                provider_export_filename=path,
                provider_export_sha256=sha256,
                provider_schema_version=parsed["schema_version"],
                provider_row_number=row_number,
                provider_record_id=str(raw_row.get("asin") or raw_row.get("id") or row_number),
                provider_snapshot_id=f"{sha256[:8]}-{row_number}",
                observed_at=observed_at,
            )

            asin_ok = valid_asin(snapshot.get("asin"))
            required_ok, missing = self._required_check(snapshot, strict=strict)

            if not asin_ok:
                status = ImportRowStatus.IDENTITY_AMBIGUOUS.value
            elif not required_ok:
                status = ImportRowStatus.MISSING_REQUIRED_FIELDS.value
            elif self._is_duplicate(snapshot):
                status = ImportRowStatus.DUPLICATE.value
            elif self._is_stale(snapshot):
                status = ImportRowStatus.STALE.value
            else:
                status = ImportRowStatus.IMPORTED.value
                imported += 1
                if not dry_run:
                    self._persist(snapshot)

            snapshot["_import_status"] = status
            snapshot["_missing_required"] = missing
            snapshots.append(snapshot)
            rows_status[status] = rows_status.get(status, 0) + 1

        return {
            "provider": PROVIDER,
            "filename": path,
            "sha256": sha256,
            "parse_kind": kind,
            "dry_run": dry_run,
            "strict": strict,
            "rows_total": len(parsed["rows"]),
            "rows_imported": imported,
            "row_status_counts": rows_status,
            "network_calls_made": 0,
            "snapshots": snapshots if dry_run else [],
        }

    def _required_check(self, snapshot: Dict[str, Any], *, strict: bool) -> Tuple[bool, List[str]]:
        if strict:
            required = ("asin", "title", "buy_box_price")
            missing = [f for f in required if snapshot["fields"].get(f, {}).get("value") is None]
            return (len(missing) == 0, missing)
        missing = []
        if snapshot["fields"].get("asin", {}).get("value") is None:
            missing.append("asin")
        if snapshot["fields"].get("title", {}).get("value") is None:
            missing.append("title")
        return (len(missing) == 0, missing)

    def _is_duplicate(self, snapshot: Dict[str, Any]) -> bool:
        if self.store is None:
            return False
        try:
            return self.store.has_imported_row(snapshot["fields"]["asin"]["value"],
                                               snapshot["fields"]["asin"].get("provider_export_sha256"),
                                               snapshot["fields"]["asin"].get("provider_row_number"))
        except Exception:
            return False

    def _is_stale(self, snapshot: Dict[str, Any]) -> bool:
        return snapshot["fields"].get("asin", {}).get("freshness_status") == "stale"

    def _persist(self, snapshot: Dict[str, Any]) -> None:
        if self.store is not None:
            self.store.persist_market_snapshot(snapshot)

    def _error_report(self, path: str, reason: str, detail: str) -> Dict[str, Any]:
        return {
            "provider": PROVIDER, "filename": path, "dry_run": True,
            "rows_total": 0, "rows_imported": 0,
            "row_status_counts": {}, "network_calls_made": 0,
            "error": {"reason": reason, "detail": detail},
        }