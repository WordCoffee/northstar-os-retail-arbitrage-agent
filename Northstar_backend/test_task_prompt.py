"""The task-scoped prompt must advertise the command that will actually run.

A small lane copies the schema example verbatim. When the example was
`python -m pytest` but the task's allowlist held only a probe, every task spent
its first step on a refused command and then stalled.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from agent_kernel.coding_agent import CodingAgent
from agent_kernel.coding_tools import Workspace


def _agent(tmp_path, commands, tools=("read", "ast_edit", "run", "finish")):
    ws = Workspace(tmp_path / "ws", allow_paths=["src.py"], read_paths=["src.py"],
                   run_allowlist=commands)
    return CodingAgent(ws, lambda prompt: '{"tool":"finish","args":{}}',
                       allowed_tools=list(tools), acceptance=lambda: (True, "ok"))


def test_run_example_is_the_task_command(tmp_path):
    agent = _agent(tmp_path, [["python", "state/probes/t5_hitl_corrupt.py"]])
    prompt = agent._prompt("fix it", [])
    assert '"cmd":["python", "state/probes/t5_hitl_corrupt.py"]' in prompt
    assert 'python -m pytest' not in prompt


def test_compact_prompt_asks_for_the_read_first(tmp_path):
    agent = _agent(tmp_path, [["python", "state/probes/t5_hitl_corrupt.py"]])
    assert "Start by reading the task's file" in agent._prompt("fix it", [])


def test_actions_are_limited_to_the_declared_set(tmp_path):
    agent = _agent(tmp_path, [["python", "p.py"]], tools=("read", "finish"))
    prompt = agent._prompt("fix it", [])
    assert '"tool":"read"' in prompt
    assert '"tool":"write"' not in prompt
    assert '"tool":"ast_edit"' not in prompt
