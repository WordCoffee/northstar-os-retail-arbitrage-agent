"""Unit bookkeeping for the director program: one command per unit transition.

The work order asks for the queue to be updated and one line appended to the autonomy
log after each unit. Doing that by hand invites drift between the JSON, the log and the
git tag, so it is one call:

    python tools/director_units.py --done D3 --tag ty-dir-D3 --next D4 \
        --summary "two parallel builders merged; overlap refused" --tokens 0
    python tools/director_units.py --status
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
QUEUE = ROOT / "reports" / "ty" / "director_queue.json"
LOG = ROOT / "reports" / "ty" / "autonomy_log.md"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _load() -> Dict[str, Any]:
    return json.loads(QUEUE.read_text(encoding="utf-8"))


def mark(unit: str, *, tag: str = "", summary: str = "", evidence: Optional[Dict[str, Any]] = None,
         next_unit: str = "", tokens: int = 0, status: str = "done") -> Dict[str, Any]:
    queue = _load()
    row = queue.setdefault("units", {}).setdefault(unit, {})
    row.update({"status": status, "unit_tag": tag or row.get("unit_tag", ""),
                "completed_at": _now() if status == "done" else row.get("completed_at")})
    if evidence:
        row["evidence"] = evidence
    if summary:
        row["summary"] = summary
    if next_unit:
        queue["unit_in_flight"] = next_unit
    else:
        queue["unit_in_flight"] = ""
    queue["updated_at"] = _now()
    QUEUE.write_text(json.dumps(queue, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    if LOG.is_file():
        text = LOG.read_text(encoding="utf-8").rstrip("\n")
        text += (f"\n| {_now()[:10]} | {unit} | director | {summary or status} | "
                 f"`{tag or '-'}` | {tokens} |")
        LOG.write_text(text + "\n", encoding="utf-8")
    return {"ok": True, "unit": unit, "status": status, "next": queue["unit_in_flight"]}


def status() -> Dict[str, Any]:
    queue = _load()
    rows = queue.get("units") or {}
    done = [name for name, row in rows.items()
            if isinstance(row, dict) and row.get("status") in ("done", "continuous")]
    pending = [name for name, row in rows.items()
               if isinstance(row, dict) and row.get("status") == "pending"]
    return {"cycle": queue.get("cycle"), "in_flight": queue.get("unit_in_flight"),
            "done": len(done), "pending": len(pending),
            "units": {name: (row.get("status") if isinstance(row, dict) else row)
                      for name, row in rows.items()}}


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Director unit bookkeeping")
    parser.add_argument("--done")
    parser.add_argument("--next", default="")
    parser.add_argument("--tag", default="")
    parser.add_argument("--summary", default="")
    parser.add_argument("--tokens", type=int, default=0)
    parser.add_argument("--status", action="store_true")
    ns = parser.parse_args(argv)

    if ns.status:
        print(json.dumps(status(), indent=2))
        return 0
    if not ns.done:
        parser.error("--done UNIT or --status")
    print(json.dumps(mark(ns.done, tag=ns.tag, summary=ns.summary,
                          next_unit=ns.next, tokens=ns.tokens), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
