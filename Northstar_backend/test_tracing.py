"""Tracing is optional and must never break a run."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "Northstar_backend"))

from agent_kernel import tracing  # noqa: E402


def test_span_is_a_noop_when_tracing_is_off(monkeypatch):
    monkeypatch.setattr(tracing, "_ENABLED", False)
    with tracing.span("test.span", task_id="t1") as current:
        assert current is None
