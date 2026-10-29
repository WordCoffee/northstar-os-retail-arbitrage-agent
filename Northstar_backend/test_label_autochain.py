"""U1 — a label brief must reach the label tool (REA 1.6 candidate U1).

Baseline this defends: 21 user turns mentioned a label, 3 called apply_label
(ratio 0.14) — see reports/rea_probe/smui_intents.json.

Three behaviours are locked here:
  (a) a label brief WITH an explicit product name chains apply_label after the
      render, once, with the render's own asset id;
  (b) a label brief with NO name asks exactly once and does not invent copy;
  (c) a second render in the same turn never double-prints.

Offline: no Ollama, no network, no GPU — the tool gateway is faked.
"""

from __future__ import annotations

import json
import os
import sqlite3
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import chat_schema  # noqa: E402
import chat_router  # noqa: E402
import data_layer  # noqa: E402


class _FakeDataLayer:
    def __init__(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(chat_schema.CHAT_TABLES_SQL)

    def execute(self, sql, params=()):
        return self.conn.execute(sql, params)

    def commit(self):
        self.conn.commit()


class _FakeDB:
    def __init__(self):
        self.layer = _FakeDataLayer()
        self.chat = data_layer.ChatContainer(self.layer)


def _tool_call(name, args):
    return {"type": "tool_call",
            "call": {"index": 0, "function": {"name": name, "arguments": args}}}


def _round(calls):
    def _provider(round_idx, messages):
        if round_idx == 0:
            yield from calls
            yield {"type": "done", "cancelled": False, "usage": {"total_tokens": 1}}
        else:
            yield {"type": "content", "delta": "done"}
            yield {"type": "done", "cancelled": False, "usage": {"total_tokens": 1}}
    return _provider


def _run(monkeypatch, brief, scripted_calls, options=None):
    """Drive one turn and return (frames, tool names called, kwargs per call)."""
    calls: list[tuple[str, dict]] = []
    frames: list[dict] = []

    def fake_gate(*, name, args, **kw):  # signature adapted below
        raise AssertionError("unused")

    import tool_gateway

    def fake_run(db_chat, account_id, name, args, ctx):
        payload = args if isinstance(args, dict) else json.loads(args or "{}")
        calls.append((name, payload))
        if name == "generate_image":
            return {"ok": True, "summary": "Rendered 816x1216",
                    "assets": [{"id": "plate-1", "kind": "image", "url": "/x", "name": "plate"}],
                    "data": {}}
        if name == "apply_label":
            return {"ok": True, "summary": "Printed the label",
                    "assets": [{"id": "label-1", "kind": "image", "url": "/y", "name": "label"}],
                    "data": {}}
        return {"ok": True, "summary": name, "assets": [], "data": {}}

    monkeypatch.setattr(tool_gateway, "run_tool_gated", fake_run)
    # The deterministic creative router runs BEFORE the model and would answer a
    # visual brief with a plan card instead of reaching the tool loop. This test
    # is about the loop, so the router is taken out of the way on purpose.
    monkeypatch.setattr(chat_router, "route_creative_intent", lambda text: None)

    db = _FakeDB()
    session = {"id": "s1", "ds_project_id": None}
    for frame in chat_router.turn_event_stream(
            db, "acct", session, brief, think=False, events=_round(scripted_calls),
            tools_enabled=True, options=options or {}):
        frames.append(frame)
    return frames, calls


RENDER = [_tool_call("generate_image", {"prompt": "a kraft pouch", "width": 896, "height": 1344})]


def test_label_brief_with_a_name_chains_the_print_pass(monkeypatch):
    frames, calls = _run(monkeypatch, 'Put the label on the pouch and call it "Lion\'s Mane"',
                         RENDER)
    names = [c[0] for c in calls]
    assert names == ["generate_image", "apply_label"], names
    args = dict(calls)["apply_label"]
    assert args["plate_asset_id"] == "plate-1"
    assert args["title"] == "Lion's Mane"
    assert "label-1" in "\n".join(frames)


def test_label_brief_without_a_name_asks_once_and_invents_nothing(monkeypatch):
    frames, calls = _run(monkeypatch, "put a label on that pouch", RENDER)
    assert [c[0] for c in calls] == ["generate_image"]
    assert "\n".join(frames).count("label_needs_title") == 1


def test_a_second_render_does_not_print_twice(monkeypatch):
    two = RENDER + [_tool_call("generate_image", {"prompt": "another", "width": 512, "height": 512})]
    frames, calls = _run(monkeypatch, 'label the pouch "Mogra"', two)
    assert [c[0] for c in calls].count("apply_label") == 1


def test_a_non_label_brief_never_chains(monkeypatch):
    frames, calls = _run(monkeypatch, "render a hero image of the product", RENDER)
    assert [c[0] for c in calls] == ["generate_image"]


def test_helper_reads_only_explicit_titles():
    assert chat_router.explicit_label_title('print "Mogra Organics" on it') == "Mogra Organics"
    assert chat_router.explicit_label_title("Lion's Mane pouch") is None
    assert chat_router.explicit_label_title("anything", {"product_name": "Shiitake"}) == "Shiitake"
    assert chat_router.label_brief("put the label on the bag")
    assert not chat_router.label_brief("what is the margin on this product")
