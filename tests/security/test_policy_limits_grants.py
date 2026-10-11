"""Phase 2 acceptance tests — rate limits, run budgets, capability grants
(incl. expiry). Denials are asserted to be logged when they flow through the
kernel.
"""
from __future__ import annotations

import pytest

from northstar.policy import PolicyDenied, RateLimiter, RunBudget
from policy_helpers import FakeClock, make_kernel


class TestRateLimiter:
    def test_breach_after_burst(self):
        clock = FakeClock()
        limiter = RateLimiter(rate_per_minute=1.0, clock=clock)
        limiter.check("allowed.example")
        with pytest.raises(PolicyDenied) as excinfo:
            limiter.check("allowed.example")
        assert excinfo.value.reason == "rate_limited"

    def test_refills_over_time(self):
        clock = FakeClock()
        limiter = RateLimiter(rate_per_minute=60.0, burst=1.0, clock=clock)
        limiter.check("d.example")
        with pytest.raises(PolicyDenied):
            limiter.check("d.example")
        clock.advance(1.0)  # 60/min ⇒ one token refills per second
        limiter.check("d.example")

    def test_per_domain_override(self):
        clock = FakeClock()
        limiter = RateLimiter(
            rate_per_minute=0.001,
            burst=1.0,
            per_domain={"fast.example": 600.0},
            clock=clock,
        )
        limiter.check("fast.example")
        limiter.check("fast.example")  # overridden domain has burst=rate
        limiter.check("slow.example")
        with pytest.raises(PolicyDenied):
            limiter.check("slow.example")

    def test_kernel_rate_limit_breach_is_denied_and_logged(self):
        clock = FakeClock()
        bundle = make_kernel(
            clock=clock, rate_limiter=RateLimiter(rate_per_minute=1.0, clock=clock)
        )
        bundle.grants.issue("t1", ["fetch:allowed.example"])
        first = bundle.kernel.authorize_fetch(task_id="t1", url="http://allowed.example/1")
        second = bundle.kernel.authorize_fetch(task_id="t1", url="http://allowed.example/2")
        assert first.allowed
        assert not second.allowed and second.reason == "rate_limited"
        assert bundle.audit.entries[-1].reason == "rate_limited"


class TestRunBudget:
    def test_request_cap(self):
        budget = RunBudget(max_requests=1, max_bytes=10, max_seconds=60)
        budget.consume_request()
        with pytest.raises(PolicyDenied) as excinfo:
            budget.consume_request()
        assert excinfo.value.reason == "budget_requests"

    def test_byte_cap(self):
        budget = RunBudget(max_requests=5, max_bytes=10, max_seconds=60)
        budget.consume_bytes(6)
        budget.consume_bytes(4)
        with pytest.raises(PolicyDenied) as excinfo:
            budget.consume_bytes(1)
        assert excinfo.value.reason == "budget_bytes"

    def test_time_budget(self):
        clock = FakeClock()
        budget = RunBudget(max_requests=5, max_bytes=10, max_seconds=10, clock=clock)
        clock.advance(11)
        with pytest.raises(PolicyDenied) as excinfo:
            budget.consume_request()
        assert excinfo.value.reason == "budget_time"

    def test_kernel_budget_denial_logged(self):
        bundle = make_kernel(budget=RunBudget(max_requests=1, max_bytes=10, max_seconds=60))
        bundle.grants.issue("t1", ["fetch:allowed.example"])
        first = bundle.kernel.authorize_fetch(task_id="t1", url="http://allowed.example/1")
        second = bundle.kernel.authorize_fetch(task_id="t1", url="http://allowed.example/2")
        assert first.allowed
        assert not second.allowed and second.reason == "budget_requests"
        assert bundle.audit.entries[-1].reason == "budget_requests"


class TestGrants:
    def test_default_none(self):
        from northstar.policy import GrantSet

        grants = GrantSet()
        with pytest.raises(PolicyDenied) as excinfo:
            grants.check_fetch("t1", "allowed.example")
        assert excinfo.value.reason == "capability_missing"

    def test_issue_check_and_subdomain_coverage(self):
        from northstar.policy import GrantSet

        grants = GrantSet()
        grants.issue("t1", ["fetch:allowed.example"])
        grants.check_fetch("t1", "allowed.example")
        grants.check_fetch("t1", "sub.allowed.example")
        with pytest.raises(PolicyDenied):
            grants.check_fetch("t1", "other.example")

    def test_release_removes_grant(self):
        from northstar.policy import GrantSet

        grants = GrantSet()
        grants.issue("t1", ["fetch:allowed.example"])
        grants.release("t1")
        with pytest.raises(PolicyDenied) as excinfo:
            grants.check_fetch("t1", "allowed.example")
        assert excinfo.value.reason == "capability_missing"

    def test_expiry(self):
        from northstar.policy import GrantSet

        clock = FakeClock()
        grants = GrantSet(clock=clock)
        grants.issue("t1", ["fetch:allowed.example"], ttl_seconds=10)
        grants.check_fetch("t1", "allowed.example")
        clock.advance(11)
        with pytest.raises(PolicyDenied) as excinfo:
            grants.check_fetch("t1", "allowed.example")
        assert excinfo.value.reason == "capability_expired"

    def test_kernel_denies_expired_capability_and_logs(self):
        bundle = make_kernel()
        bundle.grants.issue("t1", ["fetch:allowed.example"], ttl_seconds=1)
        bundle.clock.advance(2)
        decision = bundle.kernel.authorize_fetch(task_id="t1", url="http://allowed.example/x")
        assert not decision.allowed and decision.reason == "capability_expired"
        assert bundle.audit.entries[-1].reason == "capability_expired"
