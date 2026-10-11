"""Phase 2 acceptance tests — robots, approvals, SIMULATED guard, and the
tamper-evident audit log (chain integrity, tamper detection, redaction, sink).
"""
from __future__ import annotations

import dataclasses
import json

import pytest

from northstar.policy import (
    GENESIS_HASH,
    SIMULATED,
    ApprovalQueue,
    AuditLog,
    JsonlSink,
    PolicyConfigError,
    PolicyDenied,
    RobotsGate,
    assert_snapshot_writable,
)
from policy_helpers import ROBOTS_TEXT, FakeClock, make_kernel


class TestRobots:
    def test_allowed_path(self):
        bundle = make_kernel()
        bundle.grants.issue("t1", ["fetch:allowed.example"])
        decision = bundle.kernel.authorize_fetch(task_id="t1", url="http://allowed.example/page")
        assert decision.allowed

    def test_disallowed_path_denied_and_logged(self):
        bundle = make_kernel()
        bundle.grants.issue("t1", ["fetch:allowed.example"])
        decision = bundle.kernel.authorize_fetch(
            task_id="t1", url="http://allowed.example/private/x"
        )
        assert not decision.allowed and decision.reason == "robots_denied"
        assert bundle.audit.entries[-1].reason == "robots_denied"

    def test_unknown_robots_denied_by_default(self):
        bundle = make_kernel(robots=RobotsGate({}))
        bundle.grants.issue("t1", ["fetch:allowed.example"])
        decision = bundle.kernel.authorize_fetch(task_id="t1", url="http://allowed.example/x")
        assert not decision.allowed and decision.reason == "robots_unknown"

    def test_unknown_robots_allowed_only_when_operator_disables_requirement(self):
        bundle = make_kernel(robots=RobotsGate({}, require_robots=False))
        bundle.grants.issue("t1", ["fetch:allowed.example"])
        decision = bundle.kernel.authorize_fetch(task_id="t1", url="http://allowed.example/x")
        assert decision.allowed


class TestApprovals:
    def test_approval_flow_records_approver(self):
        clock = FakeClock()
        queue = ApprovalQueue(clock=clock)
        item = queue.request(
            task_id="t1", kind="live_fetch", reason="compat run", requester="brain"
        )
        assert item.status == "pending"
        assert queue.pending() == [item]
        approved = queue.approve(item.id, "operator-tyrone")
        assert approved.status == "approved"
        assert approved.decided_by == "operator-tyrone"
        assert queue.is_approved(item.id)

    def test_self_approval_denied(self):
        queue = ApprovalQueue()
        item = queue.request(
            task_id="t1", kind="spend", reason="", requester="brain"
        )
        with pytest.raises(PolicyDenied) as excinfo:
            queue.approve(item.id, "brain")
        assert excinfo.value.reason == "self_approval"

    def test_double_decision_denied(self):
        queue = ApprovalQueue()
        item = queue.request(
            task_id="t1", kind="side_effect", reason="", requester="brain"
        )
        queue.approve(item.id, "operator")
        with pytest.raises(PolicyDenied) as excinfo:
            queue.deny(item.id, "operator")
        assert excinfo.value.reason == "already_decided"

    def test_deny_flow(self):
        queue = ApprovalQueue()
        item = queue.request(
            task_id="t1", kind="live_fetch", reason="", requester="brain"
        )
        denied = queue.deny(item.id, "operator")
        assert denied.status == "denied"
        assert not queue.is_approved(item.id)

    def test_unknown_item(self):
        queue = ApprovalQueue()
        assert queue.is_approved("ap-9999") is False
        with pytest.raises(PolicyDenied) as excinfo:
            queue.approve("ap-9999", "operator")
        assert excinfo.value.reason == "unknown_item"

    def test_unknown_kind_rejected(self):
        queue = ApprovalQueue()
        with pytest.raises(PolicyConfigError):
            queue.request(task_id="t1", kind="wildcard", reason="", requester="brain")


class TestSimulatedGuard:
    def test_simulated_never_reaches_snapshot(self):
        with pytest.raises(PolicyDenied) as excinfo:
            assert_snapshot_writable(SIMULATED)
        assert excinfo.value.reason == "simulated_never_snapshot"

    def test_other_classes_pass(self):
        assert_snapshot_writable("live-verified")
        assert_snapshot_writable("provider-observation")


class TestAuditLog:
    def test_chain_verifies_and_links(self):
        log = AuditLog(clock=FakeClock())
        first = log.append(actor="t1", action="fetch", decision="allow", reason="ok", detail="")
        second = log.append(actor="t1", action="fetch", decision="deny", reason="private_ip", detail="")
        assert log.verify()
        assert first.prev_hash == GENESIS_HASH
        assert second.prev_hash == first.entry_hash

    def test_tamper_breaks_chain(self):
        log = AuditLog(clock=FakeClock())
        log.append(actor="t1", action="a", decision="allow")
        log.append(actor="t1", action="b", decision="deny", reason="x")
        log.append(actor="t1", action="c", decision="allow")
        assert log.verify()
        tampered = dataclasses.replace(log._entries[1], detail="tampered")  # type: ignore[attr-defined]
        log._entries[1] = tampered  # type: ignore[attr-defined]
        assert not log.verify()

    def test_detail_is_redacted_before_storage(self):
        log = AuditLog(clock=FakeClock())
        entry = log.append(
            actor="t1",
            action="fetch",
            decision="allow",
            detail="Authorization: Bearer sk-FAKEFAKEFAKEFAKE123456",
        )
        assert "FAKEFAKEFAKEFAKE123456" not in entry.detail
        assert "[REDACTED]" in entry.detail

    def test_jsonl_sink_writes_chain_lines(self, tmp_path):
        sink = JsonlSink(tmp_path / "audit.jsonl")
        log = AuditLog(clock=FakeClock(), sinks=[sink])
        log.append(actor="t1", action="a", decision="allow")
        log.append(actor="t1", action="b", decision="deny", reason="amazon_blocked")
        lines = (tmp_path / "audit.jsonl").read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 2
        records = [json.loads(line) for line in lines]
        assert records[0]["prev_hash"] == GENESIS_HASH
        assert records[1]["prev_hash"] == records[0]["entry_hash"]
        assert records[1]["reason"] == "amazon_blocked"


class TestKernelLogging:
    def test_denies_are_logged_with_reason(self):
        bundle = make_kernel()
        bundle.kernel.authorize_fetch(task_id="t1", url="http://10.0.0.1/x")
        entry = bundle.audit.entries[-1]
        assert entry.decision == "deny"
        assert entry.reason in ("private_ip", "domain_not_allowed")
        assert "10.0.0.1" in entry.detail

    def test_allows_are_logged(self):
        bundle = make_kernel()
        bundle.grants.issue("t1", ["fetch:allowed.example"])
        bundle.kernel.authorize_fetch(task_id="t1", url="http://allowed.example/x")
        entry = bundle.audit.entries[-1]
        assert entry.decision == "allow" and entry.action == "fetch"

    def test_log_verifies_after_mixed_traffic(self):
        bundle = make_kernel()
        bundle.grants.issue("t1", ["fetch:allowed.example"])
        bundle.kernel.authorize_fetch(task_id="t1", url="http://allowed.example/ok")
        bundle.kernel.authorize_fetch(task_id="t1", url="http://blocked.example/no")
        bundle.kernel.authorize_fetch(task_id="t1", url="http://169.254.169.254/meta")
        assert bundle.audit.verify()
