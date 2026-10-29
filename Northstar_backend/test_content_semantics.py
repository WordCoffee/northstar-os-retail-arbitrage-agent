"""Semantic content checks and kernel-side acceptance derivation.

Two things are covered here:

* **Semantic validators** (`agent_kernel.content`). A keyword match is not a
  finished artifact: a stub with TODOs left, a hunk header that disagrees with
  its body, or a JSON document missing the keys the brief requires must fail.
* **Acceptance derivation** (`agent_kernel.tys_adapter._derive_acceptance`). A
  work order that declares `params.acceptance = {commands, required_files}` must
  give the *kernel* observable assertions, not a single `executor_ok` row — the
  lane grading itself is the p01 defect at the kernel level.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from agent_kernel import content as cv
from agent_kernel.tys_adapter import _derive_acceptance

GOOD_PATCH = """\
--- a/calc.py
+++ b/calc.py
@@ -1,2 +1,2 @@
 def add(a, b):
-    return a - b
+    return a + b
"""

# The measured failure from the 2026-10-29 kernel run: the header says 7 lines,
# the body carries 8. `---`, `+++` and `@@` are all present.
MISCOUNTED_PATCH = """\
--- a/calc.py
+++ b/calc.py
@@ -1,7 +1,7 @@
 \"\"\"Tiny arithmetic helpers.\"\"\"

 def add(a, b):
-    return a - b
+    return a + b


 def subtract(a, b):
     return add(a, -b)
"""


def _write(tmp_path: Path, name: str, text: str) -> Path:
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return p


# ── patch arithmetic ────────────────────────────────────────────────────────

def test_correct_patch_passes(tmp_path):
    result = cv.validate_patch(_write(tmp_path, "fix.patch", GOOD_PATCH))
    assert result["valid"] is True
    assert result["checks"]["semantics"]["hunks"] == 1


def test_hunk_header_must_match_its_body(tmp_path):
    result = cv.validate_patch(_write(tmp_path, "fix.patch", MISCOUNTED_PATCH))
    assert result["valid"] is False
    bad = result["checks"]["semantics"]["bad_hunks"]
    assert bad and bad[0]["old"] == [8, 7] and bad[0]["new"] == [8, 7]


def test_a_patch_without_hunks_is_rejected(tmp_path):
    result = cv.validate_patch(_write(tmp_path, "fix.patch", "--- a/x\n+++ b/x\n"))
    assert result["valid"] is False


# ── text structure ──────────────────────────────────────────────────────────

def test_a_stub_with_a_todo_is_not_finished(tmp_path):
    brief = {"semantics": {"min_sentences": 3}}
    path = _write(tmp_path, "runbook.md",
                  "# Runbook\n\nTODO: name the host and set the expiry.\n")
    result = cv.validate_text(path, ["host"], 20, brief)
    assert result["valid"] is False
    assert result["checks"]["semantics"]["placeholders"] == ["TODO"]


def test_a_finished_runbook_passes(tmp_path):
    brief = {"semantics": {"min_sentences": 3, "required_headings": ["Host", "Grant"]}}
    path = _write(tmp_path, "runbook.md",
                  "# Runbook\n\n## Host\npricing.example.com is the only host.\n\n"
                  "## Grant\nread_only, with the expiry 24 hours out. Nothing else "
                  "may run.\n")
    result = cv.validate_text(path, ["host", "expiry"], 20, brief)
    assert result["valid"] is True
    assert result["checks"]["semantics"]["has_headings"] is True


def test_missing_required_heading_fails(tmp_path):
    brief = {"semantics": {"min_sentences": 1, "required_headings": ["Gate"]}}
    path = _write(tmp_path, "campaign.md", "# Campaign\n\nTwo lanes run in order.\n")
    assert cv.validate_text(path, [], 10, brief)["valid"] is False


# ── json structure ──────────────────────────────────────────────────────────

def test_json_with_the_required_keys_passes(tmp_path):
    brief = {"semantics": {"required_keys": ["run_id", "status"]}}
    path = _write(tmp_path, "resume.json",
                  json.dumps({"run_id": "r1", "status": "blocked"}))
    assert cv.validate_json(path, brief)["valid"] is True


def test_json_missing_a_required_key_fails(tmp_path):
    brief = {"semantics": {"required_keys": ["run_id", "status"]}}
    path = _write(tmp_path, "resume.json", json.dumps({"run_id": "r1"}))
    result = cv.validate_json(path, brief)
    assert result["valid"] is False
    assert result["checks"]["semantics"]["present"]["status"] is False


# ── an unchanged stub is not work ───────────────────────────────────────────

def test_artifact_identical_to_the_seed_is_rejected(tmp_path):
    stub = ("# Campaign\n\nLane 1 inspects the local fixtures and names the one fact "
            "that is still missing. Lane 2 browses a single host under a read-only "
            "grant. The gate stops the run until an operator approves it.\n")
    seed_dir = tmp_path / "seed"
    (seed_dir / "p16").mkdir(parents=True)
    (seed_dir / "p16" / "campaign.md").write_text(stub, encoding="utf-8")
    run_dir = tmp_path / "run"
    (run_dir / "p16").mkdir(parents=True)
    (run_dir / "p16" / "campaign.md").write_text(stub, encoding="utf-8")

    brief = {"id": "p16", "artifact": "campaign.md", "validator": "text",
             "terms": ["gate"], "semantics": {"min_sentences": 2}}
    # The stub satisfies every content check on its own; only the seed rule stops it.
    assert cv.validate_brief(run_dir, brief)["valid"] is True
    result = cv.validate_brief(run_dir, brief, seed_dir=seed_dir)
    assert result["valid"] is False
    assert "byte-identical" in result["detail"]


# ── kernel acceptance derives from the workspace, not the lane ──────────────

def test_acceptance_is_derived_from_the_workspace_spec(tmp_path):
    step = {"lane": "coding", "objective": "do the thing",
            "params": {"acceptance": {"required_files": ["fix.patch"],
                                      "commands": [["python", "-m", "pytest", "-q"]]}}}
    rows = _derive_acceptance(step, {"workspace": str(tmp_path)})
    verifiers = [a.verifier for a in rows]
    assert "artifact_exists" in verifiers and "command" in verifiers
    assert "executor_ok" not in verifiers
    artifact = next(a for a in rows if a.verifier == "artifact_exists")
    assert artifact.params["path"].endswith("fix.patch")


def test_a_step_without_a_spec_falls_back_to_the_self_report():
    assert _derive_acceptance({"lane": "coding"}, {}) == []


def test_command_acceptance_runs_in_the_workspace(tmp_path):
    (tmp_path / "ok.txt").write_text("x", encoding="utf-8")
    step = {"lane": "coding",
            "params": {"acceptance": {"commands": [["python", "-c",
                                                    "print('ran')"]]}}}
    rows = _derive_acceptance(step, {"workspace": str(tmp_path)})
    assert rows[0].params["cwd"] == str(tmp_path)
    assert rows[0].params["expect_exit"] == 0
