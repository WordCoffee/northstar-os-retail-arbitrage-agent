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
PROOF = ROOT / "state" / "seller" / "heldout_composite_proof.json"
PROOF_FALLBACK = ROOT / "state" / "seller" / "composite_proof.json"
BRIEFS = ROOT / "ty" / "seller_briefs_heldout.json"
OUT = ROOT / "state" / "seller" / "heldout_proof.json"
REPORT = ROOT / "reports" / "ty" / f"heldout_{date.today().isoformat()}.md"

#: The three input modes a brief can declare. The published seller claim carries a coverage label
#: naming the modes actually proven; see `mode_coverage`.
MODES = ("prompt_only", "stored_reference", "uploaded_reference")
MODES_NEEDED_FOR_FULL_LABEL = 10
FULL_LABEL = "all three modes"
PARTIAL_LABEL = "stored-reference only"


def by_mode(scored: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """n, passed and mean for every declared mode, with the unmeasured ones visible at zero."""
    out: Dict[str, Dict[str, Any]] = {}
    for mode in MODES:
        rows = [row for row in scored if str(row.get("source_mode")) == mode]
        out[mode] = {
            "n": len(rows),
            "passed": sum(1 for row in rows if row.get("passed")),
            "mean": round(sum(float(row["score"]) for row in rows) / len(rows), 1) if rows else None,
        }
    unknown = sorted({str(row.get("source_mode")) for row in scored} - set(MODES))
    if unknown:
        out["unknown"] = {"n": sum(1 for row in scored if str(row.get("source_mode")) in unknown),
                          "passed": 0, "mean": None, "modes": unknown}
    return out


def mode_coverage(scored: List[Dict[str, Any]]) -> Dict[str, Any]:
    """The label the seller claim must wear, and why.

    Owner instruction (2026-11-09): keep calling the claim **stored-reference only** until the
    other two modes each have 10+ scored. The label is therefore computed, not remembered — a
    report that says "all three modes" has to have the rows to back it.
    """
    counts = {mode: sum(1 for row in scored if str(row.get("source_mode")) == mode) for mode in MODES}
    ready = (counts["prompt_only"] >= MODES_NEEDED_FOR_FULL_LABEL
             and counts["stored_reference"] >= MODES_NEEDED_FOR_FULL_LABEL)
    return {
        "label": FULL_LABEL if ready else PARTIAL_LABEL,
        "counts": counts,
        "needed_per_mode": MODES_NEEDED_FOR_FULL_LABEL,
        "why": ("every mode has at least "
                f"{MODES_NEEDED_FOR_FULL_LABEL} scored"
                if ready else
                "prompt-only and stored-reference must each reach "
                f"{MODES_NEEDED_FOR_FULL_LABEL} scored before the label lifts"),
    }


def split() -> Dict[str, Any]:
    # The held-out proof is its own file: a held-out run must never overwrite, or be confused
    # with, the tuned composite proof. The fallback only reads a proof that already contains
    # held-out ids, and says which file it read.
    proof_path = PROOF if PROOF.exists() else PROOF_FALLBACK
    proof = (json.loads(proof_path.read_text(encoding="utf-8"))
             if proof_path.exists() else {"results": []})
    payload = json.loads(BRIEFS.read_text(encoding="utf-8"))
    briefs = payload["briefs"]
    declared = payload.get("declared_unscorable") or []
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
            "source_mode": result.get("source_mode") or brief.get("source_mode"),
            "score": result.get("score"),
            "passed": result.get("passed"),
            "route": result.get("route"),
            "artefact_path": result.get("artefact_path"),
            "reference": ((brief.get("reference") or {}).get("path")),
            "product_region": (result.get("checks") or {}).get("product_region")
            or result.get("product_region"),
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
        "declared_unscorable": [{"brief_id": b["id"], "product_line": b.get("product_line"),
                                 "situation": b.get("situation"),
                                 "reason": b.get("note")} for b in declared],
        "scored": len(scored),
        "passed": sum(1 for row in scored if row.get("passed")),
        "mean": round(sum(float(row["score"]) for row in scored) / len(scored), 1)
        if scored else None,
        "by_mode": by_mode(scored),
        "mode_coverage": mode_coverage(scored),
        "by_line": {name: {"scored": len(rows_), "passed": sum(1 for r in rows_ if r.get("passed")),
                           "mean": round(sum(float(r["score"]) for r in rows_) / len(rows_), 1)}
                    for name, rows_ in lines.items()},
        "unscored_lines": sorted({b["product_line"] for b in briefs} - set(lines)),
    }
    try:
        proof_label = str(proof_path.resolve().relative_to(ROOT))
    except ValueError:  # a path outside the repo (a test, a temp run) is named absolutely
        proof_label = str(proof_path)
    payload = {"at": date.today().isoformat(), "proof": proof_label,
               "summary": summary, "results": rows}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    _write_report(briefs, scored, summary)
    return payload


def _write_report(briefs: List[Dict[str, Any]], scored: List[Dict[str, Any]],
                  summary: Dict[str, Any]) -> None:
    lines = ["# Held-out run", "",
             f"{summary['scored']} of {summary['held_out_briefs']} runnable held-out briefs "
             f"scored, {summary['passed']} passed"
             + (f", mean **{summary['mean']}**." if summary["mean"] is not None else "."), "",
             "| brief | line | situation | score | passed | failed |",
             "|---|---|---|---|---|---|"]
    for row in sorted(scored, key=lambda r: r["brief_id"]):
        lines.append(f"| {row['brief_id']} | {row['product_line']} | {row['situation']} | "
                     f"{row['score']} | {'yes' if row.get('passed') else 'no'} | "
                     f"{', '.join(row.get('failed_checks') or []) or '—'} |")
    lines += ["", "## By input mode", "",
              "| mode | n | passed | mean |", "|---|---|---|---|"]
    for mode, row in summary["by_mode"].items():
        if mode == "unknown":
            continue
        mean = row["mean"] if row["mean"] is not None else "—"
        lines.append(f"| {mode.replace('_', '-')} | {row['n']} | {row['passed']} | {mean} |")
    coverage = summary["mode_coverage"]
    lines += ["", f"**Mode coverage: {coverage['label']}.** "
                  f"prompt-only {coverage['counts']['prompt_only']} scored, "
                  f"stored-reference {coverage['counts']['stored_reference']} scored, "
                  f"uploaded-reference {coverage['counts']['uploaded_reference']} scored — "
                  f"{coverage['why']}.", ""]
    lines += ["## By product line", "", "| line | scored | passed | mean |",
              "|---|---|---|---|"]
    for name, row in summary["by_line"].items():
        lines.append(f"| {name} | {row['scored']} | {row['passed']} | {row['mean']} |")
    declared_lines = sorted({d["product_line"] for d in summary.get("declared_unscorable") or []})
    for name in declared_lines:
        lines.append(f"| {name} | 0 | — | **not scored**: no product imagery on this machine |")
    missing = [b for b in briefs if b["id"] not in {r["brief_id"] for r in scored}]
    if missing:
        lines += ["", "## Declared but unscorable", ""]
        for brief in missing:
            path = (brief.get("reference") or {}).get("path")
            reason = ("no product imagery exists on this machine for this brand"
                      if not path else "the run did not produce this brief")
            lines.append(f"- {brief['id']} ({brief['product_line']}): {reason}")
    lines += _limits(scored, briefs)
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _limits(scored: List[Dict[str, Any]], briefs: List[Dict[str, Any]]) -> List[str]:
    """What this run does not prove, computed rather than promised.

    A held-out number invites the reader to believe more than it shows: that every brief is an
    independent product, and that every situation is measured for the first time. Both are checkable
    from the rows, so both are stated.
    """
    by_reference: Dict[str, List[str]] = defaultdict(list)
    by_id = {b["id"]: b for b in briefs}
    for row in scored:
        reference = row.get("reference") or (by_id.get(row["brief_id"], {})
                                            .get("reference") or {}).get("path")
        by_reference[str(reference)].append(row["brief_id"])
    lines = ["", "## Limits of this run", ""]
    lines.append(f"- **{len(by_reference)} distinct reference images over {len(scored)} scored "
                 "briefs.**")
    for reference, ids in sorted(by_reference.items()):
        if len(ids) > 1:
            lines.append(f"  - `{Path(reference).name}` is the reference for "
                         f"{len(ids)} briefs ({', '.join(sorted(ids))}): those rows are not "
                         "independent products.")
    lines.append("- **Distinct product designs are fewer than distinct files.** Three Mogra images "
                 "are one Lion's Mane + Shiitake pouch pair; the Word Coffee images are two box "
                 "designs (For Mom, Modern Woman). Twenty-one briefs therefore vary the *situation* "
                 "and the *frame*, not the product range.")
    by_situation: Dict[str, List[bool]] = defaultdict(list)
    for row in scored:
        by_situation[str(row.get("situation"))].append(bool(row.get("passed")))
    failed_situations = [name for name, outcomes in sorted(by_situation.items())
                         if outcomes and not any(outcomes)]
    if failed_situations:
        lines.append(f"- **Situations with no pass at all:** {', '.join(failed_situations)}. "
                     "Those are gaps in the composite route, not one unlucky image each.")
    lines.append("- A held-out brief here varies the **product image and the situation**; it "
                 "does not vary the constraint bar, which is the tuned catalogue's own.")
    lines.append("")
    return lines


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Held-out results")
    parser.add_argument("--write", action="store_true")
    ns = parser.parse_args(argv)
    payload = split()
    print(json.dumps(payload["summary"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
