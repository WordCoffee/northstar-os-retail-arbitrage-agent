"""Deterministic policy kernel facade (Phase 2).

Composes every gate in a fixed order and audits EVERY decision (allow + deny):

    scheme/host parse → Amazon hard-block → allowlist → capability grant
    → SSRF resolve-and-pin → robots → per-domain rate limit → run budget

The kernel is pure code: no network, no file writes except through an
explicitly injected audit sink, and no runtime policy mutation API.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional, Sequence

from .allowlist import DEFAULT_ALLOWLIST, check_source
from .approvals import ApprovalQueue
from .audit import AuditLog
from .errors import PolicyConfigError, PolicyDenied
from .grants import GrantSet
from .limits import RateLimiter, RunBudget, check_response_size
from .robots import RobotsGate
from .ssrf import ResolvedTarget, resolve_and_pin

DEFAULT_MAX_RESPONSE_BYTES = 2_000_000
DEFAULT_MAX_REDIRECTS = 5


@dataclass(frozen=True)
class Decision:
    allowed: bool
    reason: str
    detail: str = ""
    target: Optional[ResolvedTarget] = None


class PolicyKernel:
    def __init__(
        self,
        *,
        allowlist: Sequence[str] = DEFAULT_ALLOWLIST,
        resolve: Optional[Callable[[str], Sequence[str]]] = None,
        robots: RobotsGate,
        grants: GrantSet,
        audit: AuditLog,
        approvals: Optional[ApprovalQueue] = None,
        rate_limiter: Optional[RateLimiter] = None,
        budget: Optional[RunBudget] = None,
        max_response_bytes: int = DEFAULT_MAX_RESPONSE_BYTES,
        max_redirects: int = DEFAULT_MAX_REDIRECTS,
    ) -> None:
        self.allowlist = tuple(allowlist)
        self.resolve = resolve
        self.robots = robots
        self.grants = grants
        self.audit = audit
        self.approvals = approvals
        self.rate_limiter = rate_limiter
        self.budget = budget
        self.max_response_bytes = max_response_bytes
        self.max_redirects = max_redirects

    # -- fetch authorization --------------------------------------------------
    def authorize_fetch(self, *, task_id: str, url: str) -> Decision:
        try:
            ascii_host = check_source(url, self.allowlist)
            self.grants.check_fetch(task_id, ascii_host)
            target = resolve_and_pin(ascii_host, self.resolve)
            self.robots.check(url)
            if self.rate_limiter is not None:
                self.rate_limiter.check(ascii_host)
            if self.budget is not None:
                self.budget.consume_request()
        except PolicyDenied as denied:
            self.audit.append(
                actor=task_id,
                action="fetch",
                decision="deny",
                reason=denied.reason,
                detail=f"{url} :: {denied.detail}".strip(" :"),
            )
            return Decision(False, denied.reason, denied.detail)
        except PolicyConfigError as bad:
            self.audit.append(
                actor=task_id,
                action="fetch",
                decision="deny",
                reason="url_rejected",
                detail=f"{url} :: {bad}",
            )
            return Decision(False, "url_rejected", str(bad))
        self.audit.append(
            actor=task_id, action="fetch", decision="allow", reason="ok", detail=url
        )
        return Decision(True, "ok", "", target)

    def authorize_redirect_chain(self, *, task_id: str, urls: Sequence[str]) -> Decision:
        """Validate every hop; the redirect count is capped."""
        if not urls:
            return Decision(False, "url_rejected", "empty_redirect_chain")
        if len(urls) - 1 > self.max_redirects:
            self.audit.append(
                actor=task_id,
                action="redirect_chain",
                decision="deny",
                reason="too_many_redirects",
                detail=str(len(urls) - 1),
            )
            return Decision(False, "too_many_redirects", str(len(urls) - 1))
        for url in urls:
            decision = self.authorize_fetch(task_id=task_id, url=url)
            if not decision.allowed:
                return decision
        return Decision(True, "ok")

    # -- response handling ----------------------------------------------------
    def check_response_size(self, *, task_id: str, size: int) -> Decision:
        try:
            count = check_response_size(size, self.max_response_bytes)
        except PolicyDenied as denied:
            self.audit.append(
                actor=task_id,
                action="response_size",
                decision="deny",
                reason=denied.reason,
                detail=denied.detail,
            )
            return Decision(False, denied.reason, denied.detail)
        self.audit.append(
            actor=task_id, action="response_size", decision="allow", reason="ok", detail=str(size)
        )
        return Decision(True, "ok")
