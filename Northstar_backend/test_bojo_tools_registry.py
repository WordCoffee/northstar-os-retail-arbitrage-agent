"""The Bojo tool registry loads what exists and reports what does not."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "Northstar_backend"))

import bojo_tools_registry as R  # noqa: E402


def test_an_absent_module_contributes_nothing_and_does_not_raise():
    # both domain modules may legitimately be missing in a partial checkout
    assert isinstance(R.tools(), dict)


def test_an_unknown_tool_is_a_named_failure_not_an_exception():
    result = R.call("definitely_not_a_tool")
    assert result["ok"] is False
    assert "no Bojo tool" in result["reason"]


def test_a_loaded_tool_is_called_and_normalised(monkeypatch):
    monkeypatch.setattr(R, "tools", lambda: {"demo": lambda **kw: {"value": kw.get("x")}})
    result = R.call("demo", x=7)
    assert result["ok"] is True
    assert result["data"] == {"value": 7}


def test_a_tool_that_raises_is_reported(monkeypatch):
    def boom(**_):
        raise RuntimeError("provider down")

    monkeypatch.setattr(R, "tools", lambda: {"boom": boom})
    result = R.call("boom")
    assert result["ok"] is False
    assert "provider down" in result["reason"]


def test_bad_arguments_are_reported(monkeypatch):
    monkeypatch.setattr(R, "tools", lambda: {"strict": lambda a: a})
    result = R.call("strict")
    assert result["ok"] is False
    assert "bad arguments" in result["reason"]


def test_an_already_shaped_result_passes_through(monkeypatch):
    monkeypatch.setattr(R, "tools", lambda: {"shaped": lambda **_: {"ok": False,
                                                                   "reason": "no rows"}})
    assert R.call("shaped")["reason"] == "no rows"


def test_names_are_sorted_and_unique():
    assert R.names() == sorted(set(R.names()))
