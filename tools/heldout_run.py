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
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
PROOF = ROOT / "state" / "seller" / "heldout_composite_proof.json"
PROOF_FALLBACK = ROOT / "state" / "seller" / "composite_proof.json"

#: Every held-out proof on disk, paired with the brief file that produced it, is published together.
#: One report with one per-mode table beats two reports that each silently cover a single mode.
SOURCES = (
    (PROOF, ROOT / "ty" / "seller_briefs_heldout.json"),
    (ROOT / "state" / "seller" / "heldout_modes_proof.json",
     ROOT / "ty" / "seller_briefs_heldout_modes.json"),
)
BRIEFS = ROOT / "ty" / "seller_briefs_heldout.json"
OUT = ROOT / "state" / "seller" / "heldout_proof.json"
REPORT = ROOT / "reports" / "ty" / f"heldout_{date.today().isoformat()}.md"

#: The three input modes a brief can declare. The published seller claim carries a coverage label
#: naming the modes actually proven; see `mode_coverage`.
MODES = ("prompt_only", "stored_reference", "uploaded_reference")
#: A mode counts as *measured* at ten scored outputs. Below that it is unmeasured, not failed.
MODE_PROVEN_AT = 10


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
    """The capability label, computed from the per-mode counts rather than remembered.

    The label names the modes that actually carry measured outputs. A mode with zero scored outputs
    is **not measured** — it is not "failed", and it must not be silently folded into another mode's
    claim. The previous string said "stored-reference only" while every scored row was
    uploaded-reference and stored-reference had none, which was simply wrong; it is now derived.
    """
    counts = {mode: sum(1 for row in scored if str(row.get("source_mode")) == mode)
              for mode in MODES}
    proven = [mode for mode in MODES if counts[mode] >= MODE_PROVEN_AT]
    unmeasured = [mode for mode in MODES if counts[mode] == 0]
    thin = [mode for mode in MODES if 0 < counts[mode] < MODE_PROVEN_AT]
    if not proven:
        label = "no mode measured"
    elif len(proven) == len(MODES):
        label = "all three modes"
    else:
        label = " and ".join(mode.replace("_", "-") for mode in proven) + " only"
    return {
        "label": label,
        "proven_modes": proven,
        "unmeasured_modes": unmeasured,
        "thin_modes": thin,
        "counts": counts,
        "proven_at": MODE_PROVEN_AT,
        "why": (f"a mode is measured at {MODE_PROVEN_AT}+ scored outputs; "
                + (", ".join(f"{m} {counts[m]}" for m in MODES))),
        "zero_scored": {mode: counts[mode] == 0 for mode in MODES},
    }


def _sources() -> List[tuple]:
    return [(proof, briefs) for proof, briefs in SOURCES if briefs.exists()]


def split(sources: Optional[List[tuple]] = None) -> Dict[str, Any]:
    rows: List[Dict[str, Any]] = []
    declared: List[Dict[str, Any]] = []
    briefs: List[Dict[str, Any]] = []
    labels: List[str] = []
    for proof_path, brief_path in (sources if sources is not None else _sources()):
        proof = (json.loads(proof_path.read_text(encoding="utf-8"))
                 if proof_path.exists() else {"results": []})
        payload = json.loads(brief_path.read_text(encoding="utf-8"))
        file_briefs = payload.get("briefs") or []
        declared.extend(payload.get("declared_unscorable") or [])
        briefs.extend(file_briefs)
        by_id = {b["id"]: b for b in file_briefs}
        try:
            labels.append(str(proof_path.resolve().relative_to(ROOT)))
        except ValueError:
            labels.append(str(proof_path))
        for result in proof.get("results") or []:
            brief_id = str(result.get("brief_id"))
            brief = by_id.get(brief_id)
            if brief is None:
                continue
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
        "declared_unscorable": declared,
        "scored": len(scored),
        "passed": sum(1 for row in scored if row.get("passed")),
        "mean": round(sum(float(row["score"]) for row in scored) / len(scored), 1)
        if scored else None,
        "by_mode": by_mode(scored),
        "mode_coverage": mode_coverage(scored),
        "by_line": {name: {"scored": len(rows_), "passed": sum(1 for r in rows_ if r.get("passed")),
                           "mean": round(sum(float(r["score"]) for r in rows_) / len(rows_), 1)}
                    for name, rows_ in lines.items()},
        "unscored_lines": sorted({str(b.get("product_line")) for b in briefs} - set(lines)),
    }
    payload = {"at": date.today().isoformat(), "proofs": labels,
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
    zero = [mode for mode in summary["by_mode"]
            if mode != "unknown" and coverage["zero_scored"].get(mode)]
    plain = ", ".join(f"**{mode.replace('_', '-')} has 0 scored outputs**" for mode in zero)
    lines += ["", f"**Capability: {coverage['label']}.** "
                  f"prompt-only {coverage['counts']['prompt_only']} scored, "
                  f"stored-reference {coverage['counts']['stored_reference']} scored, "
                  f"uploaded-reference {coverage['counts']['uploaded_reference']} scored — "
                  f"{coverage['why']}.",
                  ("  " + plain + (": that mode is not measured here, which is not the "
                                    "same as failed." if len(zero) == 1 else
                                    ": those modes are not measured here, which is not the "
                                    "same as failed.") if plain else ""), ""]
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
