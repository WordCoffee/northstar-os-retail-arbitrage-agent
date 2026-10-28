"""Opt-in Ty integration: a work order runs through the agent kernel."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from tys_assistant import Adapter, StepResult, TysAssistant, TysStore


class _Inspect(Adapter):
    def run_step(self, step, task):
        return StepResult(True, "looked at it", evidence={"ok": True})


def _assistant(tmp_path):
    return TysAssistant(
        store=TysStore(str(tmp_path / "tys.db")),
        adapters={"inspect": _Inspect()},
        evidence_dir=str(tmp_path / "evidence"),
    )


def test_run_kernel_completes_and_persists(tmp_path):
    a = _assistant(tmp_path)
    task = a.submit({
        "objective": "look at the thing",
        "scope": {"lanes": ["inspect"]},
        "steps": [{"lane": "inspect", "objective": "look at the thing"}],
    })
    out = a.run_kernel(task["id"])
    assert out["status"] == "complete", out.get("reason")
    assert a.store.get(task["id"])["status"] == "done"
    events = a.store.events(task["id"])
    assert any(e["kind"] == "kernel_result" for e in events)


def test_run_kernel_refuses_a_completed_task(tmp_path):
    a = _assistant(tmp_path)
    task = a.submit({
        "objective": "look",
        "scope": {"lanes": ["inspect"]},
        "steps": [{"lane": "inspect", "objective": "look"}],
    })
    a.run_kernel(task["id"])
    try:
        a.run_kernel(task["id"])
    except Exception as exc:  # TysError
        assert "not_runnable" in str(exc) or "done" in str(exc)
    else:  # pragma: no cover - a second run must not silently repeat
        raise AssertionError("a completed task was run twice")
