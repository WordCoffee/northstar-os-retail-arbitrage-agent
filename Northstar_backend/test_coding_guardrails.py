"""p01 acceptance-recovery and p03 bounded-write guards.

Two defects, one file, because they were found together:

* **p01** — a bounded loop that wrote the artifact and passed the checks could
  still be reported `needs_human` because it stopped without calling `finish`
  (step budget, or a model that forgot). Acceptance is the authority; the stop
  reason is not.
* **p03** — a write that stalls hangs the run with no observation to repair from.
  Writes are now atomic (temp → fsync → replace) and bounded in time, and a
  stalled write is reported as a tool error.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from agent_kernel import Acceptance, Kernel, Node, Policy
from agent_kernel.coding_agent import CodingAgent
from agent_kernel.coding_tools import ToolResult, Workspace


def _kernel(executor):
    k = Kernel(policy=Policy(mode="dontAsk"))
    k.executors["inspect"] = executor
    return k


def _run_single(k, acceptance):
    p = k.create_plan(goal="g", nodes=[
        Node("n1", "inspect", "read", lane="inspect", acceptance=acceptance)],
        acceptance=[Acceptance("all done", "plan_complete")])
    k.submit(p)
    k.approve(p.plan_id, "op")
    return k.run(p), p


# ── p01: acceptance outranks the lane's self-report ─────────────────────────

def test_passing_acceptance_outranks_an_incomplete_lane_report(tmp_path):
    """The exact p01 shape: work on disk, tests green, executor says not ok."""
    artifact = tmp_path / "fix.patch"
    artifact.write_text("--- a/calc.py\n+++ b/calc.py\n", encoding="utf-8")

    k = _kernel(lambda n, p: {"ok": False, "detail": "step budget exhausted",
                              "files": [str(artifact)]})
    res, plan = _run_single(k, [Acceptance("artifact exists", "artifact_exists",
                                           {"path": str(artifact)})])

    assert res.status == "complete", res.reason
    assert plan.node("n1").state == "done"
    executor_row = next(e for e in k.evidence if e.verifier == "executor")
    assert executor_row.result == "pass"
    assert "superseded" in executor_row.detail


def test_a_failed_acceptance_keeps_the_block(tmp_path):
    """No regression: an unproven node still stops and asks."""
    missing = tmp_path / "absent.patch"
    k = _kernel(lambda n, p: {"ok": False, "detail": "nothing written"})
    res, plan = _run_single(k, [Acceptance("artifact exists", "artifact_exists",
                                           {"path": str(missing)})])

    assert res.status == "needs_human", res.reason
    assert plan.node("n1").state == "blocked"
    executor_row = next(e for e in k.evidence if e.verifier == "executor")
    assert executor_row.result == "fail"


def test_agent_rechecks_acceptance_after_the_step_budget(tmp_path):
    """The agent reports a pass when the loop ran out of steps on finished work."""
    (tmp_path / "refactor.md").write_text("- split module\n", encoding="utf-8")

    def model(prompt: str) -> str:  # never writes, never finishes
        return json.dumps({"tool": "list", "args": {"path": "."}})

    agent = CodingAgent(tmp_path, model, max_steps=3, required_artifact="refactor.md",
                        acceptance=lambda: (True, "artifact valid"))
    res = agent.run("refactor the module")

    assert res.ok is True
    assert res.summary == "acceptance passed after the step budget"
    assert res.steps == 3


def test_pressure_clears_when_a_non_write_tool_creates_the_artifact(tmp_path):
    """An `apply_patch` that produces the artifact must end write-only pressure."""
    workspace = Workspace(tmp_path)
    target = tmp_path / "refactor.md"

    def fake_execute(tool: str, args: dict) -> ToolResult:
        if tool == "apply_patch":
            target.write_text("- moved\n", encoding="utf-8")
            return ToolResult(True, "patched", files=[str(target)])
        return ToolResult(True, "a.md\nb.md")

    workspace.execute = fake_execute  # type: ignore[assignment]
    prompts = []

    def model(prompt: str) -> str:
        prompts.append(prompt)
        if len(prompts) <= 2:
            return json.dumps({"tool": "list", "args": {"path": "."}})
        if len(prompts) == 3:
            return json.dumps({"tool": "apply_patch", "args": {"patch": "x"}})
        return json.dumps({"tool": "finish", "args": {"summary": "done"}})

    agent = CodingAgent(workspace, model, max_steps=4, required_artifact="refactor.md",
                        acceptance=lambda: (True, "artifact valid"))
    res = agent.run("refactor the module")

    assert res.ok is True
    assert "Only write and finish are available" in prompts[2]
    assert "Only write and finish are available" not in prompts[3]


# ── p03: bounded, atomic writes ─────────────────────────────────────────────

def test_write_lands_and_leaves_no_temp_file(tmp_path):
    ws = Workspace(tmp_path)
    out = ws.write("notes.md", "# notes\n")

    assert out.ok is True
    assert (tmp_path / "notes.md").read_text(encoding="utf-8") == "# notes\n"
    assert not list(tmp_path.glob(".*nstmp*"))


def test_write_timeout_is_reported_not_hung(tmp_path, monkeypatch):
    import agent_kernel.coding_tools as ct
    import time

    def slow_write(target, data, cancel, errors):
        time.sleep(0.25)
        if not cancel.is_set():
            target.write_bytes(data)

    monkeypatch.setattr(ct, "_write_atomic", slow_write)
    ws = Workspace(tmp_path, write_timeout_s=0.01)
    out = ws.write("stalled.md", "body")

    assert out.ok is False
    assert "timed out" in out.error
    assert not (tmp_path / "stalled.md").exists()


def test_write_failure_is_a_tool_error_not_an_exception(tmp_path, monkeypatch):
    import agent_kernel.coding_tools as ct

    def boom(target, data, cancel, errors):
        errors.append("OSError: disk full")

    monkeypatch.setattr(ct, "_write_atomic", boom)
    ws = Workspace(tmp_path)
    out = ws.write("x.md", "body")

    assert out.ok is False
    assert "disk full" in out.error


@pytest.mark.parametrize("path", [
    ".env",
    ".env.local",
    "config/chromecontrol_policy_owner.json",
    "config/chromecontrol.json",
    "fixtures/brief.json",
    "tests/fixtures/manifest.json",
])
def test_protected_paths_are_read_only(tmp_path, path):
    ws = Workspace(tmp_path)
    out = ws.write(path, "tampered")

    assert out.ok is False
    assert "protected" in out.error
    assert not (tmp_path / path).exists()


def test_env_example_is_not_protected(tmp_path):
    """The one .env-shaped file an agent may legitimately touch."""
    ws = Workspace(tmp_path)
    out = ws.write(".env.example", "NORTHSTAR_UI_MODE=\n")

    assert out.ok is True
