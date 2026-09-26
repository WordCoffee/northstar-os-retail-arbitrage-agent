"""Keyword import pipeline (1C-05 / C04-C07).

Format detection, header aliases, required-column validation, date-range /
marketplace / currency extraction, file hashing, duplicate detection,
idempotent reimport, overlap detection, rejection reasons, import summary,
cancellation, retry safety, organization isolation, and audit.

Large imports run through 1C-04 jobs (the ``keyword_import`` handler). Source
files are NEVER modified. Overlapping reports are flagged, never silently
double-counted. Unknown metrics stay null.
"""
from __future__ import annotations

import csv
import os
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Optional
from uuid import uuid4

from ..audit import AuditService
from ..models import (
    ImportBatch, Keyword, SearchTerm, Target, AdPerformanceObservation,
    SourceRow, RejectedRow, KeywordConflict, utcnow,
)
from ..repositories import Repositories
from .normalize import normalize_phrase, normalize_match_type, normalize_marketplace
from .sources import SourceRegistry, sniff_csv, _sha256, classify_report_type


def _now_iso() -> str:
    return utcnow().isoformat()


def _dec(value, default=None):
    if value is None or value == "":
        return default
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return default


def _int(value, default=None):
    if value is None or value == "":
        return default
    try:
        return int(float(str(value).replace(",", "")))
    except (ValueError, TypeError):
        return default


def _bool_flag(value) -> bool:
    return bool(value) and str(value).lower() in ("1", "true", "yes", "y")


class ImportError_(ValueError):
    def __init__(self, code: str, message: str = "", *, batch_id=None) -> None:
        super().__init__(message or code)
        self.code = code
        self.batch_id = batch_id


class KeywordImporter:
    def __init__(self, repos: Repositories, *, audit: Optional[AuditService] = None,
                 registry: Optional[SourceRegistry] = None) -> None:
        self.repos = repos
        self.audit = audit or AuditService(repos)
        self.sources = registry or SourceRegistry(repos)

    # -- validation / dry run (C04) -----------------------------------------

    def dry_run(self, org_id: str, path: str, *,
                report_type: Optional[str] = None) -> dict:
        """Validate WITHOUT writing anything. Never touches source files."""
        if not os.path.exists(path):
            raise ImportError_("file_not_found", f"no such file: {path}")
        sniff = sniff_csv(path)
        headers = sniff["headers"]
        rtype = report_type or classify_report_type(headers) or "unknown"
        required = self._required_columns(rtype)
        missing = [c for c in required if c not in {h.strip().lower() for h in headers}]
        problems = []
        if missing:
            problems.append(f"missing_columns:{','.join(missing)}")
        if rtype == "unknown":
            problems.append("unrecognized_report_format")
        dup = self.sources.detect_duplicate(org_id, _sha256(path))
        if dup:
            problems.append("duplicate_source_file")
        rows = sniff["rows"]
        rejected = [r for r in rows if not self._row_is_valid(rtype, r)]
        return {
            "file": os.path.basename(path), "report_type": rtype,
            "required_columns": required, "missing_columns": missing,
            "problems": problems, "valid": not problems,
            "row_count": len(rows), "accepted_row_count": len(rows) - len(rejected),
            "rejected_row_count": len(rejected),
            "duplicate_source_file": bool(dup),
            "writes_performed": 0, "read_only": True,
        }

    # -- import (C05) --------------------------------------------------------

    def import_file(self, org_id: str, path: str, *,
                    submitted_by: Optional[str] = None,
                    report_type: Optional[str] = None,
                    via_job: bool = False) -> dict:
        """Register the file (dedup), create a batch, process rows, summarize.
        Returns the batch view. Idempotent for already-imported files."""
        if not os.path.exists(path):
            raise ImportError_("file_not_found", f"no such file: {path}")
        registered = self.sources.register_file(org_id, path,
                                                report_type=report_type)
        if registered["status"] == "duplicate":
            sf = registered["source_file"]
            existing = self.repos.import_batches.find(
                {"source_file_id": sf["id"], "organization_id": org_id,
                 "status": "completed"})
            if existing:
                return self._batch_view(existing, org_id, idempotent_replay=True)
            self.repos.db.conn.execute(
                "UPDATE source_files SET status=? WHERE id=?",
                ("imported", sf["id"]))
            self.repos.db.conn.commit()
        sf = self.repos.source_files.get(registered["source_file"]["id"])
        return self.import_source_file(org_id, sf["id"],
                                       submitted_by=submitted_by, via_job=via_job)

    def import_source_file(self, org_id: str, source_file_id: str, *,
                           submitted_by: Optional[str] = None,
                           via_job: bool = False) -> dict:
        sf = self.repos.source_files.get(source_file_id)
        if sf is None or sf["organization_id"] != org_id:
            raise ImportError_("not_found", "source file not found")
        path = self._resolve_path(sf["file_name"])
        sniff = sniff_csv(path)
        headers = sniff["headers"]
        rtype = sf.get("report_type") or classify_report_type(headers) or "unknown"
        required = self._required_columns(rtype)
        missing = [c for c in required if c not in {h.strip().lower() for h in headers}]
        if missing:
            raise ImportError_("missing_columns",
                               f"missing {missing} for {sf['file_name']}")
        batch = ImportBatch(organization_id=org_id, source_file_id=source_file_id,
                            status="running", submitted_by=submitted_by,
                            submitted_at=utcnow(), started_at=utcnow())
        row = self.repos.import_batches.add(batch)
        batch_id = row["id"]
        accepted = 0
        rejected = 0
        overlap = self.overlap_detection(org_id, rtype, sf.get("date_from"),
                                         sf.get("date_to"), source_file_id)
        seen_keywords: dict = {}
        for idx, raw in enumerate(sniff["rows"]):
            rtype_row = rtype
            if not self._row_is_valid(rtype_row, raw):
                self.repos.rejected_rows.add(RejectedRow(
                    organization_id=org_id, import_batch_id=batch_id,
                    source_file_id=source_file_id, row_index=idx,
                    row_json=raw, rejection_reason=self._rejection_reason(
                        rtype_row, raw)))
                rejected += 1
                continue
            accepted += 1
            self.repos.source_rows.add(SourceRow(
                organization_id=org_id, import_batch_id=batch_id,
                source_file_id=source_file_id, row_index=idx, row_json=raw,
                status="accepted"))
            self._ingest_row(org_id, raw, rtype_row, seen_keywords)
        summary = {
            "accepted_rows": accepted, "rejected_rows": rejected,
            "keywords_created": len(seen_keywords),
            "overlap_detected": overlap,
            "via_job": via_job,
        }
        self.repos.db.conn.execute(
            "UPDATE source_files SET status=? WHERE id=?", ("imported", source_file_id))
        self.repos.db.conn.execute(
            "UPDATE import_batches SET status=?, completed_at=?, summary=? WHERE id=?",
            ("completed", _now_iso(), _json(summary), batch_id))
        self.repos.db.conn.commit()
        self.audit.record(
            action="keyword.import", actor_user_id=submitted_by,
            organization_id=org_id, resource_type="import_batch",
            resource_id=batch_id,
            after_meta={"source_file": sf["file_name"], "report_type": rtype,
                        "accepted": accepted, "rejected": rejected,
                        "overlap_detected": overlap, "via_job": via_job})
        return self._batch_view(self.repos.import_batches.get(batch_id), org_id)

    def _ingest_row(self, org_id: str, row: dict, rtype: str,
                    seen: dict) -> None:
        low = {k.strip().lower(): (v or "") for k, v in row.items()}
        if rtype == "search_term":
            self._ingest_search_term_row(org_id, low, seen)
        elif rtype == "campaign":
            self._ingest_campaign_row(org_id, low, seen)
        else:
            self._ingest_generic_row(org_id, low, seen)

    def _ingest_search_term_row(self, org_id: str, low: dict, seen: dict) -> None:
        raw_term = (low.get("search term") or low.get("customer search term")
                    or "").strip()
        n = normalize_phrase(raw_term)
        match = normalize_match_type(low.get("match type"))
        mp = normalize_marketplace(low.get("marketplace")) or "amazon.com"
        campaign = low.get("campaign name") or low.get("campaign") or None
        ad_group = low.get("ad group name") or low.get("ad group") or None
        key = (n.value, match, mp)
        kw = seen.get(key)
        if kw is None:
            kw_row = self.repos.keywords.by_phrase(org_id, n.value, match, mp)
            if kw_row is None:
                kw_row = self.repos.keywords.add(Keyword(
                    organization_id=org_id, normalized_phrase=n.value,
                    original_phrase=n.original or raw_term, marketplace=mp,
                    match_type=match, confidence=1.0))
            seen[key] = kw_row
            kw = kw_row
        st_row = self.repos.search_terms.by_term(org_id, n.value, mp)
        if st_row is None:
            st_row = self.repos.search_terms.add(SearchTerm(
                organization_id=org_id, raw_term=raw_term, normalized_term=n.value,
                marketplace=mp, impressions=_int(low.get("impressions")),
                clicks=_int(low.get("clicks")), spend=_dec(low.get("spend")),
                orders=_int(low.get("orders")), revenue=_dec(low.get("revenue")),
                source="import"))
        if campaign or ad_group:
            self.repos.targets.add(Target(
                organization_id=org_id, keyword_id=kw["id"],
                campaign_id=campaign, ad_group_id=ad_group, match_type=match,
                bid=_dec(low.get("bid"))))
        impressions = _int(low.get("impressions"))
        clicks = _int(low.get("clicks"))
        orders = _int(low.get("orders"))
        spend = _dec(low.get("spend"))
        revenue = _dec(low.get("revenue"))
        ctr = round(clicks / impressions, 6) if clicks and impressions else None
        cvr = round(orders / clicks, 6) if orders and clicks else None
        self.repos.ad_perf.add(AdPerformanceObservation(
            organization_id=org_id, search_term_id=st_row["id"],
            campaign_id=campaign, ad_group_id=ad_group,
            impressions=impressions, clicks=clicks, spend=spend,
            orders=orders, revenue=revenue, ctr=ctr, cvr=cvr, source="import"))

    def _ingest_campaign_row(self, org_id: str, low: dict, seen: dict) -> None:
        raw_term = (low.get("keyword") or low.get("search term") or "").strip()
        n = normalize_phrase(raw_term)
        mp = normalize_marketplace(low.get("marketplace")) or "amazon.com"
        match = normalize_match_type(low.get("match type"))
        key = (n.value, match, mp)
        if n.value and key not in seen:
            kw_row = self.repos.keywords.by_phrase(org_id, n.value, match, mp)
            if kw_row is None:
                kw_row = self.repos.keywords.add(Keyword(
                    organization_id=org_id, normalized_phrase=n.value,
                    original_phrase=n.original or raw_term, marketplace=mp,
                    match_type=match, confidence=1.0))
            seen[key] = kw_row

    def _ingest_generic_row(self, org_id: str, low: dict, seen: dict) -> None:
        raw_term = (low.get("keyword") or low.get("search term")
                    or low.get("phrase") or "").strip()
        n = normalize_phrase(raw_term)
        mp = normalize_marketplace(low.get("marketplace")) or "amazon.com"
        match = normalize_match_type(low.get("match type"))
        key = (n.value, match, mp)
        if n.value and key not in seen:
            kw_row = self.repos.keywords.by_phrase(org_id, n.value, match, mp)
            if kw_row is None:
                kw_row = self.repos.keywords.add(Keyword(
                    organization_id=org_id, normalized_phrase=n.value,
                    original_phrase=n.original or raw_term, marketplace=mp,
                    match_type=match, confidence=0.5))
            seen[key] = kw_row

    # -- overlap detection (C07) ---------------------------------------------

    def overlap_detection(self, org_id: str, report_type: str,
                          date_from, date_to,
                          exclude_source_file_id: Optional[str] = None) -> list[dict]:
        """Flag overlapping reports for the same org/report type so they are
        never silently double-counted."""
        rows = self.repos.source_files.list(where={"organization_id": org_id,
                                                   "report_type": report_type})
        overlap = []
        for sf in rows:
            if exclude_source_file_id and sf["id"] == exclude_source_file_id:
                continue
            if not sf.get("date_from") or not sf.get("date_to"):
                continue
            if date_from and date_to and \
                    str(sf["date_to"]) >= str(date_from) and \
                    str(sf["date_from"]) <= str(date_to):
                overlap.append({"source_file_id": sf["id"],
                                "file_name": sf["file_name"],
                                "date_from": sf["date_from"],
                                "date_to": sf["date_to"]})
        return overlap

    # -- row validation (C06) -------------------------------------------------

    def _required_columns(self, rtype: str) -> list[str]:
        base = ["search term", "match type", "marketplace", "impressions",
                "clicks", "spend", "orders", "revenue"]
        if rtype == "search_term":
            return ["search term", "impressions", "clicks", "spend",
                    "orders", "revenue"]
        if rtype == "campaign":
            return ["keyword", "impressions", "clicks"]
        return base

    def _row_is_valid(self, rtype: str, row: dict) -> bool:
        if not row:
            return False
        low = {k.strip().lower(): (v or "") for k, v in row.items()}
        term = low.get("search term") or low.get("keyword") or low.get("phrase") \
            or low.get("customer search term")
        if term is None or str(term).strip() == "":
            return False
        spend = low.get("spend")
        if spend not in (None, ""):
            if _dec(spend) is None:
                return False
        revenue = low.get("revenue")
        if revenue not in (None, ""):
            if _dec(revenue) is None:
                return False
        return True

    def _rejection_reason(self, rtype: str, row: dict) -> str:
        low = {k.strip().lower(): (v or "") for k, v in row.items()}
        term = low.get("search term") or low.get("keyword") or low.get("phrase")
        if term is None or str(term).strip() == "":
            return "missing_search_term"
        spend = low.get("spend")
        if spend not in (None, "") and _dec(spend) is None:
            return "non_numeric_spend"
        revenue = low.get("revenue")
        if revenue not in (None, "") and _dec(revenue) is None:
            return "non_numeric_revenue"
        return "invalid_row"

    # -- cancellation / status -----------------------------------------------

    def cancel(self, org_id: str, batch_id: str, actor: Optional[str] = None) -> dict:
        batch = self.repos.import_batches.get(batch_id)
        if batch is None or batch["organization_id"] != org_id:
            raise ImportError_("not_found", "import batch not found")
        if batch["status"] not in ("created", "running", "dry_run"):
            raise ImportError_("not_cancellable",
                               f"batch state {batch['status']} is not cancellable")
        self.repos.db.conn.execute(
            "UPDATE import_batches SET status=?, completed_at=? WHERE id=?",
            ("cancelled", _now_iso(), batch_id))
        self.repos.db.conn.commit()
        self.audit.record(action="keyword.import.cancel",
                          actor_user_id=actor, organization_id=org_id,
                          resource_type="import_batch", resource_id=batch_id)
        return self._batch_view(self.repos.import_batches.get(batch_id), org_id)

    def batch_status(self, org_id: str, batch_id: str) -> dict:
        batch = self.repos.import_batches.get(batch_id)
        if batch is None or batch["organization_id"] != org_id:
            raise ImportError_("not_found", "import batch not found")
        return self._batch_view(batch, org_id)

    def batches(self, org_id: str, limit: int = 100) -> list[dict]:
        rows = self.repos.import_batches.for_org(org_id, limit=limit)
        return [self._batch_view(r, org_id) for r in rows]

    def rejected_rows(self, org_id: str, batch_id: str) -> list[dict]:
        batch = self.repos.import_batches.get(batch_id)
        if batch is None or batch["organization_id"] != org_id:
            raise ImportError_("not_found", "import batch not found")
        return [self._rejected_view(r) for r in
                self.repos.rejected_rows.for_batch(batch_id)]

    # -- helpers -------------------------------------------------------------

    @staticmethod
    def _resolve_path(file_name: str) -> str:
        base = os.environ.get("NORTHSTAR_KEYWORD_SOURCE_DIR") or os.path.join(
            "Northstar_backend", "foundation", "tests", "fixtures")
        return os.path.join(base, file_name)

    def _batch_view(self, batch: dict, org_id: str,
                    idempotent_replay: bool = False) -> dict:
        summary = batch.get("summary")
        if isinstance(summary, str):
            import json
            try:
                summary = json.loads(summary)
            except (ValueError, TypeError):
                summary = {}
        return {
            "id": batch["id"], "organization_id": batch["organization_id"],
            "source_file_id": batch.get("source_file_id"),
            "status": batch["status"], "submitted_by": batch.get("submitted_by"),
            "submitted_at": batch.get("submitted_at"),
            "started_at": batch.get("started_at"),
            "completed_at": batch.get("completed_at"),
            "summary": summary or {},
            "idempotent_replay": idempotent_replay,
        }

    @staticmethod
    def _rejected_view(row: dict) -> dict:
        rj = row.get("row_json")
        if isinstance(rj, str):
            import json
            try:
                rj = json.loads(rj)
            except (ValueError, TypeError):
                rj = {}
        return {"id": row["id"], "import_batch_id": row.get("import_batch_id"),
                "row_index": row.get("row_index"), "row": rj or {},
                "rejection_reason": row.get("rejection_reason")}


def _json(value) -> str:
    import json
    return json.dumps(value, default=str)