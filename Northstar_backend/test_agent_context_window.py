"""Context management: the window is measured, compaction is announced, nothing is lost.

The gap this closes: `agent_kernel/context.py` had a `Compactor` and a
`write_handoff`, and nothing called them, so a long coding run grew its
transcript until the prompt was truncated by the model server - silently, with
no handoff and no record. These tests assert the three properties that make
compaction safe rather than cosmetic:

  1. it happens at a *measured* threshold, not by guesswork;
  2. the model is told it happened (a marker, an anchor), so it does not
     re-derive lost evidence as if it had never existed;
  3. the dropped context survives on disk in the handoff.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from agent_kernel.coding_agent import CodingAgent  # noqa: E402


def _agent(tmp_path, **kw):
    return CodingAgent(tmp_path, lambda prompt: '{"tool":"finish","args":{}}', **kw)


def test_context_tokens_grows_with_the_transcript(tmp_path):
    agent = _agent(tmp_path)
    small = agent._context_tokens([{"role": "observation", "output": "x" * 40}])
    large = agent._context_tokens([{"role": "observation", "output": "x" * 4000}])
    assert large > small


def test_no_compaction_below_the_threshold(tmp_path):
    agent = _agent(tmp_path, context_limit_tokens=10000, compact_at=0.70)
    history = [{"role": "observation", "tool": "read", "output": "ok"}]
    out = agent._maybe_compact("task", history, step=1)
    assert out == history
    assert agent.compactions == 0


def test_compaction_fires_at_seventy_percent_and_announces_itself(tmp_path):
    agent = _agent(tmp_path, context_limit_tokens=1000, compact_at=0.70)
    history = [{"role": "observation", "tool": "read",
                "output": "y" * 600} for _ in range(10)]
    out = agent._maybe_compact("build the label", history, step=7)
    assert agent.compactions == 1
    assert len(out) < len(history)
    assert "compacted" in str(out[0]).lower()
    assert any("TASK ANCHOR" in str(m.get("content", "")) for m in out)


def test_compaction_writes_a_handoff_that_outlives_the_window(tmp_path):
    handoff = tmp_path / "handoff.md"
    agent = _agent(tmp_path, context_limit_tokens=500, compact_at=0.70,
                   handoff_path=str(handoff))
    history = [{"role": "observation", "tool": "read",
                "output": "z" * 500} for _ in range(6)]
    agent._maybe_compact("ship the pouch label", history, step=3)
    assert handoff.is_file()
    text = handoff.read_text(encoding="utf-8")
    assert "ship the pouch label" in text
    assert "compacted at step 3" in text


def test_compaction_is_bounded_and_does_not_loop(tmp_path):
    agent = _agent(tmp_path, context_limit_tokens=400, compact_at=0.5)
    history = [{"role": "observation", "tool": "read",
                "output": "w" * 400} for _ in range(8)]
    once = agent._maybe_compact("t", history, step=1)
    twice = agent._maybe_compact("t", once, step=2)
    # A second pass may keep trimming, but it must always shrink, never grow.
    assert len(twice) <= len(once)


def test_result_reports_compactions(tmp_path):
    agent = _agent(tmp_path)
    agent.compactions = 2
    result = agent.run("do a thing")
    assert result.to_dict()["compactions"] >= 2
