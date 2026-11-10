"""Audit service tests — redaction guarantees."""
from __future__ import annotations

from Northstar_backend.foundation.audit import AuditService


def test_audit_records_basic_event(seeded_state):
    svc = AuditService(seeded_state.repos)
    row = svc.record(action="test.action", actor_user_id="u1", actor_role="operator",
                     organization_id=seeded_state.ids["org"],
                     resource_type="thing", resource_id="t1")
    assert row["action"] == "test.action"
    assert row["result"] == "success"


def test_audit_redacts_secret_keys(seeded_state):
    svc = AuditService(seeded_state.repos)
    row = svc.record(
        action="thing.update", organization_id=seeded_state.ids["org"],
        before_meta={"price": 1.0, "api_key": "should-not-appear"},
        after_meta={"token": "nope", "nested": {"password": "nope2", "ok": 1}})
    import json
    before = json.loads(row["before_meta"])
    after = json.loads(row["after_meta"])
    assert before["api_key"] == "[REDACTED]"
    assert after["token"] == "[REDACTED]"
    assert after["nested"]["password"] == "[REDACTED]"
    assert after["nested"]["ok"] == 1


def test_audit_never_contains_plaintext_secret(seeded_state):
    svc = AuditService(seeded_state.repos)
    row = svc.record(action="x", organization_id=seeded_state.ids["org"],
                     after_meta={"credential": "supersecretvalue"})
    assert "supersecretvalue" not in (row["after_meta"] or "")