"""HITL approval queue: request, approve/deny, deny-by-default gate."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent_kernel import hitl


def test_request_is_pending_and_approve_unlocks_it(tmp_path):
    rec = hitl.request("apply_self_patch", root=tmp_path, payload={"file": "a.py"})
    assert rec["status"] == "pending"
    assert [r["id"] for r in hitl.pending(tmp_path)] == [rec["id"]]
    with pytest.raises(hitl.ApprovalRequired):
        hitl.require_approved(tmp_path, rec["id"])
    approved = hitl.approve(tmp_path, rec["id"], "operator", "looks right")
    assert approved["status"] == "approved"
    assert hitl.require_approved(tmp_path, rec["id"])["operator"] == "operator"


def test_deny_is_final_and_blocks_the_gate(tmp_path):
    rec = hitl.request("apply_self_patch", root=tmp_path)
    hitl.deny(tmp_path, rec["id"], "operator", "not now")
    with pytest.raises(hitl.ApprovalRequired):
        hitl.require_approved(tmp_path, rec["id"])
    with pytest.raises(hitl.ApprovalRequired):
        hitl.approve(tmp_path, rec["id"], "operator")


def test_unknown_or_traversal_ids_are_refused(tmp_path):
    with pytest.raises(hitl.ApprovalRequired):
        hitl.require_approved(tmp_path, "hitl_../../etc")
    with pytest.raises(hitl.ApprovalRequired):
        hitl.require_approved(tmp_path, "hitl_20260101T000000_deadbeef")


def test_publish_failure_keeps_the_local_request(tmp_path):
    def broken(_record):
        raise RuntimeError("matrix down")
    rec = hitl.request("apply_self_patch", root=tmp_path, publish=broken)
    assert rec["published"] is False
    assert "matrix down" in rec["publish_error"]
    assert hitl.pending(tmp_path)[0]["id"] == rec["id"]
