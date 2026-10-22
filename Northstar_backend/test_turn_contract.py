"""Turn contract v2 — media / thinking / style / attachments (Bojo).

The composer's switches must reach the MODEL without ever being written into the
operator's transcript. This suite pins that contract:

  * the defaults are exactly v1 behaviour (image / standard / balanced / none);
  * bad values are rejected at the schema boundary, not silently coerced;
  * the directive names each switch, including the attachment ids;
  * the directive is a SEPARATE system message, and the stored user content is
    untouched.
"""
from __future__ import annotations

import sqlite3

import pytest
from pydantic import ValidationError

import chat_router


# ── schema ───────────────────────────────────────────────────────────────────

def test_defaults_are_v1_behaviour():
    t = chat_router.TurnIn(content="hello")
    assert t.media == "image"
    assert t.thinking == "standard"
    assert t.style == "balanced"
    assert t.mode == "standard"
    assert t.attachments == []
    assert t.think is True


# ── v3 task posture: creative / standard / thinking ─────────────────────────

@pytest.mark.parametrize("mode", ["creative", "standard", "thinking"])
def test_each_mode_is_accepted(mode):
    assert chat_router.TurnIn(content="x", mode=mode).mode == mode


def test_unknown_mode_is_rejected():
    with pytest.raises(ValidationError):
        chat_router.TurnIn(content="x", mode="turbo")


@pytest.mark.parametrize("mode,needle", [
    ("creative", "Mode: creative"),
    ("standard", "Mode: standard"),
    ("thinking", "Mode: thinking"),
])
def test_directive_names_the_mode(mode, needle):
    assert needle in chat_router.turn_directive({"mode": mode})


def test_mode_sets_the_effort_ceiling():
    # thinking always takes the full budget; creative stays at medium for speed.
    assert chat_router._think_level(True, "standard", "hi", 0, "thinking") is True
    assert chat_router._think_level(True, "standard", "hi", 0, "creative") == "medium"
    # an explicit "off" wins over any mode.
    assert chat_router._think_level(True, "off", "hi", 0, "thinking") is False


def test_valid_v2_turn_is_accepted():
    t = chat_router.TurnIn(content="make a pouch", media="video", thinking="deep",
                           style="detailed", attachments=["asset-1", "asset-2"])
    assert (t.media, t.thinking, t.style) == ("video", "deep", "detailed")
    assert t.attachments == ["asset-1", "asset-2"]


@pytest.mark.parametrize("field,bad", [
    ("media", "hologram"), ("thinking", "maximum"), ("style", "poetic"),
])
def test_bad_switch_values_are_rejected(field, bad):
    with pytest.raises(ValidationError):
        chat_router.TurnIn(content="x", **{field: bad})


def test_attachment_count_is_bounded():
    with pytest.raises(ValidationError):
        chat_router.TurnIn(content="x", attachments=[f"a{i}" for i in range(13)])


# ── the directive ────────────────────────────────────────────────────────────

def test_directive_names_the_image_lane_by_default():
    text = chat_router.turn_directive({})
    assert "[Bojo turn options]" in text
    assert "still-image lane" in text


def test_directive_names_the_video_lane():
    assert "video lane" in chat_router.turn_directive({"media": "video"})


def test_directive_carries_thinking_and_style():
    text = chat_router.turn_directive({"thinking": "deep", "style": "concise"})
    assert "Think deeply" in text
    assert "concise" in text.lower()

    off = chat_router.turn_directive({"thinking": "off"})
    assert "Do not emit a reasoning trail" in off


def test_balanced_and_standard_add_no_noise():
    text = chat_router.turn_directive({"thinking": "standard", "style": "balanced"})
    assert "Think deeply" not in text
    assert "concise" not in text.lower()


def test_directive_lists_attachment_ids():
    text = chat_router.turn_directive({"attachments": ["asset-a", "asset-b"]})
    assert "asset-a" in text and "asset-b" in text
    assert "operator's own artefacts" in text


# ── the stream applies it without persisting it ────────────────────────────

def test_the_directive_is_a_separate_system_message_and_the_user_text_is_clean(tmp_path, monkeypatch):
    """The stored transcript must show exactly what the operator typed."""
    seen = {}

    def provider(round_idx, msgs):
        seen.setdefault("messages", msgs)
        return iter([{"type": "content", "delta": "ok"}, {"type": "done"}])

    db = _temp_chat_db(tmp_path, monkeypatch)
    sid = db.chat.sessions.create({"account_id": "acct-1", "title": "t"})
    session = db.chat.sessions.get_by_id(sid, account_id="acct-1")
    frames = list(chat_router.turn_event_stream(
        db, "acct-1", session, "design a pouch",
        events=provider, think=True,
        options={"media": "video", "thinking": "deep", "style": "concise",
                 "attachments": ["asset-1"]}))

    msgs = seen["messages"]
    system_parts = [m for m in msgs if m.get("role") == "system"]
    assert any("turn options" in str(m.get("content")) for m in system_parts), [
        (m.get("role"), str(m.get("content"))[:60]) for m in msgs]
    # NOTE: turn_event_stream builds from HISTORY; persisting the user turn first is
    # the caller's job (create_turn does it). So this test asserts the directive
    # contract, not the presence of the user message.

    # the stored messages never carry the directive (it is model-side only)
    stored = db.chat.messages.list_by_session(sid, account_id="acct-1")
    assert all("turn options" not in str(m.get("content") or "") for m in stored)

    start = next(f for f in frames if f.startswith("event: start"))
    assert '"media": "video"' in start


def test_v1_callers_are_unaffected(tmp_path, monkeypatch):
    """No options -> no directive, exactly the old behaviour."""
    seen = {}

    def provider(round_idx, msgs):
        seen.setdefault("messages", msgs)
        return iter([{"type": "content", "delta": "ok"}, {"type": "done"}])

    db = _temp_chat_db(tmp_path, monkeypatch)
    sid = db.chat.sessions.create({"account_id": "acct-2", "title": "t"})
    session = db.chat.sessions.get_by_id(sid, account_id="acct-2")
    list(chat_router.turn_event_stream(db, "acct-2", session, "hello", events=provider))
    assert not any("turn options" in str(m.get("content")) for m in seen["messages"])


# ── helper: an isolated product DB (never the real northstar.db) ───────────

def _temp_chat_db(tmp_path, monkeypatch):
    """Point the data layer at a disposable DB. monkeypatch restores it after."""
    import data_layer as dl

    monkeypatch.setattr(dl, "_SQLITE_PATH", tmp_path / "northstar.db")
    monkeypatch.setattr(dl, "_db_instance", None, raising=False)
    return dl.get_northstar_db()
