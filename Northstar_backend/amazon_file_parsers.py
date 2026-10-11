"""Amazon FILE parsers — read-only, stdlib only (file-only architecture).

NorthstarOS never signs in to Amazon. The seller downloads files from Amazon
and uploads them here; this module reads them. No network call exists in this
module (asserted by tools/test_no_amazon_linkage.py): xlsx is read with
``zipfile`` + ``xml.etree``, delimited files with ``csv``.

Supported uploads:
  * Ads bulksheets (.xlsx / .xls / .csv / .tsv): the campaign sheet
    (Product/Entity/Operation + entity id columns) and the search-term sheet.
    A .xls (BIFF binary) is NOT parsed: the parser reports the honest fix
    (re-save as .xlsx or .csv) instead of guessing.
  * Listing / inventory templates (tab-delimited .txt or spreadsheets):
    detected by their own header vocabulary (item_sku / update_delete / ...).
  * Brand Analytics files (CSV / xlsx): Search Query Performance style.
  * A+ ASIN lists (CSV / xls/xlsx): a small ASIN column file.

Honesty rules: a column the file does not carry is reported in
``missing_columns`` and its value is None (UNKNOWN), never a guess and never
zero. Row values are kept EXACTLY as read so a writer can round-trip them.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import zipfile
from typing import Any, Dict, List, Optional, Tuple
from xml.etree import ElementTree as ET

MAX_FILE_BYTES = 8 * 1024 * 1024

# ── Limits and notes that travel with the data ─────────────────────────────

NOTE_ADS_BULKSHEET = (
    "Ads bulksheet: the console exports up to 60-day date ranges for search-term "
    "sheets; a longer window is a union of pulls. Operation values are read, "
    "never assumed."
)
NOTE_LISTING_TEMPLATE = (
    "Listing template: column names come from the template the seller downloaded; "
    "this parser matches them by their own vocabulary and reports anything it "
    "cannot place instead of guessing."
)
NOTE_BRAND_ANALYTICS = (
    "Brand Analytics file: a snapshot the seller downloaded; missing columns are "
    "UNKNOWN, never zero."
)
NOTE_APLUS = (
    "A+ ASIN list: the ASIN bulk-upload limit is UNKNOWN (sources conflict); "
    "Northstar does not assert a limit."
)
NOTE_XLS_UNSUPPORTED = (
    "This is a legacy .xls (BIFF) workbook. Northstar does not parse binary BIFF; "
    "re-save the file as .xlsx or .csv and upload it again. Nothing was guessed."
)

_XLS_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"  # OLE2 compound file (BIFF .xls)


class ParseError(ValueError):
    pass


# ═══════════════════════════════════════════════════════════════════════════
# xlsx reader (stdlib)
# ═══════════════════════════════════════════════════════════════════════════

_NS_MAIN = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
_NS_REL = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
_NS_PKG_REL = "{http://schemas.openxmlformats.org/package/2006/relationships}"


def _col_to_index(ref: str) -> int:
    letters = re.match(r"([A-Z]+)", ref or "")
    if not letters:
        return 0
    idx = 0
    for ch in letters.group(1):
        idx = idx * 26 + (ord(ch) - ord("A") + 1)
    return idx - 1


def _shared_strings(zf: zipfile.ZipFile) -> List[str]:
    try:
        root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
    except (KeyError, ET.ParseError):
        return []
    out = []
    for si in root.findall(f"{_NS_MAIN}si"):
        text = "".join(t.text or "" for t in si.iter(f"{_NS_MAIN}t"))
        out.append(text)
    return out


def _sheet_names(zf: zipfile.ZipFile) -> List[str]:
    try:
        root = ET.fromstring(zf.read("xl/workbook.xml"))
    except (KeyError, ET.ParseError):
        return []
    return [s.get("name") or f"Sheet{i+1}" for i, s in enumerate(root.iter(f"{_NS_MAIN}sheet"))]


def _cell_value(cell, shared: List[str]) -> Optional[str]:
    t = cell.get("t")
    if t == "inlineStr":
        node = cell.find(f"{_NS_MAIN}is")
        if node is None:
            return None
        text = "".join(x.text or "" for x in node.iter(f"{_NS_MAIN}t"))
        return text if text != "" else None
    v = cell.find(f"{_NS_MAIN}v")
    if v is None or v.text is None:
        return None
    if t == "s":
        try:
            return shared[int(v.text)]
        except (ValueError, IndexError):
            return None
    if t == "b":
        return "TRUE" if v.text == "1" else "FALSE"
    return v.text  # numbers and strings as-is


def read_xlsx(content: bytes) -> List[Dict[str, Any]]:
    """Read every sheet: [{name, headers, rows}] with rows as raw string lists."""
    try:
        zf = zipfile.ZipFile(io.BytesIO(content))
    except zipfile.BadZipFile as exc:
        raise ParseError(f"not a readable .xlsx workbook: {exc}") from exc
    shared = _shared_strings(zf)
    names = _sheet_names(zf)
    sheets: List[Dict[str, Any]] = []
    sheet_files = sorted(n for n in zf.namelist() if re.fullmatch(r"xl/worksheets/sheet\d+\.xml", n))
    for i, path in enumerate(sheet_files):
        try:
            root = ET.fromstring(zf.read(path))
        except ET.ParseError as exc:
            raise ParseError(f"sheet XML could not be parsed: {exc}") from exc
        rows: List[List[Optional[str]]] = []
        for row in root.iter(f"{_NS_MAIN}row"):
            cells: Dict[int, Optional[str]] = {}
            for cell in row.iter(f"{_NS_MAIN}c"):
                cells[_col_to_index(cell.get("r") or "")] = _cell_value(cell, shared)
            width = max(cells.keys()) + 1 if cells else 0
            rows.append([cells.get(c) for c in range(width)])
        while rows and all(v is None for v in rows[-1]):
            rows.pop()
        if not rows:
            sheets.append({"name": names[i] if i < len(names) else path, "headers": [], "rows": []})
            continue
        headers = [str(h).strip() if h is not None else "" for h in rows[0]]
        body = [list(r) for r in rows[1:]]
        sheets.append({"name": names[i] if i < len(names) else path, "headers": headers, "rows": body})
    if not sheets:
        raise ParseError("the workbook carries no readable sheets")
    return sheets


def read_delimited(content: bytes, filename: str = "") -> List[Dict[str, Any]]:
    text = content.decode("utf-8-sig", errors="replace")
    delimiter = "\t" if (filename or "").lower().endswith(".txt") else ","
    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    rows = list(reader)
    if not rows:
        raise ParseError("the file carries no rows")
    headers = [str(h).strip() for h in rows[0]]
    body = [[(c if c != "" else None) for c in r] for r in rows[1:]]
    while body and all(v is None for v in body[-1]):
        body.pop()
    return [{"name": "data", "headers": headers, "rows": body}]


# ═══════════════════════════════════════════════════════════════════════════
# Header matching
# ═══════════════════════════════════════════════════════════════════════════

def norm_header(h: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(h or "").lower())


ADS_REQUIRED = ("product", "entity", "operation")
ADS_ID_COLUMNS = (
    "campaignid", "adgroupid", "keywordid", "productadsid", "targetid",
    "portfolioid", "campaign", "adgroup", "keyword",
)
LISTING_REQUIRED_ANY = (
    ("itemsku", "sellersku", "sku"),          # one of these must exist
    ("updatedelete", "update_delete", "operation"),
)
BA_REQUIRED = ("searchquery",)
BA_MARKERS = ("searchfrequencyrank", "searchqueryscore", "searchqueryvolume")
APLUS_REQUIRED = ("asin",)

# Canonical field -> accepted normalized header spellings (the first match wins).
ADS_FIELDS: Dict[str, Tuple[str, ...]] = {
    "product": ("product",),
    "entity": ("entity",),
    "operation": ("operation",),
    "campaign_id": ("campaignid",),
    "ad_group_id": ("adgroupid",),
    "keyword_id": ("keywordid",),
    "product_ads_id": ("productadsid",),
    "target_id": ("targetid",),
    "portfolio_id": ("portfolioid",),
    "campaign_name": ("campaignname", "campaign"),
    "ad_group_name": ("adgroupname", "adgroup"),
    "keyword_text": ("keywordtext", "keyword"),
    "match_type": ("matchtype",),
    "bid": ("bid",),
    "budget": ("budget", "dailybudget"),
    "state": ("state", "status"),
    "search_term": ("customersearchterm", "searchterm", "searchtermtext"),
    "impressions": ("impressions",),
    "clicks": ("clicks",),
    "spend": ("spend", "cost"),
    "sales": ("sales",),
    "orders": ("orders", "purchases", "7daytotalorders"),
}

LISTING_FIELDS: Dict[str, Tuple[str, ...]] = {
    "sku": ("itemsku", "sellersku", "sku"),
    "product_id": ("externalproductid", "productid", "asin1", "asin"),
    "title": ("itemname", "title", "productname"),
    "bullet1": ("bulletpoint1", "bullet1"),
    "description": ("productdescription", "description"),
    "update_delete": ("updatedelete", "operation"),
    "price": ("standardprice", "price"),
    "quantity": ("quantity",),
    "brand": ("brandname", "brand"),
}

APLUS_FIELDS: Dict[str, Tuple[str, ...]] = {
    "asin": ("asin",),
    "content_reference": ("contentreferencekey", "contentreference"),
    "module": ("module", "modulename"),
}


def _map_headers(headers: List[str], fields: Dict[str, Tuple[str, ...]]) -> Dict[str, int]:
    out: Dict[str, int] = {}
    normalized = [norm_header(h) for h in headers]
    for canon, spellings in fields.items():
        for i, nh in enumerate(normalized):
            if nh and nh in spellings and canon not in out:
                out[canon] = i
                break
    return out


def _missing(required: Tuple[str, ...], mapped: Dict[str, int]) -> List[str]:
    return [r for r in required if r not in mapped]


# ═══════════════════════════════════════════════════════════════════════════
# Detection + parsing
# ═══════════════════════════════════════════════════════════════════════════

def _read_any(filename: str, content: bytes) -> List[Dict[str, Any]]:
    low = (filename or "").lower()
    if content[:8] == _XLS_MAGIC:
        raise ParseError(NOTE_XLS_UNSUPPORTED)
    if low.endswith((".xlsx", ".xlsm")) or content[:2] == b"PK":
        return read_xlsx(content)
    # Everything else is treated as delimited text (csv / tsv / .txt templates).
    return read_delimited(content, filename)


def detect_amazon_file(filename: str, content: bytes) -> Dict[str, Any]:
    """Detect the file kind from its content. Never guesses silently."""
    if content[:8] == _XLS_MAGIC:
        return {"kind": "unsupported_xls", "why": NOTE_XLS_UNSUPPORTED, "sheets": []}
    try:
        sheets = _read_any(filename, content)
    except ParseError as exc:
        return {"kind": "unreadable", "why": str(exc), "sheets": []}

    per_sheet = []
    kind_votes: Dict[str, int] = {}
    for s in sheets:
        headers = [norm_header(h) for h in s["headers"]]
        hset = set(headers)
        vote = None
        if {"product", "entity", "operation"} <= hset:
            vote = "ads_bulksheet"
        elif hset & {"customersearchterm", "searchterm"} and ("clicks" in hset or "impressions" in hset):
            vote = "ads_search_terms"
        elif any(hset & set(alias) for alias in LISTING_REQUIRED_ANY) and (
            "itemsku" in hset or "sellersku" in hset or "externalproductid" in hset or "itemname" in hset
        ):
            vote = "listing_template"
        elif "searchquery" in hset and hset & set(BA_MARKERS):
            vote = "brand_analytics"
        elif "asin" in hset and len(headers) <= 8:
            vote = "aplus_asin_list"
        per_sheet.append({"name": s["name"], "kind": vote, "headers": s["headers"]})
        if vote:
            kind_votes[vote] = kind_votes.get(vote, 0) + 1

    if not kind_votes:
        return {
            "kind": "unknown",
            "why": "no recognised Amazon file headers were found (bulksheet needs Product/Entity/Operation; a listing template needs its SKU/update_delete vocabulary; Brand Analytics needs Search Query; an A+ list needs ASIN)",
            "sheets": per_sheet,
        }
    kind = max(kind_votes, key=kind_votes.get)
    return {"kind": kind, "why": f"matched by sheet headers ({kind_votes[kind]} sheet(s))", "sheets": per_sheet}


def parse_upload(filename: str, content: bytes) -> Dict[str, Any]:
    """Detect + parse an uploaded Amazon file into normalized rows.

    Returns {kind, detection, sheets:[{name, headers, rows(normalized), raw_rows}],
    columns_found, missing_columns, row_count, observed_from/to, notes, checksum}.
    Raw rows are kept EXACTLY as read for the change-file writers.
    """
    if not content:
        raise ParseError("the file is empty")
    if len(content) > MAX_FILE_BYTES:
        raise ParseError(f"file larger than {MAX_FILE_BYTES // (1024 * 1024)} MB")
    detection = detect_amazon_file(filename, content)
    kind = detection["kind"]
    if kind in ("unreadable", "unknown", "unsupported_xls"):
        return {
            "kind": kind,
            "detection": detection,
            "sheets": [],
            "columns_found": [],
            "missing_columns": [],
            "row_count": 0,
            "observed_from": None,
            "observed_to": None,
            "notes": [detection["why"]],
            "checksum": hashlib.sha256(content).hexdigest(),
        }

    try:
        sheets = _read_any(filename, content)
    except ParseError as exc:
        raise ParseError(str(exc)) from exc

    out_sheets = []
    columns_found: List[str] = []
    missing_columns: List[str] = []
    row_count = 0
    observed_dates: List[str] = []

    for s in sheets:
        hset = {norm_header(h) for h in s["headers"]}
        sheet_kind = None
        if {"product", "entity", "operation"} <= hset:
            sheet_kind = "ads_bulksheet"
        elif hset & {"customersearchterm", "searchterm"}:
            sheet_kind = "ads_search_terms"
        elif "searchquery" in hset:
            sheet_kind = "brand_analytics"
        elif "asin" in hset and len(s["headers"]) <= 8:
            sheet_kind = "aplus_asin_list"
        elif any(hset & set(a) for a in LISTING_REQUIRED_ANY):
            sheet_kind = "listing_template"
        if sheet_kind is None:
            out_sheets.append({**s, "kind": None, "mapped": {}, "normalized": []})
            continue

        fields = ADS_FIELDS if sheet_kind in ("ads_bulksheet", "ads_search_terms") else (
            LISTING_FIELDS if sheet_kind == "listing_template" else (
                APLUS_FIELDS if sheet_kind == "aplus_asin_list" else {
                    "search_query": ("searchquery",),
                    "search_frequency_rank": ("searchfrequencyrank", "sfr"),
                    "search_query_score": ("searchqueryscore",),
                }
            )
        )
        mapped = _map_headers(s["headers"], fields)
        required = ADS_REQUIRED if sheet_kind == "ads_bulksheet" else (
            BA_REQUIRED if sheet_kind == "brand_analytics" else (
                APLUS_REQUIRED if sheet_kind == "aplus_asin_list" else ()
            )
        )
        for req in _missing(required, mapped):
            missing_columns.append(f"{s['name']}:{req}")
        columns_found.extend(sorted(mapped.keys()))

        normalized = []
        for r_idx, raw in enumerate(s["rows"]):
            row = {"sheet": s["name"], "row_index": r_idx}
            for canon, idx in mapped.items():
                row[canon] = raw[idx] if idx < len(raw) else None
            # Date-ish columns feed the observed range when present and ISO.
            for i, h in enumerate(s["headers"]):
                if re.search(r"\b(date|startdate|enddate|day)\b", norm_header(h)) and i < len(raw) and raw[i]:
                    cell = str(raw[i]).strip()[:10]
                    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", cell):
                        observed_dates.append(cell)
            normalized.append(row)
        row_count += len(normalized)
        out_sheets.append({**s, "kind": sheet_kind, "mapped": {k: v for k, v in mapped.items()},
                           "normalized": normalized})

    notes = {
        "ads_bulksheet": [NOTE_ADS_BULKSHEET],
        "ads_search_terms": [NOTE_ADS_BULKSHEET],
        "listing_template": [NOTE_LISTING_TEMPLATE],
        "brand_analytics": [NOTE_BRAND_ANALYTICS],
        "aplus_asin_list": [NOTE_APLUS],
    }.get(kind, [])
    obs_from = min(observed_dates) if observed_dates else None
    obs_to = max(observed_dates) if observed_dates else None

    return {
        "kind": kind,
        "detection": detection,
        "sheets": out_sheets,
        "columns_found": sorted(set(columns_found)),
        "missing_columns": missing_columns,
        "row_count": row_count,
        "observed_from": obs_from,
        "observed_to": obs_to,
        "notes": notes,
        "checksum": hashlib.sha256(content).hexdigest(),
    }
