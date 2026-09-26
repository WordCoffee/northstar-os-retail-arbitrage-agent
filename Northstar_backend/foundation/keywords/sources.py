"""Local source-file registry (1C-05 / C03).

Discovers local report files (search-term, campaign, placement, top-of-search,
advertised-product, targeting, business, keyword workbooks). For present files:
hash, register, validate, detect duplicates, preserve originals/rows/rejected
rows, record marketplace/date-range/currency. For absent files: record
SOURCE_NOT_PRESENT_LOCALLY and continue. Never invents imported data.
"""
from __future__ import annotations

import csv
import glob
import hashlib
import os
from datetime import datetime
from typing import Optional

from ..models import SourceFile, utcnow

REPORT_TYPES = ["search_term", "campaign", "placement", "top_of_search",
                "advertised_product", "targeting", "business", "keyword_workbook"]

NOT_PRESENT = "SOURCE_NOT_PRESENT_LOCALLY"

# Header-alias -> report type detection (lowercased, normalized column names).
_HEADER_ALIASES = {
    "search_term": {"search term", "search terms", "customer search term",
                    "search term report"},
    "campaign": {"campaign", "campaign name", "campaign id"},
    "placement": {"placement", "placement report", "placement type"},
    "top_of_search": {"top of search", "top-of-search", "top of search report"},
    "advertised_product": {"advertised product", "advertised product asin",
                           "advertised product name"},
    "targeting": {"targeting", "targeting type", "targeting report"},
    "business": {"business report", "by product", "product title"},
    "keyword_workbook": {"keyword", "phrase", "match type", "bid"},
}


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _norm_header(value: str) -> str:
    return " ".join(str(value).strip().lower().split())


def classify_report_type(headers: list[str]) -> Optional[str]:
    """Detect the report type from a header row."""
    cols = {_norm_header(h) for h in headers if h}
    for rtype, aliases in _HEADER_ALIASES.items():
        if cols & aliases:
            return rtype
    return None


def extract_metadata(headers: list[str], first_row: Optional[dict]) -> dict:
    """Best-effort marketplace/currency/date-range extraction (nullable)."""
    meta = {"marketplace": None, "currency": None,
            "date_from": None, "date_to": None}
    if not first_row:
        return meta
    low = {_norm_header(k): (v or "") for k, v in first_row.items()}
    mp = low.get("marketplace") or low.get("site") or low.get("domain")
    if mp:
        from .normalize import normalize_marketplace
        meta["marketplace"] = normalize_marketplace(mp)
    cur = low.get("currency") or low.get("currency code")
    if cur:
        meta["currency"] = str(cur).strip().upper()[:3]
    for frm, to in (("start date", "end date"),
                    ("date from", "date to"),
                    ("report start date", "report end date")):
        d1, d2 = low.get(frm), low.get(to)
        if d1 and d2:
            try:
                meta["date_from"] = datetime.fromisoformat(d1.replace("/", "-"))
                meta["date_to"] = datetime.fromisoformat(d2.replace("/", "-"))
            except ValueError:
                pass
            break
    return meta


def sniff_csv(path: str, *, sample_rows: int = 5) -> dict:
    """Read headers + a few rows without mutating the file."""
    with open(path, "r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.reader(fh)
        rows = [r for _, r in zip(range(sample_rows + 1), reader)]
    if not rows:
        return {"headers": [], "rows": [], "delimiter": ","}
    headers = rows[0]
    rest = rows[1:]
    # normalized dicts for header-consistent rows
    dict_rows = []
    for r in rest:
        if len(r) == len(headers):
            dict_rows.append({h: v for h, v in zip(headers, r)})
    return {"headers": headers, "rows": dict_rows, "delimiter": ","}


class SourceRegistry:
    def __init__(self, repos) -> None:
        self.repos = repos

    # -- discovery ---------------------------------------------------------

    def discover(self, org_id: str, directory: Optional[str] = None) -> dict:
        """Discover present report files and classify them. Absent report
        types are reported as SOURCE_NOT_PRESENT_LOCALLY (never invented)."""
        directory = directory or os.environ.get("NORTHSTAR_KEYWORD_SOURCE_DIR")
        present: dict[str, list[str]] = {}
        if directory and os.path.isdir(directory):
            for path in sorted(glob.glob(os.path.join(directory, "*.csv"))):
                sniff = sniff_csv(path)
                rtype = classify_report_type(sniff["headers"])
                if rtype:
                    present.setdefault(rtype, []).append(path)
                else:
                    present.setdefault("unknown", []).append(path)
        result = {}
        for rtype in REPORT_TYPES:
            result[rtype] = {"status": NOT_PRESENT,
                             "files": present.get(rtype, [])} \
                if rtype not in present else \
                {"status": "PRESENT", "files": present[rtype]}
        if "unknown" in present:
            result["unknown"] = {"status": "PRESENT_UNCLASSIFIED",
                                 "files": present["unknown"]}
        return result

    # -- registration ------------------------------------------------------

    def register_file(self, org_id: str, path: str,
                      report_type: Optional[str] = None) -> dict:
        """Hash + register a local file. Returns the source_file row (or the
        existing duplicate row when the same org already imported this hash)."""
        if not os.path.exists(path):
            raise FileNotFoundError(path)
        sha = _sha256(path)
        existing = self.repos.source_files.by_sha(org_id, sha)
        if existing:
            return {"status": "duplicate", "source_file": existing}
        sniff = sniff_csv(path)
        rtype = report_type or classify_report_type(sniff["headers"]) or "unknown"
        meta = extract_metadata(sniff["headers"],
                                sniff["rows"][0] if sniff["rows"] else None)
        row = SourceFile(
            organization_id=org_id, file_name=os.path.basename(path),
            file_sha256=sha, file_size=os.path.getsize(path),
            marketplace=meta["marketplace"], currency=meta["currency"],
            report_type=rtype, date_from=meta["date_from"],
            date_to=meta["date_to"], status="registered",
            registered_at=utcnow())
        saved = self.repos.source_files.add(row)
        return {"status": "registered", "source_file": saved}

    def source_status(self, org_id: str) -> dict:
        """Per-report-type status: PRESENT | DUPLICATE | SOURCE_NOT_PRESENT_LOCALLY."""
        rows = self.repos.source_files.list(where={"organization_id": org_id})
        by_type: dict[str, list[str]] = {}
        for r in rows:
            by_type.setdefault(r.get("report_type") or "unknown", []).append(
                r["file_name"])
        status = {}
        for rtype in REPORT_TYPES:
            if rtype in by_type:
                status[rtype] = {"status": "PRESENT", "files": by_type[rtype]}
            else:
                status[rtype] = {"status": NOT_PRESENT, "files": []}
        return status

    def detect_duplicate(self, org_id: str, sha: str) -> Optional[dict]:
        return self.repos.source_files.by_sha(org_id, sha)