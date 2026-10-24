"""PPC bulk-file writer — the last missing piece of the PPC lane.

`ppc_agent` validated and proposed rows; it did not produce anything an operator
could upload. This writes an Amazon-style bulk sheet from VALIDATED rows only,
and refuses to write a file if any row fails validation.

Honest limitation: the exact column layout Amazon expects is **not verified**
against a current bulk template this pass. The writer therefore:
  • uses a documented column set of its own (`BULK_COLUMNS`),
  • writes a companion `README` sheet saying so,
  • and never claims to be an official Amazon template.

Every row carries the source it came from, so the operator can audit a change.
"""

from __future__ import annotations

import io
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from specialists import ppc_agent as ppa

#: Our column contract. NOT an Amazon-verified template (see module docstring).
BULK_COLUMNS = (
    "operation", "campaign", "ad group", "targeting", "match type",
    "bid", "budget", "state", "reason", "source row",
)

OPERATIONS = {"create", "update", "archive"}


class BulkFileError(ValueError):
    """Raised when a bulk file would contain an invalid or unsourced row."""


def build_rows(analysis: Dict[str, Any], *, action: str = "create",
               bid: Optional[float] = None) -> List[Dict[str, Any]]:
    """Turn a validated analysis into bulk rows, each carrying its source."""
    if not analysis.get("ok"):
        raise BulkFileError(f"cannot build rows from a failed analysis: "
                            f"{analysis.get('error')}")
    rows: List[Dict[str, Any]] = []
    for item in analysis.get("harvest") or []:
        src = item.get("source_row") or {}
        rows.append({
            "operation": action if action in OPERATIONS else "create",
            "campaign": src.get("campaign") or "",
            "ad group": src.get("ad group") or "",
            "targeting": item["source_row"].get("customer search term") if item.get("source_row") else "",
            "match type": "exact",
            "bid": "" if bid is None else round(float(bid), 2),
            "budget": "",
            "state": "enabled",
            "reason": f"orders={item.get('orders')} acos={item.get('acos')}",
            "source row": str(src),
        })
    for item in analysis.get("negatives") or []:
        src = item.get("source_row") or {}
        rows.append({
            "operation": "create",
            "campaign": src.get("campaign") or "",
            "ad group": src.get("ad group") or "",
            "targeting": src.get("customer search term") or "",
            "match type": "negative exact",
            "bid": "",
            "budget": "",
            "state": "enabled",
            "reason": f"clicks={item.get('clicks')} spend={item.get('spend')} no orders",
            "source row": str(src),
        })
    return rows


def validate_rows(rows: Sequence[Dict[str, Any]],
                  source: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """Reuse the PPC validator, then enforce our own shape."""
    problems: List[str] = []
    if not rows:
        problems.append("no rows to write")
    for i, row in enumerate(rows, 1):
        for col in BULK_COLUMNS:
            if col not in row:
                problems.append(f"row {i}: missing column {col!r}")
        if row.get("operation") not in OPERATIONS:
            problems.append(f"row {i}: bad operation {row.get('operation')!r}")
        if not str(row.get("targeting") or "").strip():
            problems.append(f"row {i}: empty targeting")
        if row.get("bid") not in ("", None):
            try:
                if float(row["bid"]) < 0:
                    problems.append(f"row {i}: negative bid")
            except (TypeError, ValueError):
                problems.append(f"row {i}: non-numeric bid")
    upstream = ppa.validate_change_rows(
        [{"operation": r.get("operation"), "campaign": r.get("campaign"),
          "ad group": r.get("ad group"), "bid": r.get("bid") or 0} for r in rows],
        source)
    problems.extend(upstream.get("problems") or [])
    return {"ok": not problems, "problems": problems, "rows": len(rows)}


def to_xlsx(rows: Sequence[Dict[str, Any]], *, title: str = "Northstar bulk plan") -> bytes:
    """Write the sheet. Refuses an empty set — an empty upload is never 'done'."""
    if not rows:
        raise BulkFileError("refusing to write an empty bulk file")
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill

    wb = Workbook()
    ws = wb.active
    ws.title = "bulk plan"
    header_fill = PatternFill("solid", fgColor="1C2E26")
    header_font = Font(color="FFFFFF", bold=True)
    ws.append(list(BULK_COLUMNS))
    for cell in ws[1]:
        cell.fill = header_fill
        cell.font = header_font
    for row in rows:
        ws.append([row.get(c, "") for c in BULK_COLUMNS])
    ws.freeze_panes = "A2"

    notes = wb.create_sheet("READ ME")
    for line in (
        "This file is a Northstar planning sheet, not an official Amazon template.",
        "Column layout is our own contract; map it to the current Amazon bulk template "
        "before uploading.",
        "Every row carries the source row it came from in the 'source row' column.",
        f"generated {datetime.now(timezone.utc).isoformat(timespec='seconds')}",
    ):
        notes.append([line])
    notes.column_dimensions["A"].width = 110

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def write_bulk_file(analysis: Dict[str, Any], *, source: Sequence[Dict[str, Any]],
                    out_path: str | Path, bid: Optional[float] = None) -> Dict[str, Any]:
    """Validate, then write. Returns the path and the validation record."""
    rows = build_rows(analysis, bid=bid)
    check = validate_rows(rows, source)
    if not check["ok"]:
        return {"ok": False, "status": "rejected", "problems": check["problems"],
                "rows": len(rows)}
    payload = to_xlsx(rows)
    path = Path(out_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return {"ok": True, "status": "written", "path": str(path),
            "bytes": len(payload), "rows": len(rows),
            "note": ("Validated against the source report. Column layout is Northstar's "
                     "own — map it to the current Amazon bulk template before upload.")}
