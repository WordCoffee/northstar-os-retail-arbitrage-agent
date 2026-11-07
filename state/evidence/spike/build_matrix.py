"""Assemble the spike matrix from the stored candidate evidence.

    python state/evidence/spike/build_matrix.py

Reads every `*/cand*/verdict.json`, re-checks the semantic properties the plan
asks for (diff shape via agent_kernel.content.validate_patch, and that the diff
touches the module the problem lives in), and writes:

  * state/evidence/spike/matrix.json   - the machine-readable matrix
  * state/evidence/spike/matrix.md     - the table used in the report

`solved` is deliberately conservative:
    acceptance gate passed  AND  targeted test file green  AND  the candidate
    produced a non-empty diff  AND  that diff touched the module the problem is
    in  AND  the diff parses as a unified patch.

Nothing here re-runs a model.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

SPIKE = Path(__file__).resolve().parent
ROOT = SPIKE.parents[2]
sys.path.insert(0, str(ROOT / "Northstar_backend"))
sys.path.insert(0, str(SPIKE / "harness"))

from cases import CASES  # noqa: E402

ORDER = ("S1", "S2", "S3", "S4", "S5")


def _patch_valid(diff_path: Path) -> dict:
    if not diff_path.is_file() or not diff_path.read_text(encoding="utf-8").strip():
        return {"valid": False, "detail": "no diff"}
    try:
        from agent_kernel import content

        return content.validate_patch(diff_path)
    except Exception as exc:  # noqa: BLE001 - a validator that raises refuses
        return {"valid": False, "detail": f"{type(exc).__name__}: {exc}"}


def main() -> int:
    rows = []
    for case_id in ORDER:
        slug = CASES[case_id]["slug"]
        for cand_dir in sorted((SPIKE / slug).glob("cand*")):
            verdict_path = cand_dir / "verdict.json"
            if not verdict_path.is_file():
                continue
            v = json.loads(verdict_path.read_text(encoding="utf-8"))
            diff_text = (cand_dir / "candidate.diff").read_text(encoding="utf-8") \
                if (cand_dir / "candidate.diff").is_file() else ""
            added = "\n".join(ln[1:] for ln in diff_text.splitlines()
                              if ln.startswith("+") and not ln.startswith("+++"))
            patch = _patch_valid(cand_dir / "candidate.diff")
            row = {
                "case": case_id,
                "slug": slug,
                "candidate": cand_dir.name,
                "model": v.get("model"),
                "agent_exit": v.get("agent_exit"),
                "timed_out": v.get("agent_timed_out"),
                "steps": v.get("agent_steps"),
                "protocol_errors": v.get("protocol_errors"),
                "scope_rejections": v.get("scope_rejections"),
                "diff_bytes": v.get("diff_bytes"),
                "touches_module": bool(v.get("diff_touches_target_module")),
                "gate_exit": v.get("gate_exit"),
                "targeted_test_exit": v.get("targeted_test_exit"),
                "claimed_ok": v.get("claimed_ok"),
                "patch_valid": bool(patch.get("valid")),
                "patch_detail": patch.get("detail"),
                "solved": bool(v.get("gate_exit") == 0
                               and v.get("targeted_test_exit") == 0
                               and v.get("diff_bytes")
                               and v.get("diff_touches_target_module")
                               and patch.get("valid")),
            }
            if case_id == "S1":
                # S1's behavioural gate is statistically weak (see the report):
                # record whether the diff at least touches cancellation logic, so
                # a flaky pass with an unrelated edit cannot look like a fix.
                row["mentions_cancel"] = bool(re.search(r"cancel", added, re.I))
            rows.append(row)

    per_case = {}
    for case_id in ORDER:
        mine = [r for r in rows if r["case"] == case_id
                and r["candidate"].startswith("cand")
                and "dryrun" not in r["candidate"]
                and not r["candidate"].endswith("b")]
        armb = [r for r in rows if r["case"] == case_id
                and r["candidate"].startswith("cand") and r["candidate"].endswith("b")]
        per_case[case_id] = {
            "candidates": len(mine),
            "solved": sum(1 for r in mine if r["solved"]),
            "gate_passes": sum(1 for r in mine if r["gate_exit"] == 0),
            "diffs": sum(1 for r in mine if (r["diff_bytes"] or 0) > 0),
            "arm_b_candidates": len(armb),
            "arm_b_diffs": sum(1 for r in armb if (r["diff_bytes"] or 0) > 0),
            "arm_b_solved": sum(1 for r in armb if r["solved"]),
        }
    solved_cases = [c for c in ORDER if per_case[c]["solved"] > 0]
    payload = {"model": rows[0]["model"] if rows else None,
               "cases": per_case,
               "solved_cases": solved_cases,
               "solved_case_count": len(solved_cases),
               "candidates_run": len([r for r in rows if "dryrun" not in r["candidate"]
                                      and not r["candidate"].endswith("b")]),
               "arm_b_run": len([r for r in rows
                                 if r["candidate"].endswith("b")]),
               "rows": rows}
    (SPIKE / "matrix.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")

    lines = ["| # | Problem | cand 1 | cand 2 | cand 3 | solved |",
             "|---|---|---|---|---|---|"]
    for case_id in ORDER:
        cells = []
        for cand in ("cand1", "cand2", "cand3"):
            row = next((r for r in rows if r["case"] == case_id
                        and r["candidate"] == cand), None)
            if row is None:
                cells.append("—")
            elif row["solved"]:
                cells.append("**solved**")
            elif row["gate_exit"] == 0:
                cells.append("gate pass, no patch")
            elif (row["diff_bytes"] or 0) > 0:
                cells.append("patched, gate red")
            else:
                cells.append("no patch")
        lines.append(f"| {case_id} | {CASES[case_id]['problem'][:60]}… | "
                     + " | ".join(cells) + f" | {per_case[case_id]['solved']}/3 |")
    (SPIKE / "matrix.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"per_case": per_case, "solved_cases": solved_cases,
                      "candidates_run": payload["candidates_run"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
