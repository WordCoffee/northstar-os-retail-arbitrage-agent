"""Plan mode — explore read-only, propose a plan, execute only after approval."""
from __future__ import annotations

import time
from typing import List, Optional

from .model import Plan, validate_plan
from .policy import Policy, PermissionDenied

#: Tools that change something. Plan mode never calls them.
SIDE_EFFECT_TOOLS = {"write", "edit", "delete", "bash", "shell", "exec",
                     "browser_click", "browser_type", "browser_submit",
                     "http_post", "http_put", "http_delete"}


class PlanError(ValueError):
    pass


class PlanMode:
    def __init__(self, policy: Optional[Policy] = None):
        self.policy = policy or Policy(mode="plan")

    def propose(self, plan: Plan) -> Plan:
        errors = validate_plan(plan)
        if errors:
            raise PlanError("; ".join(errors))
        if plan.state not in ("draft", "proposed"):
            raise PlanError(f"cannot propose a plan in state {plan.state!r}")
        plan.state = "proposed"
        return plan

    def approve(self, plan: Plan, by: str) -> Plan:
        if plan.state != "proposed":
            raise PlanError(f"cannot approve a plan in state {plan.state!r}")
        errors = validate_plan(plan)
        if errors:
            raise PlanError("; ".join(errors))
        plan.state = "approved"
        plan.approved_by = by
        plan.approved_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        return plan

    def reject(self, plan: Plan, why: str = "") -> Plan:
        plan.state = "abandoned"
        plan.gates.append({"gate": "operator_approval", "rejected": True,
                           "why": why})
        return plan

    def activate(self, plan: Plan) -> Plan:
        if plan.state != "approved":
            raise PlanError("only an approved plan may execute")
        plan.state = "active"
        return plan

    def complete(self, plan: Plan) -> Plan:
        plan.state = "complete"
        return plan

    def supersede(self, old: Plan, new: Plan) -> Plan:
        if new.version <= old.version:
            raise PlanError("a superseding plan must have a higher version")
        old.state = "superseded"
        new.supersedes = old.version
        return new

    def guard(self, tool: str, specifier: str = "") -> None:
        """Raise if a side-effect tool is attempted while planning."""
        if tool.lower() in SIDE_EFFECT_TOOLS:
            raise PermissionDenied(self.policy.evaluate(tool, specifier))

    def executable(self, plan: Plan) -> bool:
        return plan.state in ("approved", "active") and not validate_plan(plan)
