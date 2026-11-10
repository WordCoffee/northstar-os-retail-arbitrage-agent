"""Per-check failure table for the prompt-only held-out briefs.

A mean hides which rule failed. Twelve briefs at 0 passed could be one broken check or twelve
different ones, and the difference decides what to fix. This reads the proof rows and prints, per
check, how many of the twelve failed it — with the actual detail string, so the reason is visible
rather than inferred.

    python tools/prompt_only_checks.py            # writes reports/ty/prompt_only_checks.md
"""
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
PROOF = ROOT / "state" / "seller" / "heldout_prompt_only_proof2.json"
REPORT = ROOT / "reports" / "ty" / "prompt_only_checks.md"
CHECKS = ("dimensions", "aspect", "background", "subject_fill", "alpha_matte", "file_size",
          "text_free", "reference_subject", "product_region")


def rows() -> List[Dict[str, Any]]:
    proof = json.loads(PROOF.read_text(encoding="utf-8"))
    return [row for row in proof.get("results") or [] if row.get("score") is not None]


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Per-check failures for prompt-only briefs")
    parser.add_argument("--json", action="store_true")
    ns = parser.parse_args(argv)

    data = rows()
    failures: Counter = Counter()
    skipped: Counter = Counter()
    details: Dict[str, Counter] = defaultdict(Counter)
    for row in data:
        for name, check in (row.get("checks") or {}).items():
            if check.get("skipped"):
                skipped[name] += 1
                continue
            if check.get("ok"):
                continue
            failures[name] += 1
            detail = str(check.get("detail") or "")
            # keep the first clause: the numbers vary per brief, the rule does not
            head = detail.split(" vs ")[0].split(";")[0][:70]
            details[name][head] += 1

    total = len(data)
    summary = {"briefs": total,
               "passed": sum(1 for row in data if row.get("passed")),
               "mean": round(sum(float(row["score"]) for row in data) / total, 1) if total else None,
               "failures": dict(failures),
               "skipped": dict(skipped)}

    lines = ["# Prompt-only: which check actually failed", "",
             f"{summary['briefs']} briefs, {summary['passed']} passed, mean **{summary['mean']}**. "
             "A mean of 34.5 could be one broken rule or twelve; this is the breakdown.", "",
             "| check | failed in | of briefs | skipped | most common reason |",
             "|---|---|---|---|---|"]
    for name in CHECKS:
        if not failures[name] and not skipped[name]:
            continue
        reason = ""
        if details[name]:
            reason = details[name].most_common(1)[0][0]
        lines.append(f"| `{name}` | **{failures[name]}** | {total} | {skipped[name]} | {reason} |")
    lines += ["", "## Per brief", "", "| brief | score | failed checks |", "|---|---|---|"]
    for row in sorted(data, key=lambda r: str(r.get("brief_id"))):
        failed = ", ".join(row.get("failed_checks") or []) or "—"
        lines.append(f"| {row.get('brief_id')} | {row.get('score')} | {failed} |")
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")

    if ns.json:
        print(json.dumps(summary, indent=2))
    else:
        print(json.dumps(summary, indent=2))
        print("report:", REPORT.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
