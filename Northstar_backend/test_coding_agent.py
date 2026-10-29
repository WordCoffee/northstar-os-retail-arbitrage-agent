"""Coding tools + bounded agent loop."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from agent_kernel.coding_agent import CodingAgent, parse_tool_call
from agent_kernel.coding_executor import CodingAgentExecutor
from agent_kernel.coding_tools import Workspace
from agent_kernel.model import Acceptance, Node, Plan


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
