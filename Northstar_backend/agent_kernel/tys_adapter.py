"""Ty's Assistant ↔ kernel adapter.

A work order already carries exactly what a plan needs: objective, lanes, steps,
scope and limits. This converts it without changing Ty's default runner; the
caller opts in explicitly.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

from .kernel import Kernel, RunResult
from .model import Acceptance, Budget, Node, Plan, PermissionRule
from .policy import Policy
from .session import CheckpointStore, Journal

VALID_LANES = ("inspect", "coding", "browser", "creative")


def work_order_to_plan(order: Dict[str, Any], *, session_id: str = "") -> Plan:
    objective = str(order.get("objective") or "").strip()
    if not objective:
        raise ValueError("a work order needs an objective")
    scope = dict(order.get("scope") or {})
    lanes = [l for l in (scope.get("lanes") or VALID_LANES) if l in VALID_LANES]
    if not lanes:
        raise ValueError("scope.lanes must name at least one lane")
    limits = dict(order.get("limits") or {})
    steps = list(order.get("steps") or [])
    if not steps:
        steps = [{"lane": lanes[0], "objective": objective}]
    nodes: List[Node] = []
    prev: Optional[str] = None
    for i, step in enumerate(steps, 1):
        lane = str(step.get("lane") or "").strip().lower()
        if lane not in lanes:
            raise ValueError(f"step lane {lane!r} is outside scope {lanes}")
        raw_accept = step.get("acceptance") or []
        acceptance = ([a if isinstance(a, Acceptance) else Acceptance.from_dict(a)
                       for a in raw_accept]
                      or [Acceptance("the lane executor reports success", "executor_ok")])
        node_id = str(step.get("node_id") or f"n{i}")
        depends = list(step.get("depends_on") or ([] if prev is None else [prev]))
        nodes.append(Node(
            node_id=node_id, kind=lane, title=str(step.get("objective") or objective),
            acceptance=acceptance, depends_on=depends, lane=lane,
            inputs=dict(step.get("params") or {}),
            max_attempts=int(step.get("max_attempts") or limits.get(
                "max_attempts_per_node") or 2),
        ))
        prev = node_id
    budget = Budget(
        max_steps=int(limits.get("max_steps") or max(1, len(nodes) * 2)),
        max_wall_s=int(limits.get("max_wall_s") or 3600),
        max_attempts_per_node=int(limits.get("max_attempts_per_node") or 2),
        max_tokens=(int(limits["max_tokens"]) if limits.get("max_tokens") else None),
    )
    return Plan(
        plan_id="plan_" + str(order.get("id") or "tys")[:24],
        session_id=session_id or ("sess_" + str(order.get("id") or "tys")[:24]),
        goal=objective,
        constraints=[c for c in [
            "no Amazon", "no spend",
            *[f"scope:{l}" for l in lanes],
        ]],
        acceptance=[Acceptance("every step is done with evidence", "plan_complete")],
        nodes=nodes, budget=budget,
    )


def executors_for(assistant: Any, order: Dict[str, Any]) -> Dict[str, Any]:
    """Map Ty's lanes onto kernel executors.

    `assistant` only needs `_execute_step(task, step)` returning an object with
    `ok`, `summary`, `detail`, `blocked`, `artifacts` (Ty's StepResult already
    does). A fake with the same surface is enough for tests.
    """
    task = dict(order)
    task.setdefault("id", "tys_adapter")

    def _wrap(node, _plan):
        step = {"lane": node.lane or node.kind, "objective": node.title,
                "params": dict(node.inputs or {})}
        out = assistant._execute_step(task, step)
        if hasattr(out, "as_dict"):
            out = out.as_dict()
        return {"ok": bool(out.get("ok")),
                "detail": str(out.get("detail") or out.get("summary") or ""),
                "blocked": bool(out.get("blocked")),
                "ask": str(out.get("detail") or ""),
                "files": list(out.get("artifacts") or []),
                "data": out.get("evidence") or {}}

    return {lane: _wrap for lane in VALID_LANES}


def run_order(assistant: Any, order: Dict[str, Any], *,
              approve_by: str = "operator",
              grants: Sequence[PermissionRule] = (),
              journal_path: Optional[str] = None,
              checkpoint_root: Optional[str] = None) -> RunResult:
    plan = work_order_to_plan(order)
    policy = Policy(mode="dontAsk")
    kernel = Kernel(
        policy=policy,
        journal=Journal(journal_path),
        checkpoints=CheckpointStore(checkpoint_root),
        executors=executors_for(assistant, order),
    )
    kernel.submit(plan)
    kernel.approve(plan.plan_id, approve_by)
    return kernel.run(plan, grants=grants)
