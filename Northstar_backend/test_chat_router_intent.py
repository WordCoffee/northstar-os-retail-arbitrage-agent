"""Deterministic intent router — visual deliverables skip the model.

Three behaviours are locked here:
  (a) a real visual-deliverable request fires the router and emits a plan card
      without calling the model at all;
  (b) a question that merely mentions a noun ("margin on pouches") does not;
  (c) a bare noun ("mockup") does not.

Offline: no Ollama, no network, no GPU. The plan builder is pure.
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
_REPO = os.path.dirname(_HERE)
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

import chat_schema  # noqa: E402
import chat_router  # noqa: E402
import data_layer  # noqa: E402

MOGRA = (
    'Create a detailed 3D product mockup of a Mogra Organics Organic Lion\'s Mane '
    'Mushroom Powder 6 oz standing pouch, photoreal, studio lighting.'
)


class _FakeDataLayer:
    def __init__(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(chat_schema.CHAT_TABLES_SQL)

    def execute(self, sql, params=()):
        return self.conn.execute(sql, params)

    def commit(self):
        self.conn.commit()


class _FakeNorthstarDB:
    def __init__(self):
        self.layer = _FakeDataLayer()
        self.chat = data_layer.ChatContainer(self.layer)


@pytest.fixture()
def db():
    return _FakeNorthstarDB()


def _new_session(db, account="acct-1"):
    sid = db.chat.sessions.create({"account_id": account, "title": "New chat"})
    return db.chat.sessions.get_by_id(sid, account_id=account)


def _parse_frames(chunks):
    out = []
    for frame in chunks:
        lines = [ln for ln in frame.split("\n") if ln]
        event = next((ln[7:] for ln in lines if ln.startswith("event: ")), None)
        data_line = next((ln[6:] for ln in lines if ln.startswith("data: ")), "{}")
        out.append((event, json.loads(data_line)))
    return out


def _boom(*_a, **_k):
    raise AssertionError("the model must not be called for a routed visual deliverable")


# ── (a) the Mogra prompt fires ───────────────────────────────────────────────

def test_mogra_prompt_is_routed_with_the_real_product():
    routed = chat_router.route_creative_intent(MOGRA)
    assert routed is not None
    assert "Mogra Organics" in routed["product"]
    assert "standing pouch" in routed["product"]
    # The phrase is quoted from the operator; nothing was invented.
    assert routed["product"].lower() in MOGRA.lower()


def test_routed_turn_emits_a_plan_card_and_skips_the_model(db):
    session = _new_session(db)
    frames = list(chat_router.turn_event_stream(
        db, "acct-1", session, MOGRA,
        tools_enabled=True, events=_boom,
    ))
    pairs = _parse_frames(frames)
    events = [e for e, _ in pairs]

    assert "card" in events, events
    card = next(d for e, d in pairs if e == "card")
    assert card["kind"] == "generation_plan"
    assert card["plan_id"]
    assert card["title"]
    assert card["rows"]

    done = next(d for e, d in pairs if e == "done")
    assert done["status"] == "done"
    assert done["usage"]["model_called"] is False

    # The short line is the only prose, and the card is persisted with it.
    tokens = "".join(d.get("delta", "") for e, d in pairs if e == "token")
    assert "Plan ready" in tokens
    assert len(tokens.splitlines()) == 1


# ── (b) and (c) must NOT fire ───────────────────────────────────────────────

def test_margin_question_does_not_fire():
    assert chat_router.route_creative_intent("what's a good margin on pouches?") is None


def test_bare_mockup_does_not_fire():
    assert chat_router.route_creative_intent("mockup") is None


def test_verb_without_product_does_not_fire():
    # A verb and a noun but no extractable product: fall through to the model.
    assert chat_router.route_creative_intent("create a mockup") is None


def test_non_routed_turn_still_calls_the_model(db):
    session = _new_session(db)
    seen = {"called": False}

    def _model(round_idx, messages):
        seen["called"] = True
        return [json.dumps({"message": {"content": "ok"}, "done": False}),
                json.dumps({"done": True})]

    frames = list(chat_router.turn_event_stream(
        db, "acct-1", session, "what's a good margin on pouches?",
        tools_enabled=True, events=_model,
    ))
    pairs = _parse_frames(frames)
    assert seen["called"] is True
    assert not any(e == "card" for e, _ in pairs)
