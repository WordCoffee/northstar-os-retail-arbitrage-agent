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
    # The runtime tree is never a candidate's work: production ignores
    # state/author/ and writes under state/tys_runner/, so the fixture repo does
    # the same. Without this, every cycle would look like it wrote its own log.
    (tmp_path / ".gitignore").write_text("state/\n__pycache__/\n", encoding="utf-8")
    queue = {
        "phase": "C", "cycle": 0,
        "items": [
            # `done.flag` is the product of the work and therefore part of the
            # declared scope: the evaluator refuses a candidate that writes
            # outside write_paths, so the fixture declares what the worker makes.
            {"id": "runnable", "title": "do a thing", "status": "pending", "priority": 900,
             "next": "make the check pass",
             "write_paths": ["Northstar_backend/x.py", "done.flag"],
             # No ';' in the payload: the contract policy refuses a shell operator
             # anywhere in an argv token, and a fixture should use a contract the
             # loop would actually accept. A newline is not a shell operator.
             "acceptance_commands": [[
                 "python", "-c",
                 "import pathlib, sys\n"
                 "sys.exit(0 if pathlib.Path('done.flag').exists() else 1)",
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
    # A real git repo, because the restore path uses git rather than a memory
    # snapshot (a snapshot deleted files it had never seen).
    import subprocess as sp

    def g(*a):
        sp.run(["git", *a], cwd=str(tmp_path), capture_output=True, text=True)

    g("init")
    g("add", "-A")
    g("-c", "user.email=t@example.test", "-c", "user.name=test", "commit", "-m", "base")
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


def test_a_malformed_contract_is_refused_at_dispatch_not_by_a_crash(root):
    """The C3 probe found this: a shell-string contract passed ``runnable``, reached
    the pre-run gate and took the launcher down with FileNotFoundError."""
    queue = r.load_queue()
    item = next(i for i in queue["items"] if i["id"] == "runnable")
    item["acceptance_commands"] = "python -m pytest -q"
    r._write(r.QUEUE, queue)

    def explode(*_args, **_kwargs):
        raise AssertionError("a malformed contract must never reach the worker")

    out = L._run_cycle(worker=explode, dry_run=False, cycle_budget=1)

    assert out["skipped"] is True
    assert out["reason"] == "invalid_contract"
    after = r.load_queue()
    assert next(i for i in after["items"] if i["id"] == "runnable")["status"] == "pending"
    assert not r.LEASE.exists()


def test_a_contract_is_built_only_from_declared_fields(root, capsys):
    r.cmd_next()
    brief = json.loads(L.BRIEF.read_text(encoding="utf-8"))["brief"]
    item = next(i for i in r.load_queue()["items"] if i["id"] == brief["item"])
    contract = L.task_contract(item, brief)
    assert contract["objective"] == "make the check pass"
    assert contract["write_paths"] == ["Northstar_backend/x.py", "done.flag"]
    assert contract["acceptance_commands"][0][0] == "python"


def test_the_contract_carries_the_check_pin_it_used_to_drop():
    """A12 dropped check_sha256 by re-listing fields; that disabled the tamper gate."""
    item = {"id": "pin", "next": "pin the check", "write_paths": ["pkg/check.py"],
            "acceptance_commands": [["python", "pkg/check.py"]],
            "check_sha256": "a" * 64}
    contract = L.task_contract(item, {"cycle": 7}, pre_changed=["other/lane.py"])
    assert contract["check_sha256"] == "a" * 64
    assert contract["pre_changed"] == ["other/lane.py"]
    assert contract["pre_changed_source"] == "dispatch"
    assert contract["_cycle"] == 7


# ------------------------------------------------------- the evaluator is the judge
@pytest.fixture()
def repo_with_scope(tmp_path, monkeypatch):
    """A real git repo where `pkg/x.py` is in scope and `pkg/test_x.py` is not."""
    import subprocess as sp

    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "x.py").write_text("original\n", encoding="utf-8")
    (tmp_path / "pkg" / "test_x.py").write_text("def test_x():\n    assert True\n",
                                                encoding="utf-8")
    (tmp_path / "pkg" / "check.py").write_text("raise SystemExit(1)\n", encoding="utf-8")
    (tmp_path / ".gitignore").write_text("state/\n__pycache__/\n", encoding="utf-8")
    sp.run(["git", "init"], cwd=str(tmp_path), capture_output=True, text=True)
    sp.run(["git", "add", "-A"], cwd=str(tmp_path), capture_output=True, text=True)
    sp.run(["git", "-c", "user.email=t@example.test", "-c", "user.name=test",
            "commit", "-m", "base"], cwd=str(tmp_path), capture_output=True, text=True)
    monkeypatch.setattr(L, "ROOT", tmp_path)
    return tmp_path


def _contract(write_paths=None, **extra):
    base = {"id": "c", "write_paths": write_paths or ["pkg/x.py"],
            "acceptance_commands": [["python", "-c", "print('ok')"]],
            "pre_changed": [], "pre_changed_source": "dispatch"}
    base.update(extra)
    return base


def test_a_candidate_that_edits_only_write_paths_passes_scope(repo_with_scope):
    repo = repo_with_scope
    (repo / "pkg" / "x.py").write_text("changed\n", encoding="utf-8")
    out = L.judge_cycle(contract=_contract(), item_id="c1", candidate_id="1", repo=repo)
    assert out["ok"] is True and out["gate"] == "pass"
    assert out["live"]["gate"] == "pass"
    assert out["frozen"].endswith(".json")


def test_a_candidate_that_edits_a_test_file_is_out_of_scope(repo_with_scope):
    """Declared or not, a candidate may not edit the suite that judges it."""
    repo = repo_with_scope
    (repo / "pkg" / "test_x.py").write_text("def test_x():\n    assert True  # weakened\n",
                                            encoding="utf-8")
    out = L.judge_cycle(contract=_contract(["pkg/x.py", "pkg/test_x.py"]),
                        item_id="c2", candidate_id="1", repo=repo)
    assert out["ok"] is False and out["gate"] == "out_of_scope"
    assert "test module" in out["detail"]


def test_a_frozen_contract_carries_the_check_pin_and_the_dispatch_source(repo_with_scope):
    """The pin must survive into the artifact, or the tamper gate cannot fire."""
    import hashlib

    repo = repo_with_scope
    pinned = hashlib.sha256((repo / "pkg" / "check.py").read_bytes()).hexdigest()
    contract = _contract(["pkg/check.py"],
                         acceptance_commands=[["python", "pkg/check.py"]],
                         check_sha256=pinned,
                         pre_changed=["someone/else.py"])
    # the candidate rewrites the check so the check passes
    (repo / "pkg" / "check.py").write_text("raise SystemExit(0)\n", encoding="utf-8")
    out = L.judge_cycle(contract=contract, item_id="pin", candidate_id="1", repo=repo)
    assert out["gate"] == "check_tampered"
    record = json.loads(next((repo / "state" / "author" / "pin").glob("cand_*.json"))
                        .read_text(encoding="utf-8"))
    assert record["contract"]["check_sha256"] == pinned
    assert record["pre_changed_source"] == "dispatch"
    assert record["pre_changed"] == ["someone/else.py"]


def test_another_lanes_dirty_file_is_excused_by_the_dispatch_snapshot(repo_with_scope):
    repo = repo_with_scope
    (repo / "pkg" / "other_lane.py").write_text("someone else's work\n", encoding="utf-8")
    (repo / "pkg" / "x.py").write_text("changed\n", encoding="utf-8")

    refused = L.judge_cycle(contract=_contract(), item_id="strict",
                            candidate_id="1", repo=repo)
    assert refused["gate"] == "out_of_scope"          # nobody excused it

    excused = L.judge_cycle(contract=_contract(pre_changed=["pkg/other_lane.py"]),
                            item_id="excused", candidate_id="1", repo=repo)
    assert excused["ok"] is True and excused["gate"] == "pass"


def test_the_dispatch_snapshot_names_the_whole_dirty_tree(repo_with_scope):
    repo = repo_with_scope
    (repo / "pkg" / "x.py").write_text("dirty before dispatch\n", encoding="utf-8")
    (repo / "pkg" / "new_lane").mkdir()
    (repo / "pkg" / "new_lane" / "scratch.py").write_text("x\n", encoding="utf-8")
    (repo / "state" / "tys_runner").mkdir(parents=True, exist_ok=True)
    (repo / "state" / "tys_runner" / "lease.json").write_text("{}", encoding="utf-8")

    snap = L.dispatch_snapshot()
    assert "pkg/x.py" in snap                  # a dirty tracked file
    assert "pkg/new_lane/scratch.py" in snap    # untracked, listed by ls-files
    assert not [p for p in snap if p.startswith("state/")]   # ignored runtime state


def test_a_cycle_is_judged_by_the_evaluator_not_by_the_launcher(root):
    out = L._run_cycle(worker=_worker({}), dry_run=False, cycle_budget=3)
    assert out["shipped"] is True
    assert out["gate"] == "pass"
    frozen = list((root / "state" / "author" / "runnable").glob("cand_*.json"))
    assert frozen, "a cycle must freeze its candidate before it is judged"
    record = json.loads(frozen[0].read_text(encoding="utf-8"))
    assert record["pre_changed_source"] == "dispatch"
    assert record["scored"]["gate"] == "pass"
    assert record["contract"]["pre_changed_source"] == "dispatch"


def test_a_cycle_that_edits_a_test_file_is_refused_out_of_scope(root):
    def worker(task_path, result_path):
        (root / "Northstar_backend").mkdir(parents=True, exist_ok=True)
        (root / "Northstar_backend" / "test_sneaky.py").write_text(
            "def test_sneaky():\n    assert True\n", encoding="utf-8")
        (root / "done.flag").write_text("done", encoding="utf-8")
        result_path.write_text(json.dumps({"ok": True, "steps": 1}), encoding="utf-8")
        return 0

    out = L._run_cycle(worker=worker, dry_run=False, cycle_budget=3)
    assert out["shipped"] is False
    assert out["gate"] == "out_of_scope"


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
    import subprocess as sp

    sp.run(["git", "add", "-A"], cwd=str(root), capture_output=True)
    sp.run(["git", "-c", "user.email=t@example.test", "-c", "user.name=test",
            "commit", "-m", "x"], cwd=str(root), capture_output=True)

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
    # And it is parked, not deferred: a soft deferral re-admits it immediately and
    # the probe measured 40 acceptance runs in 54 s from that loop.
    item = next(i for i in r.load_queue()["items"] if i["id"] == "runnable")
    assert item["status"] == "needs_author"
    assert item["needs_author"].startswith("check_already_green:")


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


# ------------------------------------------------------------- token accounting
def _session_worker(session_id="ses_test", **extra):
    """A worker whose result names the session the model actually ran in."""
    def run(task_path, result_path):
        root = Path(task_path).resolve().parents[2]
        (root / "done.flag").write_text("done", encoding="utf-8")
        payload = {"ok": True, "steps": 3, "evidence": [],
                   "session_id": session_id, "text": "did the thing", **extra}
        result_path.write_text(json.dumps(payload), encoding="utf-8")
        return 0
    return run


def _completion(root):
    return json.loads((root / "state" / "tys_runner" / "completion.json")
                      .read_text(encoding="utf-8"))


def test_the_session_estimate_is_what_the_cap_counts(root, monkeypatch):
    """Measured 2026-11-06: a real session was 180,803 tokens; the guess said 2,162."""
    monkeypatch.setattr(L.meter, "estimate_session", lambda sid, *a, **k: {
        "tokens": 180803, "source": "session_v2", "session_id": sid})
    out = L._run_cycle(worker=_session_worker(), dry_run=False, cycle_budget=3)
    assert out["shipped"] is True
    done = _completion(root)
    assert done["tokens"] == 180803
    assert done["tokens_source"] == "session_v2"
    evidence = list((root / "state" / "evidence").glob("cycle_*.json"))
    row = json.loads(evidence[0].read_text(encoding="utf-8"))
    assert row["tokens"] == 180803 and row["tokens_source"] == "session_v2"


def test_the_payload_estimate_is_the_fallback_when_the_store_answers_none(root, monkeypatch):
    """A missing measurement must not read as free, and must say it is an estimate."""
    monkeypatch.setattr(L.meter, "estimate_session", lambda sid, *a, **k: {
        "tokens": None, "source": "unavailable", "session_id": sid})
    out = L._run_cycle(worker=_session_worker(), dry_run=False, cycle_budget=3)
    assert out["shipped"] is True
    done = _completion(root)
    assert done["tokens_source"] == "payload_estimate"
    assert done["tokens"] > 0
    assert done["tokens"] != 180803          # not the session figure it never got


def test_a_meter_that_blows_up_degrades_to_the_labelled_estimate(monkeypatch):
    def boom(sid, *a, **k):
        raise RuntimeError("store locked")

    monkeypatch.setattr(L.meter, "estimate_session", boom)
    payload = {"session_id": "ses_x", "text": "abc"}
    got = L.measure_cycle_tokens(payload)
    assert got["source"] == "payload_estimate"
    assert got["tokens"] == L.meter.estimate_payload(payload) > 0


def test_the_measurement_prefers_the_store_and_labels_what_it_used(monkeypatch):
    monkeypatch.setattr(L.meter, "estimate_session", lambda sid, *a, **k: {
        "tokens": 180803, "source": "session_message", "session_id": sid})
    got = L.measure_cycle_tokens({"session_id": "ses_x", "text": "abc"})
    assert got == {"tokens": 180803, "source": "session_message", "session_id": "ses_x"}


def test_the_completion_payload_carries_a_positive_token_count(root, monkeypatch):
    """The runner's cap reads completion["tokens"]; a zero there is a soft cap."""
    monkeypatch.setattr(L.meter, "estimate_session", lambda sid, *a, **k: {
        "tokens": None, "source": "unavailable", "session_id": sid})
    L._run_cycle(worker=_worker({}), dry_run=False, cycle_budget=3)   # no session_id
    done = _completion(root)
    assert done["tokens"] > 0
    assert done["tokens_source"] == "payload_estimate"
    events = [json.loads(l) for l in
              (root / "state" / "tys_runner" / "launcher.jsonl")
              .read_text(encoding="utf-8").splitlines()]
    measured = [e for e in events if e["event"] == "tokens_measured"]
    assert measured and measured[-1]["tokens"] == done["tokens"]



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


def test_a_dead_deepseek_lane_stops_without_asking_llama_cpp(root, monkeypatch, capsys):
    """The deepseek lane is a CLI, so the local model server is not its preflight."""
    monkeypatch.setattr(L, "model_up", lambda *a, **k: False)      # llama.cpp is down
    monkeypatch.setattr(L, "deepseek_lane_up", lambda *a, **k: True)
    monkeypatch.setattr(L, "deepseek_worker", _worker({}))
    assert L.main(["--worker", "deepseek", "--max-cycles", "1", "--max-hours", "1"]) == 0
    hb = json.loads((root / "state/tys_runner/heartbeat.json").read_text(encoding="utf-8"))
    assert hb["reason"] != "model_lane_down"
    events = [json.loads(l)["event"] for l in
              (root / "state/tys_runner/launcher.jsonl").read_text(
                  encoding="utf-8").splitlines()]
    assert "model_lane_down" not in events


# ------------------------------------------------------------------ deepseek lane
STREAM = "\n".join([
    json.dumps({"type": "step_start", "sessionID": "ses_test",
                "part": {"type": "step-start"}}),
    json.dumps({"type": "text", "sessionID": "ses_test",
                "part": {"type": "text", "text": "pong"}}),
    json.dumps({"type": "step_finish", "sessionID": "ses_test",
                "part": {"reason": "stop", "cost": 0}}),
])


class _FakeCompleted:
    def __init__(self, stdout="", stderr="", returncode=0):
        self.stdout, self.stderr, self.returncode = stdout, stderr, returncode


def _fake_transport(monkeypatch, stdout=STREAM, stderr="", returncode=0):
    """Stand in for `opencode run`; records the command and the stdin it received."""
    seen = {}

    def run(cmd, **kwargs):
        seen["cmd"] = cmd
        seen["input"] = kwargs.get("input")
        return _FakeCompleted(stdout, stderr, returncode)

    from types import SimpleNamespace

    monkeypatch.setattr(L, "subprocess", SimpleNamespace(run=run))
    return seen


def _task(root):
    path = root / "state" / "tys_runner" / "task.json"
    path.write_text(json.dumps({
        "objective": "make the check pass",
        "write_paths": ["Northstar_backend/x.py"],
        "acceptance_commands": [["python", "-c", "print(1)"]],
    }), encoding="utf-8")
    return path


def test_the_worker_records_the_text_the_transport_returned(root, monkeypatch):
    """The regression this unit exists for: exit 0 with `text: ""`.

    `opencode run --format json` puts the answer in `part.text`; a reader that
    only looked at `event["text"]` recorded nothing, and the launcher shipped a
    dispatch with no captured output.
    """
    seen = _fake_transport(monkeypatch)
    monkeypatch.setattr(L, "_session_model", lambda sid, *a, **k: {
        "agent": "tys", "model_id": "deepseek-v4.1-flash",
        "provider": "opencode-go", "variant": None, "cost": 0.0,
        "tokens": None, "source": "session_message"})
    result = root / "state" / "worker_result.json"
    code = L.deepseek_worker(_task(root), result)
    out = json.loads(result.read_text(encoding="utf-8"))
    assert code == 0
    assert out["text"] == "pong"
    assert out["ok"] is True and out["errors"] == []
    assert out["session_id"] == "ses_test"
    assert out["model"]["model_id"] == "deepseek-v4.1-flash"
    assert out["model_provenance_ok"] is True
    assert out["seconds"] >= 0
    # the prompt goes on stdin, and the agent/format flags are on the command
    assert "-agent" not in seen["input"] and "Northstar OS autonomy worker" in seen["input"]
    assert "--agent" in seen["cmd"] and "--format" in seen["cmd"]
    assert out["exe"]


def test_an_empty_answer_is_a_failure_not_a_silent_pass(root, monkeypatch):
    _fake_transport(monkeypatch, stdout="")
    monkeypatch.setattr(L, "_session_model", lambda sid, *a, **k: None)
    result = root / "state" / "worker_result.json"
    code = L.deepseek_worker(_task(root), result)
    out = json.loads(result.read_text(encoding="utf-8"))
    assert code == 0                      # the CLI exited 0 ...
    assert out["ok"] is False             # ... but that is not a usable answer
    assert out["errors"][0].startswith("empty_text")
    assert out["model_provenance_ok"] is False


def test_a_transport_error_event_is_reported(root, monkeypatch):
    stream = json.dumps({"type": "error", "sessionID": "ses_test",
                         "error": "model_not_found"})
    _fake_transport(monkeypatch, stdout=stream)
    monkeypatch.setattr(L, "_session_model", lambda sid, *a, **k: None)
    result = root / "state" / "worker_result.json"
    L.deepseek_worker(_task(root), result)
    out = json.loads(result.read_text(encoding="utf-8"))
    assert out["ok"] is False and "model_not_found" in out["errors"]


def test_provenance_comes_from_the_assistant_message_row(root, tmp_path):
    """Measured 2026-11-06: `session_v2.model` is NULL for `run` sessions."""
    import sqlite3

    db = tmp_path / "opencode.db"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE session_v2 (id TEXT, agent TEXT, model TEXT, cost REAL)")
    conn.execute("CREATE TABLE session_message "
                 "(id TEXT, session_id TEXT, type TEXT, seq INT, data TEXT)")
    conn.execute("INSERT INTO session_v2 VALUES ('ses_x','tys',NULL,1.2e-05)")
    conn.execute("INSERT INTO session_message VALUES ('m1','ses_x','assistant',6,?)", (json.dumps({
        "agent": "tys", "cost": 0,
        "model": {"id": "deepseek-v4.1-flash", "providerID": "opencode-go"},
        "tokens": {"input": 11063, "output": 4}}),))
    conn.commit()
    conn.close()

    info = L._session_model("ses_x", db)
    assert info["model_id"] == "deepseek-v4.1-flash"
    assert info["provider"] == "opencode-go"
    assert info["source"] == "session_message"
    assert L._session_model("ses_missing", db) is None


def test_the_packaged_exe_is_preferred_over_the_npm_shim(tmp_path, monkeypatch):
    """A .cmd shim re-parses arguments through a shell; the real exe does not."""
    import sys as _sys

    if _sys.platform != "win32":
        pytest.skip("npm shim layout is Windows-specific")
    bin_dir = tmp_path / "cli" / "bin"
    bin_dir.mkdir(parents=True)
    (bin_dir / "opencode.exe").write_text("", encoding="utf-8")
    shim_dir = tmp_path / "npm"
    shim_dir.mkdir()
    (shim_dir / "opencode.cmd").write_text("@echo off\n", encoding="utf-8")
    monkeypatch.delenv("TY_OPENCODE_EXE", raising=False)
    monkeypatch.setenv("PATH", str(shim_dir) + ";" + str(tmp_path / "cli"))
    # the packaged layout the test describes: <shim dir>/node_modules/@opencode/cli/bin
    packaged = shim_dir / "node_modules" / "@opencode" / "cli" / "bin"
    packaged.mkdir(parents=True)
    (packaged / "opencode.exe").write_text("", encoding="utf-8")
    assert L._opencode_exe().endswith("opencode.exe")
