"""Focused regression: a hard budget stops AT its limit.

`BudgetTracker` bounds the agent kernel's own steps, wall clock and tokens. It is
worker-control code, so this file is the evaluator and lives OUTSIDE anything a
live model task may write. The behaviour is also mirrored by the standalone probe
state/probes/t4_budget_stop.py, which was failing before the repair.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from agent_kernel.budget import BudgetTracker
from agent_kernel.model import Budget


def _tracker(**kw):
    return BudgetTracker(Budget(**kw), clock=lambda: 0.0)


def test_steps_stop_at_the_limit_not_one_past_it():
    t = _tracker(max_steps=3, max_wall_s=60)
    t.step()
    t.step()
    assert t.exhausted is False
    t.step()
    assert t.exhausted is True
    assert t.state.stopped == "max_steps"
    assert t.remaining()["steps"] == 0


def test_tokens_stop_at_the_limit():
    t = _tracker(max_steps=10, max_wall_s=60, max_tokens=100)
    t.tokens(99)
    assert t.exhausted is False
    t.tokens(1)
    assert t.exhausted is True
    assert t.state.stopped == "max_tokens"


def test_wall_clock_still_stops():
    now = [0.0]
    t = BudgetTracker(Budget(max_steps=10, max_wall_s=5), clock=lambda: now[0])
    now[0] = 5.5
    t.step()
    assert t.state.stopped == "max_wall_s"


def test_a_budget_that_is_not_reached_is_not_exhausted():
    t = _tracker(max_steps=5, max_wall_s=60, max_tokens=100)
    t.step()
    t.tokens(10)
    assert t.exhausted is False
    assert t.remaining() == {"steps": 4, "wall_s": 60.0, "tokens": 90}
