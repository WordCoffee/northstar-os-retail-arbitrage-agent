"""The generator decides what counts as work: the T0..T5 ladder, dedupe, brakes.

What is **real** here and what is injected:

* **Real**: the queue on disk (a temporary ``reports/ty/autonomy_queue.json``),
  ``tys_runner``'s own ``_write``/``select_next``/``validate_contract``, the
  emission ledger, the lock file, ``tys_author.derive`` (the scope deriver reads
  a real traceback and a real source file in the temporary repo), and
  ``improvement_backlog.check`` for the backlog tier.
* **Injected**: the subprocess runner. ``FakeRun`` answers by exact argv, so no
  probe, scan or pytest is ever started - a test that shelled out to the real
  probes would measure the machine instead of the generator.

The temporary root is monkeypatched onto the module constants exactly like
``test_tys_runner.py``'s ``root`` fixture, so nothing can reach the real queue,
the real ``state/`` directory or the real probe output.
"""
from __future__ import annotations

import importlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(REPO / "scripts"))

import tys_generator as G  # noqa: E402
import tys_probes as P  # noqa: E402
import tys_runner as R  # noqa: E402

GATE = G.GATE_DEP

#: A pytest-shaped failure whose own frame is a real file in the temporary repo.
#: ``Northstar_backend/lib/thing.py`` is deliberately not under ``tests/`` and not
#: a ``tools/tys_*`` policy path, so the deriver may name it as a write scope.
TRACEBACK = (
    "============================= test session starts =============================\n"
    "Northstar_backend/test_tys_runner.py:44: in test_selection\n"
    "    nxt = r.select_next()\n"
    "Northstar_backend/lib/thing.py:12: in helper\n"
    "    raise AssertionError('red')\n"
    "E   AssertionError: red\n"
)

SCAN = " ".join(G.SCAN_ARGV)


# ------------------------------------------------------------------- the fixture
class FakeRun:
    """An injected command runner: it answers by exact argv and starts nothing."""

    def __init__(self, routes=None, default=(0, "")):
        self.routes = dict(routes or {})
        self.default = default
        self.calls = []

    def __call__(self, cmd, cwd=None, timeout=None, capture_output=True,
                 text=True, **kw):
        parts = [str(part) for part in cmd]
        self.calls.append(parts)
        code, out = self.routes.get(" ".join(parts), self.default)
        return subprocess.CompletedProcess(parts, code, out, "")


def probe_argv(probe_id: str) -> str:
    spec = P.probe(probe_id)
    assert spec is not None, f"{probe_id} is not in the probe table"
    return " ".join(spec["argv"])


def green_scan(**over):
    """A scanner that saw 1043 files and found nothing: green, and not vacuous."""
    report = {"schema": "northstar.readiness_scan.v1", "checks": ["dead_module"],
              "total": 0, "files_scanned": 1043, "findings": []}
    report.update(over)
    return json.dumps(report)


def make_run(**overrides):
    routes = {SCAN: (0, green_scan())}
    routes.update(overrides)
    return FakeRun(routes)


def red_incident_probe(**overrides):
    """The incident probe is red *with* a traceback the deriver can read."""
    routes = {probe_argv("tys-runner-tests"): (1, TRACEBACK)}
    routes.update(overrides)
    return make_run(**routes)


@pytest.fixture()
def root(tmp_path, monkeypatch):
    (tmp_path / "reports" / "ty").mkdir(parents=True)
    (tmp_path / "state" / "tys_runner").mkdir(parents=True)
    (tmp_path / "state" / "author").mkdir(parents=True)
    (tmp_path / "state" / "backlog").mkdir(parents=True)
    (tmp_path / "state" / "probes").mkdir(parents=True)
    (tmp_path / "Northstar_backend" / "lib").mkdir(parents=True)
    (tmp_path / "Northstar_backend" / "lib" / "thing.py").write_text(
        "VALUE = 1\n", encoding="utf-8")

    queue = {
        "phase": "C", "cycle": 0,
        "items": [{"id": GATE, "title": "the work generator", "status": "pending",
                   "priority": 1130}],
    }
    queue_path = tmp_path / "reports" / "ty" / "autonomy_queue.json"
    queue_path.write_text(json.dumps(queue, indent=2) + "\n", encoding="utf-8")

    monkeypatch.setattr(G, "ROOT", tmp_path)
    monkeypatch.setattr(G, "QUEUE", queue_path)
    monkeypatch.setattr(G, "STATE", tmp_path / "state" / "tys_generator")
    monkeypatch.setattr(G, "EMITTED", tmp_path / "state" / "tys_generator" / "emitted.jsonl")
    monkeypatch.setattr(G, "LOCK", tmp_path / "state" / "tys_generator" / "lock.json")
    monkeypatch.setattr(G, "PROPOSALS", tmp_path / "state" / "backlog" / "proposals.json")
    monkeypatch.setattr(G, "IMPROVEMENTS", tmp_path / "state" / "backlog" / "improvements.json")
    monkeypatch.setattr(G, "GAPS", tmp_path / "state" / "intel" / "gaps.json")
    monkeypatch.setattr(G, "REGRESSIONS", tmp_path / "state" / "probes" / "regressions.json")
    monkeypatch.setattr(G, "NEEDS_YOU", tmp_path / "reports" / "ty" / "needs_you.md")
    monkeypatch.setattr(G, "STOP", tmp_path / "STOP")

    # tys_runner is the same module object the generator imports lazily, so the
    # queue, the ledger and the STOP marker all point at the temporary root.
    monkeypatch.setattr(R, "QUEUE", queue_path)
    monkeypatch.setattr(R, "STATE_DIR", tmp_path / "state" / "tys_runner")
    monkeypatch.setattr(R, "LEDGER", tmp_path / "state" / "tys_runner" / "ledger.json")
    monkeypatch.setattr(R, "LEASE", tmp_path / "state" / "tys_runner" / "lease.json")
    monkeypatch.setattr(R, "CHECKPOINT", tmp_path / "state" / "tys_runner" / "checkpoint.json")
    monkeypatch.setattr(R, "SESSIONS", tmp_path / "state" / "tys_runner" / "sessions.jsonl")
    monkeypatch.setattr(R, "HANDOFF", tmp_path / "reports" / "ty" / "cycle_handoff.json")
    monkeypatch.setattr(R, "STOP", tmp_path / "STOP")
    return tmp_path


# ---------------------------------------------------------------------- helpers
def queue_of(root) -> dict:
    return json.loads((root / "reports" / "ty" / "autonomy_queue.json")
                      .read_text(encoding="utf-8"))


def generated(root):
    return [item for item in queue_of(root)["items"]
            if item.get("generated_by") == G.MARK]


def by_key(root, key):
    return next((item for item in queue_of(root)["items"]
                 if G.dedupe_key(item) == key), None)


def seed(root, **item):
    queue = queue_of(root)
    queue["items"].append(item)
    G._plain_write(root / "reports" / "ty" / "autonomy_queue.json", queue)


def set_status(root, key, status):
    queue = queue_of(root)
    for item in queue["items"]:
        if G.dedupe_key(item) == key:
            item["status"] = status
    G._plain_write(root / "reports" / "ty" / "autonomy_queue.json", queue)


def drop(root, key):
    queue = queue_of(root)
    queue["items"] = [item for item in queue["items"] if G.dedupe_key(item) != key]
    G._plain_write(root / "reports" / "ty" / "autonomy_queue.json", queue)


def write_proposals(root, *proposals):
    G._plain_write(root / "state" / "backlog" / "proposals.json",
                   {"schema": "northstar.backlog_proposals.v1",
                    "proposals": list(proposals)})


def proposal(nodeid="Northstar_backend/test_tys_runner.py::test_selection", **over):
    item = {
        "id": "fix-" + nodeid.replace("::", "-").replace("/", "-"),
        "name": f"Make {nodeid} pass",
        "acceptance_commands": [["python", "-m", "pytest", "-q", nodeid]],
        "write_paths": [],
        "blocked": "needs_author: name the write scope",
    }
    item.update(over)
    return item


def improvement(**over):
    item = {
        "id": "imp-example",
        "theme": "tooling",
        "priority": "P2",
        "status": "ready",
        "title": "Use the example helper",
        "problem": "Northstar_backend/lib/thing.py:12 is never called",
        "evidence": ["Northstar_backend/lib/thing.py:12"],
        "proposed_change": "call the helper",
        "write_paths": ["Northstar_backend/lib/thing.py"],
        "verification": "the example test stays green",
        "checks": [{"cmd": ["python", "-m", "pytest", "-q",
                            "Northstar_backend/test_tys_generator.py"]}],
        "risk": "low",
    }
    item.update(over)
    return item


def write_backlog(root, *items):
    G._plain_write(root / "state" / "backlog" / "improvements.json",
                   {"schema": "northstar.improvement_backlog.v1", "items": list(items)})


def scan_report(line, check="dead_module", path="northstar-os-ui/src/lib/orphan.js"):
    return json.dumps({"schema": "northstar.readiness_scan.v1", "checks": [check],
                       "total": 1, "files_scanned": 12,
                       "findings": [{"check": check, "file": path, "line": line,
                                     "message": "never imported", "severity": "medium"}]})


# --------------------------------------------------------------- the ladder
def test_an_empty_queue_gets_exactly_one_dispatchable_item(root):
    out = G.generate(probe_runner=red_incident_probe())

    assert out["ok"] is True, out
    assert out["reason"] == "generated"
    assert out["tier"] == "T0"
    assert len(out["added"]) == 1
    items = generated(root)
    assert len(items) == 1
    item = items[0]
    assert item["tier"] == "T0"
    assert item["status"] == "pending"
    assert 1300 <= item["priority"] <= 1399
    assert item["depends_on"] == []
    # The queue's own selector hands the item back, ahead of the gate item.
    assert R.select_next()["id"] == item["id"]


def test_a_generated_item_passes_the_launcher_contract(root):
    G.generate(probe_runner=red_incident_probe())

    item = generated(root)[0]
    assert R.validate_contract(item) == []
    assert G._dispatchable(item) is True
    assert item["write_paths"] == ["Northstar_backend/lib/thing.py"]
    assert item["acceptance_commands"] == [P.probe("tys-runner-tests")["argv"]]


def test_a_probe_red_with_a_traceback_is_dispatchable(root):
    """A red check with a real frame yields a scope: that is a task, not a note."""
    G.generate(probe_runner=red_incident_probe())

    item = generated(root)[0]
    assert item["status"] == "pending"
    assert item["scope_derivation"].endswith("derivation.json")
    assert item["check_sha256"] is None or isinstance(item["check_sha256"], str)


def test_a_probe_red_without_a_traceback_needs_an_author(root):
    runner = make_run(**{probe_argv("tys-runner-tests"): (1, "E   AssertionError: red\n")})

    out = G.generate(probe_runner=runner)

    assert out["ok"] is True
    item = generated(root)[0]
    assert item["status"] == "needs_author"
    assert "scope not derived (scope_unproven)" in item["needs_author"]
    assert not item.get("acceptance_commands")
    assert G._dispatchable(item) is False


def test_a_second_call_adds_nothing(root):
    runner = red_incident_probe()
    assert G.generate(probe_runner=runner)["ok"] is True
    before = (root / "reports" / "ty" / "autonomy_queue.json").read_text(encoding="utf-8")

    second = G.generate(probe_runner=runner)

    assert second["ok"] is False
    assert second["reason"] == "duplicate"
    assert second["added"] == []
    assert (root / "reports" / "ty" / "autonomy_queue.json").read_text(
        encoding="utf-8") == before


def test_dedupe_ignores_line_drift(root):
    """A finding that moved down a file is the same question, not a new one."""
    first = {"scan_check": "dead_module", "scan_path": "ui/x.js", "scan_line": 10}
    second = {"scan_check": "dead_module", "scan_path": "ui/x.js", "scan_line": 99}
    assert G.dedupe_key(first) == G.dedupe_key(second) == "scan:dead_module:ui/x.js"
    # A Windows node id and a posix one name the same test: one key, not two.
    windows = {"nodeid": "Northstar_backend\\tests\\test_x.py::test_y"}
    posix = {"nodeid": "Northstar_backend/tests/test_x.py::test_y"}
    assert G.dedupe_key(windows) == G.dedupe_key(posix)

    G.generate(probe_runner=make_run(**{SCAN: (0, scan_report(10))}))
    finding = generated(root)[0]
    # A scan finding has no check and no derivable scope: it is always a note to a
    # human, never something the loop can be dispatched to "fix".
    assert finding["status"] == "needs_author"
    assert "name the check that proves dead_module" in finding["needs_author"]
    assert G._dispatchable(finding) is False

    out = G.generate(probe_runner=make_run(**{SCAN: (0, scan_report(99))}))

    assert out["reason"] == "promoted"
    assert len(generated(root)) == 1
    assert generated(root)[0]["scan_line"] == 10, "promotion refreshes, it does not replace"
    assert generated(root)[0]["depends_on"] == [GATE]


def test_a_needs_author_item_is_promoted_in_place(root):
    key = "pytest:Northstar_backend/test_tys_example.py::test_x"
    seed(root, id="gen-existing", status="needs_author", attempts=3, priority=700,
         dedupe_key=key, needs_author="the old reason")
    write_proposals(root, proposal(nodeid="Northstar_backend/test_tys_example.py::test_x"))
    before = len(queue_of(root)["items"])

    out = G.generate(probe_runner=make_run(
        **{"python -m pytest -q Northstar_backend/test_tys_example.py::test_x": (1, TRACEBACK)}))

    assert out["reason"] == "promoted"
    item = by_key(root, key)
    assert item["id"] == "gen-existing"
    assert item["attempts"] == 3, "promotion never resets the attempt count"
    assert item["needs_author"] != "the old reason"
    assert len(queue_of(root)["items"]) == before, "promotion never re-emits"


def test_all_green_is_starvation_and_writes_nothing(root):
    before = (root / "reports" / "ty" / "autonomy_queue.json").read_text(encoding="utf-8")

    out = G.generate(probe_runner=make_run())

    assert out["ok"] is False
    assert out["reason"] == "starvation"
    assert set(out["tiers"]) == set(G.TIERS)
    assert "files scanned" in out["tiers"]["T2"]["detail"]
    assert out["tiers"]["T4"]["state"] == "no_source"
    assert (root / "reports" / "ty" / "autonomy_queue.json").read_text(
        encoding="utf-8") == before
    assert not G.EMITTED.exists()


def test_a_vacuous_scanner_is_the_finding(root):
    """Zero findings from a scanner that saw zero files is a defect, not silence."""
    runner = make_run(**{SCAN: (0, green_scan(total=0, files_scanned=0))})

    out = G.generate(probe_runner=runner)

    assert out["ok"] is True
    item = generated(root)[0]
    assert item["dedupe_key"] == "probe:discovery-vacuous"
    assert item["tier"] == "T5"
    assert 100 <= item["priority"] <= 139
    assert item["status"] == "needs_author"
    assert "0 files" in item["needs_author"]


def test_an_absent_intel_plane_is_no_source(root):
    got = G.discover("T4", probe_runner=make_run(), now=None)

    assert got["state"] == "no_source"
    assert got["candidates"] == []
    assert "gaps.json" in got["detail"]


def test_an_intel_gap_needs_a_falsifiable_argv_to_be_work(root):
    G._plain_write(root / "state" / "intel" / "gaps.json",
                   {"gaps": [{"id": "gap-vague", "title": "somebody should look"}]})

    got = G.discover("T4", probe_runner=make_run())

    assert got["state"] == "green"
    assert got["candidates"] == []


def test_an_intel_gap_with_a_falsifiable_argv_becomes_a_gated_task(root):
    command = ["python", "-m", "pytest", "-q",
               "Northstar_backend/test_tys_example.py::test_gap"]
    G._plain_write(root / "state" / "intel" / "gaps.json",
                   {"gaps": [{"id": "gap-1", "title": "A gap with a check",
                              "argv": command}]})

    out = G.generate(probe_runner=make_run(**{" ".join(command): (1, TRACEBACK)}))

    assert out["tier"] == "T4"
    item = generated(root)[0]
    assert item["dedupe_key"] == "intel:gap-1"
    assert item["status"] == "pending"
    assert item["write_paths"] == ["Northstar_backend/lib/thing.py"]
    assert item["depends_on"] == [GATE]


def test_generation_refuses_under_stop(root):
    (root / "STOP").write_text("stopped by the operator\n", encoding="utf-8")
    before = (root / "reports" / "ty" / "autonomy_queue.json").read_text(encoding="utf-8")

    out = G.generate(probe_runner=red_incident_probe())

    assert out["ok"] is False
    assert out["reason"] == "STOP"
    assert out["added"] == []
    assert (root / "reports" / "ty" / "autonomy_queue.json").read_text(
        encoding="utf-8") == before


def test_a_live_generator_lock_is_busy(root, monkeypatch):
    G.LOCK.parent.mkdir(parents=True, exist_ok=True)
    G.LOCK.write_text(json.dumps({"pid": 424242}), encoding="utf-8")
    monkeypatch.setattr(G, "_pid_alive", lambda pid: True)

    out = G.generate(probe_runner=red_incident_probe())

    assert out["reason"] == "busy"
    assert json.loads(G.LOCK.read_text(encoding="utf-8"))["pid"] == 424242
    assert generated(root) == []


def test_a_dead_generator_lock_is_reclaimed(root, monkeypatch):
    G.LOCK.parent.mkdir(parents=True, exist_ok=True)
    G.LOCK.write_text(json.dumps({"pid": 999999}), encoding="utf-8")
    monkeypatch.setattr(G, "_pid_alive", lambda pid: False)

    out = G.generate(probe_runner=red_incident_probe())

    assert out["ok"] is True
    assert not G.LOCK.exists(), "the generator releases its own lock"


def test_reopen_is_capped_and_attempts_never_reset(root):
    key = "probe:tys-runner-tests"
    seed(root, id="gen-reopen", status="done", attempts=2, reopens=0,
         priority=1300, dedupe_key=key)
    runner = red_incident_probe()

    first = G.generate(probe_runner=runner)
    assert first["reason"] == "reopened"
    item = by_key(root, key)
    assert item["status"] == "pending"
    assert item["reopens"] == 1
    assert item["attempts"] == 2

    set_status(root, key, "done")
    second = G.generate(probe_runner=runner)
    assert second["reason"] == "reopened"
    item = by_key(root, key)
    assert item["reopens"] == 2
    assert item["attempts"] == 2

    set_status(root, key, "done")
    third = G.generate(probe_runner=runner)
    assert third["reason"] == "reopen_capped"
    item = by_key(root, key)
    assert item["status"] == "needs_author"
    assert item["attempts"] == 2, "an escalation never rewrites the history"
    assert "reopened 2 times" in item["needs_author"]


def test_a_parked_item_keeps_its_rejection_cap_reason(root):
    """A13 parks at the strike limit; the generator may not overwrite that reason."""
    key = "probe:tys-runner-tests"
    seed(root, id="gen-parked", status="needs_author", attempts=3, priority=1300,
         dedupe_key=key, needs_author="rejection_cap:target_red x3",
         parked_signature="sig-abc", parked_cycle=7)

    out = G.generate(probe_runner=red_incident_probe())

    assert out["reason"] == "promoted"
    item = by_key(root, key)
    assert item["needs_author"] == "rejection_cap:target_red x3"
    assert item["parked_signature"] == "sig-abc"
    assert item["attempts"] == 3


def test_three_reverts_without_a_ledger_need_a_human(root):
    """A13 owns rejection_streak; until then the item's own record is the fallback."""
    key = "probe:tys-runner-tests"
    seed(root, id="gen-wall", status="pending", attempts=3, last_result="reverted",
         priority=1300, dedupe_key=key)

    out = G.generate(probe_runner=red_incident_probe())

    assert out["reason"] == "reverts"
    item = by_key(root, key)
    assert item["status"] == "needs_author"
    assert item["attempts"] == 3
    assert "3 consecutive reverts" in item["needs_author"]


def test_a_deleted_key_is_reemitted_once_and_then_escalated(root):
    key = "probe:tys-runner-tests"
    runner = red_incident_probe()
    G.generate(probe_runner=runner)

    drop(root, key)
    again = G.generate(probe_runner=runner)
    assert again["reason"] == "reemitted"
    assert by_key(root, key) is not None

    drop(root, key)
    twice = G.generate(probe_runner=runner)
    assert twice["reason"] == "deleted_twice"
    item = by_key(root, key)
    assert item["status"] == "needs_author"
    assert "deleted twice" in item["needs_author"]


# ------------------------------------------------------------------ the gate
def test_a_dirty_target_is_refused_rather_than_queued(root):
    """Someone else owns those bytes; a queued item would only be refused later."""
    queue = queue_of(root)
    queue["dirty_targets"] = ["Northstar_backend/lib/thing.py"]
    G._plain_write(root / "reports" / "ty" / "autonomy_queue.json", queue)

    out = G.generate(probe_runner=red_incident_probe())

    assert out["ok"] is False
    assert out["reason"] == "targets_dirty"
    assert out["tier"] == "T0"
    assert generated(root) == []


def test_a_launcher_dirty_refusal_counts_as_a_dirty_target(root):
    seed(root, id="held", status="pending", priority=1300,
         blocked_reason="targets_dirty: Northstar_backend/lib/thing.py")

    out = G.generate(probe_runner=red_incident_probe())

    assert out["reason"] == "targets_dirty"
    assert generated(root) == []


def test_product_tiers_wait_on_the_generator_gate(root):
    write_backlog(root, improvement())

    out = G.generate(probe_runner=make_run())

    assert out["tier"] == "T3"
    item = generated(root)[0]
    assert item["depends_on"] == [GATE]
    assert item["status"] == "pending"
    assert R.validate_contract(item) == []


def test_product_work_is_refused_when_the_gate_item_is_absent(root):
    write_backlog(root, improvement())
    queue = queue_of(root)
    queue["items"] = [item for item in queue["items"] if item["id"] != GATE]
    G._plain_write(root / "reports" / "ty" / "autonomy_queue.json", queue)

    out = G.generate(probe_runner=make_run())

    assert out["ok"] is False
    assert out["reason"] == "gate_closed"
    assert out["tier"] == "T3"
    assert generated(root) == []


def test_floor_tiers_carry_no_dependency(root):
    runner = make_run(**{SCAN: (0, green_scan(total=0, files_scanned=0))})
    G.generate(probe_runner=runner)

    item = generated(root)[0]
    assert item["tier"] == "T5"
    assert item["depends_on"] == []


def test_an_owner_probe_is_not_supply(root):
    runner = make_run(**{probe_argv("disk-free"): (1, "2.1 GB free disk")})

    G.generate(probe_runner=runner)

    item = generated(root)[0]
    assert item["status"] == "needs_owner"
    assert "2.1 GB free disk" in item["needs_owner"]
    assert G.NEEDS_YOU.is_file()
    assert "disk-free" in G.NEEDS_YOU.read_text(encoding="utf-8")
    rows = [json.loads(line) for line in
            G.EMITTED.read_text(encoding="utf-8").splitlines()]
    assert rows[-1]["event"] == "emit-owner"
    assert G._emitted_today(None) == 0, "an owner ask is not generated supply"


# -------------------------------------------------------------- atomic append
def test_append_writes_the_item_and_the_emission_record(root):
    item = {"id": "gen-append", "dedupe_key": "probe:append-me", "priority": 1310,
            "status": "pending", "write_paths": ["Northstar_backend/lib/thing.py"],
            "acceptance_commands": [["python", "-m", "pytest", "-q", "t.py"]]}

    out = G.append_item(queue_of(root), item)

    assert out["ok"] is True
    assert by_key(root, "probe:append-me") is not None
    rows = [json.loads(line) for line in
            G.EMITTED.read_text(encoding="utf-8").splitlines()]
    assert rows[-1]["event"] == "emit"
    assert rows[-1]["key"] == "probe:append-me"


def test_append_rolls_back_when_the_readback_is_tampered(root, monkeypatch):
    queue = queue_of(root)
    item = {"id": "gen-tampered", "dedupe_key": "probe:tampered", "priority": 1310,
            "status": "pending"}
    real = G._write_queue

    def tampering(path, data):
        doc = dict(data)
        doc["items"] = [row for row in doc["items"] if row.get("id") != "gen-tampered"]
        real(path, doc)

    monkeypatch.setattr(G, "_write_queue", tampering)

    out = G.append_item(queue, item)

    assert out["ok"] is False
    assert out["reason"] == "readback_tampered"
    assert queue_of(root) == queue, "the queue is restored to the bytes it had"
    assert not G.EMITTED.exists(), "a refused append records nothing"


# ------------------------------------------------------------------- the brakes
def test_a_spent_token_budget_defers_generation(root, monkeypatch):
    monkeypatch.setattr(R, "TOKEN_CAP_PER_DAY", 1000)
    R._add_tokens(950)
    before = (root / "reports" / "ty" / "autonomy_queue.json").read_text(encoding="utf-8")

    out = G.generate(probe_runner=red_incident_probe())

    assert out["ok"] is False
    assert out["reason"] == "deferred_budget"
    assert out["cause"] == "token_cap"
    assert out["added"] == []
    assert (root / "reports" / "ty" / "autonomy_queue.json").read_text(
        encoding="utf-8") == before
    # A refusal is a stop, not a failure: the launcher returns 0 on every stop.
    assert R.cmd_next() == 4


def test_supply_is_capped_at_twelve_active_generated_items(root):
    for index in range(G.MAX_GENERATED_ACTIVE):
        seed(root, id=f"gen-full-{index}", status="pending", priority=1300,
             generated_by=G.MARK, dedupe_key=f"probe:filler-{index}",
             write_paths=["Northstar_backend/lib/thing.py"],
             acceptance_commands=[["python", "-m", "pytest", "-q", "t.py"]])
    before = len(queue_of(root)["items"])

    out = G.generate(probe_runner=red_incident_probe())

    assert out["reason"] == "supply_capped"
    assert len(queue_of(root)["items"]) == before


def test_needs_forward_counts_only_dispatchable_active_items(root):
    seed(root, id="ok", status="pending", priority=100,
         write_paths=["Northstar_backend/lib/thing.py"],
         acceptance_commands=[["python", "-m", "pytest", "-q", "t.py"]])
    seed(root, id="no-checks", status="pending", priority=100,
         write_paths=["Northstar_backend/lib/thing.py"])
    seed(root, id="refused", status="pending", priority=100,
         write_paths=["Northstar_backend/lib/thing.py"],
         acceptance_commands=[["curl", "https://example.test/x"]])
    seed(root, id="finished", status="done", priority=100,
         write_paths=["Northstar_backend/lib/thing.py"],
         acceptance_commands=[["python", "-m", "pytest", "-q", "t.py"]])

    assert G.needs_forward() == 1


# --------------------------------------------------- the command policy boundary
def test_every_probe_argv_passes_the_supervisor_command_policy():
    cl = importlib.import_module("continuous_loop")
    for spec in P.probe_table():
        refusal = cl.check_command(spec["argv"])
        assert refusal is None, (spec["id"], refusal)


def test_a_generated_command_that_names_a_gated_host_is_refused(root):
    write_backlog(root, improvement(checks=[{"cmd": ["python", "tools/fetch_amazon_feed.py"]}]))

    out = G.generate(probe_runner=make_run())

    assert out["ok"] is True
    item = generated(root)[0]
    assert item["status"] == "needs_author"
    assert "forbidden command token" in item["needs_author"]
    assert G._dispatchable(item) is False


# ---------------------------------------------------------------- the probe module
def test_the_probe_table_is_complete_and_a_copy():
    table = P.probe_table()
    assert table
    for spec in table:
        for field in ("id", "tier", "argv", "why", "fixable_by", "cadence", "timeout_s"):
            assert field in spec, (spec.get("id"), field)
        assert isinstance(spec["argv"], list) and spec["argv"]
        assert all(isinstance(part, str) and part.strip() for part in spec["argv"])
        assert spec["tier"] in ("T0", "T1", "T5")
        assert spec["fixable_by"] in ("worker", "owner")
        assert int(spec["timeout_s"]) > 0
    table[0]["argv"].append("--mutated")
    assert "--mutated" not in P.probe_table()[0]["argv"]


def test_run_probe_reports_exit_code_and_output_tail():
    runner = FakeRun({}, default=(3, "boom\n"))
    got = P.run_probe({"id": "x", "argv": ["python", "-m", "pytest", "-q", "t.py"],
                       "timeout_s": 5}, run=runner)

    assert got["id"] == "x"
    assert got["exit"] == 3
    assert got["ok"] is False
    assert "boom" in got["output_tail"]
    assert runner.calls == [["python", "-m", "pytest", "-q", "t.py"]]


def test_run_exits_zero_one_and_two():
    green = P.run(ids=["backlog-check"], run=FakeRun())
    assert (green["exit"], green["ok"]) == (0, True)

    red = P.run(ids=["backlog-check"], run=FakeRun({}, default=(1, "problems\n")))
    assert (red["exit"], red["ok"]) == (1, False)

    class Unstartable:
        def __call__(self, cmd, **kw):
            raise OSError("no such probe")

    broken = P.run(ids=["backlog-check"], run=Unstartable())
    assert broken["exit"] == 2
    assert "could not be started" in broken["probes"][0]["output_tail"]

    assert P.run(ids=["not-a-probe"], run=FakeRun())["exit"] == 2


def test_priority_bands_are_fixed():
    assert G.priority_for("T0") == 1300
    assert G.priority_for("T0", 5) == 1305
    assert G.priority_for("T0", 10_000) == 1399
    assert G.priority_for("T1", 99) == 999
    assert G.priority_for("T2", 10) == 710
    assert G.priority_for("T3", 9) == 509
    assert G.priority_for("T4", 0) == 300
    assert G.priority_for("T5", 10_000) == 139
    with pytest.raises(ValueError):
        G.priority_for("T9")
