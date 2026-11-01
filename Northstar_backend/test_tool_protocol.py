"""Strict action protocol: parsing, scope, bounded edits, bounded repair.

Unit coverage for the executor. The LIVE proof is
``tools/probe_lane_protocol.py``, which runs a real local model through the same
actions; these tests are the deterministic half.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from agent_kernel import tool_protocol as tp
from agent_kernel.coding_agent import CodingAgent
from agent_kernel.coding_tools import Workspace


def _ws(tmp_path, *, allow=("src.py",), read=None, run_allow=None):
    root = tmp_path / "ws"
    root.mkdir(exist_ok=True)
    return Workspace(root, allow_paths=list(allow), read_paths=list(read or allow),
                     run_allowlist=run_allow)


# ── 1. a valid action is accepted ───────────────────────────────────────────

def test_valid_json_action_is_accepted_and_normalised(tmp_path):
    ws = _ws(tmp_path)
    action = tp.validate_action(tp.parse_action(
        '{"tool":"read","args":{"path":"src.py"}}'), workspace=ws)
    assert action.tool == "read" and action.args == {"path": "src.py"}


def test_one_fence_and_case_and_alias_are_normalised(tmp_path):
    ws = _ws(tmp_path)
    raw = '```json\n{"tool":"READ","args":{"path":"src.py"}}\n```'
    assert tp.validate_action(tp.parse_action(raw), workspace=ws).tool == "read"
    alias = tp.parse_action('{"tool":"cat","args":{"path":"src.py"}}')
    assert alias.tool == "read"


# ── 2. malformed JSON is rejected, and repaired within budget ───────────────

def test_malformed_json_is_rejected_with_a_code():
    with pytest.raises(tp.ActionError) as exc:
        tp.parse_action('{"tool":"read","args":{"path":')
    assert exc.value.code == "invalid_json"
    assert exc.value.observation().startswith("PROTOCOL invalid_json")


def test_prose_without_json_is_rejected():
    with pytest.raises(tp.ActionError) as exc:
        tp.parse_action("I will now read the file.")
    assert exc.value.code == "not_json"


def test_the_agent_repairs_one_invalid_turn_then_succeeds(tmp_path):
    ws = _ws(tmp_path)
    (Path(ws.root) / "src.py").write_text("x = 1\n", encoding="utf-8")
    turns = iter(["I think I should read it",          # invalid
                  '{"tool":"read","args":{"path":"src.py"}}',
                  '{"tool":"finish","args":{"summary":"done"}}'])

    result = CodingAgent(ws, lambda prompt: next(turns), max_steps=5,
                         acceptance=lambda: (True, "ok")).run("read")
    assert result.ok is True
    assert result.protocol_errors == 1
    assert any(h["tool"] == "protocol" for h in result.transcript)


def test_the_agent_fails_cleanly_when_the_protocol_budget_is_spent(tmp_path):
    ws = _ws(tmp_path)
    result = CodingAgent(ws, lambda prompt: "not json", max_steps=9,
                         max_protocol_errors=2,
                         acceptance=lambda: (True, "ok")).run("x")
    assert result.ok is False
    assert result.error == "protocol_failed: not_json"
    assert result.protocol_errors == 3          # 2 allowed, the 3rd ends the run
    assert result.steps <= 4                    # it did NOT burn the step budget


# ── 3. more than one action per turn ────────────────────────────────────────

def test_two_actions_in_one_turn_are_rejected():
    raw = ('{"tool":"read","args":{"path":"a.py"}}\n'
           '{"tool":"write","args":{"path":"b.py","content":"x"}}')
    with pytest.raises(tp.ActionError) as exc:
        tp.parse_action(raw)
    assert exc.value.code == "multiple_actions"


# ── 4. unknown action ───────────────────────────────────────────────────────

def test_unknown_action_is_rejected_with_the_canonical_list():
    with pytest.raises(tp.ActionError) as exc:
        tp.parse_action('{"tool":"execute_shell","args":{"cmd":"rm -rf /"}}')
    assert exc.value.code == "unknown_tool"
    assert "read" in exc.value.hint and "ast_edit" in exc.value.hint


def test_unknown_argument_is_rejected(tmp_path):
    ws = _ws(tmp_path)
    with pytest.raises(tp.ActionError) as exc:
        tp.validate_action(tp.parse_action(
            '{"tool":"read","args":{"path":"src.py","offset":3}}'), workspace=ws)
    assert exc.value.code == "unknown_argument"


# ── 5. out-of-scope paths are refused before execution ─────────────────────

def test_write_outside_the_scope_creates_nothing(tmp_path):
    ws = _ws(tmp_path, allow=("src.py",))
    with pytest.raises(tp.ActionError) as exc:
        tp.validate_action(tp.parse_action(
            '{"tool":"write","args":{"path":"other.py","content":"x=1"}}'), workspace=ws)
    assert exc.value.code == "out_of_scope"
    assert not (Path(ws.root) / "other.py").exists()


def test_read_outside_the_scope_is_refused(tmp_path):
    ws = _ws(tmp_path, allow=("src.py",), read=("src.py",))
    with pytest.raises(tp.ActionError) as exc:
        tp.validate_action(tp.parse_action(
            '{"tool":"read","args":{"path":"secrets.env"}}'), workspace=ws)
    assert exc.value.code == "out_of_scope"


def test_path_traversal_is_refused(tmp_path):
    ws = _ws(tmp_path)
    with pytest.raises(tp.ActionError) as exc:
        tp.validate_action(tp.parse_action(
            '{"tool":"read","args":{"path":"../../etc/passwd"}}'), workspace=ws)
    assert exc.value.code == "out_of_scope"


# ── 6. whole-file rewrites of existing source are refused ──────────────────

def test_full_file_rewrite_of_a_source_module_is_refused(tmp_path):
    ws = _ws(tmp_path)
    target = Path(ws.root) / "src.py"
    target.write_text("x = 1\n" * 200, encoding="utf-8")      # > 512 bytes
    with pytest.raises(tp.ActionError) as exc:
        tp.validate_action(tp.parse_action(
            '{"tool":"write","args":{"path":"src.py","content":"x = 2\\n"}}'), workspace=ws)
    assert exc.value.code == "bounded_edit_required"
    assert target.read_text(encoding="utf-8").startswith("x = 1")


def test_an_existing_source_file_cannot_be_written_whole_even_if_small(tmp_path):
    ws = _ws(tmp_path)
    target = Path(ws.root) / "src.py"
    target.write_text("def add(a, b):\n    return a - b\n", encoding="utf-8")   # 38 bytes
    with pytest.raises(tp.ActionError) as exc:
        tp.validate_action(tp.parse_action(
            '{"tool":"write","args":{"path":"src.py","content":"x = 1\\n"}}'), workspace=ws)
    assert exc.value.code == "bounded_edit_required"
    assert "return a - b" in target.read_text(encoding="utf-8")


def test_a_double_encoded_args_string_is_unwrapped(tmp_path):
    ws = _ws(tmp_path)
    raw = '{"tool":"read","args":"{\\"path\\": \\"src.py\\"}"}'
    action = tp.validate_action(tp.parse_action(raw), workspace=ws)
    assert action.args == {"path": "src.py"}


def test_arguments_lifted_to_the_top_level_are_accepted(tmp_path):
    ws = _ws(tmp_path)
    action = tp.validate_action(tp.parse_action(
        '{"tool":"read","path":"src.py"}'), workspace=ws)
    assert action.tool == "read" and action.args == {"path": "src.py"}


def test_a_new_source_file_may_be_written_whole(tmp_path):
    ws = _ws(tmp_path, allow=("new.py",))
    action = tp.validate_action(tp.parse_action(
        '{"tool":"write","args":{"path":"new.py","content":"x = 1\\n"}}'), workspace=ws)
    assert action.tool == "write"


def test_ast_edit_is_accepted_on_the_same_module(tmp_path):
    ws = _ws(tmp_path)
    (Path(ws.root) / "src.py").write_text("def f():\n    return 1\n" * 40, encoding="utf-8")
    action = tp.validate_action(tp.parse_action(
        '{"tool":"ast_edit","args":{"path":"src.py","op":"replace_function_body",'
        '"target":"f","source":"return 2"}}'), workspace=ws)
    assert action.tool == "ast_edit"


def test_a_truncated_path_is_normalised_when_unambiguous(tmp_path):
    ws = _ws(tmp_path, allow=("Northstar_backend/calc.py",),
             read=("Northstar_backend/calc.py",))
    (Path(ws.root) / "Northstar_backend").mkdir(parents=True, exist_ok=True)
    (Path(ws.root) / "Northstar_backend" / "calc.py").write_text("x = 1\n", encoding="utf-8")
    action = tp.validate_action(tp.parse_action(
        '{"tool":"read","args":{"path":"North"}}'), workspace=ws)
    assert action.args["path"] == "Northstar_backend/calc.py"
    assert action.notes and action.notes[0].startswith("path_normalised")


def test_an_ambiguous_prefix_is_never_guessed(tmp_path):
    ws = _ws(tmp_path, allow=("src/a.py", "src/b.py"), read=("src/a.py", "src/b.py"))
    with pytest.raises(tp.ActionError) as exc:
        tp.validate_action(tp.parse_action(
            '{"tool":"read","args":{"path":"src"}}'), workspace=ws)
    assert exc.value.code == "out_of_scope"
    assert "allowed paths" in exc.value.hint


# ── 7. a batch with one bad path is refused atomically ─────────────────────

def test_write_many_is_validated_atomically(tmp_path):
    ws = _ws(tmp_path, allow=("src.py",))
    with pytest.raises(tp.ActionError) as exc:
        tp.validate_action(tp.parse_action(
            '{"tool":"write_many","args":{"files":['
            '{"path":"src.py","content":"x=1"},'
            '{"path":"outside.py","content":"y=2"}]}}'), workspace=ws)
    assert exc.value.code == "out_of_scope"
    assert not (Path(ws.root) / "src.py").exists()      # nothing half-applied
    assert not (Path(ws.root) / "outside.py").exists()


# ── 8. commands are argv, never a shell string ─────────────────────────────

def test_a_string_command_is_refused(tmp_path):
    ws = _ws(tmp_path)
    with pytest.raises(tp.ActionError) as exc:
        tp.validate_action(tp.parse_action(
            '{"tool":"run","args":{"cmd":"python -m pytest"}}'), workspace=ws)
    assert exc.value.code == "bad_command"


def test_control_characters_in_argv_are_refused(tmp_path):
    ws = _ws(tmp_path)
    with pytest.raises(tp.ActionError) as exc:
        tp.validate_action(tp.parse_action(
            '{"tool":"run","args":{"cmd":["python","-m","pytest\\nrm -rf /"]}}'), workspace=ws)
    assert exc.value.code == "control_char"


def test_a_semicolon_inside_a_python_snippet_is_not_a_shell_string(tmp_path):
    ws = _ws(tmp_path)
    action = tp.validate_action(tp.parse_action(
        '{"tool":"run","args":{"cmd":["python","-c","import sys; sys.exit(0)"]}}'),
        workspace=ws)
    assert action.args["cmd"][1] == "-c"


def test_the_workspace_allowlist_still_refuses_an_unlisted_command(tmp_path):
    ws = _ws(tmp_path, run_allow=[("python", "-m", "pytest")])
    result = ws.run(["python", "-c", "print(1)"])
    assert result.ok is False and "not allowlisted" in result.error


# ── 9. bounded retry, not an infinite loop ────────────────────────────────

def test_rejections_never_exceed_the_configured_budget(tmp_path):
    ws = _ws(tmp_path)
    calls = {"n": 0}

    def model(prompt):
        calls["n"] += 1
        return "garbage"

    result = CodingAgent(ws, model, max_steps=20, max_protocol_errors=1,
                         acceptance=lambda: (True, "ok")).run("x")
    assert result.ok is False
    assert calls["n"] == 2          # one rejection, then one that ends the run
    assert result.error.startswith("protocol_failed")


# ── 10. model failure and executor rejection are different evidence ───────

def test_scope_rejection_is_counted_separately_from_bad_json(tmp_path):
    ws = _ws(tmp_path, allow=("src.py",))
    turns = iter(['{"tool":"write","args":{"path":"evil.py","content":"x"}}',
                  '{"tool":"finish","args":{}}'])
    result = CodingAgent(ws, lambda p: next(turns), max_steps=3,
                         acceptance=lambda: (True, "ok")).run("x")
    assert result.scope_rejections == 1
    assert result.protocol_errors == 0
    payload = result.to_dict()
    assert payload["scope_rejections"] == 1 and payload["protocol_errors"] == 0


# ── 11. a timed-out command is reported, not raised ───────────────────────

def test_a_slow_command_times_out_without_raising(tmp_path):
    ws = Workspace(tmp_path / "ws", allow_paths=["src.py"],
                   run_allowlist=[["python", "-c"]], run_timeout_s=0.5)
    result = ws.run(["python", "-c", "import time; time.sleep(5)"])
    assert result.ok is False and "timeout" in result.error
