"""The visible todo state machine. Exactly one task is `in_progress`."""
from __future__ import annotations

from typing import Dict, List

from .model import Node, Plan

ICONS = {"pending": "[ ]", "ready": "[ ]", "running": "[>]", "verifying": "[~]",
         "done": "[x]", "failed": "[!]", "blocked": "[#]", "skipped": "[-]"}


class TodoError(RuntimeError):
    pass


class Todos:
    """A view over a plan's nodes; it never invents a completion."""

    def __init__(self, plan: Plan):
        self.plan = plan

    def items(self) -> List[Dict[str, str]]:
        return [{"node_id": n.node_id, "title": n.title, "state": n.state}
                for n in self.plan.nodes]

    def running(self) -> List[Node]:
        return [n for n in self.plan.nodes if n.state == "running"]

    def start(self, node_id: str) -> Node:
        node = self.plan.node(node_id)
        if node is None:
            raise TodoError(f"unknown node {node_id!r}")
        if node.state not in ("pending", "ready"):
            raise TodoError(f"{node_id} cannot start from {node.state!r}")
        active = self.running()
        if active and active[0].node_id != node_id:
            raise TodoError(f"{active[0].node_id} is already in progress")
        node.state = "running"
        return node

    def verify(self, node_id: str) -> Node:
        node = self._must(node_id)
        if node.state != "running":
            raise TodoError(f"{node_id} is not running")
        node.state = "verifying"
        return node

    def finish(self, node_id: str) -> Node:
        node = self._must(node_id)
        if node.state not in ("running", "verifying"):
            raise TodoError(f"{node_id} cannot finish from {node.state!r}")
        if not node.evidence_ids:
            raise TodoError(f"{node_id} has no evidence; it cannot be done")
        node.state = "done"
        return node

    def fail(self, node_id: str, why: str = "") -> Node:
        node = self._must(node_id)
        node.state = "failed"
        if why:
            node.outputs = list(node.outputs) + [f"failure: {why}"]
        return node

    def block(self, node_id: str, why: str = "") -> Node:
        node = self._must(node_id)
        node.state = "blocked"
        if why:
            node.outputs = list(node.outputs) + [f"blocked: {why}"]
        return node

    def skip(self, node_id: str) -> Node:
        node = self._must(node_id)
        node.state = "skipped"
        return node

    def render(self) -> str:
        return "\n".join(f"{ICONS.get(n.state, '[?]')} {n.node_id}  {n.title}"
                         for n in self.plan.nodes)

    def counts(self) -> Dict[str, int]:
        out: Dict[str, int] = {}
        for n in self.plan.nodes:
            out[n.state] = out.get(n.state, 0) + 1
        return out

    def _must(self, node_id: str) -> Node:
        node = self.plan.node(node_id)
        if node is None:
            raise TodoError(f"unknown node {node_id!r}")
        return node
