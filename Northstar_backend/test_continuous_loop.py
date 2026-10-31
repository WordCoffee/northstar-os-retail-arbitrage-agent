"""Continuous-loop supervisor: task selection, safety filters, ledger."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import continuous_loop as cl


def _tasks():
    return {"tasks": [
        {"id": "a", "name": "first"},
        {"id": "b", "name": "second", "blocked": True},
        {"id": "c", "name": "third"},
    ]}


def test_select_task_picks_first_pending_and_skips_completed_or_blocked():
    tasks = _tasks()
    state = {"completed": {"a": {"commit": "abc"}}}
    assert cl.select_task(tasks, state)["id"] == "c"
    assert cl.select_task(tasks, {"completed": {}})["id"] == "a"
    assert cl.select_task(tasks, {"completed": {}}, "b") is None
    assert cl.select_task(tasks, {"completed": {"a": {}}}, "a") is None


def test_commit_paths_allowlist_and_denylist():
    allowed, refused = cl.validate_commit_paths([
        "config/continuous_loop_tasks.json",
        "docs/CONTINUOUS_LOOP.md",
        "scripts/continuous_loop.py",
        "Northstar_backend/main.py",
        "../outside.py",
        "exports/run.png",
        "Northstar_backend/.env",
        "data/northstar.db",
        "/absolute/path.py",
        "random/file.py",
    ])
    assert "config/continuous_loop_tasks.json" in allowed
    assert "scripts/continuous_loop.py" in allowed
    assert "Northstar_backend/main.py" in allowed
    assert len(refused) == 6
    assert any("escape" in r for r in refused)
    assert any("protected" in r for r in refused)
    assert any("allowlist" in r for r in refused)


def test_forbidden_command_tokens():
    assert cl.check_command(["python", "-m", "pytest"]) is None
    assert cl.check_command(["npm", "run", "test:ui"]) is None
    assert "amazon" in (cl.check_command(["python", "amazon_search.py"]) or "")
    assert "chrome" in (cl.check_command(["node", "chromeconnect.js"]) or "")
    assert "openrouter" in (cl.check_command(["curl", "https://openrouter.ai"]) or "")


def test_scrub_redacts_secret_shaped_text():
    text = "token=abc123 password: hunter2 sk-live-123456789 Bearer abc.def"
    out = cl._scrub(text)
    assert "abc123" not in out
    assert "hunter2" not in out
    assert "sk-live-123456789" not in out
    assert out.count("<redacted>") >= 3


def test_append_ledger_is_jsonl(tmp_path):
    ledger = tmp_path / "ledger.jsonl"
    cl.append_ledger({"cycle": "one", "status": "ok"}, ledger)
    cl.append_ledger({"cycle": "two", "status": "failed"}, ledger)
    rows = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines()]
    assert [r["cycle"] for r in rows] == ["one", "two"]


def test_status_reports_completed_and_pending(tmp_path):
    tasks = _tasks()
    state = {"completed": {"a": {"commit": "abc123"}}}
    ledger = tmp_path / "ledger.jsonl"
    ledger.write_text(json.dumps({"cycle": "a", "status": "ok"}) + "\n", encoding="utf-8")
    out = cl.status(tasks, state, ledger)
    assert out["pending"] == ["c"]
    assert out["tasks"][0]["status"] == "completed"
    assert out["last_cycles"][0]["cycle"] == "a"


def test_dry_run_command_does_not_execute(tmp_path):
    out = cl.run_command(["python", "-c", "raise SystemExit(1)"],
                         cwd=tmp_path, dry_run=True)
    assert out["ok"] is True
    assert out["output"] == "[dry-run]"
