"""Freeze the qualification queue: one control repair is blocked, three app tasks stay.

Run once; idempotent. The worker's own budget controls are NOT a model task - a
live worker must never rewrite the limits that judge it. That repair is trusted
bootstrap maintenance and lives outside the model's write scope.
"""
from __future__ import annotations

import json
from pathlib import Path

REG = Path(__file__).resolve().parents[1] / "config" / "continuous_loop_tasks.json"

PROFILE = {
    "model": "qwen2.5-coder:3b",
    "provider": "ollama",
    "num_ctx": 8192,
    "max_steps": 8,
    "max_protocol_errors": 6,
    "allowed_tools": ["read", "ast_edit", "run", "finish"],
}

BLOCKED = {
    "ty-budget-stop": (
        "blocked: self-modification. budget.py is the worker's own step/time/token "
        "control, so a live worker must not rewrite the limits that judge its task. "
        "The off-by-one was repaired as trusted bootstrap maintenance "
        "(Northstar_backend/agent_kernel/budget.py, test_budget_limits.py, "
        "state/probes/t4_budget_stop.py); it does not count as a model-authored fix."),
    "ty-dpi-image-guard": "superseded: 16 KB module; replaced by the smaller app tasks",
    "ty-frame-fill-guard": "superseded: 10 KB module; replaced by the smaller app tasks",
    "ty-hero-fill-guard": "superseded: 15 KB module; replaced by the smaller app tasks",
}

APP_TASKS = [
    {
        "id": "ty-artifact-jpeg",
        "name": "A JPEG artifact is classified as an image",
        "schema_version": 2,
        "authorized": True,
        "authorization_note": (
            "Local-only behavioural fix authorized by the 2026-11-01 repair directive. "
            "No auth, tenancy, billing, security, provider or external I/O. The probe is "
            "read-only and outside the model's write scope."),
        "risk": "low",
        "risk_class": "low",
        "execution": "ty",
        "objective": (
            "Northstar_backend/agent_kernel/artifacts.py has one behavioural defect: "
            "artifact_kind recognises PNG and MP4 by magic bytes but has no JPEG branch, "
            "so a valid .jpg is labelled 'binary' and the evidence cannot tell a rendered "
            "module from an opaque blob. Read the file and fix artifact_kind so a JPEG "
            "(magic FF D8 FF ... FF D9) is 'image_jpeg' and a .jpg with wrong magic is "
            "'jpeg_invalid'; leave every other kind unchanged. The read-only probe "
            "state/probes/t7_artifact_jpeg.py is the contract - run it and repair from its "
            "output. Change only that file."),
        "dependencies": [],
        "write_paths": ["Northstar_backend/agent_kernel/artifacts.py"],
        "read_paths": ["Northstar_backend/agent_kernel/artifacts.py",
                       "state/probes/t7_artifact_jpeg.py"],
        "checks": [{"name": "jpeg artifact probe", "cwd": ".",
                    "cmd": ["python", "state/probes/t7_artifact_jpeg.py"]}],
        "acceptance_commands": [["python", "state/probes/t7_artifact_jpeg.py"]],
        "commit_paths": ["Northstar_backend/agent_kernel/artifacts.py"],
        "commit_message": "fix(artifacts): classify a JPEG artifact as an image",
        "required_artifact": "Northstar_backend/agent_kernel/artifacts.py",
        "timeout_seconds": 600,
        "max_repairs": 1,
        **PROFILE,
    },
    {
        "id": "ty-hitl-skip-report",
        "name": "Unreadable HITL records are reported, not dropped",
        "schema_version": 2,
        "authorized": True,
        "authorization_note": (
            "Local-only behavioural fix authorized by the 2026-11-01 repair directive. "
            "The probe is read-only and outside the model's write scope."),
        "risk": "low",
        "risk_class": "low",
        "execution": "ty",
        "objective": (
            "Northstar_backend/agent_kernel/hitl_counts.py silently skips a corrupt or "
            "unreadable hitl_*.json with a bare continue, so an operator sees a smaller "
            "queue than exists with no signal. Read the file and fix hitl_counts so every "
            "unreadable record is counted in a new 'skipped' key, while pending/approved/"
            "denied/total keep their meaning (total is the number of counted statuses, not "
            "files on disk) and the missing-directory behaviour is unchanged. The read-only "
            "probe state/probes/t5_hitl_corrupt.py is the contract - run it and repair from "
            "its output. Change only that file."),
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
        **PROFILE,
    },
    {
        "id": "ty-diff-select-headers",
        "name": "A selected-hunk diff keeps its file headers",
        "schema_version": 2,
        "authorized": True,
        "authorization_note": (
            "Local-only behavioural fix authorized by the 2026-11-01 repair directive. "
            "The probe is read-only and outside the model's write scope."),
        "risk": "low",
        "risk_class": "low",
        "execution": "ty",
        "objective": (
            "Northstar_backend/agent_kernel/diff.py has one behavioural defect: "
            "select_hunks joins only the hunk bodies and drops the '--- a/file' and "
            "'+++ b/file' header lines, so a selected-hunk diff names no target file and "
            "cannot be applied. Read the file and fix select_hunks so the file headers from "
            "the input stay ahead of the selected hunks, the selection order is kept, an "
            "empty selection returns an empty string, and parse_diff/review/stats are "
            "unchanged. The read-only probe state/probes/t6_diff_select_headers.py is the "
            "contract - run it and repair from its output. Change only that file."),
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
        **PROFILE,
    },
]


def main() -> int:
    data = json.loads(REG.read_text(encoding="utf-8-sig"))
    tasks = data["tasks"]
    ids = {t.get("id") for t in tasks}
    for task in APP_TASKS:
        if task["id"] in ids:
            tasks[:] = [task if t.get("id") == task["id"] else t for t in tasks]
        else:
            tasks.append(task)
    for task in tasks:
        if task.get("id") in BLOCKED:
            task["authorized"] = False
            task["blocked"] = BLOCKED[task["id"]]
    data["updated_at"] = "2026-11-01"
    data["notes"] = ("Qualification queue frozen 2026-11-01: three app-level tasks "
                     "(artifact JPEG, HITL corrupt records, diff headers). The worker's own "
                     "budget control is bootstrap maintenance, not a model task.")
    REG.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"app_tasks": [t["id"] for t in APP_TASKS],
                      "blocked": sorted(BLOCKED)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
