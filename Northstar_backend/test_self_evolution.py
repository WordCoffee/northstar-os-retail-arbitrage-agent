"""Self-evolution loop — proposal-only, with no way to apply anything."""
from __future__ import annotations

import sqlite3

import pytest

import self_evolution as se


@pytest.fixture()
def db(tmp_path):
    conn = sqlite3.connect(str(tmp_path / "northstar.db"))
    conn.row_factory = sqlite3.Row
    yield conn
    conn.close()


def purpose(cmd):
    if cmd == "optimize-architecture":
        # 4 wide_interface findings (3 of them on one hotspot) + 1 cycle:
        # enough to exercise both the >=3-repeats prompt rule and the >=3 hotspot rule.
        return {"ok": True, "counts": {"wide_interface": 4, "import_cycle": 1},
                "findings": [{"kind": "wide_interface", "target": "pkg.hub"},
                             {"kind": "wide_interface", "target": "pkg.hub"},
                             {"kind": "wide_interface", "target": "pkg.hub"},
                             {"kind": "wide_interface", "target": "pkg.other"},
                             {"kind": "import_cycle", "target": "pkg.a <-> pkg.b"}]}
    return {"ok": True, "counts": {}, "findings": []}


# ── the hard rule ────────────────────────────────────────────────────────────

def test_the_module_cannot_apply_anything():
    assert not hasattr(se, "apply"), "a self-evolution module must not be able to apply changes"
    assert not hasattr(se, "mutate")


def test_weight_updating_is_blocked_on_the_owner_decision():
    wu = se.weight_updates()
    assert wu["status"] == "blocked"
    assert wu["blocked_on"] == "D2"
    assert "training pipeline" in wu["reason"]
    assert len(wu["what_would_be_needed"]) >= 3


def test_gates_are_declared_with_commands():
    gates = se.declared_gates()
    assert len(gates) >= 5
    for g in gates:
        assert g["id"] and g["command"] and g["why"]
    assert any(g["id"] == "shell-gate" for g in gates)


# ── 1. collect ───────────────────────────────────────────────────────────────

def test_collect_reports_that_nothing_was_parsed_without_a_runner(db):
    out = se.collect(db)
    assert any("no runner supplied" in s for s in out["skipped"])
    assert out["purpose"] == {}
    assert out["telemetry"] is not None


def test_collect_captures_injected_purpose_findings(db):
    out = se.collect(db, purpose_runner=purpose)
    assert out["purpose"]["optimize-architecture"]["ok"] is True
    assert out["purpose"]["optimize-architecture"]["counts"] == {
        "wide_interface": 4, "import_cycle": 1}


def test_collect_reports_a_failing_runner_per_command(db):
    def boom(_cmd):
        raise RuntimeError("parse failed")

    out = se.collect(db, purpose_runner=boom)
    for rep in out["purpose"].values():
        assert rep["ok"] is False and "parse failed" in rep["error"]


# ── 2. analyse ───────────────────────────────────────────────────────────────

def test_analyse_counts_kinds_and_hotspots_from_evidence(db):
    out = se.analyse(se.collect(db, purpose_runner=purpose))
    assert out["finding_kinds"]["optimize-architecture:wide_interface"] == 4
    assert out["finding_kinds"]["optimize-architecture:import_cycle"] == 1
    assert out["hotspots"][0] == {"target": "pkg.hub", "findings": 3}


def test_analyse_admits_when_there_is_no_evidence():
    out = se.analyse({"purpose": {}, "telemetry": {"lanes": {}}})
    assert out["finding_kinds"] == {}
    assert out["hotspots"] == []
    assert any("no architectural pattern is claimed" in o for o in out["observations"])


def test_analyse_surfaces_weak_and_thin_lanes(db):
    import lane_telemetry as lt
    for _ in range(31):
        lt.record(db, "local", latency_ms=100, ok=True)
    for _ in range(31):
        lt.record(db, "cloud", latency_ms=90, ok=False)
    out = se.analyse(se.collect(db))
    assert [w["lane"] for w in out["weak_lanes"]] == ["cloud"]
    assert any("90% measured success rate" in o for o in out["observations"])


# ── 3. propose ───────────────────────────────────────────────────────────────

def test_propose_is_traceable_and_invents_nothing_when_there_is_no_evidence():
    assert se.propose({"finding_kinds": {}, "hotspots": [], "weak_lanes": [], "thin_lanes": []}) == []


def test_propose_emits_guarded_proposals_with_evidence(db):
    analysis = se.analyse(se.collect(db, purpose_runner=purpose))
    props = se.propose(analysis)
    assert props, "expected proposals from the injected findings"
    for p in props:
        assert p["id"] and p["area"] and p["change"] and p["rationale"]
        assert p["evidence"], "every proposal must carry the evidence that produced it"
        assert p["risk"] in ("none", "low", "medium", "high")
        assert p["risk_note"], "a risk level must carry its explanation"
    kinds = {p["id"].split("-")[0] for p in props}
    assert "refine" in kinds                     # the >=3-repeats prompt guard
    assert "split" in kinds                      # the hotspot


def test_propose_suggests_measurement_when_lanes_are_thin():
    props = se.propose({"finding_kinds": {}, "hotspots": [], "weak_lanes": [],
                        "thin_lanes": ["local", "cloud"]})
    assert [p["id"] for p in props] == ["record-more-lane-runs"]
    assert props[0]["risk"] == "none"
    assert props[0]["verification"] == []


# ── 4. verify ────────────────────────────────────────────────────────────────

def test_verify_refuses_to_claim_a_gate_it_did_not_run():
    out = se.verify([{"verification": ["python-tests"]}])
    assert out["status"] == "not_run"
    assert "nothing was executed" in out["reason"]
    assert out["gates"][0]["id"] == "python-tests"


def test_verify_records_injected_gate_results():
    ok_run = se.verify([{"verification": ["python-tests"]}],
                       gate_runner=lambda g: {"status": "pass"})
    assert ok_run["status"] == "pass" and ok_run["failed"] == []

    bad_run = se.verify([{"verification": ["python-tests", "shell-gate"]}],
                        gate_runner=lambda g: {"status": "fail"} if g["id"] == "shell-gate"
                        else {"status": "pass"})
    assert bad_run["status"] == "fail"
    assert bad_run["failed"] == ["shell-gate"]


def test_a_gate_runner_that_raises_is_recorded_not_propagated():
    def boom(_g):
        raise RuntimeError("runner died")

    out = se.verify([{"verification": ["python-tests"]}], gate_runner=boom)
    assert out["status"] == "fail"
    assert out["gates"][0]["status"] == "error"
    assert "runner died" in out["gates"][0]["detail"]


# ── the whole loop ───────────────────────────────────────────────────────────

def test_loop_nothing_is_applied_and_the_record_is_complete(db):
    out = se.loop(db, purpose_runner=purpose,
                  gate_runner=lambda g: {"status": "pass"})
    assert out["applied"] is False
    assert "no apply()" in out["note"] or "no apply" in out["note"]
    assert set(out["steps"]) == {"1_collect", "2_analyse", "3_propose", "4_verify"}
    assert out["proposals"]
    assert out["verification"]["status"] == "pass"
    assert out["weight_updates"]["status"] == "blocked"


def test_loop_without_runners_reports_the_gap_honestly(db):
    out = se.loop(db)
    assert out["steps"]["1_collect"]
    assert out["proposals"] == [] or all(p["verification"] is not None for p in out["proposals"])
    assert out["verification"]["status"] == "not_run"


# ── GUARDRAILS: the proposal-only contract, made hard to break ──────────────
# These are the assertions that matter most: they are what stops this module from
# ever becoming an applier. They are deliberately paranoid.

_NO_APPLY_ATTRIBUTES = (
    "apply", "apply_all", "apply_proposal", "mutate", "write", "save", "install",
    "commit_change", "patch", "train", "fine_tune", "finetune", "deploy", "enable",
)


@pytest.mark.parametrize("attr", _NO_APPLY_ATTRIBUTES)
def test_module_exposes_no_apply_style_entry_point(attr):
    assert not hasattr(se, attr), (
        f"self_evolution.{attr} must not exist: this module records proposals, it never "
        "applies them")


def _strip(src: str) -> str:
    import re
    src = re.sub(r'"""[\s\S]*?"""', "", src)
    return re.sub(r"(?m)^\s*#.*$", "", src)


def test_the_proposal_pipeline_contains_no_side_effecting_operations():
    """The pipeline itself must be inert.

    Scope: collect / analyse / propose / verify / loop / weight_updates. The CLI
    below them may RUN declared gates (verification), which is a different thing
    from changing the system — that boundary is asserted separately.
    """
    import inspect

    code = "".join(inspect.getsource(fn) for fn in (
        se.collect, se.analyse, se.propose, se.verify, se.loop,
        se.weight_updates, se.declared_gates))
    for banned in ("subprocess", "os.system", "shutil", "os.remove", "os.rename",
                   "write_text", "write_bytes", "open("):
        assert banned not in _strip(code), (
            f"the proposal pipeline contains {banned!r}; it must have no way to write, "
            "move or spawn anything")


def test_the_only_subprocess_is_the_opt_in_gate_runner():
    """Running the declared gates is verification, and it is explicitly opt-in."""
    import inspect

    module_src = inspect.getsource(se)
    assert "subprocess" in module_src, "the gate runner should exist for --run-gates"
    main_src = inspect.getsource(se.main)
    assert "--run-gates" in main_src, "gate execution must be opt-in on the CLI"
    assert "_subprocess_gate" in main_src, "main must be the only caller"
    # It can only execute a command that came from the DECLARED catalogue.
    runner = inspect.getsource(se._subprocess_gate)
    assert 'gate["command"]' in runner
    # And the catalogue is a fixed module constant, not caller-supplied.
    assert all(isinstance(g.get("command"), str) for g in se.declared_gates())
    assert len(se.declared_gates()) >= 5


def test_no_call_ever_reports_an_applied_change(db):
    """Whatever the runners do, the loop reports applied=False."""
    for runners in (
        {},
        {"purpose_runner": purpose},
        {"gate_runner": lambda g: {"status": "pass"}},
        {"purpose_runner": purpose, "gate_runner": lambda g: {"status": "pass"}},
        {"gate_runner": lambda g: {"status": "fail"}},
    ):
        out = se.loop(db, **runners)
        assert out["applied"] is False
        assert "no apply" in out["note"].lower() or "proposal-only" in out["note"].lower()


def test_every_proposal_is_complete_and_verifiable():
    analysis = {"finding_kinds": {"x:long_function": 5},
                "hotspots": [{"target": "m.py", "findings": 4}],
                "weak_lanes": [{"lane": "cloud", "success_rate": 0.5, "samples": 40}],
                "thin_lanes": ["local"]}
    props = se.propose(analysis)
    assert len(props) >= 4
    for p in props:
        assert set(p) >= {"id", "area", "change", "rationale", "evidence", "risk",
                          "risk_note", "verification"}
        assert isinstance(p["verification"], list)
        assert p["risk"] in ("none", "low", "medium", "high")
        assert "applied" not in p          # a proposal never carries an applied flag


def test_weight_updates_stays_blocked_until_the_owner_decides():
    for _ in range(3):
        wu = se.weight_updates()
        assert wu["status"] == "blocked"
        assert wu["blocked_on"] == "D2"
        assert wu["what_would_be_needed"]


def test_verification_never_claims_a_pass_without_a_runner():
    out = se.verify([{"verification": ["python-tests", "ui-build"]}])
    assert out["status"] == "not_run"
    assert all("status" not in g for g in out["gates"])   # nothing was asserted about them
