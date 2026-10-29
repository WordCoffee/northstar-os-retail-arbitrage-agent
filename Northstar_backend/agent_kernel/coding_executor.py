"""Kernel executor that runs the bounded coding agent for a coding node."""
from __future__ import annotations

from typing import Any, Callable, Dict, Optional

from .coding_agent import Acceptance, CodingAgent, Model
from .coding_tools import Workspace
from .model import Node, Plan


class CodingAgentExecutor:
    def __init__(self, model: Model, workspace: str | Workspace, *,
                 task: str = "", acceptance: Optional[Acceptance] = None,
                 max_steps: int = 12, max_repairs: int = 1):
        self.model = model
        self.workspace = workspace
        self.task = task
        self.acceptance = acceptance
        self.max_steps = max_steps
        self.max_repairs = max_repairs

    def __call__(self, node: Node, plan: Plan) -> Dict[str, Any]:
        task = self.task or f"{node.title}. {node.inputs.get('objective', '')}"
        agent = CodingAgent(
            self.workspace, self.model, max_steps=self.max_steps,
            max_repairs=self.max_repairs, acceptance=self.acceptance)
        result = agent.run(task)
        return {"ok": result.ok, "detail": result.summary,
                "files": result.files, "data": result.to_dict()}
