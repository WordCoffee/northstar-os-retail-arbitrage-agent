"""Proactive improvement proposals from measured state. It never queues or changes anything.

Reads the scorecards, the queue and `needs_you`, and returns ranked, owner-gated proposals.
The director loop stays the only writer; this is the suggestion surface OpenDuet-style.

    python -m tools.ty_toolkit.proposals --write
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[2]
SCORES = ROOT / "ty" / "scorecards.json"
QUEUE = ROOT / "reports" / "ty" / "director_queue.json"
NEEDS = ROOT / "reports" / "ty" / "needs_you.md"
OUT = ROOT / "reports" / "ty" / "proposals.md"

#: A service whose gap can only be closed by an owner action or a render lane. The proposal is
#: still surfaced, but flagged so nothing looks like work a builder may start unattended.
OWNER_GATED = {
    "listings": "G2 is accepted as an honest zero (health/alert watchtower)",
    "design-studio": "G1 generation needs the render lane and the owner's word",
}


def _owner_items(text: str) -> List[Dict[str, str]]:
    items: List[Dict[str, str]] = []
    for line in (text or "").splitlines():
        if not line.startswith("## "):
            continue
        title = line[3:].strip()
        low = title.lower()
        if "resolved" in low or "delivered" in low or low.startswith("docs"):
            continue
        items.append({"title": title, "owner_gate": True})
    return items


def build(scorecards: Optional[Dict[str, Any]] = None,
          queue: Optional[Dict[str, Any]] = None,
          needs_you: Optional[str] = None, *, limit: int = 8) -> Dict[str, Any]:
    scores = scorecards if scorecards is not None else json.loads(SCORES.read_text(encoding="utf-8"))
    jobs = (queue if queue is not None else
            json.loads(QUEUE.read_text(encoding="utf-8"))).get("jobs") or []
    needs = needs_you if needs_you is not None else NEEDS.read_text(encoding="utf-8")

    proposals: List[Dict[str, Any]] = []
    for row in scores.get("services") or []:
        gap = float(row.get("gap") or 0.0)
        if gap <= 0 or row.get("meets_bar"):
            continue
        sid = str(row.get("id"))
        owner = sid in OWNER_GATED
        proposals.append({
            "kind": "service",
            "id": f"raise-{sid}-{row.get('weakest')}",
            "title": f"Raise {row.get('weakest')} for {sid} (+{gap} points of ranked gap)",
            "why": f"score {row.get('score')} against a bar of {row.get('bar')}; weakest dimension "
                   f"{row.get('weakest')}",
            "impact": gap,
            "owner_gate": owner,
            "note": OWNER_GATED.get(sid, ""),
            "source": "ty/scorecards.json",
        })

    for job in jobs:
        if job.get("status") == "blocked":
            proposals.append({
                "kind": "queue",
                "id": f"unblock-{job.get('id')}",
                "title": f"Unblock {job.get('id')}: {job.get('title')}",
                "why": str(job.get("blocked_on") or job.get("evidence") or "")[:300],
                "impact": 0.0,
                "owner_gate": True,
                "note": "blocked in the director queue",
                "source": "reports/ty/director_queue.json",
            })

    for item in _owner_items(needs):
        proposals.append({
            "kind": "owner",
            "id": "owner-" + re.sub(r"[^a-z0-9]+", "-", item["title"].lower())[:48],
            "title": item["title"],
            "why": "owner-only action recorded in needs_you.md",
            "impact": 0.0,
            "owner_gate": True,
            "note": "only the owner can close it",
            "source": "reports/ty/needs_you.md",
        })

    proposals.sort(key=lambda row: (-float(row["impact"]), row["owner_gate"], row["id"]))
    return {"ok": True, "count": len(proposals), "proposals": proposals[: max(1, int(limit))],
            "note": "Suggestion surface only. It writes no queue entry and changes no state."}


def render(result: Dict[str, Any]) -> str:
    lines = ["# Proactive proposals", "",
             "Generated from measured state. Nothing here is queued or applied automatically.", "",
             "| # | proposal | impact | owner gate | why |", "|---|---|---|---|---|"]
    for i, row in enumerate(result["proposals"], 1):
        lines.append(f"| {i} | {row['title']} | {row['impact']} | "
                     f"{'yes' if row['owner_gate'] else 'no'} | {row['why']} |")
    lines += ["", "Sources: `ty/scorecards.json`, `reports/ty/director_queue.json`, "
                  "`reports/ty/needs_you.md`."]
    return "\n".join(lines) + "\n"


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Proactive proposals from measured state")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--limit", type=int, default=8)
    ns = parser.parse_args(argv)
    result = build(limit=ns.limit)
    if ns.write:
        OUT.write_text(render(result), encoding="utf-8")
        print(f"wrote {OUT} ({len(result['proposals'])} proposal(s), {result['count']} measured)")
    else:
        print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
