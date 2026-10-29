"""Agent kernel data model — the contracts every product shares.

Nothing here calls a model, a network or a database. A plan that cannot be
validated cannot be executed; an evidence row without an assertion cannot make a
node `done`. These are the rules the rest of the kernel relies on.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, Iterable, List, Optional, Sequence

PLAN_STATES = ("draft", "proposed", "approved", "active",
               "superseded", "complete", "abandoned")
NODE_STATES = ("pending", "ready", "running", "verifying", "done",
               "failed", "skipped", "blocked")
NODE_KINDS = ("inspect", "coding", "graphics", "browser", "creative", "human")
EVIDENCE_RESULTS = ("pass", "fail", "unknown")
EFFECTS = ("deny", "ask", "allow")


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


@dataclass
class Acceptance:
    """One machine-checkable assertion."""
    text: str
    verifier: str
    params: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"text": self.text, "verifier": self.verifier,
                "params": dict(self.params)}

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "Acceptance":
        return cls(text=str(raw.get("text") or ""),
                   verifier=str(raw.get("verifier") or ""),
                   params=dict(raw.get("params") or {}))


@dataclass
class Node:
    node_id: str
    kind: str
    title: str
    acceptance: List[Acceptance] = field(default_factory=list)
    depends_on: List[str] = field(default_factory=list)
    lane: str = ""
    inputs: Dict[str, Any] = field(default_factory=dict)
    outputs: List[str] = field(default_factory=list)
    max_attempts: int = 2
    state: str = "pending"
    attempts: int = 0
    evidence_ids: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["acceptance"] = [a.to_dict() for a in self.acceptance]
        return d

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "Node":
        return cls(
            node_id=str(raw.get("node_id") or ""),
            kind=str(raw.get("kind") or "inspect"),
            title=str(raw.get("title") or ""),
            acceptance=[Acceptance.from_dict(a) for a in (raw.get("acceptance") or [])],
            depends_on=list(raw.get("depends_on") or []),
            lane=str(raw.get("lane") or ""),
            inputs=dict(raw.get("inputs") or {}),
            outputs=list(raw.get("outputs") or []),
            max_attempts=int(raw.get("max_attempts") or 2),
            state=str(raw.get("state") or "pending"),
            attempts=int(raw.get("attempts") or 0),
            evidence_ids=list(raw.get("evidence_ids") or []),
        )


@dataclass
class Budget:
    max_steps: int = 40
    max_wall_s: int = 3600
    max_attempts_per_node: int = 2
    max_tokens: Optional[int] = None

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: Optional[Dict[str, Any]]) -> "Budget":
        raw = raw or {}
        return cls(max_steps=int(raw.get("max_steps") or 40),
                   max_wall_s=int(raw.get("max_wall_s") or 3600),
                   max_attempts_per_node=int(raw.get("max_attempts_per_node") or 2),
                   max_tokens=(int(raw["max_tokens"]) if raw.get("max_tokens") else None))


@dataclass
class Plan:
    plan_id: str
    session_id: str
    goal: str
    version: int = 1
    supersedes: Optional[int] = None
    constraints: List[str] = field(default_factory=list)
    acceptance: List[Acceptance] = field(default_factory=list)
    nodes: List[Node] = field(default_factory=list)
    edges: List[List[str]] = field(default_factory=list)
    gates: List[Dict[str, Any]] = field(default_factory=list)
    budget: Budget = field(default_factory=Budget)
    state: str = "draft"
    created_at: str = field(default_factory=_now_iso)
    approved_at: Optional[str] = None
    approved_by: Optional[str] = None

    def node(self, node_id: str) -> Optional[Node]:
        return next((n for n in self.nodes if n.node_id == node_id), None)

    def to_dict(self) -> dict:
        return {
            "plan_id": self.plan_id, "session_id": self.session_id,
            "goal": self.goal, "version": self.version,
            "supersedes": self.supersedes,
            "constraints": list(self.constraints),
            "acceptance": [a.to_dict() for a in self.acceptance],
            "nodes": [n.to_dict() for n in self.nodes],
            "edges": [list(e) for e in self.edges],
            "gates": list(self.gates), "budget": self.budget.to_dict(),
            "state": self.state, "created_at": self.created_at,
            "approved_at": self.approved_at, "approved_by": self.approved_by,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "Plan":
        return cls(
            plan_id=str(raw.get("plan_id") or ""),
            session_id=str(raw.get("session_id") or ""),
            goal=str(raw.get("goal") or ""),
            version=int(raw.get("version") or 1),
            supersedes=raw.get("supersedes"),
            constraints=list(raw.get("constraints") or []),
            acceptance=[Acceptance.from_dict(a) for a in (raw.get("acceptance") or [])],
            nodes=[Node.from_dict(n) for n in (raw.get("nodes") or [])],
            edges=[list(e) for e in (raw.get("edges") or [])],
            gates=list(raw.get("gates") or []),
            budget=Budget.from_dict(raw.get("budget")),
            state=str(raw.get("state") or "draft"),
            created_at=str(raw.get("created_at") or _now_iso()),
            approved_at=raw.get("approved_at"),
            approved_by=raw.get("approved_by"),
        )


@dataclass
class Evidence:
    evidence_id: str
    session_id: str
    node_id: str
    kind: str
    assertion: str
    verifier: str
    result: str
    observed_at: str = field(default_factory=_now_iso)
    path: Optional[str] = None
    sha256: Optional[str] = None
    detail: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "Evidence":
        return cls(**{k: raw.get(k) for k in (
            "evidence_id", "session_id", "node_id", "kind", "assertion",
            "verifier", "result", "observed_at", "path", "sha256", "detail")})


@dataclass
class Checkpoint:
    checkpoint_id: str
    session_id: str
    plan_version: int
    node_states: Dict[str, str] = field(default_factory=dict)
    conversation_seq: int = 0
    file_snapshot: List[Dict[str, Any]] = field(default_factory=list)
    restore_scope: str = "both"
    created_at: str = field(default_factory=_now_iso)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class PermissionRule:
    effect: str
    tool: str
    specifier: str = ""
    scope: str = "session"
    expires_at: Optional[float] = None
    source: str = "operator_default"
    why: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Event:
    seq: int
    session_id: str
    type: str
    node_id: Optional[str] = None
    payload: Dict[str, Any] = field(default_factory=dict)
    ts: str = field(default_factory=_now_iso)
    policy_fingerprint: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def validate_plan(plan: Plan) -> List[str]:
    """Return every reason the plan must not execute. Empty means valid."""
    errors: List[str] = []
    if not plan.plan_id:
        errors.append("plan_id is required")
    if not plan.session_id:
        errors.append("session_id is required")
    if not plan.goal.strip():
        errors.append("goal is required")
    if plan.state not in PLAN_STATES:
        errors.append(f"unknown plan state {plan.state!r}")
    if plan.budget.max_steps <= 0 or plan.budget.max_wall_s <= 0:
        errors.append("budget must be positive")

    ids = [n.node_id for n in plan.nodes]
    if len(ids) != len(set(ids)):
        errors.append("node ids must be unique")
    known = set(ids)
    for n in plan.nodes:
        if not n.title.strip():
            errors.append(f"{n.node_id}: title is required")
        if n.kind not in NODE_KINDS:
            errors.append(f"{n.node_id}: unknown kind {n.kind!r}")
        if not n.acceptance:
            errors.append(f"{n.node_id}: at least one acceptance assertion is required")
        for a in n.acceptance:
            if not a.text.strip() or not a.verifier.strip():
                errors.append(f"{n.node_id}: acceptance needs text and verifier")
        for dep in n.depends_on:
            if dep not in known:
                errors.append(f"{n.node_id}: unknown dependency {dep!r}")
        if n.node_id in n.depends_on:
            errors.append(f"{n.node_id}: cannot depend on itself")
        if n.state not in NODE_STATES:
            errors.append(f"{n.node_id}: unknown state {n.state!r}")

    for edge in plan.edges:
        if len(edge) != 2:
            errors.append(f"edge {edge!r} must be [from, to]")
            continue
        a, b = edge
        if a not in known or b not in known:
            errors.append(f"edge {edge!r} references an unknown node")
        if a == b:
            errors.append(f"edge {edge!r} is a self-loop")

    if _has_cycle(plan):
        errors.append("plan graph contains a cycle")

    for gate in plan.gates:
        node_id = gate.get("node_id")
        if node_id not in known:
            errors.append(f"gate references unknown node {node_id!r}")
        if gate.get("gate") not in ("operator_approval", "login", "spend", "amazon"):
            errors.append(f"gate {gate.get('gate')!r} is not a known gate")

    if not plan.acceptance:
        errors.append("plan-level acceptance is required")
    return errors


def _has_cycle(plan: Plan) -> bool:
    indeg = {n.node_id: 0 for n in plan.nodes}
    adj: Dict[str, List[str]] = {n.node_id: [] for n in plan.nodes}
    for n in plan.nodes:
        for dep in n.depends_on:
            if dep in adj:
                adj[dep].append(n.node_id)
                indeg[n.node_id] += 1
    for a, b in plan.edges:
        if a in adj and b in indeg:
            adj[a].append(b)
            indeg[b] += 1
    queue = [k for k, v in indeg.items() if v == 0]
    seen = 0
    while queue:
        cur = queue.pop()
        seen += 1
        for nxt in adj[cur]:
            indeg[nxt] -= 1
            if indeg[nxt] == 0:
                queue.append(nxt)
    return seen != len(indeg)


def plan_from_json(text: str) -> Plan:
    return Plan.from_dict(json.loads(text))


def evidence_pass(rows: Iterable[Evidence]) -> bool:
    return any(e.result == "pass" for e in rows)
