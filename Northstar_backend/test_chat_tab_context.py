"""ux-07c: the chat turn carries the open workspace tab all the way to the model.

ux-07b published `tab` in the request body; pydantic's `extra='ignore'` accepted it and threw it
away, so Bojo never received it. These tests pin the three places it has to survive: the request
model, the options passthrough, and the directive the model actually reads.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import chat_router as C  # noqa: E402

TAB = {"id": "tab-7", "route": "/ui/monitoring?window=7d", "title": "Monitoring",
       "state": {"tabCount": 2, "view": "timeline"}}


def test_the_turn_model_accepts_a_tab_and_keeps_it():
    body = C.TurnIn(content="what am I looking at?", tab=TAB)
    assert body.tab == TAB


def test_a_turn_without_a_tab_stays_none_rather_than_an_empty_dict():
    body = C.TurnIn(content="hello")
    assert body.tab is None


def test_the_directive_tells_the_model_which_tab_is_open():
    directive = C.turn_directive({"media": "image", "tab": TAB})
    line = [row for row in directive.splitlines() if "Open workspace tab" in row]
    assert line, directive
    assert "Monitoring" in line[0]
    assert "/ui/monitoring" in line[0]
    assert "tabCount=2" in line[0]


def test_no_tab_means_no_line_rather_than_an_empty_claim():
    directive = C.turn_directive({"media": "image"})
    assert "Open workspace tab" not in directive


def test_a_malformed_tab_is_ignored_rather_than_crashing_the_turn():
    directive = C.turn_directive({"media": "image", "tab": "not-a-dict"})
    assert "[Bojo turn options]" in directive
    assert "Open workspace tab" not in directive
