"""The runner owns the loop: selection, lease, caps, rotation, crash resume.

These tests use a temporary root so nothing touches the real queue or state.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import tys_runner as r  # noqa: E402


@pytest.fixture()
def root(tmp_path, monkeypatch):
    (tmp_path / "reports" / "ty").mkdir(parents=True)
    (tmp_path / "state" / "tys_runner").mkdir(parents=True)
    queue = {
        "phase": "C", "cycle": 0,
        "items": [
            {"id": "low", "title": "low", "status": "pending", "priority": 10},
            {"id": "high", "title": "high", "status": "pending", "priority": 900},
            {"id": "done", "title": "done", "status": "done", "priority": 999},
        ],
    }
    (tmp_path / "reports" / "ty" / "autonomy_queue.json").write_text(
        json.dumps(queue), encoding="utf-8")
    monkeypatch.setattr(r, "ROOT", tmp_path)
    monkeypatch.setattr(r, "QUEUE", tmp_path / "reports" / "ty" / "autonomy_queue.json")
    monkeypatch.setattr(r, "STATE_DIR", tmp_path / "state" / "tys_runner")
    monkeypatch.setattr(r, "LEDGER", tmp_path / "state" / "tys_runner" / "ledger.json")
    monkeypatch.setattr(r, "LEASE", tmp_path / "state" / "tys_runner" / "lease.json")
    monkeypatch.setattr(r, "CHECKPOINT", tmp_path / "state" / "tys_runner" / "checkpoint.json")
    monkeypatch.setattr(r, "SESSIONS", tmp_path / "state" / "tys_runner" / "sessions.jsonl")
    monkeypatch.setattr(r, "HANDOFF", tmp_path / "reports" / "ty" / "cycle_handoff.json")
    monkeypatch.setattr(r, "STOP", tmp_path / "STOP")
    return tmp_path


def test_selection_is_priority_then_id(root):
    nxt = r.select_next()
    assert nxt["id"] == "high"


def test_done_items_are_never_selected(root):
    ids = set()
    for _ in range(2):
        nxt = r.select_next()
        ids.add(nxt["id"])
        queue = r.load_queue()
        r.mark(queue, nxt["id"], "done")
    assert "done" not in ids


def test_next_reserves_the_item_and_refuses_a_second_lease(root, capsys):
    assert r.cmd_next() == 0
    out = json.loads(capsys.readouterr().out)
    assert out["ok"] and out["brief"]["item"] == "high"
    assert r.cmd_next() == 5          # a lease is already held
    queue = r.load_queue()
    assert next(i for i in queue["items"] if i["id"] == "high")["status"] == "in_progress"


def test_first_cycle_in_the_session_is_one(root, capsys):
    r.cmd_next()
    out = json.loads(capsys.readouterr().out)
    assert out["brief"]["cycle"] == 1


def test_stop_marker_halts_the_loop(root):
    r.cmd_stop()
    assert r.STOP.exists()
    assert r.cmd_next() == 3


def test_token_cap_is_enforced(root, monkeypatch):
    monkeypatch.setattr(r, "TOKEN_CAP_PER_DAY", 1000)
    r._add_tokens(950)
    assert r.cmd_next() == 4


def test_completion_requires_evidence_for_a_shipped_cycle(root):
    r.cmd_next()
    result = {"item": "high", "cycle": 1, "shipped": True, "tag": "autonomy-cycle-01",
              "evidence": ["does/not/exist.json"]}
    path = root / "result.json"
    path.write_text(json.dumps(result), encoding="utf-8")
    assert r.cmd_complete(str(path)) == 7


def test_a_valid_completion_closes_the_cycle_and_rotates_at_the_limit(root, monkeypatch):
    monkeypatch.setattr(r, "CYCLES_PER_SESSION", 2)
    for n in (1, 2):
        r.cmd_next()
        evidence = root / f"e{n}.json"
        evidence.write_text("{}", encoding="utf-8")
        result = {"item": "high" if n == 1 else "low", "cycle": n, "shipped": False,
                  "evidence": [str(evidence.relative_to(root))], "tokens": 10}
        path = root / "result.json"
        path.write_text(json.dumps(result), encoding="utf-8")
        code = r.cmd_complete(str(path))
        assert code == 0
    sessions = r.SESSIONS.read_text(encoding="utf-8").strip().splitlines()
    events = [json.loads(line)["event"] for line in sessions]
    assert "session_ended" in events
    assert r._cycles_in_session() == 0      # a new session starts clean


def test_crash_recovery_keeps_the_reserved_item(root, capsys):
    r.cmd_next()
    # Simulate a dead session: the holder pid no longer exists.
    lease = json.loads(r.LEASE.read_text(encoding="utf-8"))
    lease["pid"] = 999999
    r.LEASE.write_text(json.dumps(lease), encoding="utf-8")
    assert r._lease() is None
    assert r.cmd_next() == 0                # the same item is reserved again


def test_rotation_releases_the_lease(root):
    r.cmd_next()
    assert r.cmd_rotate("context heavy") == 0
    assert not r.LEASE.exists()


def test_dry_run_simulates_rotations_without_writing(root, capsys):
    before = r.LEDGER.read_text(encoding="utf-8") if r.LEDGER.exists() else None
    assert r.cmd_dry_run(6, 2) == 0
    out = json.loads(capsys.readouterr().out)
    # Two active items, one rotation per two cycles: one rotation, then empty.
    assert out["rotations"] == 1
    assert out["cycles"] == 3
    after = r.LEDGER.read_text(encoding="utf-8") if r.LEDGER.exists() else None
    assert before == after


# ------------------------------------------------------- A15: contract validation
def _contract(**fields):
    item = {"id": "M1g-contract-writer",
            "write_paths": ["Northstar_backend/lib/thing.py"],
            "acceptance_commands": [["python", "-m", "pytest", "-q",
                                     "Northstar_backend/test_thing.py"]]}
    item.update(fields)
    return item


def test_a_well_formed_contract_has_no_problems():
    assert r.validate_contract(_contract()) == []


def test_a_contract_without_scope_or_checks_names_the_gap():
    assert r.validate_contract({"id": "x",
                                "acceptance_commands": [["python", "-c", "print(1)"]]}
                               ) == ["no write_paths declared"]
    # Both facts are reported: the item has no commands *and* the shape is wrong.
    # Returning early on ``None`` hid the second half behind ``runnable``'s refusal.
    assert r.validate_contract({"id": "x", "write_paths": ["a.py"]}) == [
        "no acceptance_commands declared",
        "acceptance_commands must be a list of argv lists"]


def test_a_shell_string_or_a_network_command_is_refused():
    assert any("shell string" in p for p in r.validate_contract(
        _contract(acceptance_commands=["python -m pytest -q"])))

    shell = r.validate_contract(_contract(
        acceptance_commands=[["python", "-c", "print(1) && print(2)"]]))
    assert any("shell operators" in p for p in shell), shell

    browser = r.validate_contract(_contract(
        acceptance_commands=[["python", "-m", "pytest", "chromeconnect/test_x.py"]]))
    assert any("forbidden command token" in p for p in browser), browser

    network = r.validate_contract(_contract(
        acceptance_commands=[["curl", "https://example.test/x"]]))
    assert any("forbidden command token" in p for p in network), network
