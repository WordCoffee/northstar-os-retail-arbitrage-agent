"""Unattended Go lane: accounting, refusal paths, and no credential leakage."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "Northstar_backend"))

import go_author as ga
import go_usage as gu


@pytest.fixture()
def ledger(tmp_path, monkeypatch):
    path = tmp_path / "go_usage_ledger.jsonl"
    monkeypatch.setattr(gu, "LEDGER", path)
    return path


def _add(cost, *, age_s=0.0, task="t"):
    gu.record({"task": task, "cost_usd": cost, "epoch": time.time() - age_s,
               "input_tokens": 10, "output_tokens": 2, "model": ga.MODEL})


def test_totals_sum_and_windows_roll_over(ledger):
    _add(0.5, age_s=0)
    _add(0.25, age_s=6 * 3600)          # outside the 5h window, inside the week
    _add(0.10, age_s=8 * 86400)         # outside the week, inside the month
    w = gu.totals()
    assert w["5h"]["spent_usd"] == pytest.approx(0.5)
    assert w["week"]["spent_usd"] == pytest.approx(0.75)
    assert w["month"]["spent_usd"] == pytest.approx(0.85)


def test_preflight_refuses_at_the_conservative_share(ledger):
    _add(7.15)                       # 59.6% of the $12 five-hour limit
    assert gu.preflight(0.01)["ok"] is True
    refused = gu.preflight(0.10)     # 7.25 > $7.20 (60%)
    assert refused["ok"] is False and refused["window"] == "5h"
    assert "halt cap" in refused["reason"]


def test_preflight_allows_below_the_cap(ledger):
    _add(1.0)
    assert gu.preflight(0.5)["ok"] is True


def test_estimate_fallback_is_conservative():
    est = gu.estimate_tokens("x" * 4000, 200)
    assert est["input_tokens"] == 1000 and est["cost_usd"] > 0
    assert est["source"] == "estimate"


def test_ledger_rows_carry_no_credential_material(ledger):
    _add(0.01, task="ty-x")
    raw = Path(ledger).read_text(encoding="utf-8").lower()
    for needle in ("sk-", "openrouter", "authorization", "bearer", "api_key"):
        assert needle not in raw


def test_the_prompt_carries_no_credential_material():
    prompt = ga._prompt("fix it", "a.py", "x = 1\n")
    low = prompt.lower()
    for needle in ("sk-", "openrouter", "authorization", "bearer"):
        assert needle not in low


def test_apply_refuses_a_path_outside_the_contract(tmp_path, monkeypatch):
    monkeypatch.setattr(ga.cl, "ROOT", tmp_path)
    (tmp_path / "allowed.py").write_text("x = 1\n", encoding="utf-8")
    (tmp_path / "other.py").write_text("y = 2\n", encoding="utf-8")
    task = {"write_paths": ["allowed.py"]}
    err = ga._apply("other.py", "y = 2", "y = 3", task)
    assert "outside the contract" in err
    assert (tmp_path / "other.py").read_text(encoding="utf-8") == "y = 2\n"


def test_apply_refuses_an_ambiguous_search_block(tmp_path, monkeypatch):
    monkeypatch.setattr(ga.cl, "ROOT", tmp_path)
    (tmp_path / "a.py").write_text("x = 1\nx = 1\n", encoding="utf-8")
    err = ga._apply("a.py", "x = 1", "x = 2", {"write_paths": ["a.py"]})
    assert "occurs 2 times" in err
    assert (tmp_path / "a.py").read_text(encoding="utf-8") == "x = 1\nx = 1\n"


def test_apply_writes_exactly_one_replacement(tmp_path, monkeypatch):
    monkeypatch.setattr(ga.cl, "ROOT", tmp_path)
    (tmp_path / "a.py").write_text("def f():\n    return 1\n", encoding="utf-8")
    err = ga._apply("a.py", "return 1", "return 2", {"write_paths": ["a.py"]})
    assert err == ""
    assert (tmp_path / "a.py").read_text(encoding="utf-8") == "def f():\n    return 2\n"


def test_a_usage_less_reply_is_estimated_not_zero(ledger):
    ga._log("t", {"text": "ok", "tokens": {}, "cost_usd": 0.0,
                  "elapsed_s": 1.0}, prompt="x" * 4000, reply="y" * 400)
    rows = gu.entries()
    assert rows and rows[-1]["tokens_source"] == "estimate"
    assert rows[-1]["input_tokens"] == 1000 and rows[-1]["cost_usd"] > 0


def test_a_usage_less_reply_is_estimated_not_zero_marker():
    pass


def test_a_stalled_cli_turn_fails_instead_of_hanging(monkeypatch):
    def boom(*a, **k):
        raise __import__("subprocess").TimeoutExpired(cmd="opencode", timeout=300)
    monkeypatch.setattr(ga.subprocess, "run", boom)
    turn = ga._run("prompt", session="t")
    assert turn["returncode"] == 124 and "timeout" in turn["stderr"]


def test_the_task_deadline_stops_before_another_turn(monkeypatch, tmp_path):
    monkeypatch.setattr(ga.cl, "ROOT", tmp_path)
    (tmp_path / "a.py").write_text("x = 1\n", encoding="utf-8")
    task = {"id": "t", "write_paths": ["a.py"], "objective": "x"}
    monkeypatch.setattr(ga.usage, "preflight", lambda est: {"ok": True, "windows": {}})
    monkeypatch.setattr(ga.al, "open_task", lambda *a, **k: {"write_paths": ["a.py"]})
    calls = {"n": 0}

    def fake_run(prompt, session):
        calls["n"] += 1
        return {"text": "no json", "tokens": {}, "cost_usd": 0.0, "session_id": "",
                "elapsed_s": 1.0, "returncode": 0, "stderr": ""}

    monkeypatch.setattr(ga, "_run", fake_run)
    monkeypatch.setattr(ga, "_log", lambda *a, **k: None)
    monkeypatch.setattr(ga, "TASK_DEADLINE_S", 0)
    monkeypatch.setattr(ga.al, "close_task", lambda *a, **k: {"status": "failed"})
    out = ga.author_task("t", {"tasks": [task]}, {"tasks": {}})
    assert out["status"] == "failed" and "deadline" in out["error"]
    assert calls["n"] == 0


def test_quota_gate_halts_before_opening_any_task(monkeypatch):
    monkeypatch.setattr(ga.usage, "preflight",
                        lambda est: {"ok": False, "window": "5h",
                                     "reason": "5h window would reach $7.30 of a $7.20 cap",
                                     "windows": {}})
    opened = {"n": 0}
    monkeypatch.setattr(ga.al, "open_task", lambda *a, **k: opened.__setitem__("n", 1))
    out = ga.author_task("t", {"tasks": [{"id": "t"}]}, {"tasks": {}})
    assert out["status"] == "quota" and opened["n"] == 0


def test_a_good_reply_is_applied_then_closed(monkeypatch, tmp_path):
    monkeypatch.setattr(ga.cl, "ROOT", tmp_path)
    (tmp_path / "a.py").write_text("def f():\n    return 1\n", encoding="utf-8")
    task = {"id": "t", "write_paths": ["a.py"], "objective": "return 2",
            "checks": [{"name": "p", "cmd": ["python", "-c", "print(1)"]}]}
    monkeypatch.setattr(ga.usage, "preflight", lambda est: {"ok": True, "windows": {}})
    monkeypatch.setattr(ga.al, "open_task",
                        lambda tid, tasks, state: {"write_paths": ["a.py"]})
    monkeypatch.setattr(ga, "_run", lambda prompt, session: {
        "text": json.dumps({"path": "a.py", "search": "return 1", "replace": "return 2"}),
        "tokens": {"input": 100, "output": 20}, "cost_usd": 0.0002,
        "session_id": "s", "elapsed_s": 1.0, "returncode": 0, "stderr": ""})
    monkeypatch.setattr(ga, "_log", lambda task_id, turn, **kw: None)
    closed = {}
    monkeypatch.setattr(ga.al, "close_task",
                        lambda tid, tasks, state: closed.update({"called": True}) or
                        {"status": "completed", "commit": {"sha": "abc"}})
    out = ga.author_task("t", {"tasks": [task]}, {"tasks": {}})
    assert out["status"] == "completed"
    assert (tmp_path / "a.py").read_text(encoding="utf-8") == "def f():\n    return 2\n"
    assert closed["called"] is True
