"""The launcher is what makes "turn ended" different from "work stopped".

Tests drive `_run_cycle` with a stub worker against a temporary root, so no model
is called and nothing touches the real queue.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import tys_launcher as L  # noqa: E402
import tys_runner as r  # noqa: E402


@pytest.fixture()
def root(tmp_path, monkeypatch):
    (tmp_path / "reports" / "ty").mkdir(parents=True)
    (tmp_path / "state" / "tys_runner").mkdir(parents=True)
    queue = {
        "phase": "C", "cycle": 0,
        "items": [
            {"id": "runnable", "title": "do a thing", "status": "pending", "priority": 900,
             "next": "make the check pass",
             "write_paths": ["Northstar_backend/x.py"],
             "acceptance_commands": [[
                 "python", "-c",
                 "import pathlib,sys; sys.exit(0 if pathlib.Path('done.flag').exists() else 1)",
             ]]},
            {"id": "no_checks", "title": "vague", "status": "pending", "priority": 800,
             "write_paths": ["Northstar_backend/y.py"]},
        ],
    }
    (tmp_path / "reports" / "ty" / "autonomy_queue.json").write_text(
        json.dumps(queue), encoding="utf-8")
    targets = {
        "ROOT": tmp_path,
        "QUEUE": tmp_path / "reports" / "ty" / "autonomy_queue.json",
        "STATE_DIR": tmp_path / "state" / "tys_runner",
        "LEDGER": tmp_path / "state" / "tys_runner" / "ledger.json",
        "LEASE": tmp_path / "state" / "tys_runner" / "lease.json",
        "CHECKPOINT": tmp_path / "state" / "tys_runner" / "checkpoint.json",
        "SESSIONS": tmp_path / "state" / "tys_runner" / "sessions.jsonl",
        "HANDOFF": tmp_path / "reports" / "ty" / "cycle_handoff.json",
        "STOP": tmp_path / "STOP",
    }
    for name, value in targets.items():
        monkeypatch.setattr(r, name, value)
    monkeypatch.setattr(L, "ROOT", tmp_path)
    monkeypatch.setattr(L, "STATE", tmp_path / "state/tys_runner")
    monkeypatch.setattr(L, "HEARTBEAT", tmp_path / "state/tys_runner/heartbeat.json")
    monkeypatch.setattr(L, "JOURNAL", tmp_path / "state/tys_runner/launcher.jsonl")
    monkeypatch.setattr(L, "BRIEF", tmp_path / "reports/ty/cycle_handoff.json")
    return tmp_path


def _worker(result, *, ok=True, steps=3, evidence=None):
    def run(task_path, result_path):
        json.loads(task_path.read_text(encoding="utf-8"))
        if ok:
            # STATE is <root>/state/tys_runner, so parents[2] is the root the
            # launcher runs acceptance commands in.
            root = Path(task_path).resolve().parents[2]
            (root / "done.flag").write_text("done", encoding="utf-8")
        payload = {"ok": ok, "steps": steps, "evidence": evidence or [],
                   "files": ["Northstar_backend/x.py"]}
        result_path.write_text(json.dumps(payload), encoding="utf-8")
        return 0
    return run


def test_a_contract_is_built_only_from_declared_fields(root, capsys):
    r.cmd_next()
    brief = json.loads(L.BRIEF.read_text(encoding="utf-8"))["brief"]
    item = next(i for i in r.load_queue()["items"] if i["id"] == brief["item"])
    contract = L.task_contract(item, brief)
    assert contract["objective"] == "make the check pass"
    assert contract["write_paths"] == ["Northstar_backend/x.py"]
    assert contract["acceptance_commands"][0][0] == "python"


def test_an_item_without_checks_is_skipped_not_run(root, monkeypatch):
    # Remove the runnable item so the vague one is next.
    queue = r.load_queue()
    r.mark(queue, "runnable", "done")
    out = L._run_cycle(worker=_worker({}), dry_run=False, cycle_budget=3)
    assert out["skipped"] is True
    assert "acceptance_commands" in out["reason"]
    item = next(i for i in r.load_queue()["items"] if i["id"] == "no_checks")
    assert item["needs_author"]


def test_a_successful_worker_closes_the_cycle(root):
    evidence = root / "state" / "evidence.json"
    evidence.write_text("{}", encoding="utf-8")
    out = L._run_cycle(worker=_worker({}, evidence=[str(evidence)]),
                       dry_run=False, cycle_budget=3)
    assert out["ok"] is True and out["shipped"] is True
    item = next(i for i in r.load_queue()["items"] if i["id"] == "runnable")
    assert item["status"] == "done"


def test_a_failed_worker_restores_the_bytes_it_wrote(root):
    target = root / "Northstar_backend" / "x.py"
    target.parent.mkdir(parents=True)
    target.write_text("original\n", encoding="utf-8")

    def worker(task_path, result_path):
        target.write_text("damaged by the worker\n", encoding="utf-8")
        result_path.write_text(json.dumps({"ok": False, "steps": 1}), encoding="utf-8")
        return 0

    out = L._run_cycle(worker=worker, dry_run=False, cycle_budget=3)
    assert out["shipped"] is False
    assert target.read_text(encoding="utf-8") == "original\n"


def test_a_new_file_from_a_failed_worker_is_deleted(root):
    target = root / "Northstar_backend" / "created.py"
    queue = r.load_queue()
    for item in queue["items"]:
        if item["id"] == "runnable":
            item["write_paths"] = ["Northstar_backend/x.py", "Northstar_backend/created.py"]
    (root / "reports" / "ty" / "autonomy_queue.json").write_text(json.dumps(queue), encoding="utf-8")

    def worker(task_path, result_path):
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("junk\n", encoding="utf-8")
        result_path.write_text(json.dumps({"ok": False, "steps": 1}), encoding="utf-8")
        return 0

    L._run_cycle(worker=worker, dry_run=False, cycle_budget=3)
    assert not target.exists()


def test_a_file_created_outside_the_declared_scope_is_not_silently_restored(root):
    """Out-of-scope writes are a scope violation, not a revert case.

    `_snapshot` only knows the declared `write_paths`; anything else the worker
    creates is invisible to it. That is deliberate - a restore that guesses at
    paths would delete files nobody declared - and it is why the evaluator's
    scope gate exists.
    """
    target = root / "Northstar_backend" / "sneaky.py"

    def worker(task_path, result_path):
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("x\n", encoding="utf-8")
        result_path.write_text(json.dumps({"ok": False, "steps": 1}), encoding="utf-8")
        return 0

    L._run_cycle(worker=worker, dry_run=False, cycle_budget=3)
    assert target.exists()          # stays until the scope gate reports it


def test_a_check_that_is_already_green_never_reaches_the_worker(root):
    queue = r.load_queue()
    for item in queue["items"]:
        if item["id"] == "runnable":
            item["acceptance_commands"] = [["python", "-c", "print('green')"]]
    (root / "reports" / "ty" / "autonomy_queue.json").write_text(json.dumps(queue), encoding="utf-8")
    called = {"n": 0}

    def worker(_t, _r):
        called["n"] += 1
        return 0

    out = L._run_cycle(worker=worker, dry_run=False, cycle_budget=3)
    assert out["skipped"] is True and out["reason"] == "check_already_green"
    assert called["n"] == 0


def test_a_failed_worker_reverts_and_defers(root):
    out = L._run_cycle(worker=_worker({}, ok=False, steps=0), dry_run=False, cycle_budget=3)
    assert out["shipped"] is False
    item = next(i for i in r.load_queue()["items"] if i["id"] == "runnable")
    assert item["status"] == "pending"
    assert item["attempts"] == 1
    assert item["defer_until_cycle"] >= 1


def test_the_runner_refuses_a_shipped_cycle_with_no_evidence(root):
    """The rule lives in the runner; the launcher is required to satisfy it."""
    r.cmd_next()
    path = root / "completion.json"
    path.write_text(json.dumps({"item": "runnable", "cycle": 1, "shipped": True,
                                "tag": "t", "evidence": []}), encoding="utf-8")
    assert r.cmd_complete(str(path)) == 7
    item = next(i for i in r.load_queue()["items"] if i["id"] == "runnable")
    assert item["status"] == "in_progress"   # unchanged, not silently accepted


def test_a_shipped_cycle_cites_an_evidence_record_the_launcher_wrote(root):
    out = L._run_cycle(worker=_worker({}, evidence=[]), dry_run=False, cycle_budget=3)
    assert out["ok"] is True and out["shipped"] is True
    evidence = list((root / "state" / "evidence").glob("cycle_*.json"))
    assert evidence, "the launcher must persist an evidence record for a shipped cycle"
    row = json.loads(evidence[0].read_text(encoding="utf-8"))
    assert row["item"] == "runnable" and row["worker"]["ok"] is True


def test_dry_run_never_calls_the_worker(root):
    called = {"n": 0}

    def worker(_t, _r):
        called["n"] += 1
        return 0

    out = L._run_cycle(worker=worker, dry_run=True, cycle_budget=3)
    assert out["dry_run"] is True
    assert called["n"] == 0


def test_token_estimate_is_reported_not_invented():
    assert L.estimate_tokens("x" * 400) == 100
    assert L.estimate_tokens({"a": "b"}) >= 1


def test_runner_stops_on_the_stop_marker(root, monkeypatch):
    (root / "STOP").write_text("stop\n", encoding="utf-8")
    monkeypatch.setattr(L, "default_worker", _worker({}))
    assert L.main(["--max-cycles", "3", "--max-hours", "0.01", "--dry-run"]) == 0
    hb = json.loads((root / "state/tys_runner/heartbeat.json").read_text(encoding="utf-8"))
    assert hb["reason"] == "STOP"


def test_a_dead_model_lane_stops_without_burning_a_cycle(root, monkeypatch, capsys):
    monkeypatch.setattr(L, "model_up", lambda *a, **k: False)
    assert L.main(["--max-cycles", "3", "--max-hours", "0.01"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["reason"] == "model_lane_down"
    item = next(i for i in r.load_queue()["items"] if i["id"] == "runnable")
    assert item["status"] == "pending" and not item.get("attempts")


def test_max_cycles_is_respected(root, monkeypatch):
    evidence = root / "state" / "evidence.json"
    evidence.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(L, "default_worker", _worker({}, evidence=[str(evidence)]))
    assert L.main(["--max-cycles", "1", "--max-hours", "1"]) == 0
    lines = (root / "state/tys_runner/launcher.jsonl").read_text(encoding="utf-8").splitlines()
    events = [json.loads(l)["event"] for l in lines]
    assert "launcher_stopped" in events
