"""Shared helpers for Phase 2 policy-kernel tests.

Deterministic: fake clock, injected resolver, supplied robots text.
NO network, NO sleeps.
"""
from __future__ import annotations

from types import SimpleNamespace

from northstar.policy import AuditLog, GrantSet, PolicyKernel, RobotsGate

PUBLIC_IP = "93.184.216.34"

ROBOTS_TEXT = "User-agent: *\nAllow: /\nDisallow: /private\n"


class FakeClock:
    def __init__(self, t: float = 1_000.0) -> None:
        self.t = float(t)

    def __call__(self) -> float:
        return self.t

    def advance(self, seconds: float) -> None:
        self.t += seconds


def make_resolver(*ips: str):
    """Resolver returning fixed answers; records calls in ``.calls``."""
    calls: list[str] = []

    def resolve(host: str):
        calls.append(host)
        return list(ips)

    resolve.calls = calls  # type: ignore[attr-defined]
    return resolve


def make_robots(hosts=("allowed.example", "sub.allowed.example")):
    return RobotsGate({host: ROBOTS_TEXT for host in hosts})


def make_kernel(
    *,
    allowlist=("allowed.example",),
    resolve=None,
    clock=None,
    robots=None,
    grants=None,
    audit=None,
    **kwargs,
):
    """Build a kernel bundle with deterministic defaults.

    Returns SimpleNamespace(kernel, audit, grants, robots, clock, resolve).
    ``resolve=None`` means the fake public-IP resolver (pass ``"none"`` for a
    genuinely missing resolver).
    """
    clock = clock or FakeClock()
    if resolve == "none":
        resolve = None
    elif resolve is None:
        resolve = make_resolver(PUBLIC_IP)
    robots = robots if robots is not None else make_robots()
    grants = grants if grants is not None else GrantSet(clock=clock)
    audit = audit if audit is not None else AuditLog(clock=clock)
    kernel = PolicyKernel(
        allowlist=allowlist,
        resolve=resolve,
        robots=robots,
        grants=grants,
        audit=audit,
        **kwargs,
    )
    return SimpleNamespace(
        kernel=kernel, audit=audit, grants=grants, robots=robots, clock=clock, resolve=resolve
    )
