"""ast-grep and repomix are real coding-lane tools, workspace-scoped."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "Northstar_backend"))

from agent_kernel.coding_tools import Workspace  # noqa: E402
from agent_kernel import tool_protocol as tp  # noqa: E402


def _workspace(tmp_path):
    (tmp_path / "a.py").write_text("def hello():\n    return 1\n", encoding="utf-8")
    return Workspace(tmp_path)


def test_ast_grep_finds_a_structural_match(tmp_path):
    result = _workspace(tmp_path).ast_grep("def $F($$$)", ".", "python")
    assert result.ok is True, result.error
    assert "hello" in result.output


def test_repo_pack_returns_a_bounded_context(tmp_path):
    result = _workspace(tmp_path).repo_pack(".", max_chars=5000)
    assert result.ok is True, result.error
    assert "a.py" in result.output
    assert "hello" in result.output


def test_the_action_schema_accepts_the_new_tools():
    action = tp.parse_action('{"tool":"ast_grep","args":{"pattern":"def $F($$$)","lang":"python"}}')
    assert action.tool == "ast_grep"
    action = tp.parse_action('{"tool":"repo_pack","args":{}}')
    assert action.tool == "repo_pack"
