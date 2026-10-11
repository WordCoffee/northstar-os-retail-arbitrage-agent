"""Design Studio — marketplace report import parsing (Phase 6 item 4).

Pure, offline functions: no network, no provider, no credentials. They turn an
uploaded Sponsored Products search-term report (CSV/JSON) or a Brand Analytics
Search Query Performance file (CSV/JSON) into normalized rows.

Honesty rules baked in here:
  • A column the file does not carry becomes NULL, never 0. A blank cell is
    NULL too. A literal 0 in the file is a real zero.
  • The parse never invents a value, a rank, a currency or a date.
  • Every import carries the notes that limit what the data can say:
    the report's 65-day lookback ceiling, the reporting API's 31-days-per-
    request ceiling, and the click-only bias of search-term reports (a term
    only appears once it has at least one click).
  • Brand Analytics data is simply absent until a file provides it; nothing
    fabricates a stand-in.

Column matching is alias-based and case/punctuation-insensitive so a real
console export with the usual header row parses without a hand-maintained map.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

# ── Limits and caveats (functional constants, not marketing copy) ──────────

SP_LOOKBACK_MAX_DAYS = 65
SP_API_RANGE_MAX_DAYS = 31

NOTE_LOOKBACK = (
    f"Search-term reports cover at most a {SP_LOOKBACK_MAX_DAYS}-day lookback "
    "in the console; a file cannot show older terms than that window."
)
NOTE_API_RANGE = (
    f"The reporting API returns at most {SP_API_RANGE_MAX_DAYS} days per "
    "request. A file spanning a longer range is a union of multiple pulls and "
    "may be missing days inside it."
)
NOTE_CLICK_ONLY = (
    "Click-only bias: this report lists a search term only after it received at "
    "least one click. Impressions that never produced a click are absent, so "
    "term-level impression and CTR figures understate the query's real volume."
)
NOTE_FILE_NOT_LIVE = (
    "Imported file data. It is a snapshot the operator supplied, not a live "
    "feed; re-import to refresh."
)

KIND_SP_SEARCH_TERMS = "sp_search_terms"
KIND_BRAND_ANALYTICS_SQP = "brand_analytics_sqp"
KIND_BRAND_VOICE = "brand_voice"
KIND_KEYWORDS = "keywords"
KINDS = (KIND_SP_SEARCH_TERMS, KIND_BRAND_ANALYTICS_SQP, KIND_BRAND_VOICE, KIND_KEYWORDS)

MAX_CONTENT_BYTES = 5 * 1024 * 1024  # a report file, not a data dump


class ImportParseError(ValueError):
    pass


# ── Header normalization and aliases ───────────────────────────────────────
# Keys are normalized header spellings (lowercase, alphanumerics only).

def _norm_key(name: str) -> str:
    return "".join(ch for ch in str(name or "").lower() if ch.isalnum())


_ALIASES: Dict[str, Tuple[str, ...]] = {
    "term": (
        "customersearchterm", "searchterm", "searchquery", "query",
        "customerquery", "searchtermquery",
    ),
    "campaign": ("campaignname", "campaign"),
    "ad_group": ("adgroupname", "adgroup"),
    "match_type": ("matchtype",),
    "targeting": ("targeting", "keywordtext", "targetingexpression"),
    "impressions": ("impressions", "impression"),
    "clicks": ("clicks", "click"),
    "orders": (
        "orders", "totalorders", "7daytotalorders", "14daytotalorders",
        "30daytotalorders",
    ),
    "units": (
        "units", "totalunits", "7daytotalunits", "14daytotalunits",
        "30daytotalunits",
    ),
    "spend": ("spend", "cost", "totalcost", "costspend"),
    "sales": (
        "sales", "totalsales", "7daytotalsales", "14daytotalsales",
        "30daytotalsales",
    ),
    "currency": ("currency", "currencycode"),
    "date": ("date", "reportingdate", "daterange", "startdate"),
    "end_date": ("enddate",),
    # Brand Analytics Search Query Performance.
    "search_frequency_rank": ("searchfrequencyrank", "sfr"),
    "search_query_score": ("searchqueryscore", "searchqueryscorebyimpressions"),
    "asin_click_share": (
        "asinclickshare", "clickedsameasinshare", "clickshare",
    ),
}

_REVERSE: Dict[str, str] = {}
for canonical, aliases in _ALIASES.items():
    for a in aliases:
        _REVERSE[a] = canonical

# Columns the search-terms surface reads. `missing_columns` records which of
# these the file did not carry, so the UI can say WHICH evidence is UNKNOWN.
EXPECTED_TERM_COLUMNS = (
    "term", "campaign", "ad_group", "match_type", "impressions", "clicks",
    "orders", "spend", "sales",
)
EXPECTED_BA_COLUMNS = ("term", "search_frequency_rank", "search_query_score")
EXPECTED_KEYWORD_COLUMNS = ("term", "volume")
BRAND_VOICE_FIELDS = ("name", "promise", "voice", "audience", "prohibited")

# Brand-voice aliases: normalized header/key -> canonical field.
_VOICE_ALIASES = {
    "brandname": "name", "name": "name", "brand": "name",
    "promise": "promise", "onelinepromise": "promise", "positioning": "promise",
    "voice": "voice", "brandvoice": "voice", "tone": "voice", "toneofvoice": "voice",
    "audience": "audience", "targetaudience": "audience", "who": "audience",
    "prohibited": "prohibited", "prohibitedclaims": "prohibited", "neverclaim": "prohibited",
    "keywords": "keywords",
}


def _parse_number(raw: Any) -> Optional[float]:
    """A missing/blank/unparseable cell is NULL. A literal number is itself -
    including a real 0. Never coerced to zero."""
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return float(raw)
    s = str(raw).strip()
    if s == "" or s.lower() in ("null", "none", "n/a", "na", "-", "--"):
        return None
    # Percentages stay as given ("1.23%" -> 1.23), with the unit implied by the
    # source column. Currency symbols and thousands separators are stripped.
    s = s.replace(",", "")
    for sym in ("$", "€", "£", "¥", "₹", "%"):
        s = s.replace(sym, "")
    s = s.strip()
    try:
        return float(s)
    except ValueError:
        return None


def _parse_date(raw: Any) -> Optional[str]:
    """Return an ISO date (YYYY-MM-DD) or None. Never guesses a date."""
    if raw is None:
        return None
    if isinstance(raw, datetime):
        return raw.date().isoformat()
    s = str(raw).strip()
    if not s:
        return None
    # Try the full cell, then an ISO date prefix (drops a trailing time part).
    for candidate in (s, s[:10]):
        for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%m/%d/%Y", "%d/%m/%Y",
                    "%m-%d-%Y", "%b %d, %Y", "%B %d, %Y"):
            try:
                return datetime.strptime(candidate, fmt).date().isoformat()
            except ValueError:
                continue
    return None


def _detect_format(filename: Optional[str], content: str) -> str:
    low = (filename or "").lower()
    if low.endswith(".json"):
        return "json"
    if low.endswith(".csv") or low.endswith(".tsv"):
        return "csv"
    stripped = content.lstrip()
    return "json" if stripped.startswith(("[", "{")) else "csv"


def _rows_from_content(content: str, fmt: str, filename: Optional[str] = None) -> List[Dict[str, Any]]:
    if fmt == "json":
        try:
            data = json.loads(content)
        except json.JSONDecodeError as exc:
            raise ImportParseError(f"JSON could not be parsed: {exc.msg}") from exc
        if isinstance(data, dict):
            for key in ("rows", "data", "records", "items", "results"):
                if isinstance(data.get(key), list):
                    data = data[key]
                    break
            else:
                data = [data]
        if not isinstance(data, list):
            raise ImportParseError("JSON must be an array of row objects or an object with a rows array")
        return [r for r in data if isinstance(r, dict)]

    delimiter = "\t" if (filename or "").lower().endswith(".tsv") else ","
    reader = csv.DictReader(io.StringIO(content), delimiter=delimiter)
    if reader.fieldnames is None:
        raise ImportParseError("CSV has no header row")
    return [dict(r) for r in reader]


def content_fingerprint(kind: str, content: str) -> str:
    """Stable idempotency key for an import: the kind plus the file content
    with BOM and line-ending noise normalized. Re-importing the same file (or a
    byte-identical copy) produces the same fingerprint."""
    body = content.lstrip("\ufeff").replace("\r\n", "\n").replace("\r", "\n")
    return hashlib.sha256((kind + "\n" + body).encode("utf-8")).hexdigest()


def parse_import(
    *,
    kind: str,
    content: str,
    filename: Optional[str] = None,
    observed_from: Optional[str] = None,
    observed_to: Optional[str] = None,
) -> Dict[str, Any]:
    """Parse an uploaded report into normalized rows plus honest metadata.

    Returns a dict with:
      rows               - one dict per report row (columns per kind)
      columns_found      - canonical column names the file carried
      missing_columns    - expected-but-absent columns (their values are NULL)
      skipped_rows       - rows dropped because they carried no term at all
      observed_from/to   - operator values, else derived from row dates, else None
      notes              - the caveat list that must accompany the data
    """
    if kind not in KINDS:
        raise ImportParseError(f"unknown import kind {kind!r}; expected one of {', '.join(KINDS)}")
    if content is None or str(content).strip() == "":
        raise ImportParseError("the file is empty")
    content = str(content)
    if len(content.encode("utf-8", errors="ignore")) > MAX_CONTENT_BYTES:
        raise ImportParseError(f"file larger than {MAX_CONTENT_BYTES // (1024 * 1024)} MB")

    # Brand voice and keyword lists are not metric reports; they have their own
    # honest shapes (a field set / a term list), each carrying provenance.
    if kind == KIND_BRAND_VOICE:
        return _parse_brand_voice(content=content, filename=filename)
    if kind == KIND_KEYWORDS:
        return _parse_keywords(content=content, filename=filename)

    fmt = _detect_format(filename, content)
    raw_rows = _rows_from_content(content, fmt, filename)
    if not raw_rows:
        raise ImportParseError("the file carries no data rows")

    header_map: Dict[str, str] = {}
    for key in raw_rows[0].keys():
        canonical = _REVERSE.get(_norm_key(key))
        if canonical and canonical not in header_map:
            header_map[canonical] = key
    # A file with JSON rows of differing keys: extend the map from every row.
    for r in raw_rows[1:]:
        for key in r.keys():
            canonical = _REVERSE.get(_norm_key(key))
            if canonical and canonical not in header_map:
                header_map[canonical] = key

    if "term" not in header_map:
        raise ImportParseError(
            "no search-term / search-query column was found. Expected a header "
            "like 'Customer Search Term' (Sponsored Products) or 'Search Query' "
            "(Brand Analytics)."
        )

    rows: List[Dict[str, Any]] = []
    skipped = 0
    derived_min: Optional[str] = None
    derived_max: Optional[str] = None

    for raw in raw_rows:
        term = raw.get(header_map["term"])
        term_s = str(term).strip() if term is not None else ""
        if not term_s:
            skipped += 1
            continue
        row: Dict[str, Any] = {"term": term_s}
        for canonical in ("campaign", "ad_group", "match_type", "targeting",
                          "currency"):
            src = header_map.get(canonical)
            val = raw.get(src) if src else None
            row[canonical] = str(val).strip() if val is not None and str(val).strip() != "" else None
        for canonical in ("impressions", "clicks", "orders", "units", "spend",
                          "sales", "search_frequency_rank",
                          "search_query_score", "asin_click_share"):
            src = header_map.get(canonical)
            row[canonical] = _parse_number(raw.get(src)) if src else None

        d_from = _parse_date(raw.get(header_map["date"])) if "date" in header_map else None
        d_to = _parse_date(raw.get(header_map["end_date"])) if "end_date" in header_map else None
        row["row_from"] = d_from
        row["row_to"] = d_to or d_from
        if d_from and (derived_min is None or d_from < derived_min):
            derived_min = d_from
        if row["row_to"] and (derived_max is None or row["row_to"] > derived_max):
            derived_max = row["row_to"]
        rows.append(row)

    if not rows:
        raise ImportParseError("every data row was missing a search term; nothing to import")

    expected = EXPECTED_TERM_COLUMNS if kind == KIND_SP_SEARCH_TERMS else EXPECTED_BA_COLUMNS
    present = tuple(c for c in expected if c in header_map)
    missing = tuple(c for c in expected if c not in header_map)

    notes = [NOTE_FILE_NOT_LIVE]
    if kind == KIND_SP_SEARCH_TERMS:
        notes += [NOTE_LOOKBACK, NOTE_API_RANGE, NOTE_CLICK_ONLY]
    else:
        notes += [NOTE_LOOKBACK]

    of = _parse_date(observed_from) or derived_min
    ot = _parse_date(observed_to) or derived_max

    return {
        "format": fmt,
        "rows": rows,
        "columns_found": list(present),
        "missing_columns": list(missing),
        "skipped_rows": skipped,
        "observed_from": of,
        "observed_to": ot,
        "observed_source": "operator" if (_parse_date(observed_from) or _parse_date(observed_to)) else ("row-dates" if (derived_min or derived_max) else "none"),
        "notes": notes,
        # Provenance is part of the data: the file, its fingerprint and when the
        # server stored it. The transport is never a live feed.
        "fingerprint": content_fingerprint(kind, content),
    }


def _parse_brand_voice(*, content: str, filename: Optional[str] = None) -> Dict[str, Any]:
    """Parse a brand-voice file (JSON object / CSV key,value rows).

    Recognised fields: name, promise, voice, audience, prohibited, keywords.
    An unrecognised key is kept in `extras` rather than dropped. A field the
    file does not carry is ABSENT here (the UI shows UNKNOWN, never a guess).
    """
    fmt = _detect_format(filename, content)
    raw_rows = _rows_from_content(content, fmt, filename)
    if not raw_rows:
        raise ImportParseError("the file carries no brand-voice fields")
    fields: Dict[str, str] = {}
    extras: Dict[str, Any] = {}
    for raw in raw_rows:
        for key, val in raw.items():
            if val is None or str(val).strip() == "":
                continue
            canon = _VOICE_ALIASES.get(_norm_key(key))
            if canon:
                fields[canon] = str(val).strip()
            else:
                extras[str(key)] = str(val).strip()
    if not fields:
        raise ImportParseError(
            "no recognised brand-voice fields were found. Expected keys like "
            "name / promise / voice / audience / prohibited (or a CSV of key,value rows)."
        )
    rows = [{
        "term": key,
        "extras": {"value": value},
        "row_from": None, "row_to": None,
    } for key, value in fields.items()]
    if extras:
        rows.append({"term": "_extra", "extras": extras, "row_from": None, "row_to": None})
    return {
        "format": fmt,
        "rows": rows,
        "columns_found": sorted(fields.keys()),
        "missing_columns": [f for f in BRAND_VOICE_FIELDS if f not in fields],
        "skipped_rows": 0,
        "observed_from": None,
        "observed_to": None,
        "observed_source": "none",
        "notes": [
            NOTE_FILE_NOT_LIVE,
            "Brand voice imported from a file: it is the operator's own wording, not a marketplace read.",
        ],
        "fingerprint": content_fingerprint(KIND_BRAND_VOICE, content),
    }


def _parse_keywords(*, content: str, filename: Optional[str] = None) -> Dict[str, Any]:
    """Parse a keyword list (JSON array of strings/objects, or CSV with a
    keyword/term column). A keyword with no volume column keeps volume NULL -
    UNKNOWN, never 0."""
    fmt = _detect_format(filename, content)
    out: List[Dict[str, Any]] = []
    skipped = 0
    term_keys = ("keyword", "term", "searchterm", "phrase", "query")

    def take(item: Dict[str, Any]) -> None:
        nonlocal skipped
        term = None
        extra: Dict[str, Any] = {}
        for k, v in item.items():
            nk = _norm_key(k)
            if nk in term_keys and v is not None and str(v).strip():
                term = str(v).strip()
            elif v is not None and str(v).strip() != "":
                extra[str(k)] = _parse_number(v) if nk in ("volume", "searchvolume", "monthlysearches", "rank") else str(v).strip()
        if term:
            out.append({"term": term, "extras": extra, "row_from": None, "row_to": None})
        else:
            skipped += 1

    if fmt == "json":
        try:
            data = json.loads(content)
        except json.JSONDecodeError as exc:
            raise ImportParseError(f"JSON could not be parsed: {exc.msg}") from exc
        if isinstance(data, dict):
            data = data.get("keywords") or data.get("rows") or data.get("data") or []
        if not isinstance(data, list):
            raise ImportParseError("JSON must be an array of keywords or an object with a keywords array")
        for item in data:
            if isinstance(item, str):
                term = item.strip()
                if term:
                    out.append({"term": term, "extras": {}, "row_from": None, "row_to": None})
                else:
                    skipped += 1
            elif isinstance(item, dict):
                take(item)
    else:
        raw_rows = _rows_from_content(content, fmt, filename)
        for raw in raw_rows:
            take(raw)

    if not out:
        raise ImportParseError("no keywords were found (expected a keyword/term column or a list of strings)")
    return {
        "format": fmt,
        "rows": out,
        "columns_found": ["term"],
        "missing_columns": ["volume"] if not any(r["extras"].get("volume") is not None for r in out) else [],
        "skipped_rows": skipped,
        "observed_from": None,
        "observed_to": None,
        "observed_source": "none",
        "notes": [
            NOTE_FILE_NOT_LIVE,
            "Keyword list imported from a file: a snapshot, not a live search-volume feed. A missing volume is UNKNOWN, never 0.",
        ],
        "fingerprint": content_fingerprint(KIND_KEYWORDS, content),
    }


def confidence_label(clicks: Optional[float]) -> Dict[str, Any]:
    """The one sample-size labelling used by briefs AND variant comparisons."""
    if clicks is None:
        return {"sample": "UNKNOWN", "clicks": None,
                "note": "No clicks figure is available, so no sample-size claim can be made."}
    c = float(clicks)
    if c < 5:
        return {"sample": "very small", "clicks": c,
                "note": "Fewer than 5 clicks: treat every rate from this term as noise."}
    if c < 25:
        return {"sample": "small", "clicks": c,
                "note": "Under 25 clicks: directionally useful only."}
    if c < 100:
        return {"sample": "moderate", "clicks": c,
                "note": "25-100 clicks: reviewable, still shadable by one campaign change."}
    return {"sample": "large", "clicks": c,
            "note": "100+ clicks: the strongest evidence this file can carry."}


def parse_variant_metrics(*, content: str, filename: Optional[str] = None) -> Dict[str, Any]:
    """Parse a small variant-metrics file (CSV/JSON) — Phase 6 item 6.

    Each row must name a variant (by id or by exact name) and may carry any of
    impressions / clicks / orders / spend / sales (+ optional observed dates).
    A missing metric is NULL; nothing is filled in. Rows that name no variant
    are reported, not guessed at.
    """
    if content is None or str(content).strip() == "":
        raise ImportParseError("the file is empty")
    content = str(content)
    if len(content.encode("utf-8", errors="ignore")) > MAX_CONTENT_BYTES:
        raise ImportParseError(f"file larger than {MAX_CONTENT_BYTES // (1024 * 1024)} MB")

    fmt = _detect_format(filename, content)
    raw_rows = _rows_from_content(content, fmt, filename)
    if not raw_rows:
        raise ImportParseError("the file carries no data rows")

    alias = {
        "variant": ("variant", "variantid", "variantname", "creative", "creativeid", "name"),
        "observed_from": ("observedfrom", "startdate", "from", "date"),
        "observed_to": ("observedto", "enddate", "to"),
        "impressions": ("impressions",),
        "clicks": ("clicks",),
        "orders": ("orders", "totalorders", "7daytotalorders"),
        "spend": ("spend", "cost"),
        "sales": ("sales", "totalsales", "7daytotalsales"),
    }
    header_map: Dict[str, str] = {}
    for key in raw_rows[0].keys():
        canonical = None
        nk = _norm_key(key)
        for target, names in alias.items():
            if nk in names:
                canonical = target
                break
        if canonical and canonical not in header_map:
            header_map[canonical] = key
    if "variant" not in header_map:
        raise ImportParseError("no variant column was found. Expected a header like 'variant' or 'variant name'.")

    rows: List[Dict[str, Any]] = []
    skipped = 0
    for raw in raw_rows:
        name = raw.get(header_map["variant"])
        name_s = str(name).strip() if name is not None else ""
        if not name_s:
            skipped += 1
            continue
        row = {"variant": name_s}
        for c in ("observed_from", "observed_to"):
            row[c] = _parse_date(raw.get(header_map[c])) if c in header_map else None
        for c in ("impressions", "clicks", "orders", "spend", "sales"):
            row[c] = _parse_number(raw.get(header_map[c])) if c in header_map else None
        rows.append(row)
    if not rows:
        raise ImportParseError("every data row was missing a variant name; nothing to import")
    return {"format": fmt, "rows": rows, "skipped_rows": skipped,
            "notes": [NOTE_FILE_NOT_LIVE]}


def build_brief(
    *,
    terms: List[Dict[str, Any]],
    brand: Optional[Dict[str, Any]] = None,
    keywords: Optional[List[str]] = None,
    voice_source: Optional[Dict[str, Any]] = None,
    keywords_source: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Compose a creative brief from imported search terms + the brand profile.

    No generation. Every ranking is labelled with its sample size and a
    confidence band, and a term is NEVER called a winner without the click-only
    bias being stated next to it. A metric that is absent is reported as UNKNOWN,
    never as zero. `voice_source` records where the voice text came from (the
    brand profile, or an imported file with its date) so the brief carries its
    own provenance.
    """
    brand = brand or {}
    keywords = [str(k).strip().lower() for k in (keywords or []) if str(k).strip()]

    ranked = []
    for t in terms:
        clicks = t.get("clicks")
        evidence = {
            "term": t.get("term"),
            "impressions": t.get("impressions") if t.get("impressions") is not None else "UNKNOWN",
            "clicks": clicks if clicks is not None else "UNKNOWN",
            "orders": t.get("orders") if t.get("orders") is not None else "UNKNOWN",
            "spend": t.get("spend") if t.get("spend") is not None else "UNKNOWN",
            "sales": t.get("sales") if t.get("sales") is not None else "UNKNOWN",
            "observed_from": t.get("row_from") or t.get("observed_from") or "UNKNOWN",
            "observed_to": t.get("row_to") or t.get("observed_to") or "UNKNOWN",
        }
        labels = confidence_label(clicks)
        matched_keyword = None
        term_l = str(t.get("term") or "").lower()
        for k in keywords:
            if k and k in term_l:
                matched_keyword = k
                break
        ranked.append({
            "evidence": evidence,
            "confidence": labels,
            "matched_keyword": matched_keyword,
            # The caveat is attached to EVERY ranking that reads click data.
            "bias": NOTE_CLICK_ONLY if clicks is not None else None,
        })

    ranked.sort(key=lambda r: (r["confidence"].get("clicks") is None,
                               -(r["confidence"].get("clicks") or 0),
                               str(r["evidence"]["term"])))

    return {
        "objective": brand.get("objective") or "Move the listing's strongest search terms into the creative.",
        "audience": brand.get("audience") or "UNKNOWN - set the audience in the brand profile.",
        "voice": brand.get("voice") or "UNKNOWN - set the brand voice in the brand profile.",
        "voice_provenance": voice_source or {
            "source": "brand profile",
            "observed_at": None,
            "note": "Voice text from the studio brand profile (a local record).",
        },
        "keywords_provenance": keywords_source or {
            "source": "brand profile (promise + audience words)",
            "observed_at": None,
            "note": "No keyword list was imported, so matching uses the brand profile's own words.",
        },
        "promise": brand.get("promise") or "UNKNOWN - set the one-line promise in the brand profile.",
        # Headlines are NEVER invented: absent brand copy stays an instruction.
        "headline_slots": [
            {
                "slot": "primary",
                "from_term": r["evidence"]["term"],
                "headline": "Draft from the brand promise - the studio does not invent copy.",
                "evidence": r["evidence"],
                "confidence": r["confidence"],
                "bias": r["bias"],
            }
            for r in ranked[:3]
        ],
        "ranked_terms": ranked,
        "notes": [
            "No image or video is generated by this brief.",
            "A search term is not a winner unless its click volume is stated; search-term reports carry only clicked terms, so absence of a term is not evidence it never ran.",
            "Performance is import-file evidence at the observed date, not live data.",
        ],
    }


# ── Brief -> assets: copy variants + on-image text (templates only) ────────
# Item 7 of the 2026-10-11 directive. The studio turns a brief into copy
# variants and on-image text using TEMPLATES over the operator's own words
# (brand promise / voice / audience + the imported search term). Nothing is
# generated; a slot whose source words are absent stays an instruction. Each
# variant is meant to be stored in the variants table so a later results
# import can match it by id or exact name.

BRIEF_ASSET_LIMIT = 3
CTA_TEMPLATE = "Choose a call to action from the platform's own options; the studio does not invent one."


def brief_to_assets(
    *,
    brief: Dict[str, Any],
    brand: Optional[Dict[str, Any]] = None,
    limit: int = BRIEF_ASSET_LIMIT,
) -> Dict[str, Any]:
    """Turn a brief into copy-variant payloads (TEMPLATES ONLY, no generation).

    Each variant carries: a name (stable, matchable by a later results import),
    copy slots (headline / subhead / cta), on-image text layers with their
    sources, and the brief reference with its evidence + confidence + bias so
    the tie back to the imported term survives into the variant record.
    """
    brand = brand or {}
    promise = str(brand.get("promise") or "").strip()
    voice = str(brand.get("voice") or "").strip()
    audience = str(brand.get("audience") or "").strip()
    variants: List[Dict[str, Any]] = []
    for r in (brief.get("ranked_terms") or [])[: max(1, int(limit))]:
        term = r["evidence"]["term"]
        headline = (f"{promise} - {term}" if promise else
                    "Draft the headline from your brand promise; the studio does not invent copy.")
        subhead = (f"{voice} - {term}" if voice else
                   "Draft the subhead from your brand voice; the studio does not invent copy.")
        on_image = [
            {"layer": "headline", "text": headline,
             "source": "brand promise template" if promise else "instruction"},
            {"layer": "term", "text": term, "source": "imported search term"},
        ]
        if audience:
            on_image.append({"layer": "audience-note", "text": audience, "source": "brand profile"})
        variants.append({
            "name": f"Brief variant: {term}",
            "format": "image",
            "status": "draft",
            "copy": {"headline": headline, "subhead": subhead, "cta": CTA_TEMPLATE},
            "on_image_text": on_image,
            "brief_ref": {
                "term": term,
                "evidence": r["evidence"],
                "confidence": r["confidence"],
                "bias": r["bias"],
            },
        })
    return {
        "variants": variants,
        "count": len(variants),
        "template_only": True,
        "note": ("Templates only: no image, video or copy is generated. Each variant is created in the "
                 "variants table so a later results import can match it by id or exact name."),
    }
