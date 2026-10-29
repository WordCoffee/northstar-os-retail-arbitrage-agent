"""Kernel executor that runs the bounded coding agent for a coding node."""
from __future__ import annotations

from typing import Any, Callable, Dict, Optional

from .coding_agent import Acceptance, CodingAgent, Model
from .coding_tools import Workspace
from .model import Node, Plan


class CodingAgentExecutor:
    def __init__(self, model: Model, workspace: str | Workspace, *,
                 task: str = "", acceptance: Optional[Acceptance] = None,
                 max_steps: int = 12, max_repairs: int = 1,
                 required_artifact: str = ""):
        self.model = model
        self.workspace = workspace
        self.task = task
        self.acceptance = acceptance
        self.max_steps = max_steps
        self.max_repairs = max_repairs
        self.required_artifact = required_artifact

    def __call__(self, node: Node, plan: Plan) -> Dict[str, Any]:
        task = self.task or f"{node.title}. {node.inputs.get('objective', '')}"
        agent = CodingAgent(
            self.workspace, self.model, max_steps=self.max_steps,
            max_repairs=self.max_repairs, acceptance=self.acceptance,
            required_artifact=self.required_artifact)
        result = agent.run(task)
        data = result.to_dict()
        # The acceptance is the authority, not the loop's stop reason. A run can
        # write every required artifact, then hit its step budget before `finish`;
        # re-checking acceptance prevents a false `needs_human`.
        if result.acceptance_recovered:
            data["acceptance_recovered"] = True
            return {"ok": True, "detail": result.summary,
                    "files": result.files, "data": data}
        if not result.ok and self.acceptance is not None:
            ok, detail = self.acceptance()
            if ok:
                data["acceptance_recovered"] = True
                return {"ok": True,
                        "detail": f"acceptance satisfied after loop stop: {detail}",
                        "files": result.files, "data": data}
        return {"ok": result.ok, "detail": result.summary,
                "files": result.files, "data": data}
