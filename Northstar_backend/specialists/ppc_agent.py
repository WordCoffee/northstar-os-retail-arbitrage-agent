"""PPC Analyst — report in, bulk file out. No Amazon API, no guesses.

Blueprint §8.3 is unusually specific about the validation bar, and it is the
part that actually protects the operator: a bulk file that references a campaign
which does not exist in the source report can pause or break a real account.
So the validators run before anything is returned, and a bad upload is REJECTED
rather than repaired silently.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

SEARCH_TERM_COLUMNS = ("campaign", "ad group", "customer search term", "impressions",
                       "clicks", "spend", "sales", "orders")
TARGETING_COLUMNS = ("campaign", "ad group", "targeting", "match type", "impressions",
                     "clicks", "spend", "sales", "orders")
PLACEMENT_COLUMNS = ("campaign", "placement", "impressions", "clicks", "spend",
                     "sales", "orders")

MIN_CLICKS_FOR_NEGATIVE = 8
MAX_BID_MOVE = 0.30


def _norm(row: Dict[str, Any]) -> Dict[str, Any]:
    return {str(k).strip().lower(): v for k, v in (row or {}).items()}


def validate_report(rows: Sequence[Dict[str, Any]], kind: str) -> Dict[str, Any]:
    """Reject the wrong report instead of guessing what it is."""
    tables = {"search_term": SEARCH_TERM_COLUMNS, "targeting": TARGETING_COLUMNS,
              "placement": PLACEMENT_COLUMNS}
    required = tables.get(kind)
    if not required:
        return {"ok": False, "error": f"unknown report kind {kind!r}"}
    if not rows:
        return {"ok": False, "error": "the report is empty"}
    first = _norm(rows[0])
    missing = [c for c in required if c not in first]
    if missing:
        return {
            "ok": False,
            "error": (f"this does not look like a {kind.replace('_', ' ')} report — "
                      f"missing column(s): {', '.join(missing)}"),
            "missing_columns": missing,
            "expected": list(required),
        }
    return {"ok": True, "rows": len(rows), "kind": kind}


def _num(row: Dict[str, Any], key: str) -> float:
    try:
        return float(str(row.get(key, 0) or 0).replace("%", "").replace(",", "").strip())
    except (TypeError, ValueError):
        return 0.0


def analyze(search_terms: Sequence[Dict[str, Any]], *, target_acos: float = 0.35,
            min_clicks_negative: int = MIN_CLICKS_FOR_NEGATIVE) -> Dict[str, Any]:
    """Harvest converting terms, propose negatives, never invent a row."""
    check = validate_report(search_terms, "search_term")
    if not check.get("ok"):
        return {"ok": False, "status": "rejected", "error": check["error"],
                "expected": check.get("expected")}

    harvest: List[Dict[str, Any]] = []
    negatives: List[Dict[str, Any]] = []
    for raw in search_terms:
        row = _norm(raw)
        clicks = _num(row, "clicks")
        orders = _num(row, "orders")
        spend = _num(row, "spend")
        sales = _num(row, "sales")
        term = str(row.get("customer search term") or "").strip()
        if not term:
            continue
        acos = (spend / sales) if sales > 0 else None
        if orders >= 1 and (acos is None or acos <= target_acos):
            harvest.append({
                "source_row": {"campaign": row.get("campaign"),
                               "ad group": row.get("ad group"),
                               "customer search term": term},
                "orders": int(orders), "acos": round(acos, 3) if acos is not None else None,
                "action": "add as exact-match keyword",
            })
        elif orders == 0 and clicks >= min_clicks_negative:
            negatives.append({
                "source_row": {"campaign": row.get("campaign"),
                               "ad group": row.get("ad group"),
                               "customer search term": term},
                "clicks": int(clicks), "spend": round(spend, 2),
                "action": "add as negative exact",
            })
    return {
        "ok": True,
        "status": "planned",
        "summary": (f"{len(harvest)} term(s) converting within a {target_acos:.0%} ACOS target; "
                    f"{len(negatives)} term(s) with {min_clicks_negative}+ clicks and no order."),
        "harvest": harvest,
        "negatives": negatives,
        "thresholds": {"target_acos": target_acos,
                       "min_clicks_negative": min_clicks_negative},
        "notes": ["Every proposal carries the source row it came from.",
                  "Nothing is uploaded; you take the change log into Amazon yourself."],
    }


def validate_change_rows(rows: Sequence[Dict[str, Any]],
                         source: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """The blueprint's guard: a change may only reference entities in the source."""
    known_campaigns = {str(_norm(r).get("campaign") or "").strip().lower() for r in source}
    known_agroups = {str(_norm(r).get("ad group") or "").strip().lower() for r in source}
    problems: List[str] = []
    allowed_ops = {"create", "update", "archive"}
    for i, raw in enumerate(rows, 1):
        row = _norm(raw)
        op = str(row.get("operation") or "").strip().lower()
        if op not in allowed_ops:
            problems.append(f"row {i}: operation {op!r} is not one of {sorted(allowed_ops)}")
        camp = str(row.get("campaign") or "").strip().lower()
        ag = str(row.get("ad group") or "").strip().lower()
        if op != "create" and camp and camp not in known_campaigns:
            problems.append(f"row {i}: campaign {camp!r} is not in the source report")
        if op != "create" and ag and ag not in known_agroups:
            problems.append(f"row {i}: ad group {ag!r} is not in the source report")
        for money in ("bid", "budget"):
            if money in row:
                try:
                    if float(row[money]) < 0:
                        problems.append(f"row {i}: {money} cannot be negative")
                except (TypeError, ValueError):
                    problems.append(f"row {i}: {money} is not numeric")
    return {"ok": not problems, "problems": problems,
            "checked": len(rows), "note": "validate against the operator's own export"}
