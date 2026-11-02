"""Freeze the suppression-phrase contract (creative quality unit)."""
from __future__ import annotations

import json
from pathlib import Path

REG = Path(__file__).resolve().parents[1] / "config" / "continuous_loop_tasks.json"

TASK = {
    "id": "ty-suppression-subject",
    "name": "The text suppressor must not choose the subject",
    "schema_version": 2,
    "authorized": True,
    "authorization_note": (
        "Local-only creative-quality fix from the 2026-11-02 simple-mode campaign. No "
        "auth, tenancy, billing, security, provider or external I/O; the probe is "
        "read-only and outside the author's write scope."),
    "risk": "low",
    "risk_class": "low",
    "execution": "ty",
    "contract_version": 1,
    "objective": (
        "Northstar_backend/text_fidelity.py has one behavioural defect with a visible "
        "consequence: every text-safe render appends SUPPRESSION_PHRASE to the brief, and "
        "that constant ends with 'botanical illustration only', so a product-pouch brief is "
        "rendered as a herbarium drawing (observed live: a 6 oz pouch request returned a "
        "botanical plate). Read the file and fix SUPPRESSION_PHRASE so it still forbids "
        "lettering, words, typography, logos, barcodes, QR codes, captions and watermarks, "
        "but no longer names a subject or medium. Do not change the sanitizer's rules, the "
        "router, or anything else in the file. The read-only probe "
        "state/probes/t10_suppression_phrase.py is the contract - run it to check your "
        "change; if it fails, edit the source file - never the probe. Change only that file."),
    "write_paths": ["Northstar_backend/text_fidelity.py"],
    "read_paths": ["Northstar_backend/text_fidelity.py",
                   "state/probes/t10_suppression_phrase.py"],
    "checks": [{"name": "suppression phrase probe", "cwd": ".",
                "cmd": ["python", "state/probes/t10_suppression_phrase.py"]}],
    "acceptance_commands": [["python", "state/probes/t10_suppression_phrase.py"]],
    "commit_paths": ["Northstar_backend/text_fidelity.py"],
    "commit_message": "fix(text-fidelity): the suppressor forbids lettering, not a subject",
    "required_artifact": "Northstar_backend/text_fidelity.py",
    "timeout_seconds": 600,
    "max_repairs": 1,
    "max_steps": 8,
    "model": "qwen3.5:4b",
    "provider": "ollama",
    "num_ctx": 8192,
    "native_tools": True,
    "allowed_tools": ["read", "ast_edit", "run", "finish"],
    "author_lane": "opencode-go/deepseek-v4.1-flash (unattended CLI)",
}

data = json.loads(REG.read_text(encoding="utf-8-sig"))
tasks = [t for t in data["tasks"] if t.get("id") != TASK["id"]]
tasks.append(TASK)
data["tasks"] = tasks
data["updated_at"] = "2026-11-02"
REG.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"frozen": TASK["id"]}, indent=2))
