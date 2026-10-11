"""Amazon change-file engine — proposals, approval, round-trip validation.

File-only architecture: nothing here talks to Amazon. The seller downloads a
file, uploads it, Northstar proposes changes, the seller approves row by row,
Northstar writes a NEW change file, and the seller uploads that to Amazon
manually. The round-trip validator re-reads the written file and proves the
only differences are the approved ones.

Honesty rules: a row with a missing or unmatched ID is BLOCKED, never written.
A source file older than the stated freshness window carries a warning (never a
silent pass). A spend-increase above the seller's own limit requires a SECOND
confirmation before it can be approved. Title changes carry the title-rule
flags (length 75 / banned characters / repeated word / promotional phrases) as
date-sensitive FLAGS, never blocks, and the engine never edits a title itself.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

# ── The title-rule port (mirrors studio/engine/registryClaims.js) ──────────
# The rules are a small, stable set; both implementations carry the SAME rule
# ids and behaviour. The JS side remains the UI's source of truth.

TITLE_LIMIT_CHARS = 75
TITLE_BANNED_CHARS = ["!", "$", "?", "_", "{", "}", "^", "\u00ac", "\u00a6"]
TITLE_PROMOTIONAL_EXAMPLES = [
    r"\bfree\s+shipping\b", r"\bbest\s*seller\b", r"\bmoney[\s-]*back\b",
    r"\blimited[\s-]*time\b", r"\bhot\s+deal\b", r"\bbuy\s+now\b",
    r"\b\d+\s*%\s*off\b", r"\bsale\b", r"\bguarantee\b",
]
TITLE_COLUMN_ALIASES = {"title", "item_name", "product_name"}


def title_rule_flags(title: str) -> List[Dict[str, str]]:
    s = str(title or "")
    flags: List[Dict[str, str]] = []
    if not s.strip():
        return flags
    if len(s) > TITLE_LIMIT_CHARS:
        flags.append({
            "rule": "title-length-75", "review": "FLAG (date-sensitive)",
            "detail": f"The title is {len(s)} characters; the limit is {TITLE_LIMIT_CHARS} including spaces (brand name counts; bundles are not exempt). Nothing is auto-truncated.",
        })
    for pat in TITLE_PROMOTIONAL_EXAMPLES:
        m = re.search(pat, s, re.I)
        if m:
            flags.append({
                "rule": "title-no-promotional", "review": "FLAG",
                "detail": f"The title appears to carry a promotional phrase (\"{m.group(0)}\"). The check's example list is illustrative, not exhaustive.",
            })
            break
    bad = [c for c in TITLE_BANNED_CHARS if c in s]
    if bad:
        flags.append({
            "rule": "title-special-chars", "review": "FLAG",
            "detail": f"The title contains characters Amazon does not allow: {' '.join(bad)}.",
        })
    counts: Dict[str, int] = {}
    for w in re.split(r"[^a-z0-9']+", s.lower()):
        if w:
            counts[w] = counts.get(w, 0) + 1
    repeated = [w for w, n in counts.items() if n > 2]
    if repeated:
        flags.append({
            "rule": "title-same-word-twice", "review": "FLAG",
            "detail": f"The same word appears more than twice: {', '.join(repeated)}.",
        })
    return flags


# ── Proposals ──────────────────────────────────────────────────────────────

ADS_OPS = ("Create", "Update", "Archive")
LISTING_OP_MAP = {"Create": "Update", "Update": "PartialUpdate", "Archive": "Delete"}
LISTING_OP_COLUMN = "update_delete"

ENTITY_ID_COLUMN = {
    "campaign": "campaign_id",
    "ad group": "ad_group_id",
    "adgroup": "ad_group_id",
    "keyword": "keyword_id",
    "product ad": "product_ads_id",
    "productad": "product_ads_id",
    "target": "target_id",
    "targeting": "target_id",
    "portfolio": "portfolio_id",
}
ADS_ID_CANDIDATES = ("campaign_id", "ad_group_id", "keyword_id", "product_ads_id", "target_id", "portfolio_id")

STALE_SOURCE_DAYS = 14  # engineering choice, stated in the UI, not an Amazon figure


def _entity_id(sheet: Dict[str, Any], row: Dict[str, Any]) -> Tuple[Optional[str], Optional[str], List[str]]:
    """Return (id_field, id_value, blocks). Never guesses an ID."""
    mapped = sheet.get("mapped") or {}
    kind = sheet.get("kind")
    blocks: List[str] = []
    if kind == "listing_template":
        field = "sku"
    elif kind == "aplus_asin_list":
        field = "asin"
    else:
        entity = str(row.get("entity") or "").strip().lower()
        field = ENTITY_ID_COLUMN.get(entity)
        if field is None:
            # Fall back to the first mapped id column that actually carries a value.
            field = next((f for f in ADS_ID_CANDIDATES if mapped.get(f) is not None and row.get(f)), None)
            if field is None:
                blocks.append("unmatched-id: the row's Entity does not name a known entity type and no ID column carries a value")
                return None, None, blocks
    if mapped.get(field) is None:
        blocks.append(f"unmatched-id: the sheet does not carry the {field} column for this row")
        return field, None, blocks
    value = row.get(field)
    if value is None or str(value).strip() == "":
        blocks.append(f"missing-id: the {field} cell is empty")
        return field, None, blocks
    return field, str(value).strip(), blocks


def _numeric(v: Any) -> Optional[float]:
    try:
        return float(str(v).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def build_proposals(parsed: Dict[str, Any], requested: List[Dict[str, Any]], meta: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Build row-level proposals with before/after, reasons, evidence and blocks.

    meta: {upload_id, filename, checksum, downloaded_at, spend_limit_cents, now}
    requested: [{sheet, row_index, op, fields:{canon:value}, reason}]
    """
    sheets = {s["name"]: s for s in parsed.get("sheets", [])}
    now = meta.get("now") or datetime.now(timezone.utc).isoformat()
    downloaded = meta.get("downloaded_at")
    stale = False
    stale_note = None
    if downloaded:
        try:
            d0 = datetime.fromisoformat(str(downloaded)[:10])
            age = (datetime.now(timezone.utc).date() - d0.date()).days
            if age > STALE_SOURCE_DAYS:
                stale = True
                stale_note = (f"The source file was downloaded {age} days ago; beyond the "
                              f"{STALE_SOURCE_DAYS}-day freshness window. Re-download before uploading changes.")
        except ValueError:
            stale = True
            stale_note = "The download date could not be read; freshness is UNKNOWN."

    proposals: List[Dict[str, Any]] = []
    for i, req in enumerate(requested):
        sheet_name = req.get("sheet")
        sheet = sheets.get(sheet_name)
        blocks: List[str] = []
        if sheet is None:
            blocks.append(f"unknown-sheet: {sheet_name}")
        row_index = req.get("row_index")
        row: Dict[str, Any] = {}
        if sheet is not None:
            try:
                row = sheet["normalized"][int(row_index)]
            except (IndexError, TypeError, ValueError):
                blocks.append(f"unknown-row: row_index {row_index} is outside sheet {sheet_name}")
        id_field, id_value, id_blocks = (None, None, [])
        if sheet is not None and not blocks:
            id_field, id_value, id_blocks = _entity_id(sheet, row)
            blocks.extend(id_blocks)

        op = req.get("op")
        kind = sheet.get("kind") if sheet else None
        op_column = None
        op_value = None
        if kind in ("ads_bulksheet", "ads_search_terms"):
            if op not in ADS_OPS:
                blocks.append(f"invalid-operation: {op!r} is not one of {', '.join(ADS_OPS)}")
            op_column, op_value = "operation", op
        elif kind == "listing_template":
            if op not in LISTING_OP_MAP:
                blocks.append(f"invalid-operation: {op!r} is not one of {', '.join(LISTING_OP_MAP)}")
            op_column, op_value = LISTING_OP_COLUMN, LISTING_OP_MAP.get(op)

        fields = dict(req.get("fields") or {})
        before = {c: row.get(c) for c in fields}
        after = {c: fields[c] for c in fields}

        # Title flags: date-sensitive FLAGS, never blocks, never edits.
        title_flags: List[Dict[str, str]] = []
        for canon, value in fields.items():
            if canon in TITLE_COLUMN_ALIASES or canon == "title":
                title_flags = title_rule_flags(value)

        # Spend guardrail: a bid/budget increase above the seller's limit needs
        # a SECOND confirmation before approval.
        requires_second = False
        spend_notes: List[str] = []
        limit_cents = meta.get("spend_limit_cents")
        if limit_cents is not None:
            for canon in ("bid", "budget"):
                if canon in fields:
                    new_num = _numeric(fields[canon])
                    if new_num is not None and new_num * 100 > float(limit_cents):
                        requires_second = True
                        spend_notes.append(
                            f"The new {canon} ({fields[canon]}) exceeds your limit "
                            f"({float(limit_cents) / 100:.2f}). Approving it needs a second confirmation."
                        )

        proposals.append({
            "id": f"prop-{meta.get('upload_id', 'u')}-{i}",
            "sheet": sheet_name,
            "row_index": int(row_index) if row_index is not None else None,
            "kind": kind,
            "entity": row.get("entity"),
            "id_field": id_field,
            "id_value": id_value,
            "op": op,
            "op_column": op_column,
            "op_value": op_value,
            "fields": fields,
            "before": before,
            "after": after,
            "reason": req.get("reason") or "operator-proposed change",
            "title_flags": title_flags,
            "evidence": {
                "upload_id": meta.get("upload_id"),
                "filename": meta.get("filename"),
                "checksum": meta.get("checksum"),
                "downloaded_at": downloaded,
            },
            "stale": stale,
            "stale_note": stale_note,
            "requires_second_confirmation": requires_second,
            "spend_notes": spend_notes,
            "blocks": blocks,
            "status": "proposed" if not blocks else "blocked",
            "created_at": now,
        })
    return proposals


def approve_proposals(proposals: List[Dict[str, Any]], ids: List[str], *, second_confirmation: bool = False) -> Dict[str, Any]:
    """Approve the named proposals. Blocked rows can never be approved; a
    second-confirmation row needs the explicit flag."""
    approved: List[str] = []
    refused: List[Dict[str, str]] = []
    for p in proposals:
        if p["id"] not in ids:
            continue
        if p["blocks"]:
            refused.append({"id": p["id"], "reason": "blocked: " + "; ".join(p["blocks"])})
            continue
        if p.get("requires_second_confirmation") and not second_confirmation:
            refused.append({"id": p["id"], "reason": "second confirmation required above the spend limit"})
            continue
        p["status"] = "approved"
        approved.append(p["id"])
    return {"approved": approved, "refused": refused}


def validate_roundtrip(
    source_parsed: Dict[str, Any],
    written_parsed: Dict[str, Any],
    approved: List[Dict[str, Any]],
    *,
    source_content: bytes = b"",
    written_content: bytes = b"",
) -> Dict[str, Any]:
    """Re-read the written file and prove the ONLY differences are approved.

    Matching is by the recorded ID value per row (never by position), so a
    reordered or truncated file cannot slip through. Returns a diff report with
    checksums.
    """
    violations: List[str] = []
    src_sheets = {s["name"]: s for s in source_parsed.get("sheets", [])}
    wrt_sheets = {s["name"]: s for s in written_parsed.get("sheets", [])}

    if len(approved) == 0:
        # The no-op case: the written file must carry no data rows at all.
        total = sum(len(s.get("rows") or []) for s in wrt_sheets.values())
        if total == 0:
            return {
                "ok": True, "violations": [], "approved_count": 0, "written_count": 0,
                "source_checksum": hashlib.sha256(source_content).hexdigest() if source_content else None,
                "written_checksum": hashlib.sha256(written_content).hexdigest() if written_content else None,
                "diff_digest": hashlib.sha256(b"[]").hexdigest(),
                "note": "No approved changes: the written file carries zero data rows. Nothing changed.",
            }
        violations.append(f"no-op write carried {total} data row(s)")
        return _report(False, violations, 0, total, source_content, written_content, approved)

    used_written: set = set()
    diffs: List[Dict[str, Any]] = []
    for ch in approved:
        sheet_name = ch["sheet"]
        src = src_sheets.get(sheet_name)
        wrt = wrt_sheets.get(sheet_name)
        if src is None or wrt is None:
            violations.append(f"sheet {sheet_name} missing on one side")
            continue
        mapped = src.get("mapped") or {}
        id_idx = mapped.get(ch.get("id_field")) if ch.get("id_field") else None
        # Locate the written row by the ID value.
        target = None
        for wi, wrow in enumerate(wrt.get("rows") or []):
            if wi in used_written:
                continue
            if id_idx is not None and id_idx < len(wrow) and str(wrow[id_idx] or "").strip() == str(ch.get("id_value")):
                target = wi
                break
        if target is None:
            violations.append(f"approved row for {ch.get('id_field')}={ch.get('id_value')} is missing from the written file")
            continue
        used_written.add(target)

        srow = (src.get("rows") or [])[int(ch["row_index"])]
        wrow = (wrt.get("rows") or [])[target]
        allowed = {}
        for canon, value in (ch.get("fields") or {}).items():
            if mapped.get(canon) is not None:
                allowed[mapped[canon]] = "" if value is None else str(value)
        if ch.get("op_column") and mapped.get(ch["op_column"]) is not None:
            allowed[mapped[ch["op_column"]]] = str(ch["op_value"])
        width = max(len(srow), len(wrow))
        for i in range(width):
            a = str(srow[i]) if i < len(srow) and srow[i] is not None else ""
            b = str(wrow[i]) if i < len(wrow) and wrow[i] is not None else ""
            if a == b:
                continue
            if i in allowed and allowed[i] == b:
                diffs.append({"row": ch.get("id_value"), "column": i, "from": a, "to": b})
                continue
            violations.append(f"unapproved change at {ch.get('id_value')} column {i}: {a!r} -> {b!r}")

    written_total = sum(len(s.get("rows") or []) for s in wrt_sheets.values())
    if written_total != len(approved):
        violations.append(f"written file carries {written_total} data row(s) for {len(approved)} approved change(s)")
    return _report(not violations, violations, len(approved), written_total, source_content, written_content, approved, diffs)


def _report(ok: bool, violations: List[str], approved_count: int, written_count: int,
            source_content: bytes, written_content: bytes, approved: List[Dict[str, Any]],
            diffs: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    canonical = json.dumps([
        {"id": a.get("id_value"), "op": a.get("op_value"), "fields": a.get("fields")}
        for a in approved
    ], sort_keys=True)
    return {
        "ok": ok,
        "violations": violations,
        "approved_count": approved_count,
        "written_count": written_count,
        "diffs": diffs or [],
        "source_checksum": hashlib.sha256(source_content).hexdigest() if source_content else None,
        "written_checksum": hashlib.sha256(written_content).hexdigest() if written_content else None,
        "diff_digest": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        "note": "The validator re-read the written file and compared it cell by cell against the source; every difference must be an approved one.",
    }


# ── A+ asset pack (item 6) ─────────────────────────────────────────────────

APLUS_BULK_UPLOAD_LIMIT = None  # UNKNOWN: sources conflict; never asserted


def build_aplus_pack(parsed: Dict[str, Any], assets: List[Dict[str, Any]], meta: Dict[str, Any]) -> Dict[str, Any]:
    """An A+ asset pack: assets + placement instructions + required alt text.

    NOT an uploadable module file: the seller assembles the module in Amazon's
    A+ Content Manager. The ASIN bulk-upload limit is recorded UNKNOWN.
    """
    asins: List[str] = []
    for s in parsed.get("sheets", []):
        for row in s.get("normalized", []):
            if row.get("asin"):
                asins.append(str(row["asin"]).strip())
    return {
        "kind": "aplus_asset_pack",
        "uploadable_module_file": False,
        "note": "This is an asset pack plus instructions, NOT an uploadable A+ module file. Assemble the module in A+ Content Manager yourself.",
        "asins": sorted(set(asins)),
        "asin_bulk_upload_limit": APLUS_BULK_UPLOAD_LIMIT,
        "asin_bulk_upload_limit_note": "UNKNOWN: published figures conflict, so the studio asserts no limit.",
        "assets": [
            {
                "name": a.get("name"),
                "placement": a.get("placement") or "per the module's image slot",
                "alt_text_required": True,
                "alt_text": a.get("alt_text") or None,
                "alt_text_note": None if a.get("alt_text") else "UNKNOWN: alt text is required by Amazon for every A+ image; write it before publishing.",
            }
            for a in (assets or [])
        ],
        "instructions": [
            "Open A+ Content Manager and start the module for each ASIN listed above.",
            "Upload each asset into its named slot; supply the alt text for every image (required, not optional).",
            "Preview the module on mobile and desktop, then submit for moderation yourself.",
        ],
        "evidence": {
            "upload_id": meta.get("upload_id"),
            "filename": meta.get("filename"),
            "checksum": meta.get("checksum"),
            "downloaded_at": meta.get("downloaded_at"),
        },
    }
