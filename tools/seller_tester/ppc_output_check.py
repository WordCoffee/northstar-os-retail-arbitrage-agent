"""PPC output checks: does the bulk file the app wrote actually conform, reconcile, and stay in budget?

The PPC service path already proves upload → propose → approve → write → download, and that the
downloaded bytes are the written bytes. It does not prove three things a seller depends on:

1. **Format.** The written file must parse through the app's own parser with the same required
   columns as the source, and keep the same header order. A file that opens in our parser but not in
   the ads console is a file the seller cannot use.
2. **Reconciliation.** Every row that was not approved must be byte-for-byte the same value, and the
   approved row must carry exactly the approved change. A writer that "helpfully" re-types other
   rows is a writer that loses a seller's account history.
3. **Budget.** Every bid in the output must be above zero and at or below the cap the brief declares.
   A bid over the seller's cap is money they did not agree to spend.

These are pure functions over parsed rows, so they can run on a fixture without a database.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence


def _sheets(parsed: Dict[str, Any]) -> List[Dict[str, Any]]:
    sheets = parsed.get("sheets")
    return sheets if isinstance(sheets, list) else []


def _header(parsed: Dict[str, Any]) -> List[str]:
    sheets = _sheets(parsed)
    if not sheets:
        return []
    header = (sheets[0].get("headers") or sheets[0].get("header")
              or sheets[0].get("columns") or [])
    return [str(name).strip().lower() for name in header]


def _rows(parsed: Dict[str, Any]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for sheet in _sheets(parsed):
        out.extend(sheet.get("normalized") or [])
    return out


def _bid(value: Any) -> Optional[float]:
    try:
        text = str(value).replace("$", "").replace(",", "").strip()
        return float(text) if text else None
    except (TypeError, ValueError):
        return None


def check_format(parsed: Dict[str, Any], source: Dict[str, Any],
                 required: Sequence[str], *, min_rows: int = 1) -> Dict[str, Any]:
    """The written file parses, keeps the required columns, and keeps the source header order."""
    sheets = _sheets(parsed)
    header = _header(parsed)
    source_header = _header(source)
    missing = [name for name in required if name.lower() not in header]
    rows = _rows(parsed)
    same_order = (not source_header) or header[:len(source_header)] == source_header
    ok = bool(sheets) and not missing and len(rows) >= min_rows and same_order
    detail = (f"sheets={len(sheets)} rows={len(rows)} "
              f"missing={missing or 'none'} header_order={'same' if same_order else 'changed'}")
    return {"ok": ok, "check": "output_format_conforms", "detail": detail,
            "rows": len(rows), "missing_columns": missing, "header_order_preserved": same_order}


#: Columns that describe a row's position in *this* file, not the seller's account. A delta file
#: necessarily renumbers them, so they are not part of "unchanged without approval".
POSITIONAL = {"sheet", "row_index"}


def _key(row: Dict[str, Any]) -> tuple:
    return (row.get("campaign_id"), row.get("ad_group_id"), row.get("keyword_id"),
            row.get("entity"), row.get("operation"), row.get("keyword_text"))


def reconcile(source: Dict[str, Any], written: Dict[str, Any],
              approved: Dict[int, Dict[str, Any]]) -> Dict[str, Any]:
    """A delta file: only approved rows, only approved values, nothing invented.

    The writer emits the **change** file, not a copy of the source — one row for each approved
    proposal. So the honest reconciliation is: every written row exists in the source, it was one of
    the approved rows, its approved columns carry exactly the approved values, every other column is
    unchanged from the source, and every approved row is present.
    """
    src, out = _rows(source), _rows(written)
    by_key = {_key(row): (index, row) for index, row in enumerate(src)}
    problems: List[str] = []
    if not out:
        problems.append("the written file carries no rows")
    for row in out:
        found = by_key.get(_key(row))
        if not found:
            problems.append(f"a written row is not in the source: {_key(row)}")
            continue
        index, before = found
        expected = approved.get(index)
        if expected is None:
            problems.append(f"row {index} was written but was never approved")
            continue
        for column, value in expected.items():
            if str(row.get(column)) != str(value):
                problems.append(f"row {index} {column}: written {row.get(column)!r}, "
                                f"approved {value!r}")
        for column, value in (before or {}).items():
            if column in expected or column in POSITIONAL:
                continue
            if str(row.get(column)) != str(value):
                problems.append(f"row {index} {column} changed without approval: "
                                f"{value!r} -> {row.get(column)!r}")
    written_keys = {_key(row) for row in out}
    for index in approved:
        if index < len(src) and _key(src[index]) not in written_keys:
            problems.append(f"approved row {index} is missing from the written file")
    ok = not problems and bool(out)
    return {"ok": ok, "check": "reconciles_with_source",
            "detail": (f"{len(out)} written row(s) for {len(approved)} approved; "
                       f"{len(problems)} problem(s)"),
            "problems": problems[:6]}


def bids_within_caps(parsed: Dict[str, Any], *, max_bid: float, min_bid: float = 0.02
                     ) -> Dict[str, Any]:
    """Every bid in the file is > 0 and <= the brief's cap."""
    over: List[float] = []
    under: List[float] = []
    seen = 0
    for row in _rows(parsed):
        value = _bid((row or {}).get("bid"))
        if value is None:
            continue
        seen += 1
        if value > float(max_bid) + 1e-9:
            over.append(value)
        if value < float(min_bid):
            under.append(value)
    ok = seen > 0 and not over and not under
    detail = (f"{seen} bid(s); over cap ({max_bid}) {len(over)}; below floor ({min_bid}) "
              f"{len(under)}")
    return {"ok": ok, "check": "bids_within_caps", "detail": detail,
            "bids_seen": seen, "max_bid": max_bid, "min_bid": min_bid,
            "over": over[:5], "under": under[:5]}


def run_all(parsed: Dict[str, Any], source: Dict[str, Any], approved: Dict[int, Dict[str, Any]],
            required: Sequence[str], *, max_bid: float) -> Dict[str, Any]:
    return {
        "output_format_conforms": check_format(parsed, source, required),
        "reconciles_with_source": reconcile(source, parsed, approved),
        "bids_within_caps": bids_within_caps(parsed, max_bid=max_bid),
    }


__all__ = ["bids_within_caps", "check_format", "reconcile", "run_all"]
