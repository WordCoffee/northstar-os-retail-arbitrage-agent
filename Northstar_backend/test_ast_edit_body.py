"""ast_edit body contract: a `def` line passed as the body must not nest."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from agent_kernel.coding_tools import Workspace

MODULE = '''"""Inventory limits."""


def summarise(rows):
    """Count usable rows by state."""
    counts = {}
    return counts
'''


def _ws(tmp_path):
    root = tmp_path / "ws"
    (root / "src").mkdir(parents=True)
    (root / "src" / "limits.py").write_text(MODULE, encoding="utf-8")
    return Workspace(root, allow_paths=["src/limits.py"], read_paths=["src/limits.py"]), \
        root / "src" / "limits.py"


def test_a_body_only_source_is_applied(tmp_path):
    ws, target = _ws(tmp_path)
    res = ws.ast_edit("src/limits.py", "replace_function_body", target="summarise",
                      source="counts = {}\nreturn counts")
    assert res.ok is True
    assert "def summarise" not in target.read_text(encoding="utf-8").split("def summarise", 1)[1]


def test_an_included_matching_def_line_is_stripped_not_nested(tmp_path):
    ws, target = _ws(tmp_path)
    res = ws.ast_edit("src/limits.py", "replace_function_body", target="summarise",
                      source='def summarise(rows):\n    """count"""\n    counts = {}\n    return counts')
    assert res.ok is True
    assert "stripped an included def line" in res.output
    text = target.read_text(encoding="utf-8")
    assert text.count("def summarise(") == 1          # not nested
    assert text.rstrip().endswith("return counts")


def test_a_different_def_in_the_body_is_refused(tmp_path):
    ws, target = _ws(tmp_path)
    res = ws.ast_edit("src/limits.py", "replace_function_body", target="summarise",
                      source="def other(rows):\n    return 1")
    assert res.ok is False
    assert "defines a different symbol" in res.error
    assert "def other" not in target.read_text(encoding="utf-8")
