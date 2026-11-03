"""AdPilot API (U9) — report in, change log out, bulk file out.

Two endpoints, both file-only: the operator uploads an Amazon search-term report
they already have, the server analyses it with the EXISTING PPC specialist, and
the operator downloads a bulk sheet. No Amazon API is contacted, nothing is
uploaded anywhere, and no change is applied to any account.

Reuse, not reimplementation:
  • `specialists.ppc_agent.analyze` decides what is worth harvesting or negating.
  • `specialists.ppc_bulk.build_rows / validate_rows / to_xlsx` builds and
    validates the sheet. A row that fails validation refuses the whole file.

Honest limits (inherited from the specialist and stated in the response):
  • The column layout is Northstar's own, not a verified Amazon bulk template.
  • A report with the wrong columns is REJECTED with the missing names, never
    repaired silently.
"""

from __future__ import annotations

import base64
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from specialists import ppc_agent, ppc_bulk

router = APIRouter(prefix="/api/adpilot", tags=["adpilot"])

MAX_ROWS = 20000


class ReportIn(BaseModel):
    """Rows exactly as the operator's file states them (keys are matched loosely)."""

    rows: List[Dict[str, Any]] = Field(default_factory=list)
    target_acos: float = Field(default=0.35, gt=0, le=2)
    bid: Optional[float] = Field(default=None, ge=0, le=100)


def _guard(rows: List[Dict[str, Any]]) -> None:
    if len(rows) > MAX_ROWS:
        raise HTTPException(status_code=413, detail=f"too many rows (limit {MAX_ROWS})")


@router.post("/analyze")
def analyze_report(body: ReportIn) -> Dict[str, Any]:
    """Analyse an uploaded search-term report. Nothing is written."""
    _guard(body.rows)
    analysis = ppc_agent.analyze(body.rows, target_acos=body.target_acos)
    # The specialist's verdict is the response: a rejection says why and what it
    # expected, and the caller must show that rather than an empty table.
    return {**analysis, "rows_read": len(body.rows)}


@router.post("/bulk")
def build_bulk(body: ReportIn) -> Dict[str, Any]:
    """Analyse, then build + validate the bulk sheet. Returns base64 bytes."""
    _guard(body.rows)
    analysis = ppc_agent.analyze(body.rows, target_acos=body.target_acos)
    if not analysis.get("ok"):
        return {"ok": False, "status": "rejected", "error": analysis.get("error"),
                "expected": analysis.get("expected"), "rows_read": len(body.rows)}

    try:
        rows = ppc_bulk.build_rows(analysis, bid=body.bid)
    except ppc_bulk.BulkFileError as exc:
        return {"ok": False, "status": "rejected", "error": str(exc)}
    except Exception as exc:  # noqa: BLE001 - a malformed analysis is a refusal, not a 500
        return {"ok": False, "status": "rejected",
                "error": f"the analysis could not be turned into rows: {exc}"}

    check = ppc_bulk.validate_rows(rows, body.rows)
    if not check.get("ok"):
        return {"ok": False, "status": "rejected",
                "error": "a proposed row did not validate against the source report",
                "problems": check.get("problems", []), "rows": len(rows)}

    payload = ppc_bulk.to_xlsx(rows)
    return {
        "ok": True,
        "status": "written",
        "filename": "northstar-ppc-bulk.xlsx",
        "mime": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "bytes": len(payload),
        "rows": len(rows),
        "bytes_b64": base64.b64encode(payload).decode("ascii"),
        "columns": list(ppc_bulk.BULK_COLUMNS),
        "note": ("Validated against the source report. Column layout is Northstar's own - "
                 "map it to the current Amazon bulk template before upload."),
        "summary": analysis.get("summary", ""),
    }


@router.get("/status")
def status() -> Dict[str, Any]:
    """What this lane can do, stated as facts rather than a capability claim."""
    return {
        "ok": True,
        "kinds": ["search_term"],
        "columns": {k: list(v) for k, v in {
            "search_term": ppc_agent.SEARCH_TERM_COLUMNS,
            "targeting": ppc_agent.TARGETING_COLUMNS,
            "placement": ppc_agent.PLACEMENT_COLUMNS,
        }.items()},
        "thresholds": {"min_clicks_negative": ppc_agent.MIN_CLICKS_FOR_NEGATIVE,
                       "max_bid_move": ppc_agent.MAX_BID_MOVE},
        "bulk_columns": list(ppc_bulk.BULK_COLUMNS),
        "amazon_api": False,
        "note": "File-only: nothing is sent to or read from any advertising platform.",
    }
