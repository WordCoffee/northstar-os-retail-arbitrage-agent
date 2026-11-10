"""Separate *accuracy against ground truth* from *cheapness* in the bake-off result.

The composite score weights accuracy 0.40, detail 0.25, speed 0.15, tokens 0.10, reliability 0.10.
That means 60 % of it is not accuracy. On the hosted target both tools found 7 of 7 ground-truth
facts and craft-anything still won the composite — because it emitted 702 KB instead of 96 MB and
finished in 0.11 s instead of 22.9 s. That is a real result about cost, and it is *not* evidence
that craft-anything produces a better behaviour spec.

So the verdict is published twice: the composite winner, and the **accuracy leader** — the tool
that surfaced more of the declared ground truth, with ties stated as ties. Where the two disagree,
the disagreement is the headline, not a footnote.

    python tools/bakeoff_accuracy.py --run
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "ty" / "bakeoff_results.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def verdict(payload: Dict[str, Any]) -> Dict[str, Any]:
    rows: List[Dict[str, Any]] = []
    for target in payload.get("targets") or []:
        cells = [cell for cell in target.get("cells") or [] if cell.get("status") == "ran"]
        if not cells:
            rows.append({"target": target["target"]["id"], "accuracy_leader": None,
                         "composite_leader": None, "disagree": False,
                         "reason": "no cell ran"})
            continue
        best_accuracy = max(float(cell.get("accuracy") or 0.0) for cell in cells)
        accuracy_leaders = [cell["tool"] for cell in cells
                            if abs(float(cell.get("accuracy") or 0.0) - best_accuracy) < 1e-9]
        composite_leader = target.get("decision", {}).get("default")
        disagree = bool(composite_leader and composite_leader not in accuracy_leaders)
        facts = {cell["tool"]: f"{cell.get('facts_found')}/{cell.get('facts_total')}"
                 for cell in cells}
        if not disagree:
            why = ""
        elif len(accuracy_leaders) == 1:
            leader_facts = facts.get(accuracy_leaders[0])
            winner_facts = facts.get(composite_leader)
            why = (f"the composite winner is cheaper, not more accurate: "
                   f"{accuracy_leaders[0]} surfaced {leader_facts} of the declared ground truth "
                   f"against {composite_leader}'s {winner_facts}")
        else:
            why = ("the composite winner is cheaper at the same accuracy — the ground truth was "
                   "tied, so the win is entirely cost")
        rows.append({
            "target": target["target"]["id"],
            "accuracy_leader": accuracy_leaders[0] if len(accuracy_leaders) == 1 else "tie",
            "accuracy_leaders": accuracy_leaders,
            "accuracy": round(best_accuracy, 3),
            "facts": facts,
            "composite_leader": composite_leader,
            "disagree": disagree,
            "why": why,
        })
    return {"at": _now(), "weights": payload.get("weights"), "targets": rows,
            "ground_truth": "each target declares a facts list read off the target itself; "
                            "accuracy = fraction of those facts the tool's own output names",
            "composite_note": "accuracy is 0.40 of the composite; detail, speed and tokens make up "
                              "the other 0.45 and reliability 0.10, so a composite win can come "
                              "entirely from cost"}


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Accuracy-first bake-off verdict")
    parser.add_argument("--run", action="store_true")
    ns = parser.parse_args(argv)
    payload = json.loads(RESULTS.read_text(encoding="utf-8"))
    result = verdict(payload)
    if ns.run:
        payload["accuracy_verdict"] = result
        RESULTS.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
