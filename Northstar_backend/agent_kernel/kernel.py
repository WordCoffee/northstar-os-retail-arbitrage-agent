"""The orchestrator: plan → approval → execute → verify → checkpoint → resume.

It is deliberately small and deterministic. Executors and verifiers are injected,
so the same kernel runs Ty's lanes, a benchmark's dry executor or a test stub.
"""
from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence

from . import graph
from .budget import BudgetTracker
from .model import (Acceptance, Budget, Evidence, Node, Plan, PermissionRule,
                    validate_plan)
from .plan_mode import PlanMode
from .policy import Policy
from .session import CheckpointStore, Journal
from .todos import Todos, TodoError
from .verify import VerifyContext, VerifierRegistry

Executor = Callable[[Node, Plan], Dict[str, Any]]

LANE_TOOL = {"inspect": "read", "coding": "edit", "graphics": "graphics_generate",
             "browser": "browser_click",
             "creative": "creative_generate", "human": "ask"}


@dataclass
class RunResult:
    status: str                 # complete | needs_human | denied | exhausted | failed
    plan: Plan
    reason: str = ""
    ask: str = ""
    interventions: List[Dict[str, str]] = field(default_factory=list)
    budget: Dict[str, Any] = field(default_factory=dict)
    events: int = 0

    def to_dict(self) -> dict:
        return {"status": self.status, "reason": self.reason, "ask": self.ask,
                "plan": self.plan.to_dict(), "interventions": self.interventions,
                "budget": self.budget, "events": self.events}


class Kernel:
    def __init__(self, *, policy: Optional[Policy] = None,
                 journal: Optional[Journal] = None,
                 checkpoints: Optional[CheckpointStore] = None,
                 verifiers: Optional[VerifierRegistry] = None,
                 executors: Optional[Dict[str, Executor]] = None,
                 clock: Callable[[], float] = time.time):
        self.policy = policy or Policy(mode="dontAsk")
        self.journal = journal or Journal()
        self.checkpoints = checkpoints or CheckpointStore()
        self.verifiers = verifiers or VerifierRegistry()
        self.executors: Dict[str, Executor] = dict(executors or {})
        self.clock = clock
        self.plans: Dict[str, Plan] = {}
        self.evidence: List[Evidence] = []
        self.interventions: List[Dict[str, str]] = []

    # ── plan lifecycle ──────────────────────────────────────────────────────
    def create_plan(self, *, goal: str, nodes: Sequence[Node], session_id: str = "",
                    constraints: Sequence[str] = (),
                    acceptance: Optional[Sequence[Acceptance]] = None,
                    gates: Optional[Sequence[Dict[str, Any]]] = None,
                    budget: Optional[Budget] = None,
                    version: int = 1) -> Plan:
        plan = Plan(
            plan_id="plan_" + uuid.uuid4().hex[:12],
            session_id=session_id or "sess_" + uuid.uuid4().hex[:12],
            goal=goal, version=version,
            constraints=list(constraints),
            acceptance=list(acceptance or []),
            nodes=list(nodes), edges=[],
            gates=list(gates or []),
            budget=budget or Budget(),
        )
        self.plans[plan.plan_id] = plan
        return plan

    def submit(self, plan: Plan) -> Plan:
        mode = PlanMode(self.policy)
        plan = mode.propose(plan)
        self.plans[plan.plan_id] = plan
        self._event(plan, "plan_proposed", payload={"version": plan.version})
        return plan

    def approve(self, plan_id: str, by: str) -> Plan:
        plan = self.plans[plan_id]
        plan = PlanMode(self.policy).approve(plan, by)
        self._event(plan, "plan_approved", payload={"by": by})
        return plan

    # ── execution ───────────────────────────────────────────────────────────
    def run(self, plan: str | Plan, *, grants: Sequence[PermissionRule] = (),
            operator: str = "operator", max_steps: Optional[int] = None) -> RunResult:
        plan = self.plans[plan] if isinstance(plan, str) else plan
        errors = validate_plan(plan)
        if errors:
            raise ValueError("; ".join(errors))
        if plan.state == "proposed":
            raise ValueError("the plan is proposed, not approved")
        if plan.state not in ("approved", "active"):
            raise ValueError(f"cannot run a plan in state {plan.state!r}")

        policy = Policy(rules=list(self.policy.rules) + list(grants),
                        mode=self.policy.mode,
                        allowed_paths=self.policy.allowed_paths, now=self.clock())
        plan.state = "active"
        budget = BudgetTracker(Budget(
            max_steps=int(max_steps or plan.budget.max_steps),
            max_wall_s=plan.budget.max_wall_s,
            max_attempts_per_node=plan.budget.max_attempts_per_node,
            max_tokens=plan.budget.max_tokens), clock=self.clock)
        todos = Todos(plan)
        self._event(plan, "plan_started", payload={"operator": operator,
                                                   "policy": policy.fingerprint()})

        while True:
            if budget.exhausted:
                self._checkpoint(plan, [])
                self._event(plan, "error", payload={"error": budget.state.stopped})
                return self._result(plan, "exhausted",
                                    f"budget stopped the run: {budget.state.stopped}",
                                    budget)

            node = graph.next_node(plan)
            if node is None:
                if all(n.state == "done" for n in plan.nodes):
                    return self._finish(plan, budget)
                blocked = [n.node_id for n in graph.blocked_nodes(plan)]
                return self._result(plan, "blocked",
                                    "no runnable node; blocked: " + ", ".join(blocked),
                                    budget)

            gate = next((g for g in plan.gates
                         if g.get("node_id") == node.node_id
                         and not g.get("satisfied")), None)
            if gate:
                return self._needs_human(plan, node, budget,
                                         ask=str(gate.get("gate") or "operator_approval"),
                                         reason=str(gate.get("reason") or ""))
            if node.kind == "human":
                return self._needs_human(plan, node, budget, ask="human step",
                                         reason=node.title)

            try:
                todos.start(node.node_id)
            except TodoError as exc:
                return self._result(plan, "blocked", str(exc), budget)

            tool = LANE_TOOL.get(node.lane or node.kind, "read")
            decision = policy.evaluate(tool, str((node.inputs or {}).get("specifier", "")),
                                       host=(node.inputs or {}).get("host"),
                                       now=self.clock())
            self._event(plan, "tool_call", node_id=node.node_id,
                        payload={"tool": tool, "effect": decision.effect,
                                 "source": decision.source})
            if decision.effect == "ask":
                return self._needs_human(plan, node, budget, ask=tool,
                                         reason=decision.reason)
            if decision.effect == "deny":
                node.state = "blocked"
                self._checkpoint(plan, [])
                self._event(plan, "error", node_id=node.node_id,
                            payload={"error": decision.reason})
                return self._result(plan, "denied", decision.reason, budget)

            executor = self.executors.get(node.lane or node.kind)
            if executor is None:
                return self._fail_node(plan, node, budget,
                                       f"no executor registered for {node.kind!r}")
            try:
                result = executor(node, plan) or {}
            except Exception as exc:  # noqa: BLE001 - a lane crash is a result
                result = {"ok": False, "detail": f"executor error: {str(exc)[:300]}"}
            self._event(plan, "tool_result", node_id=node.node_id,
                        payload={"ok": bool(result.get("ok")),
                                 "detail": str(result.get("detail") or "")[:300]})

            if result.get("blocked"):
                return self._needs_human(plan, node, budget,
                                         ask=str(result.get("ask") or "external condition"),
                                         reason=str(result.get("detail") or ""))

            rows = self._verify_node(plan, node, bool(result.get("ok")))
            failed = [e for e in rows if e.result != "pass"]
            if not failed:
                todos.finish(node.node_id)
                self._checkpoint(plan, result.get("files") or [])
                self._event(plan, "node_finished", node_id=node.node_id,
                            payload={"state": "done"})
                budget.step()
                continue

            node.attempts += 1
            if node.attempts < max(1, node.max_attempts):
                node.state = "ready"
                self._event(plan, "node_retry", node_id=node.node_id,
                            payload={"attempt": node.attempts,
                                     "failed": [e.assertion for e in failed]})
                budget.step()
                continue
            node.state = "blocked"
            self._checkpoint(plan, [])
            self._event(plan, "gate", node_id=node.node_id,
                        payload={"failed": [e.assertion for e in failed]})
            return self._result(
                plan, "needs_human",
                "verification failed: " + "; ".join(e.assertion for e in failed[:3]),
                budget, ask="fix or amend the plan for " + node.node_id)

    def _verify_node(self, plan: Plan, node: Node, executor_ok: bool) -> List[Evidence]:
        """Evidence for one node. Acceptance outranks the lane's self-report.

        The executor row is a self-report, so it must not be able to veto a
        passing acceptance. A bounded loop can write every required artifact,
        pass the tests, and still stop without `finish` — budget exhausted, or a
        model that forgot the final call. Before this rule, that run reported
        `needs_human` with the work already on disk and the tests already green
        (defect p01). A node with no acceptance keeps the old behaviour: with
        nothing else to prove the work, an executor that did not report success
        still fails.
        """
        ctx = VerifyContext(plan.session_id, node.node_id)
        acceptance: List[Evidence] = []
        for a in node.acceptance:
            params = dict(a.params)
            params["_executor_ok"] = executor_ok
            acceptance.append(self.verifiers.verify(replace(a, params=params), ctx))

        acceptance_passed = bool(acceptance) and all(e.result == "pass" for e in acceptance)
        if executor_ok:
            result, detail = "pass", "lane self-report; not independent proof"
        elif acceptance_passed:
            result, detail = ("pass",
                              "acceptance satisfied after the loop stopped without "
                              "finishing; the lane self-report is superseded")
        else:
            result, detail = "fail", "lane self-report; not independent proof"

        rows = [Evidence(
            evidence_id="ev_" + uuid.uuid4().hex[:12], session_id=plan.session_id,
            node_id=node.node_id, kind="executor",
            assertion="the lane executor reports it completed",
            verifier="executor", result=result, detail=detail)]
        rows.extend(acceptance)
        node.evidence_ids = [e.evidence_id for e in rows]
        self.evidence.extend(rows)
        for e in rows:
            self._event(plan, "evidence", node_id=node.node_id,
                        payload={"evidence_id": e.evidence_id, "result": e.result,
                                 "assertion": e.assertion})
        return rows

    def _finish(self, plan: Plan, budget: BudgetTracker) -> RunResult:
        rows = []
        ctx = VerifyContext(plan.session_id, "plan")
        plan_ok = all(n.state == "done" and n.evidence_ids for n in plan.nodes)
        for a in plan.acceptance:
            ev = self.verifiers.verify(
                replace(a, params={**dict(a.params), "_plan_ok": plan_ok}), ctx)
            self.evidence.append(ev)
            rows.append(ev)
        failed = [e for e in rows if e.result != "pass"]
        if failed:
            plan.state = "active"
            return self._result(plan, "failed",
                                "plan-level acceptance failed: "
                                + "; ".join(e.assertion for e in failed[:3]), budget)
        plan.state = "complete"
        self._checkpoint(plan, [])
        self._event(plan, "plan_complete", payload={"version": plan.version})
        return self._result(plan, "complete", "", budget)

    # ── helpers ─────────────────────────────────────────────────────────────
    def _needs_human(self, plan: Plan, node: Node, budget: BudgetTracker,
                     *, ask: str, reason: str) -> RunResult:
        node.state = "blocked"
        item = {"node_id": node.node_id, "ask": ask, "reason": reason}
        self.interventions.append(item)
        self._checkpoint(plan, [])
        self._event(plan, "gate", node_id=node.node_id,
                    payload={"ask": ask, "reason": reason})
        return self._result(plan, "needs_human", reason or ask, budget,
                            ask=ask)

    def _fail_node(self, plan: Plan, node: Node, budget: BudgetTracker,
                   reason: str) -> RunResult:
        node.state = "failed"
        self._checkpoint(plan, [])
        self._event(plan, "error", node_id=node.node_id, payload={"error": reason})
        return self._result(plan, "failed", reason, budget)

    def _checkpoint(self, plan: Plan, files: Sequence[str]) -> None:
        states = {n.node_id: n.state for n in plan.nodes}
        ckpt = self.checkpoints.create(plan.session_id, plan.version, states,
                                       files=files)
        self._event(plan, "checkpoint", payload={"checkpoint_id": ckpt.checkpoint_id})

    def _event(self, plan: Plan, type_: str, *, node_id: Optional[str] = None,
               payload: Optional[Dict[str, Any]] = None) -> None:
        self.journal.append(plan.session_id, type_, node_id=node_id,
                            payload=payload,
                            policy_fingerprint=self.policy.fingerprint())

    def _result(self, plan: Plan, status: str, reason: str,
                budget: BudgetTracker, ask: str = "") -> RunResult:
        return RunResult(status, plan, reason, ask,
                         interventions=list(self.interventions),
                         budget=budget.snapshot(),
                         events=len(self.journal.read(plan.session_id)))

    def release(self, node_id: str, *, resolution: str = "") -> None:
        """Operator resolved a blocked node; make it runnable again."""
        for plan in self.plans.values():
            node = plan.node(node_id)
            if node and node.state == "blocked":
                for gate in plan.gates:
                    if gate.get("node_id") == node_id:
                        gate["satisfied"] = True
                        gate["resolution"] = resolution
                node.state = "ready"
                self._event(plan, "gate_released", node_id=node_id,
                            payload={"resolution": resolution})
                return
        raise KeyError(node_id)

    def status(self, plan: str | Plan) -> Dict[str, Any]:
        plan = self.plans[plan] if isinstance(plan, str) else plan
        return {"plan_id": plan.plan_id, "state": plan.state,
                "todos": Todos(plan).counts(),
                "evidence": len([e for e in self.evidence
                                 if e.session_id == plan.session_id]),
                "events": len(self.journal.read(plan.session_id)),
                "checkpoints": len(self.checkpoints.list(plan.session_id))}

    def save(self, path: str | Path) -> Path:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({
            "plans": [pl.to_dict() for pl in self.plans.values()],
            "evidence": [e.to_dict() for e in self.evidence],
            "interventions": self.interventions,
        }, indent=2), encoding="utf-8")
        return p

    def load(self, path: str | Path) -> None:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        self.plans = {r["plan_id"]: Plan.from_dict(r) for r in raw.get("plans", [])}
        self.evidence = [Evidence.from_dict(r) for r in raw.get("evidence", [])]
        self.interventions = list(raw.get("interventions") or [])
