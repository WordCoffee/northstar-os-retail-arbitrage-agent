"""Agent kernel tests — schemas, policy, graph, memory, verify and the loop."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from agent_kernel import (Acceptance, Budget, Evidence, Kernel, Node, PermissionRule,
                          Plan, Policy, grant, validate_plan)
from agent_kernel.budget import BudgetTracker
from agent_kernel.context import Compactor, RepoMap, write_handoff
from agent_kernel.diff import parse_diff, review, select_hunks, stats
from agent_kernel.graph import next_node, ready_nodes, topological_order
from agent_kernel.memory import AutoMemory, load_memory
from agent_kernel.plan_mode import PlanError, PlanMode
from agent_kernel.policy import PermissionDenied
from agent_kernel.session import CheckpointStore, Journal
from agent_kernel.skills import Skill, SkillRegistry
from agent_kernel.subagents import SubagentTask, merge, run_subagents
from agent_kernel.todos import Todos, TodoError
from agent_kernel.tys_adapter import run_order, work_order_to_plan
from agent_kernel.verify import VerifierRegistry, VerifyContext


def _plan(**kw):
    nodes = kw.pop("nodes", [Node("n1", "inspect", "read the file",
                                  acceptance=[Acceptance("ok", "executor_ok")],
                                  lane="inspect")])
    return Plan(plan_id=kw.pop("plan_id", "p1"), session_id=kw.pop("session_id", "s1"),
                goal=kw.pop("goal", "test the kernel"), nodes=nodes,
                acceptance=kw.pop("acceptance",
                                  [Acceptance("all nodes done", "plan_complete")]),
                **kw)


# ── model ───────────────────────────────────────────────────────────────────
def test_valid_plan_has_no_errors():
    assert validate_plan(_plan()) == []


def test_missing_goal_is_rejected():
    assert any("goal" in e for e in validate_plan(_plan(goal="")))


def test_node_without_acceptance_is_rejected():
    p = _plan(nodes=[Node("n1", "inspect", "x")])
    assert any("acceptance" in e for e in validate_plan(p))


def test_unknown_dependency_is_rejected():
    p = _plan(nodes=[Node("n1", "inspect", "x", depends_on=["nope"],
                          acceptance=[Acceptance("ok", "executor_ok")])])
    assert any("unknown dependency" in e for e in validate_plan(p))


def test_cycle_is_rejected():
    p = _plan(nodes=[
        Node("a", "inspect", "a", depends_on=["b"], acceptance=[Acceptance("ok", "executor_ok")]),
        Node("b", "inspect", "b", depends_on=["a"], acceptance=[Acceptance("ok", "executor_ok")]),
    ])
    assert any("cycle" in e for e in validate_plan(p))


def test_gate_must_reference_a_node():
    p = _plan(gates=[{"node_id": "nope", "gate": "operator_approval"}])
    assert any("gate" in e for e in validate_plan(p))


# ── plan mode ───────────────────────────────────────────────────────────────
def test_plan_must_be_proposed_from_draft():
    mode = PlanMode()
    p = mode.propose(_plan())
    assert p.state == "proposed"
    assert mode.approve(p, "operator").state == "approved"
    assert mode.activate(p).state == "active"


def test_unapproved_plan_cannot_activate():
    with pytest.raises(PlanError):
        PlanMode().activate(_plan(state="proposed"))


def test_plan_mode_denies_a_side_effect_tool():
    with pytest.raises(PermissionDenied):
        PlanMode().guard("write", "x.py")


def test_plan_mode_allows_a_read():
    PlanMode().guard("read", "x.py")


# ── policy ──────────────────────────────────────────────────────────────────
def test_amazon_is_denied_even_with_an_allow_rule():
    p = Policy([PermissionRule("allow", "browser_click", "domain:amazon.com")],
               mode="auto")
    d = p.evaluate("browser_click", host="www.amazon.com")
    assert d.effect == "deny" and d.source == "hardcoded"


def test_spend_and_credentials_are_denied():
    p = Policy(mode="auto")
    assert p.evaluate("purchase", "buy credits").effect == "deny"
    assert p.evaluate("browser_type", "enter password").effect == "deny"


def test_deny_beats_allow_regardless_of_specificity():
    p = Policy([PermissionRule("allow", "edit", "src/"),
                PermissionRule("deny", "edit", "")], mode="acceptEdits")
    assert p.evaluate("edit", "src/a.py").effect == "deny"


def test_bare_deny_removes_the_tool_from_context():
    p = Policy([PermissionRule("deny", "bash")], mode="auto")
    assert p.visible_tools(["bash", "read", "edit"]) == ["read", "edit"]


def test_dont_ask_denies_a_side_effect_without_a_grant():
    p = Policy(mode="dontAsk")
    assert p.evaluate("edit", "src/a.py").effect == "deny"


def test_a_grant_expires():
    g = grant("edit", "src/", minutes=1, now=1000)
    p = Policy([g], mode="dontAsk", now=1060)
    assert p.evaluate("edit", "src/a.py", now=1060).effect == "allow"
    assert p.evaluate("edit", "src/a.py", now=2000).effect == "deny"


def test_accept_edits_only_inside_allowed_paths():
    p = Policy(mode="acceptEdits", allowed_paths=["src/"])
    assert p.evaluate("edit", "src/a.py").effect == "allow"
    assert p.evaluate("edit", "secrets/a.py").effect == "ask"


# ── graph / todos ───────────────────────────────────────────────────────────
def test_graph_order_and_ready_nodes():
    p = _plan(nodes=[
        Node("a", "inspect", "a", acceptance=[Acceptance("ok", "executor_ok")]),
        Node("b", "inspect", "b", depends_on=["a"], acceptance=[Acceptance("ok", "executor_ok")]),
    ])
    assert topological_order(p) == ["a", "b"]
    assert [n.node_id for n in ready_nodes(p)] == ["a"]
    p.node("a").state = "done"
    assert ready_nodes(p)[0].node_id == "b"
    assert next_node(p).node_id == "b"


def test_only_one_todo_can_be_in_progress():
    p = _plan(nodes=[
        Node("a", "inspect", "a", acceptance=[Acceptance("ok", "executor_ok")]),
        Node("b", "inspect", "b", acceptance=[Acceptance("ok", "executor_ok")]),
    ])
    t = Todos(p)
    t.start("a")
    with pytest.raises(TodoError):
        t.start("b")


def test_todo_cannot_finish_without_evidence():
    p = _plan()
    t = Todos(p)
    t.start("n1")
    with pytest.raises(TodoError):
        t.finish("n1")
    p.node("n1").evidence_ids = ["ev_1"]
    assert t.finish("n1").state == "done"


# ── budget ──────────────────────────────────────────────────────────────────
def test_budget_stops_on_steps_and_wall_clock():
    t = BudgetTracker(Budget(max_steps=2, max_wall_s=10), clock=lambda: 0)
    t.step(); t.step()
    assert not t.exhausted
    t.step()
    assert t.state.stopped == "max_steps"
    now = [0.0]
    t2 = BudgetTracker(Budget(max_steps=99, max_wall_s=5), clock=lambda: now[0])
    now[0] = 6.0
    t2.step()
    assert t2.state.stopped == "max_wall_s"


# ── journal / checkpoints ───────────────────────────────────────────────────
def test_journal_is_append_only_and_replays_without_side_effects():
    j = Journal()
    j.append("s1", "node_started", node_id="n1")
    j.append("s1", "evidence", payload={"result": "pass"})
    j.append("s1", "node_finished", node_id="n1", payload={"state": "done"})
    r = j.replay("s1")
    assert r["nodes"] == {"n1": "done"}
    assert r["evidence_rows"] == 1
    assert len(j.read("s1")) == 3


def test_checkpoint_restores_a_file(tmp_path):
    f = tmp_path / "a.txt"
    f.write_text("before", encoding="utf-8")
    store = CheckpointStore(tmp_path / "ckpts")
    ck = store.create("s1", 1, {"n1": "done"}, [f])
    f.write_text("after", encoding="utf-8")
    out = store.restore(ck.checkpoint_id)
    assert f.read_text(encoding="utf-8") == "before"
    assert out["restored"]


def test_checkpoint_reports_scope_limits(tmp_path):
    store = CheckpointStore(tmp_path)
    ck = store.create("s1", 1, {}, [])
    assert "browser" in store.restore(ck.checkpoint_id)["limits"]


# ── memory / context / skills ───────────────────────────────────────────────
def test_memory_loads_and_expands_an_import(tmp_path):
    (tmp_path / "extra.md").write_text("extra rule", encoding="utf-8")
    (tmp_path / "NORTHSTAR.md").write_text(
        "Project rules\n@extra.md\n<!-- hidden -->", encoding="utf-8")
    files = load_memory(tmp_path)
    text = "\n".join(f.text for f in files)
    assert "Project rules" in text and "extra rule" in text
    assert "hidden" not in text


def test_memory_reports_a_missing_import(tmp_path):
    (tmp_path / "NORTHSTAR.md").write_text("@nope.md", encoding="utf-8")
    text = load_memory(tmp_path)[0].text
    assert "missing import" in text


def test_auto_memory_is_proposed_until_approved(tmp_path):
    m = AutoMemory(tmp_path / "auto.json")
    m.propose("use 2-space indent", source="operator", date="2026-10-28")
    assert m.approved() == []
    m.approve(0)
    assert m.render().startswith("- use 2-space indent")
    m.forget(0)
    assert m.approved() == []


def test_repo_map_builds_and_searches(tmp_path):
    (tmp_path / "a.py").write_text("def hello():\n    pass\n", encoding="utf-8")
    (tmp_path / "b.md").write_text("# notes", encoding="utf-8")
    rm = RepoMap(tmp_path)
    rm.build()
    assert {f.path for f in rm.files} == {"a.py", "b.md"}
    assert rm.search("hello")[0].path == "a.py"


def test_compactor_keeps_anchors_and_says_what_it_dropped():
    c = Compactor(threshold=0.5, max_chars=100)
    msgs = [{"role": "user", "content": "x" * 100} for _ in range(8)]
    r = c.compact(msgs, [{"role": "system", "content": "goal"}], limit_tokens=10)
    assert r.dropped > 0
    assert any(m.get("content") == "goal" for m in r.messages)
    assert "compacted" in r.messages[0]["content"]


def test_handoff_writes_the_anchors(tmp_path):
    p = write_handoff(tmp_path / "h.md", goal="g", constraints=["no Amazon"],
                      decisions=["d1"], evidence_paths=["e.json"])
    text = p.read_text(encoding="utf-8")
    assert "Goal: g" in text and "no Amazon" in text and "e.json" in text


def test_skill_registry_is_progressive():
    reg = SkillRegistry([Skill("packaging", "build a pouch label", "x", "body")])
    assert "body" not in json.dumps(reg.metadata())
    assert reg.select("pouch label")[0]["name"] == "packaging"
    assert reg.load("packaging").body == "body"


# ── diff / verify / subagents ───────────────────────────────────────────────
DIFF = """--- a/x.txt
+++ b/x.txt
@@ -1,2 +1,2 @@
-old
+new
 same
@@ -10 +10 @@
-late
+later
"""


def test_diff_parses_selects_and_counts():
    assert len(parse_diff(DIFF)) == 2
    assert stats(DIFF) == {"hunks": 2, "added": 2, "removed": 2}
    only = select_hunks(DIFF, [1])
    assert "late" in only and "old" not in only
    assert review(DIFF)[0]["added"] == 1


def test_file_hash_verifier(tmp_path):
    f = tmp_path / "a.txt"
    f.write_text("hello", encoding="utf-8")
    reg = VerifierRegistry()
    ev = reg.verify(Acceptance("hash", "file_hash", {"path": str(f)}),
                    VerifyContext("s", "n"))
    assert ev.result == "pass" and ev.sha256


def test_file_min_bytes_verifier(tmp_path):
    f = tmp_path / "a.txt"
    f.write_text("x" * 10, encoding="utf-8")
    reg = VerifierRegistry()
    ok = reg.verify(Acceptance("min", "file_min_bytes",
                               {"path": str(f), "min_bytes": 10}),
                    VerifyContext("s", "n"))
    bad = reg.verify(Acceptance("min", "file_min_bytes",
                                {"path": str(f), "min_bytes": 11}),
                     VerifyContext("s", "n"))
    assert ok.result == "pass" and bad.result == "fail"


def test_markdown_fence_is_stripped_only_when_it_wraps_the_payload():
    from agent_kernel.artifacts import strip_markdown_fence
    text, stripped = strip_markdown_fence("```diff\n--- a/x\n+++ b/x\n```")
    assert stripped is True and text.startswith("--- a/x")
    same, stripped2 = strip_markdown_fence("--- a/x\n+++ b/x")
    assert stripped2 is False and same.startswith("--- a/x")
    partial, stripped3 = strip_markdown_fence("```json\n{\"a\": 1}")
    assert stripped3 is False and partial.startswith("```json")


def test_unknown_verifier_is_unknown_not_pass():
    ev = VerifierRegistry().verify(Acceptance("x", "does_not_exist"),
                                   VerifyContext("s", "n"))
    assert ev.result == "unknown"


def test_command_verifier(tmp_path):
    reg = VerifierRegistry()
    ok = reg.verify(Acceptance("ok", "command",
                               {"cmd": [sys.executable, "-c", "print('hi')"]}),
                    VerifyContext("s", "n"))
    bad = reg.verify(Acceptance("bad", "command",
                                {"cmd": [sys.executable, "-c", "raise SystemExit(2)"]}),
                     VerifyContext("s", "n"))
    assert ok.result == "pass" and bad.result == "fail"


def test_subagent_report_with_a_bad_hash_is_rejected(tmp_path):
    f = tmp_path / "a.txt"
    f.write_text("real", encoding="utf-8")
    task = SubagentTask("t1", "x", "p")
    rep = run_subagents([task], lambda t: {"task_id": "t1", "ok": True,
                                           "summary": "done",
                                           "files": [{"path": str(f),
                                                      "sha256": "0" * 64}]})
    assert rep[0].ok is False
    assert merge(rep)["ok"] is False


def test_subagent_success_merges(tmp_path):
    f = tmp_path / "a.txt"
    f.write_text("real", encoding="utf-8")
    import hashlib
    digest = hashlib.sha256(f.read_bytes()).hexdigest()
    task = SubagentTask("t1", "x", "p")
    rep = run_subagents([task], lambda t: {"task_id": "t1", "ok": True,
                                           "summary": "done",
                                           "files": [{"path": str(f),
                                                      "sha256": digest}]})
    assert merge(rep)["ok"] is True


# ── kernel loop ─────────────────────────────────────────────────────────────
def _kernel(executor, *, mode="dontAsk"):
    k = Kernel(policy=Policy(mode=mode), journal=Journal(),
               checkpoints=CheckpointStore())
    k.executors["inspect"] = executor
    return k


def test_kernel_completes_and_requires_evidence():
    k = _kernel(lambda n, p: {"ok": True, "detail": "read"})
    p = k.create_plan(goal="g", nodes=[
        Node("n1", "inspect", "read", lane="inspect",
             acceptance=[Acceptance("ok", "executor_ok")])],
        acceptance=[Acceptance("all done", "plan_complete")])
    k.submit(p); k.approve(p.plan_id, "op")
    res = k.run(p)
    assert res.status == "complete", res.reason
    assert p.node("n1").state == "done"
    assert p.node("n1").evidence_ids
    assert k.status(p)["checkpoints"] >= 1


def test_kernel_retries_then_succeeds():
    calls = {"n": 0}

    def flaky(node, plan):
        calls["n"] += 1
        return {"ok": calls["n"] > 1, "detail": "attempt"}

    k = _kernel(flaky)
    p = k.create_plan(goal="g", nodes=[
        Node("n1", "inspect", "read", lane="inspect", max_attempts=2,
             acceptance=[Acceptance("ok", "executor_ok")])],
        acceptance=[Acceptance("all done", "plan_complete")])
    k.submit(p); k.approve(p.plan_id, "op")
    assert k.run(p).status == "complete"
    assert calls["n"] == 2


def test_kernel_blocks_on_a_gate_and_resumes():
    k = _kernel(lambda n, p: {"ok": True})
    p = k.create_plan(goal="g", nodes=[
        Node("n1", "inspect", "read", lane="inspect",
             acceptance=[Acceptance("ok", "executor_ok")])],
        acceptance=[Acceptance("all done", "plan_complete")],
        gates=[{"node_id": "n1", "gate": "operator_approval", "reason": "check"}])
    k.submit(p); k.approve(p.plan_id, "op")
    res = k.run(p)
    assert res.status == "needs_human" and res.ask == "operator_approval"
    k.release("n1", resolution="approved")
    assert k.run(p).status == "complete"


def test_kernel_denies_amazon_even_with_a_grant():
    k = Kernel(policy=Policy(mode="dontAsk"))
    k.executors["browser"] = lambda n, p: {"ok": True}
    p = k.create_plan(goal="g", nodes=[
        Node("n1", "browser", "open", lane="browser",
             inputs={"host": "www.amazon.com"},
             acceptance=[Acceptance("ok", "executor_ok")])],
        acceptance=[Acceptance("all done", "plan_complete")])
    k.submit(p); k.approve(p.plan_id, "op")
    res = k.run(p, grants=[grant("browser_click", "domain:amazon.com")])
    assert res.status == "denied"
    assert "Amazon" in res.reason


def test_kernel_requires_a_grant_for_a_side_effect_lane():
    k = Kernel(policy=Policy(mode="dontAsk"))
    k.executors["coding"] = lambda n, p: {"ok": True}
    p = k.create_plan(goal="g", nodes=[
        Node("n1", "coding", "edit", lane="coding",
             acceptance=[Acceptance("ok", "executor_ok")])],
        acceptance=[Acceptance("all done", "plan_complete")])
    k.submit(p); k.approve(p.plan_id, "op")
    assert k.run(p).status == "denied"
    k.release("n1")
    assert k.run(p, grants=[grant("edit", "")]).status == "complete"


def test_kernel_verification_failure_blocks_after_attempts(tmp_path):
    # A node whose external assertion cannot pass must not be marked done.
    f = tmp_path / "missing.txt"
    k = Kernel(policy=Policy(mode="dontAsk"))
    k.executors["inspect"] = lambda n, p: {"ok": True}
    p = k.create_plan(goal="g", nodes=[
        Node("n1", "inspect", "read", lane="inspect", max_attempts=1,
             acceptance=[Acceptance("file exists", "artifact_exists",
                                    {"path": str(f)})])],
        acceptance=[Acceptance("all done", "plan_complete")])
    k.submit(p); k.approve(p.plan_id, "op")
    res = k.run(p)
    assert res.status == "needs_human"
    assert p.node("n1").state == "blocked"


# ── Ty adapter ──────────────────────────────────────────────────────────────
class _FakeAssistant:
    def __init__(self, ok=True):
        self.ok = ok
        self.calls = []

    def _execute_step(self, task, step):
        self.calls.append(step)
        return {"ok": self.ok, "summary": "done", "detail": "",
                "blocked": False, "artifacts": []}


def test_work_order_maps_to_a_plan():
    p = work_order_to_plan({
        "id": "tys_1", "objective": "fix the thing",
        "scope": {"lanes": ["coding", "inspect"]},
        "steps": [{"lane": "inspect", "objective": "look"},
                  {"lane": "coding", "objective": "fix"}],
        "limits": {"max_steps": 4, "max_wall_s": 120},
    })
    assert [n.node_id for n in p.nodes] == ["n1", "n2"]
    assert p.nodes[1].depends_on == ["n1"]
    assert p.budget.max_steps == 4


def test_run_order_with_a_fake_assistant():
    assistant = _FakeAssistant(ok=True)
    res = run_order(assistant, {
        "id": "tys_2", "objective": "look",
        "scope": {"lanes": ["inspect"]},
        "steps": [{"lane": "inspect", "objective": "look"}],
    }, grants=[grant("read", "")])
    assert res.status == "complete"
    assert assistant.calls[0]["lane"] == "inspect"


def test_run_order_rejects_a_step_outside_scope():
    with pytest.raises(ValueError):
        work_order_to_plan({"objective": "x", "scope": {"lanes": ["inspect"]},
                            "steps": [{"lane": "coding", "objective": "x"}]})
