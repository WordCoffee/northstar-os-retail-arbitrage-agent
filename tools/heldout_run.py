"""Held-out results, split out of the composite proof and reported by product line.

The point of a held-out set is that the number it produces was not available while the pipeline
was being tuned. So it is published separately from the tuned catalogue, per product line, with
the failures named — including the line that could not be scored at all.

    python -m tools.seller_tester composite --limit 40   # produces the proof
    python tools/heldout_run.py --write
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
PROOF = ROOT / "state" / "seller" / "composite_proof.json"
BRIEFS = ROOT / "ty" / "seller_briefs_heldout.json"
OUT = ROOT / "state" / "seller" / "heldout_proof.json"
REPORT = ROOT / "reports" / "ty" / f"heldout_{date.today().isoformat()}.md"


def split() -> Dict[str, Any]:
    proof = json.loads(PROOF.read_text(encoding="utf-8")) if PROOF.exists() else {"results": []}
    briefs = json.loads(BRIEFS.read_text(encoding="utf-8"))["briefs"]
    by_id = {b["id"]: b for b in briefs}
    rows: List[Dict[str, Any]] = []
    for result in proof.get("results") or []:
        brief_id = str(result.get("brief_id"))
        if brief_id not in by_id:
            continue
        brief = by_id[brief_id]
        rows.append({
            "brief_id": brief_id,
            "product_line": brief.get("product_line"),
            "situation": brief.get("situation"),
            "score": result.get("score"),
            "passed": result.get("passed"),
            "route": result.get("route"),
            "artefact_path": result.get("artefact_path"),
            "failed_checks": result.get("failed_checks") or [],
            "cannot_verify": result.get("cannot_verify"),
            "fidelity": result.get("fidelity"),
        })
    scored = [row for row in rows if row.get("score") is not None]
    lines: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in scored:
        lines[str(row["product_line"])].append(row)
    summary = {
        "held_out_briefs": len(briefs),
        "scored": len(scored),
        "passed": sum(1 for row in scored if row.get("passed")),
        "mean": round(sum(float(row["score"]) for row in scored) / len(scored), 1)
        if scored else None,
        "by_line": {name: {"scored": len(rows_), "passed": sum(1 for r in rows_ if r.get("passed")),
                           "mean": round(sum(float(r["score"]) for r in rows_) / len(rows_), 1)}
                    for name, rows_ in lines.items()},
        "unscored_lines": sorted({b["product_line"] for b in briefs} - set(lines)),
    }
    payload = {"at": date.today().isoformat(), "summary": summary, "results": rows}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    _write_report(briefs, scored, summary)
    return payload


def _write_report(briefs: List[Dict[str, Any]], scored: List[Dict[str, Any]],
                  summary: Dict[str, Any]) -> None:
    lines = ["# Held-out run", "",
             f"{summary['scored']} of {summary['held_out_briefs']} held-out briefs scored, "
             f"{summary['passed']} passed, mean **{summary['mean']}**.", "",
             "| brief | line | situation | score | passed | failed |",
             "|---|---|---|---|---|---|"]
    for row in sorted(scored, key=lambda r: r["brief_id"]):
        lines.append(f"| {row['brief_id']} | {row['product_line']} | {row['situation']} | "
                     f"{row['score']} | {'yes' if row.get('passed') else 'no'} | "
                     f"{', '.join(row.get('failed_checks') or []) or '—'} |")
    lines += ["", "## By product line", "", "| line | scored | passed | mean |",
              "|---|---|---|---|"]
    for name, row in summary["by_line"].items():
        lines.append(f"| {name} | {row['scored']} | {row['passed']} | {row['mean']} |")
    missing = [b for b in briefs if b["id"] not in {r["brief_id"] for r in scored}]
    if missing:
        lines += ["", "## Declared but unscorable", ""]
        for brief in missing:
            path = (brief.get("reference") or {}).get("path")
            reason = ("no product imagery exists on this machine for this brand"
                      if not path else "the run did not produce this brief")
            lines.append(f"- {brief['id']} ({brief['product_line']}): {reason}")
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Held-out results")
    parser.add_argument("--write", action="store_true")
    ns = parser.parse_args(argv)
    payload = split()
    print(json.dumps(payload["summary"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
