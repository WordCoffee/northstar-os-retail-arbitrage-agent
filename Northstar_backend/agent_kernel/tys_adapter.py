"""Ty's Assistant ↔ kernel adapter.

A work order already carries exactly what a plan needs: objective, lanes, steps,
scope and limits. This converts it without changing Ty's default runner; the
caller opts in explicitly.
"""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from .kernel import Kernel, RunResult
from .model import Acceptance, Budget, Node, Plan, PermissionRule
from .policy import Policy
from .session import CheckpointStore, Journal

VALID_LANES = ("inspect", "coding", "browser", "creative")


def make_workspace_acceptance(workspace: str, spec: Optional[Dict[str, Any]] = None):
    """Build an acceptance callable from a step's explicit acceptance spec.

    spec = {"commands": [["python","-m","pytest","-q"]],
            "required_files": ["fix.patch"]}
    """
    spec = dict(spec or {})
    commands = list(spec.get("commands") or [])
    required = list(spec.get("required_files") or [])
    root = Path(workspace)

    def check():
        missing = [f for f in required if not (root / f).is_file()]
        failures: List[str] = []
        for cmd in commands:
            try:
                r = subprocess.run([str(c) for c in cmd], cwd=str(root),
                                   capture_output=True, text=True, timeout=180)
            except Exception as exc:  # noqa: BLE001
                failures.append(f"{cmd}: {exc}")
                continue
            if r.returncode != 0:
                failures.append(f"{' '.join(str(c) for c in cmd)} exit "
                                f"{r.returncode}: {(r.stderr or r.stdout)[-300:]}")
        return (not missing and not failures,
                f"missing={missing}; failures={failures}")

    return check


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


def executors_for(assistant: Any, order: Dict[str, Any],
                  *, task: Optional[Dict[str, Any]] = None,
                  coding_factory: Optional[Any] = None) -> Dict[str, Any]:
    """Map Ty's lanes onto kernel executors.

    `assistant` only needs `_execute_step(task, step)` returning an object with
    `ok`, `summary`, `detail`, `blocked`, `artifacts` (Ty's StepResult already
    does). A fake with the same surface is enough for tests.

    `task` is the real Ty task when this is called from `TysAssistant`; it
    carries the cursor the evidence writer needs. Without it, a minimal task is
    built from the order.
    """
    task = task if task is not None else dict(order)
    task.setdefault("id", "tys_adapter")
    task.setdefault("cursor", 0)
    task.setdefault("scope", dict(order.get("scope") or {}))

    def _wrap(node, _plan):
        step = {"lane": node.lane or node.kind, "objective": node.title,
                "params": dict(node.inputs or {})}
        out = assistant._execute_step(task, step)
        if hasattr(out, "as_dict"):
            out = out.as_dict()
        task["cursor"] = int(task.get("cursor") or 0) + 1
        return {"ok": bool(out.get("ok")),
                "detail": str(out.get("detail") or out.get("summary") or ""),
                "blocked": bool(out.get("blocked")),
                "ask": str(out.get("detail") or ""),
                "files": list(out.get("artifacts") or []),
                "data": out.get("evidence") or {}}

    mapping = {lane: _wrap for lane in VALID_LANES}
    if coding_factory is not None:
        def _coding(node, plan):
            return coding_factory(node)(node, plan)
        mapping["coding"] = _coding
    return mapping


def run_order(assistant: Any, order: Dict[str, Any], *,
              approve_by: str = "operator",
              grants: Sequence[PermissionRule] = (),
              journal_path: Optional[str] = None,
              checkpoint_root: Optional[str] = None,
              task: Optional[Dict[str, Any]] = None,
              coding_factory: Optional[Any] = None) -> RunResult:
    plan = work_order_to_plan(order)
    policy = Policy(mode="dontAsk")
    kernel = Kernel(
        policy=policy,
        journal=Journal(journal_path),
        checkpoints=CheckpointStore(checkpoint_root),
        executors=executors_for(assistant, order, task=task,
                                coding_factory=coding_factory),
    )
    kernel.submit(plan)
    kernel.approve(plan.plan_id, approve_by)
    return kernel.run(plan, grants=grants)
