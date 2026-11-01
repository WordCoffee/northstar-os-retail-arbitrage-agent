"""Register the three small-file Ty tasks and block the superseded large-file ones."""
from __future__ import annotations

import json
from pathlib import Path

REG = Path(__file__).resolve().parents[1] / "config" / "continuous_loop_tasks.json"

NOTE = ("Local-only behavioural fix authorized by the 2026-11-01 Ty autonomy directive. "
        "No auth, payment, browser, credential or external I/O. The acceptance probe is "
        "independent of the implementation and is outside the model's write scope.")

TASKS = [
    {
        "id": "ty-budget-stop",
        "name": "A hard budget stops at the limit",
        "schema_version": 2,
        "authorized": True,
        "authorization_note": NOTE,
        "risk": "low",
        "risk_class": "low",
        "execution": "ty",
        "objective": (
            "Fix Northstar_backend/agent_kernel/budget.py so a hard budget stops AT its "
            "limit. BudgetTracker._check currently compares with > after incrementing, so "
            "max_steps=3 permits a fourth step and max_tokens=100 permits 101 tokens; the "
            "module contract is 'a limit is a stop, not a warning'. Change the step and "
            "token comparisons so reaching the limit sets state.stopped. Keep the wall-clock "
            "check, remaining(), snapshot() and every other behaviour unchanged. "
            "state/probes/t4_budget_stop.py is READ-ONLY: never write it. Run it with "
            "python state/probes/t4_budget_stop.py and repair from its output."),
        "dependencies": [],
        "write_paths": ["Northstar_backend/agent_kernel/budget.py"],
        "read_paths": ["Northstar_backend/agent_kernel/budget.py",
                       "state/probes/t4_budget_stop.py"],
        "checks": [{"name": "budget stop probe", "cwd": ".",
                    "cmd": ["python", "state/probes/t4_budget_stop.py"]}],
        "acceptance_commands": [["python", "state/probes/t4_budget_stop.py"]],
        "commit_paths": ["Northstar_backend/agent_kernel/budget.py"],
        "commit_message": "fix(budget): a hard step or token limit stops at the limit",
        "required_artifact": "Northstar_backend/agent_kernel/budget.py",
        "timeout_seconds": 600,
        "max_repairs": 1,
        "max_steps": 10,
        "model": "qwen2.5-coder:3b",
        "provider": "ollama",
    },
    {
        "id": "ty-hitl-skip-report",
        "name": "Unreadable HITL records are reported, not dropped",
        "schema_version": 2,
        "authorized": True,
        "authorization_note": NOTE,
        "risk": "low",
        "risk_class": "low",
        "execution": "ty",
        "objective": (
            "Fix Northstar_backend/agent_kernel/hitl_counts.py. It silently skips a corrupt "
            "or unreadable hitl_*.json with a bare continue, so an operator sees a smaller "
            "queue than exists with no signal. Count every unreadable record in a new "
            "'skipped' key of the returned dict, keep pending/approved/denied/total exactly "
            "as they are (total remains the number of counted statuses, not files on disk), "
            "and keep the missing-directory behaviour. state/probes/t5_hitl_corrupt.py is "
            "READ-ONLY: never write it. Run it with python state/probes/t5_hitl_corrupt.py "
            "and repair from its output."),
        "dependencies": [],
        "write_paths": ["Northstar_backend/agent_kernel/hitl_counts.py"],
        "read_paths": ["Northstar_backend/agent_kernel/hitl_counts.py",
                       "state/probes/t5_hitl_corrupt.py"],
        "checks": [{"name": "hitl corrupt probe", "cwd": ".",
                    "cmd": ["python", "state/probes/t5_hitl_corrupt.py"]}],
        "acceptance_commands": [["python", "state/probes/t5_hitl_corrupt.py"]],
        "commit_paths": ["Northstar_backend/agent_kernel/hitl_counts.py"],
        "commit_message": "fix(hitl): report unreadable records instead of dropping them",
        "required_artifact": "Northstar_backend/agent_kernel/hitl_counts.py",
        "timeout_seconds": 600,
        "max_repairs": 1,
        "max_steps": 10,
        "model": "qwen2.5-coder:3b",
        "provider": "ollama",
    },
    {
        "id": "ty-diff-select-headers",
        "name": "A selected-hunk diff keeps its file headers",
        "schema_version": 2,
        "authorized": True,
        "authorization_note": NOTE,
        "risk": "low",
        "risk_class": "low",
        "execution": "ty",
        "objective": (
            "Fix Northstar_backend/agent_kernel/diff.py so select_hunks returns a valid diff "
            "instead of a bare fragment. It currently joins only the hunk bodies, dropping "
            "the '--- a/file' and '+++ b/file' header lines, so the selection names no target "
            "file and cannot be applied. Keep the file headers from the input ahead of the "
            "selected hunks, keep the selection order, return an empty string when nothing is "
            "selected, and leave parse_diff/review/stats unchanged. "
            "state/probes/t6_diff_select_headers.py is READ-ONLY: never write it. Run it with "
            "python state/probes/t6_diff_select_headers.py and repair from its output."),
        "dependencies": [],
        "write_paths": ["Northstar_backend/agent_kernel/diff.py"],
        "read_paths": ["Northstar_backend/agent_kernel/diff.py",
                       "state/probes/t6_diff_select_headers.py"],
        "checks": [{"name": "diff header probe", "cwd": ".",
                    "cmd": ["python", "state/probes/t6_diff_select_headers.py"]}],
        "acceptance_commands": [["python", "state/probes/t6_diff_select_headers.py"]],
        "commit_paths": ["Northstar_backend/agent_kernel/diff.py"],
        "commit_message": "fix(diff): a selected-hunk diff keeps its file headers",
        "required_artifact": "Northstar_backend/agent_kernel/diff.py",
        "timeout_seconds": 600,
        "max_repairs": 1,
        "max_steps": 10,
        "model": "qwen2.5-coder:3b",
        "provider": "ollama",
    },
]

SUPERSEDED = {
    "ty-dpi-image-guard": "superseded: the 3B lane rewrites whole files, so a 16 KB module is "
                          "not a fair unit; kept as evidence of the failed attempt",
    "ty-frame-fill-guard": "superseded: same reason (10 KB module)",
    "ty-hero-fill-guard": "superseded: same reason (15 KB module)",
}


def main() -> int:
    data = json.loads(REG.read_text(encoding="utf-8-sig"))
    tasks = data["tasks"]
    ids = {t.get("id") for t in tasks}
    for task in TASKS:
        if task["id"] in ids:
            tasks[:] = [task if t.get("id") == task["id"] else t for t in tasks]
        else:
            tasks.append(task)
    for task in tasks:
        if task.get("id") in SUPERSEDED:
            task["authorized"] = False
            task["blocked"] = SUPERSEDED[task["id"]]
    data["updated_at"] = "2026-11-01"
    REG.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"added": [t["id"] for t in TASKS],
                      "blocked": sorted(SUPERSEDED)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
