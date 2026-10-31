"""AST structural editing: operations, preservation, validation, atomic batches."""
from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent_kernel.ast_edit import (AstEditError, apply_batch, apply_edit,
                                   apply_to_file)

SRC = '''"""Module docstring."""
import os
from typing import Any

LIMIT = 10


class Greeter:
    """Greets."""

    def hello(self, name: str) -> str:
        """Say hello."""
        return "hello " + name

    def bye(self):
        return "bye"


def top(a, b=2):
    """Top doc."""
    return a + b
'''


def _tree(text):
    return ast.parse(text)


def _find(text, name):
    for node in _tree(text).body:
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name == name:
            return node
    raise AssertionError(name)


def test_replace_function_body_keeps_signature_and_docstring():
    out = apply_edit(SRC, {"op": "replace_function_body", "target": "Greeter.hello",
                           "source": 'return f"hi {name}"'})
    node = _find(out, "Greeter").body[1]
    assert node.name == "hello"
    assert node.args.args[1].arg == "name"
    assert node.returns is not None
    assert ast.get_docstring(node) == "Say hello."
    assert any(isinstance(n, ast.Return) for n in node.body)


def test_replace_function_changes_the_signature():
    out = apply_edit(SRC, {"op": "replace_function", "target": "top",
                           "source": "def top(x: int = 3) -> int:\n    return x * 2"})
    node = _find(out, "top")
    assert len(node.args.args) == 1
    assert node.args.args[0].arg == "x"


def test_add_method_appends_to_the_class():
    out = apply_edit(SRC, {"op": "add_method", "target": "Greeter",
                           "source": "def shout(self, s):\n    return s.upper()"})
    names = [n.name for n in _find(out, "Greeter").body
             if isinstance(n, ast.FunctionDef)]
    assert "shout" in names


def test_add_before_and_after_insert_at_module_level():
    out = apply_edit(SRC, {"op": "add_before", "target": "top",
                           "source": "BEFORE = 1"})
    assert "BEFORE = 1" in out
    out = apply_edit(SRC, {"op": "add_after", "target": "top",
                           "source": "AFTER = 2"})
    assert "AFTER = 2" in out
    names = [n.name for n in _tree(out).body if isinstance(n, ast.FunctionDef)]
    assert names[-1] == "top"


def test_delete_removes_the_node():
    out = apply_edit(SRC, {"op": "delete", "target": "Greeter.bye"})
    names = [n.name for n in _find(out, "Greeter").body
             if isinstance(n, ast.FunctionDef)]
    assert "bye" not in names


def test_add_import_is_idempotent():
    once = apply_edit(SRC, {"op": "add_import", "source": "import json"})
    twice = apply_edit(once, {"op": "add_import", "source": "import json"})
    assert twice.count("import json") == 1


def test_replace_imports_keeps_docstring_and_code():
    out = apply_edit(SRC, {"op": "replace_imports",
                           "source": "import sys\nfrom pathlib import Path"})
    assert out.startswith('"""Module docstring."""')
    assert "import sys" in out and "from pathlib import Path" in out
    assert "import os" not in out
    assert "class Greeter" in out and "def top" in out


def test_replace_global_updates_module_assignment():
    out = apply_edit(SRC, {"op": "replace_global", "target": "LIMIT",
                           "source": "LIMIT = 20"})
    assert "LIMIT = 20" in out


def test_missing_target_is_refused():
    with pytest.raises(AstEditError):
        apply_edit(SRC, {"op": "delete", "target": "Nope"})


def test_invalid_source_is_refused_before_any_write():
    with pytest.raises(AstEditError):
        apply_edit(SRC, {"op": "replace_function_body", "target": "top",
                         "source": "return ("})


def test_unknown_op_is_refused():
    with pytest.raises(AstEditError):
        apply_edit(SRC, {"op": "rename", "target": "top"})


def test_apply_to_file_is_atomic_and_path_scoped(tmp_path):
    target = tmp_path / "mod.py"
    target.write_text(SRC, encoding="utf-8")
    before = target.read_text(encoding="utf-8")
    with pytest.raises(AstEditError):
        apply_to_file(tmp_path, "mod.py", [{"op": "delete", "target": "Nope"}])
    assert target.read_text(encoding="utf-8") == before
    out = apply_to_file(tmp_path, "mod.py", [{"op": "replace_global",
                                              "target": "LIMIT",
                                              "source": "LIMIT = 99"}])
    assert out["ok"] is True
    assert "LIMIT = 99" in target.read_text(encoding="utf-8")


def test_apply_to_file_refuses_escape_and_non_python(tmp_path):
    (tmp_path / "mod.py").write_text(SRC, encoding="utf-8")
    with pytest.raises(AstEditError):
        apply_to_file(tmp_path, "../outside.py", [])
    (tmp_path / "notes.txt").write_text("x", encoding="utf-8")
    with pytest.raises(AstEditError):
        apply_to_file(tmp_path, "notes.txt", [])


def test_apply_batch_is_all_or_nothing(tmp_path):
    a = tmp_path / "a.py"
    b = tmp_path / "b.py"
    a.write_text(SRC, encoding="utf-8")
    b.write_text("VALUE = 1\n", encoding="utf-8")
    with pytest.raises(AstEditError):
        apply_batch(tmp_path, [
            {"path": "a.py", "edits": [{"op": "replace_global", "target": "LIMIT",
                                        "source": "LIMIT = 2"}]},
            {"path": "b.py", "edits": [{"op": "delete", "target": "Missing"}]},
        ])
    assert "LIMIT = 10" in a.read_text(encoding="utf-8")
    assert b.read_text(encoding="utf-8") == "VALUE = 1\n"
    out = apply_batch(tmp_path, [
        {"path": "a.py", "edits": [{"op": "replace_global", "target": "LIMIT",
                                    "source": "LIMIT = 2"}]},
        {"path": "b.py", "edits": [{"op": "replace_global", "target": "VALUE",
                                    "source": "VALUE = 2"}]},
    ])
    assert out["ok"] is True
    assert "LIMIT = 2" in a.read_text(encoding="utf-8")
    assert "VALUE = 2" in b.read_text(encoding="utf-8")


def test_workspace_exposes_ast_tools(tmp_path):
    from agent_kernel.coding_tools import Workspace
    (tmp_path / "m.py").write_text(SRC, encoding="utf-8")
    ws = Workspace(tmp_path)
    res = ws.execute("ast_edit", {"path": "m.py", "op": "replace_global",
                                  "target": "LIMIT", "source": "LIMIT = 42"})
    assert res.ok, res.error
    assert "LIMIT = 42" in (tmp_path / "m.py").read_text(encoding="utf-8")
    bad = ws.execute("ast_edit", {"path": "m.py", "op": "delete",
                                  "target": "Missing"})
    assert not bad.ok


def test_crlf_is_preserved(tmp_path):
    target = tmp_path / "crlf.py"
    target.write_bytes(SRC.replace("\n", "\r\n").encode("utf-8"))
    apply_to_file(tmp_path, "crlf.py", [{"op": "replace_global", "target": "LIMIT",
                                         "source": "LIMIT = 7"}])
    data = target.read_bytes()
    assert b"LIMIT = 7" in data
    assert b"\r\n" in data
