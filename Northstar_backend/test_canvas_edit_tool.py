"""U8 — the canvas_edit tool.

The tool never mutates a document. It answers one question: can the canvas the
operator has open satisfy this instruction? The browser applies the edit through
the same command layer the workbench registers, so the edit semantics exist once
(JavaScript) and this handler cannot drift from them.

These tests pin the refusal cases, because a tool that says "done" when there is
no canvas is worse than one that says nothing.
"""
from __future__ import annotations

import pytest

from chat_tools import TOOLS, run_tool


CANVAS = {
    "id": "DOC-1",
    "name": "Spring drop",
    "contentType": "ad",
    "w": 1080,
    "h": 1080,
    "selected": "",
    "layers": [
        {"id": "BG-1", "kind": "bg", "name": "Background", "role": ""},
        {"id": "L-1", "kind": "text", "name": "Text: Spring drop", "role": "headline",
         "text": "Spring drop", "size": 0.09},
    ],
    "assets": [],
}


def test_the_tool_is_registered_with_a_bounded_schema():
    spec = TOOLS["canvas_edit"]
    assert spec["handler"] is not None
    props = spec["parameters"]["properties"]
    assert list(props) == ["instruction"]
    assert spec["parameters"]["required"] == ["instruction"]


def test_an_instruction_the_canvas_can_satisfy_is_accepted():
    out = run_tool("canvas_edit", {"instruction": "make the headline bigger"}, {"canvas": CANVAS})
    assert out["ok"] is True
    assert out["instruction"] == "make the headline bigger"
    assert "Spring drop" in out["summary"]


def test_no_canvas_is_a_refusal_not_a_success():
    for ctx in ({}, {"canvas": None}, None):
        out = run_tool("canvas_edit", {"instruction": "make the headline bigger"}, ctx)
        assert out["ok"] is False, f"ctx={ctx!r} must refuse"
        assert "canvas" in out["error"].lower()


def test_a_layer_that_does_not_exist_is_named():
    out = run_tool("canvas_edit", {"instruction": "make the subhead smaller"}, {"canvas": CANVAS})
    assert out["ok"] is False
    assert "subhead" in out["error"]
    assert "Add one" in out["error"]


def test_an_empty_instruction_is_rejected_by_the_validator():
    out = run_tool("canvas_edit", {"instruction": ""}, {"canvas": CANVAS})
    assert out["ok"] is False


def test_the_tool_does_not_mutate_the_canvas_it_was_given():
    import copy
    before = copy.deepcopy(CANVAS)
    run_tool("canvas_edit", {"instruction": "make the headline bigger"}, {"canvas": CANVAS})
    assert CANVAS == before
