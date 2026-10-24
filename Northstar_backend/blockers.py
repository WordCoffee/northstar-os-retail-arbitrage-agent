"""Blocker ledger for the Northstar harness (section 2B of the operating constitution).

A blocker is a missing key / config / decision that stops a specific step but
not the whole build. The protocol: stub it, log it here, keep building, and
surface it ONCE as a batched report. This module is the "log it here" half, and
it consumes the decision layer's `blocker_escalation` decision to decide whether
each blocker interrupts the operator now or rides the next batched report.

Storage is the shared northstar.db (data_layer.get_db()), so blockers survive a
process restart. Nothing here retries, un-stubs or auto-resolves anything.
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import sys
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

STATUS_OPEN = "open"
STATUS_RESOLVED = "resolved"

VALID_KINDS = ("missing_key", "missing_config", "missing_decision",
               "missing_tool", "other")


def _db():
    sys.path.insert(0, os.path.dirname(__file__))
    from data_layer import get_db
    return get_db()


def _ensure(db: sqlite3.Connection) -> None:
    db.execute(
        """CREATE TABLE IF NOT EXISTS blockers (
               id TEXT PRIMARY KEY,
               title TEXT NOT NULL,
               kind TEXT NOT NULL,
               detail TEXT,
               decision_value TEXT NOT NULL,
               decision_confidence REAL NOT NULL,
               decision_flags TEXT,
               status TEXT NOT NULL,
               created_at TEXT NOT NULL,
               resolved_at TEXT,
               title_hash TEXT NOT NULL
           )"""
    )
    db.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS ux_blockers_title_hash ON blockers(title_hash)"
    )


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash(title: str) -> str:
    return hashlib.sha256(title.strip().lower().encode("utf-8")).hexdigest()


def _decision(text: str) -> Dict[str, Any]:
    try:
        import decision_layer
        return decision_layer.decide("blocker_escalation", text or "")
    except Exception as exc:  # noqa: BLE001 - a missing decision layer must not block logging
        return {"value": "later", "confidence": 0.0, "abstained": True,
                "flags": ["decision_layer_unavailable"], "reason": str(exc)[:120]}


def log(title: str, *, kind: str = "other", detail: str = "",
        text: str = "") -> Dict[str, Any]:
    """Log a blocker. Idempotent on title: re-logging the same title is a no-op.

    Returns the blocker record (existing or new) plus whether it was newly created.
    """
    if kind not in VALID_KINDS:
        kind = "other"
    title = (title or "").strip()
    if not title:
        raise ValueError("blocker title must not be empty")
    db = _db()
    _ensure(db)
    h = _hash(title)
    existing = db.execute(
        "SELECT * FROM blockers WHERE title_hash = ?", (h,)
    ).fetchone()
    if existing:
        row = dict(existing)
        row["newly_created"] = False
        return row

    decision = _decision(text or title)
    bid = str(uuid.uuid4())
    try:
        db.execute(
            """INSERT INTO blockers (id, title, kind, detail, decision_value,
                   decision_confidence, decision_flags, status, created_at, title_hash)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (bid, title, kind, detail[:500], decision["value"],
             float(decision["confidence"]), json.dumps(decision.get("flags", [])),
             STATUS_OPEN, _now(), h),
        )
        db.commit()
    except sqlite3.IntegrityError:  # concurrent insert of the same title
        db.rollback()
        row = dict(db.execute("SELECT * FROM blockers WHERE title_hash = ?", (h,)).fetchone())
        row["newly_created"] = False
        return row
    row = dict(db.execute("SELECT * FROM blockers WHERE id = ?", (bid,)).fetchone())
    row["newly_created"] = True
    row["decision"] = decision
    return row


def list_open() -> List[Dict[str, Any]]:
    db = _db()
    _ensure(db)
    cur = db.execute(
        "SELECT * FROM blockers WHERE status = ? ORDER BY created_at", (STATUS_OPEN,)
    )
    return [dict(r) for r in cur.fetchall()]


def resolve(blocker_id: str) -> Dict[str, Any]:
    db = _db()
    _ensure(db)
    cur = db.execute(
        "UPDATE blockers SET status = ?, resolved_at = ? WHERE id = ? AND status = ?",
        (STATUS_RESOLVED, _now(), blocker_id, STATUS_OPEN),
    )
    db.commit()
    return {"resolved": cur.rowcount > 0, "id": blocker_id}


def batch_report() -> str:
    """One batched report (section 2B): 'now' blockers first, then 'later', never 'never'."""
    rows = list_open()
    if not rows:
        return "# Blockers\n\n(none open)\n"
    now = [r for r in rows if r["decision_value"] == "now"]
    later = [r for r in rows if r["decision_value"] == "later"]
    never = [r for r in rows if r["decision_value"] == "never"]
    lines = ["# Blockers (batched report)", "",
             f"Open: {len(rows)}  (now: {len(now)}, later: {len(later)}, never: {len(never)})",
             ""]
    for group_name, group in (("Interrupt now", now), ("Next batched report", later),
                              ("Backlog (never interrupt)", never)):
        if not group:
            continue
        lines.append(f"## {group_name}")
        lines.append("")
        for r in group:
            lines.append(f"- **{r['title']}** (`{r['kind']}`, conf {r['decision_confidence']:.2f})")
            if r.get("detail"):
                lines.append(f"  {r['detail']}")
        lines.append("")
    return "\n".join(lines)


def from_provider_check(tool_id: str, provider: str = "local") -> Optional[Dict[str, Any]]:
    """Log a blocker when a needed tool is unavailable on the chosen lane."""
    try:
        import provider_suite as ps
        v = ps.verify(tool_id, provider)
    except Exception:  # noqa: BLE001
        return None
    if v.usable:
        return None
    return log(
        f"{tool_id} unavailable on {provider} lane",
        kind="missing_tool",
        detail=f"reason={v.reason}; {v.notes or ''}".strip(),
        text=f"{tool_id} {v.reason} {v.notes or ''}",
    )


def _main(argv: List[str]) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="Northstar blocker ledger")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p_log = sub.add_parser("log")
    p_log.add_argument("title")
    p_log.add_argument("--kind", default="other", choices=VALID_KINDS)
    p_log.add_argument("--detail", default="")
    p_log.add_argument("--text", default="")
    p_list = sub.add_parser("list")
    p_list.add_argument("--open", action="store_true", default=True)
    p_resolve = sub.add_parser("resolve")
    p_resolve.add_argument("id")
    sub.add_parser("report")
    p_scan = sub.add_parser("scan-suite")
    p_scan.add_argument("--provider", default="local")
    args = ap.parse_args(argv)

    if args.cmd == "log":
        row = log(args.title, kind=args.kind, detail=args.detail, text=args.text)
        print(json.dumps({"id": row["id"], "title": row["title"],
                          "decision": row["decision_value"],
                          "newly_created": row.get("newly_created")}, indent=2))
        return 0
    if args.cmd == "list":
        rows = list_open()
        print(json.dumps([{"id": r["id"], "title": r["title"],
                           "kind": r["kind"], "decision": r["decision_value"],
                           "created_at": r["created_at"]} for r in rows], indent=2))
        return 0
    if args.cmd == "resolve":
        print(json.dumps(resolve(args.id), indent=2))
        return 0
    if args.cmd == "report":
        print(batch_report())
        return 0
    if args.cmd == "scan-suite":
        import provider_suite as ps
        logged = []
        for tid in ps.tool_ids():
            v = ps.verify(tid, args.provider)
            if not v.usable:
                b = from_provider_check(tid, args.provider)
                if b is not None and b.get("newly_created"):
                    logged.append(tid)
        print(json.dumps({"scanned": len(ps.tool_ids()),
                          "newly_logged": logged}, indent=2))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
