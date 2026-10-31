"""Coding tools + bounded agent loop."""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from agent_kernel.coding_agent import CodingAgent, parse_tool_call
from agent_kernel.coding_executor import CodingAgentExecutor
from agent_kernel.coding_tools import Workspace
from agent_kernel.model import Acceptance, Node, Plan

GIT = shutil.which("git")
needs_git = pytest.mark.skipif(GIT is None, reason="git is required for apply_patch")


def _git(root: Path, *args: str) -> str:
    r = subprocess.run([GIT, "-c", "core.autocrlf=false", *args], cwd=str(root),
                       capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    return r.stdout


def _init_repo(root: Path) -> None:
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "worker@northstar.invalid")
    _git(root, "config", "user.name", "northstar test")


def test_prompt_history_is_compacted_to_four_observations(tmp_path):
    ws = Workspace(tmp_path / "ws")
    ws.write("calc.py", "def add(a, b):\n    return a - b\n")
    agent = CodingAgent(ws, lambda p: "{}")
    history = [{"tool": "read", "output": f"{i}-" + "x" * 1800} for i in range(6)]
    prompt = agent._prompt("fix the failing add function", history)
    assert prompt.count("[read]") == 4
    assert len(prompt) < 9000


def test_prompt_history_dedupes_and_keeps_error_detail(tmp_path):
    agent = CodingAgent(Workspace(tmp_path / "ws"), lambda p: "{}")
    duplicate = [{"tool": "read", "output": "same"}] * 2
    assert len(agent._compact_history(duplicate)) == 1
    observed = agent._compact_history([{"tool": "run", "output": "Error: " + "e" * 2500}])
    assert len(observed[0]) > 1200          # error text keeps the larger slice
    plain = agent._compact_history([{"tool": "read", "output": "p" * 2500}])
    assert len(plain[0]) <= 1200 + len("[read] ")


def test_path_cannot_escape_the_workspace(tmp_path):
    ws = Workspace(tmp_path / "ws")
    with pytest.raises(ValueError):
        ws.resolve("../../etc/passwd")


def test_write_read_and_allowlist(tmp_path):
    ws = Workspace(tmp_path / "ws")
    assert ws.write("a.txt", "hello").ok
    assert ws.read("a.txt").output == "hello"
    assert not ws.run(["rm", "-rf", "."]).ok
    ok = ws.run(["python", "-m", "py_compile", "a.txt"])
    # a.txt is not valid Python; the point is that the command is allowlisted
    assert ok.error.startswith("exit") or ok.ok


def test_parse_tool_call_accepts_a_fenced_object():
    call = parse_tool_call('```json\n{"tool":"read","args":{"path":"a.py"}}\n```')
    assert call == {"tool": "read", "args": {"path": "a.py"}}
    assert parse_tool_call("prose only") is None


def test_agent_writes_then_finishes(tmp_path):
    ws = Workspace(tmp_path / "ws")
    replies = iter([
        '{"tool":"write","args":{"path":"out.txt","content":"done"}}',
        '{"tool":"finish","args":{"summary":"wrote out.txt"}}',
    ])
    agent = CodingAgent(ws, lambda prompt: next(replies), max_steps=4)
    result = agent.run("write out.txt")
    assert result.ok
    assert (tmp_path / "ws" / "out.txt").read_text() == "done"
    assert result.steps == 2


def test_agent_stops_when_acceptance_passes_after_a_write(tmp_path):
    ws = Workspace(tmp_path / "ws")

    def acceptance():
        return ((tmp_path / "ws" / "out.txt").is_file(), "artifact exists")

    agent = CodingAgent(
        ws, lambda prompt: '{"tool":"write","args":{"path":"out.txt","content":"x"}}',
        max_steps=4, acceptance=acceptance)
    result = agent.run("write out.txt")
    assert result.ok and result.steps == 1


def test_agent_recovers_from_invalid_json(tmp_path):
    ws = Workspace(tmp_path / "ws")
    replies = iter([
        "I will write a file now.",
        '{"tool":"write","args":{"path":"out.txt","content":"x"}}',
        '{"tool":"finish","args":{"summary":"ok"}}',
    ])
    agent = CodingAgent(ws, lambda prompt: next(replies), max_steps=4)
    assert agent.run("x").ok


def test_executor_returns_kernel_shape(tmp_path):
    ws = Workspace(tmp_path / "ws")
    replies = iter([
        '{"tool":"write","args":{"path":"out.txt","content":"x"}}',
        '{"tool":"finish","args":{"summary":"ok"}}',
    ])
    ex = CodingAgentExecutor(lambda prompt: next(replies), ws)
    plan = Plan(plan_id="p", session_id="s", goal="g", nodes=[],
                acceptance=[Acceptance("all", "plan_complete")])
    out = ex(Node("n1", "coding", "write", lane="coding"), plan)
    assert out["ok"] is True
    assert out["files"]


def test_executor_recovers_when_acceptance_passes_after_loop_stop(tmp_path):
    ws = Workspace(tmp_path / "ws")
    (tmp_path / "ws" / "done.txt").write_text("x", encoding="utf-8")
    ex = CodingAgentExecutor(
        lambda prompt: '{"tool":"list","args":{"path":"."}}', ws,
        max_steps=1, acceptance=lambda: (True, "the artifact exists"))
    plan = Plan(plan_id="p", session_id="s", goal="g", nodes=[],
                acceptance=[Acceptance("all", "plan_complete")])
    out = ex(Node("n1", "coding", "write", lane="coding"), plan)
    assert out["ok"] is True
    assert out["data"]["acceptance_recovered"] is True


def test_required_artifact_pressure_after_two_steps(tmp_path):
    ws = Workspace(tmp_path / "ws")
    prompts = []

    def model(prompt):
        prompts.append(prompt)
        if "STEP PRESSURE" in prompt:
            return '{"tool":"write","args":{"path":"out.txt","content":"x"}}'
        return '{"tool":"list","args":{"path":"."}}'

    agent = CodingAgent(
        ws, model, max_steps=5, required_artifact="out.txt",
        acceptance=lambda: ((tmp_path / "ws" / "out.txt").is_file(), "exists"))
    result = agent.run("write out.txt")
    assert result.ok
    assert any("STEP PRESSURE" in p for p in prompts)


def test_repeated_acceptance_run_after_failure_is_refused(tmp_path):
    """A failing `run` cannot change by repeating it: the loop must refuse the re-run
    and push the model back to editing (measured 17-of-24 steps lost to bare runs)."""
    ws = Workspace(tmp_path / "ws")
    ws.write("a.txt", "x")
    prompts = []

    def model(prompt):
        prompts.append(prompt)
        return '{"tool":"run","args":{"cmd":["python","-c","import sys; sys.exit(2)"]}}'

    agent = CodingAgent(ws, model, max_steps=4,
                        acceptance=lambda: ((tmp_path / "ws" / "a.txt").is_file(), "exists"))
    result = agent.run("x")
    stalls = [h for h in result.transcript if h.get("tool") == "verify_stall"]
    assert stalls, "the second bare run must be refused"
    assert "VERIFY STALL" in prompts[-1]
    assert len(stalls) == 3  # step 1 really runs, steps 2-4 are refused


# ── apply_patch ─────────────────────────────────────────────────────────────
@needs_git
def test_apply_patch_applies_a_real_unified_diff(tmp_path):
    ws = Workspace(tmp_path / "ws")
    _init_repo(ws.root)
    target = ws.root / "a.txt"
    target.write_text("old line\n", encoding="utf-8", newline="\n")
    _git(ws.root, "add", "a.txt")
    _git(ws.root, "commit", "-q", "-m", "base")

    target.write_text("new line\n", encoding="utf-8", newline="\n")
    patch = _git(ws.root, "diff", "--", "a.txt")
    _git(ws.root, "checkout", "--", "a.txt")
    assert target.read_bytes() == b"old line\n"
    assert patch.startswith("diff --git a/a.txt b/a.txt")

    result = ws.execute("apply_patch", {"patch": patch})
    assert result.ok, result.error
    assert target.read_bytes() == b"new line\n"
    assert str(target) in result.files
    # the staged patch file is always removed, even after a successful apply
    assert not list(ws.root.glob(".northstar_patch_*"))


def test_apply_patch_accepts_a_crlf_encoded_patch(tmp_path):
    # Models on Windows often emit CRLF diffs; git will not match those against
    # an LF tree, so the tool retries once with normalised line endings.
    if GIT is None:
        pytest.skip("git is required for apply_patch")
    ws = Workspace(tmp_path / "ws")
    _init_repo(ws.root)
    target = ws.root / "a.txt"
    target.write_bytes(b"old line\n")
    _git(ws.root, "add", "a.txt")
    _git(ws.root, "commit", "-q", "-m", "base")
    target.write_bytes(b"new line\n")
    patch = _git(ws.root, "diff", "--", "a.txt")
    _git(ws.root, "checkout", "--", "a.txt")

    result = ws.execute("apply_patch", {"patch": patch.replace("\n", "\r\n")})
    assert result.ok, result.error
    assert target.read_bytes() == b"new line\n"


def test_apply_patch_rejects_a_path_that_escapes_the_root(tmp_path):
    ws = Workspace(tmp_path / "ws")
    outside = tmp_path / "outside.txt"
    outside.write_text("keep\n", encoding="utf-8")
    patch = ("--- a/../outside.txt\n"
             "+++ b/../outside.txt\n"
             "@@ -1 +1 @@\n"
             "-keep\n"
             "+changed\n")

    result = ws.execute("apply_patch", {"patch": patch})
    assert not result.ok
    assert "escape" in result.error.lower()
    assert outside.read_text(encoding="utf-8") == "keep\n"
    assert not list(ws.root.glob(".northstar_patch_*"))


def test_apply_patch_rejects_an_absolute_path(tmp_path):
    ws = Workspace(tmp_path / "ws")
    patch = (f"--- {tmp_path.as_posix()}/abs.txt\n"
             f"+++ {tmp_path.as_posix()}/abs.txt\n"
             "@@ -1 +1 @@\n"
             "-a\n"
             "+b\n")
    result = ws.execute("apply_patch", {"patch": patch})
    assert not result.ok
    assert "absolute" in result.error.lower()


def test_apply_patch_fails_clearly_outside_a_git_workspace(tmp_path):
    # No `git init` here: apply_patch is git-only, so it must say so and write
    # nothing rather than fall back to a pure-python writer.
    ws = Workspace(tmp_path / "ws")
    target = ws.root / "a.txt"
    target.write_text("old\n", encoding="utf-8")
    patch = "--- a/a.txt\n+++ b/a.txt\n@@ -1 +1 @@\n-old\n+new\n"

    result = ws.execute("apply_patch", {"patch": patch})
    assert not result.ok
    assert "git" in result.error.lower()
    assert target.read_text(encoding="utf-8") == "old\n"
    assert not list(ws.root.glob(".northstar_patch_*"))


def test_apply_patch_refuses_a_workspace_nested_in_another_repo(tmp_path):
    # git apply resolves paths from the repo root, so a subdirectory workspace
    # would apply somewhere other than the workspace: refuse instead.
    if GIT is None:
        pytest.skip("git is required for apply_patch")
    outer = tmp_path / "outer"
    outer.mkdir()
    _init_repo(outer)
    ws = Workspace(outer / "ws")
    patch = "--- a/a.txt\n+++ b/a.txt\n@@ -1 +1 @@\n-old\n+new\n"

    result = ws.execute("apply_patch", {"patch": patch})
    assert not result.ok
    assert "git workspace root" in result.error


def test_apply_patch_caps_patch_size(tmp_path):
    ws = Workspace(tmp_path / "ws", max_patch_bytes=64)
    result = ws.execute("apply_patch", {"patch": "x" * 65})
    assert not result.ok
    assert "cap" in result.error


def test_apply_patch_returns_git_stderr_when_the_patch_does_not_apply(tmp_path):
    if GIT is None:
        pytest.skip("git is required for apply_patch")
    ws = Workspace(tmp_path / "ws")
    _init_repo(ws.root)
    target = ws.root / "a.txt"
    target.write_text("actual\n", encoding="utf-8")
    patch = "--- a/a.txt\n+++ b/a.txt\n@@ -1 +1 @@\n-expected\n+new\n"

    result = ws.execute("apply_patch", {"patch": patch})
    assert not result.ok
    assert "a.txt" in result.error  # git's own message, not a reshaped one
    assert target.read_text(encoding="utf-8") == "actual\n"


def test_prompt_schema_lists_apply_patch(tmp_path):
    ws = Workspace(tmp_path / "ws")
    prompt = CodingAgent(ws, lambda prompt: "{}")._prompt("t", [])
    assert '"tool":"apply_patch"' in prompt
