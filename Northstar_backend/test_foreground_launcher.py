"""Foreground launcher: refuses before dispatch, never invokes Ty on a low-memory host."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import continuous_loop as cl
import ty_foreground as fg

PROFILES = [{"model": "qwen2.5-coder:3b", "num_ctx": 8192}]


def test_preload_requirement_is_the_profile_minimum():
    assert fg.preload_requirement(PROFILES) == 6.0
    assert fg.preload_requirement([]) == 6.0


def test_low_memory_is_refused_before_anything_loads(monkeypatch, capsys):
    monkeypatch.setattr(cl, "queue_profiles", lambda: PROFILES)
    monkeypatch.setattr(cl, "_free_ram_gb", lambda: 4.53)
    monkeypatch.setattr(cl, "readiness_gate",
                        lambda *a, **k: pytest.fail("readiness must not run"))
    monkeypatch.setattr(cl, "run_campaign",
                        lambda *a, **k: pytest.fail("Ty must not be invoked"))
    assert fg.main(["--check"]) == 3
    out = capsys.readouterr().out
    assert "pre-load 4.53 GB < 6.0 GB required" in out
    assert "close the interactive session" in out


def test_low_memory_refuses_even_without_check_flag(monkeypatch):
    monkeypatch.setattr(cl, "queue_profiles", lambda: PROFILES)
    monkeypatch.setattr(cl, "_free_ram_gb", lambda: 3.0)
    monkeypatch.setattr(cl, "readiness_gate", lambda *a, **k: {"ok": True})
    monkeypatch.setattr(cl, "run_campaign",
                        lambda *a, **k: pytest.fail("Ty must not be invoked"))
    assert fg.main([]) == 3


def test_no_authorized_task_is_refused(monkeypatch):
    monkeypatch.setattr(cl, "queue_profiles", lambda: [])
    assert fg.main(["--check"]) == 3


def test_ready_gate_no_go_is_reported_without_dispatch(monkeypatch, capsys):
    monkeypatch.setattr(cl, "queue_profiles", lambda: PROFILES)
    monkeypatch.setattr(cl, "_free_ram_gb", lambda: 6.5)
    monkeypatch.setattr(cl, "readiness_gate",
                        lambda *a, **k: {"ok": False, "verdict": "NO-GO",
                                         "checked_at": "now",
                                         "failures": [{"name": "model-resident",
                                                       "detail": "min 2.0 GB"}]})
    monkeypatch.setattr(cl, "run_campaign",
                        lambda *a, **k: pytest.fail("Ty must not be invoked"))
    assert fg.main(["--check"]) == 3
    assert "model-resident" in capsys.readouterr().out


def test_go_path_dispatches_a_bounded_campaign(monkeypatch):
    seen = {}
    monkeypatch.setattr(cl, "queue_profiles", lambda: PROFILES)
    monkeypatch.setattr(cl, "_free_ram_gb", lambda: 6.5)
    monkeypatch.setattr(cl, "readiness_gate", lambda *a, **k: {"ok": True})
    monkeypatch.setattr(cl, "load_tasks", lambda *a, **k: {"tasks": []})
    monkeypatch.setattr(cl, "load_state", lambda *a, **k: {"tasks": {}})
    monkeypatch.setattr(cl, "recover_interrupted", lambda state: None)

    def fake_campaign(tasks, state, **kw):
        seen.update(kw)
        return {"ok": True, "run_id": "r1", "stop_reason": "queue_exhausted",
                "attempted": 0, "completed": 0, "failed": 0, "manifest": {}}

    monkeypatch.setattr(cl, "run_campaign", fake_campaign)
    assert fg.main(["--max-tasks", "3", "--deadline-minutes", "120"]) == 0
    assert seen["max_tasks"] == 3
    assert seen["deadline_minutes"] == 120.0
    assert seen["max_consecutive_failures"] == 2
