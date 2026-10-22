"""Chatter control — the answer starts with the answer.

The model is instructed not to preamble, but instruction-following is not a
guarantee. These tests pin the deterministic stripper: a leading "Sure!" is
removed from the stream, a trailing "let me know if..." is removed before
persistence, and a normal answer is emitted immediately with no added latency.
"""

from __future__ import annotations

import chat_adapter as ca


def ev(delta: str) -> dict:
    return {"type": "content", "delta": delta}


def joined(events) -> str:
    return "".join(str(e.get("delta") or "") for e in events if e.get("type") == "content")


# ── finished text ───────────────────────────────────────────────────────────

def test_text_strips_acknowledgement():
    assert ca.strip_preamble_text("Sure! The title is Mogra Lion's Mane.") == \
        "The title is Mogra Lion's Mane."


def test_text_keeps_a_clean_answer():
    text = "The title is Mogra Lion's Mane."
    assert ca.strip_preamble_text(text) == text


def test_text_never_deletes_an_answer_without_a_boundary():
    assert ca.strip_preamble_text("Sure") == "Sure"


def test_closing_filler_is_removed():
    assert ca.strip_closing_filler("Title: X. Let me know if you need anything else!") == "Title: X."
    assert ca.strip_closing_filler("Title: X.") == "Title: X."


def test_closing_filler_does_not_eat_real_content():
    text = "You should let me know if the invoice is rejected."
    assert ca.strip_closing_filler(text) == text


# ── the stream ──────────────────────────────────────────────────────────────

def test_stream_drops_preamble_and_keeps_the_answer():
    got = joined(ca.strip_preamble_events([ev("Sure"), ev("! Here is"), ev(" the title.")]))
    assert got == "Here is the title."


def test_stream_is_immediate_when_there_is_no_preamble():
    events = list(ca.strip_preamble_events([ev("The title"), ev(" is X.")]))
    assert events[0]["delta"] == "The title"
    assert joined(events) == "The title is X."


def test_stream_survives_an_opener_split_across_deltas():
    got = joined(ca.strip_preamble_events([ev("Cert"), ev("ainly. The"), ev(" answer.")]))
    assert got == "The answer."


def test_stream_passes_non_content_events_through():
    out = list(ca.strip_preamble_events([{"type": "thinking", "delta": "weigh"},
                                         ev("Sure. Answer.")]))
    assert out[0]["type"] == "thinking"
    assert joined(out) == "Answer."


def test_stream_emits_everything_if_the_opener_never_ends():
    deltas = [ev("Sure " + ("x" * 80)) for _ in range(4)]
    got = joined(ca.strip_preamble_events(deltas))
    assert got.startswith("Sure")  # never silently swallow the whole answer
