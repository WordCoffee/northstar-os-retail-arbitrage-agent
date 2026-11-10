"""Dependency graph helpers: what is ready, what is blocked, what is next."""
from __future__ import annotations

from typing import Dict, List, Set

from .model import Node, Plan

DONE = "done"
TERMINAL = {"done", "skipped", "failed", "blocked"}


def deps(node: Node) -> List[str]:
    return list(dict.fromkeys(list(node.depends_on)))


def indegree(plan: Plan) -> Dict[str, int]:
    return {n.node_id: len(deps(n)) for n in plan.nodes}


def ready_nodes(plan: Plan) -> List[Node]:
    """Nodes whose every dependency is done, in declaration order."""
    done = {n.node_id for n in plan.nodes if n.state == DONE}
    out = []
    for n in plan.nodes:
        if n.state not in ("pending", "ready"):
            continue
        if all(d in done for d in deps(n)):
            out.append(n)
    return out


def blocked_nodes(plan: Plan) -> List[Node]:
    failed = {n.node_id for n in plan.nodes
              if n.state in ("failed", "blocked", "skipped")}
    return [n for n in plan.nodes
            if n.state in ("pending", "ready") and any(d in failed for d in deps(n))]


def topological_order(plan: Plan) -> List[str]:
    """Kahn's algorithm; raises ValueError on a cycle."""
    indeg = indegree(plan)
    children: Dict[str, List[str]] = {n.node_id: [] for n in plan.nodes}
    for n in plan.nodes:
        for d in deps(n):
            if d in children:
                children[d].append(n.node_id)
    queue = [n.node_id for n in plan.nodes if indeg[n.node_id] == 0]
    order: List[str] = []
    while queue:
        cur = queue.pop(0)
        order.append(cur)
        for child in children.get(cur, []):
            indeg[child] -= 1
            if indeg[child] == 0:
                queue.append(child)
    if len(order) != len(plan.nodes):
        raise ValueError("plan graph contains a cycle")
    return order


def parallel_safe(plan: Plan) -> Set[str]:
    """Nodes that may run together: same dependency set and no edge between them."""
    groups: Dict[frozenset, List[str]] = {}
    for n in plan.nodes:
        groups.setdefault(frozenset(deps(n)), []).append(n.node_id)
    safe: Set[str] = set()
    edge_pairs = {tuple(e) for e in plan.edges}
    for ids in groups.values():
        if len(ids) < 2:
            continue
        if any((a, b) in edge_pairs or (b, a) in edge_pairs
               for i, a in enumerate(ids) for b in ids[i + 1:]):
            continue
        safe.update(ids)
    return safe


def next_node(plan: Plan) -> Node | None:
    ready = ready_nodes(plan)
    return ready[0] if ready else None


def mark_ready(plan: Plan) -> List[Node]:
    ready = ready_nodes(plan)
    for n in ready:
        n.state = "ready"
    return ready
