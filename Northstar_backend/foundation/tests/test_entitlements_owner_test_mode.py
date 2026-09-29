"""P3-T2 entitlements/quota bypass tests for Owner Test Mode."""
from __future__ import annotations

import json

import pytest

from Northstar_backend.foundation.api.state import FoundationState
from Northstar_backend.foundation.billing.entitlements import EntitlementError
from Northstar_backend.foundation.bootstrap import bootstrap_owner
from Northstar_backend.foundation.context import build_context
from Northstar_backend.foundation.enums import Role

ADMIN = Role.INTERNAL_PLATFORM_ADMIN.value
VIEWER = Role.VIEWER.value
FEATURE = "advanced_reports"  # FREE tier denies this


def _state(tmp_path):
    st = FoundationState.build(str(tmp_path / "foundation.db"))
    r = bootstrap_owner(st, org_name="Test", user_email="owner@test.test",
                        role=ADMIN, recover=True)
    return st, r


def _ctx(r, role=ADMIN):
    return build_context(user_id=r["user_id"],
                         organization_id=r["organization_id"], role=role)


def test_flag_off_denies(monkeypatch, tmp_path):
    monkeypatch.delenv("NORTHSTAR_OWNER_TEST_MODE", raising=False)
    st, r = _state(tmp_path)
    try:
        with pytest.raises(EntitlementError):
            st.entitlements.enforce_feature(_ctx(r), FEATURE)
        assert st.entitlements.entitlements_for_org(r["organization_id"])[FEATURE] is False
    finally:
        st.close()


def test_flag_on_owner_gets_all_testable_features(monkeypatch, tmp_path):
    monkeypatch.setenv("NORTHSTAR_OWNER_TEST_MODE", "1")
    monkeypatch.setenv("ENVIRONMENT", "development")
    st, r = _state(tmp_path)
    try:
        ctx = _ctx(r)
        st.entitlements.enforce_feature(ctx, FEATURE)  # no raise
        eff = st.entitlements.entitlements_for_org(r["organization_id"], ctx=ctx)
        assert eff[FEATURE] is True
        assert eff["export_enabled"] is True
        assert eff["max_jobs_per_month"] >= 10 ** 9
        # base (non-owner) view is unchanged
        assert st.entitlements.entitlements_for_org(r["organization_id"])[FEATURE] is False
    finally:
        st.close()


def test_flag_on_non_owner_not_granted(monkeypatch, tmp_path):
    monkeypatch.setenv("NORTHSTAR_OWNER_TEST_MODE", "1")
    monkeypatch.setenv("ENVIRONMENT", "development")
    st, r = _state(tmp_path)
    try:
        vctx = _ctx(r, role=VIEWER)
        with pytest.raises(EntitlementError):
            st.entitlements.enforce_feature(vctx, FEATURE)
        assert st.entitlements.entitlements_for_org(r["organization_id"], ctx=vctx)[FEATURE] is False
    finally:
        st.close()


def test_owner_without_org_still_fails_closed(monkeypatch, tmp_path):
    monkeypatch.setenv("NORTHSTAR_OWNER_TEST_MODE", "1")
    monkeypatch.setenv("ENVIRONMENT", "development")
    st, r = _state(tmp_path)
    try:
        noorg = build_context(user_id=r["user_id"], organization_id=None, role=ADMIN)
        with pytest.raises(EntitlementError):
            st.entitlements.enforce_feature(noorg, FEATURE)
    finally:
        st.close()


def test_production_environment_fails_closed(monkeypatch, tmp_path):
    monkeypatch.setenv("NORTHSTAR_OWNER_TEST_MODE", "1")
    monkeypatch.setenv("ENVIRONMENT", "production")
    st, r = _state(tmp_path)
    try:
        with pytest.raises(EntitlementError):
            st.entitlements.enforce_feature(_ctx(r), FEATURE)
    finally:
        st.close()


def _set_usage(st, org, used):
    period = st.entitlements.current_period()
    st.db.insert_ignore("usage_counters",
                        {"organization_id": org, "period": period,
                         "monthly_jobs_used": used, "updated_at": "2026-01-01T00:00:00"},
                        conflict_cols=("organization_id",))
    st.db.conn.execute("UPDATE usage_counters SET monthly_jobs_used=? WHERE organization_id=?",
                       (used, org))
    st.db.conn.commit()


def test_quota_counted_but_not_enforced_then_restored(monkeypatch, tmp_path):
    monkeypatch.setenv("ENVIRONMENT", "development")
    st, r = _state(tmp_path)
    try:
        org = r["organization_id"]
        limit = int(st.entitlements.entitlements_for_org(org)["max_jobs_per_month"])
        _set_usage(st, org, limit - 1)

        monkeypatch.setenv("NORTHSTAR_OWNER_TEST_MODE", "1")
        st.entitlements.enforce_max_jobs(_ctx(r))            # reserves slot -> == limit
        assert st.entitlements.jobs_used_this_month(org) == limit
        st.entitlements.enforce_max_jobs(_ctx(r))            # over limit: still counted, not blocked
        assert st.entitlements.jobs_used_this_month(org) == limit + 1

        # flag off -> normal enforcement returns
        monkeypatch.delenv("NORTHSTAR_OWNER_TEST_MODE", raising=False)
        with pytest.raises(EntitlementError):
            st.entitlements.enforce_max_jobs(_ctx(r))
    finally:
        st.close()


def test_concept_rooms_reachable_for_owner_only(monkeypatch, tmp_path):
    # Concept-badged rooms have NO server-side feature gate (UI-nav only), so
    # "reachable" for the test-mode owner means all gated entitlements enabled;
    # non-owners keep normal decisions. Static/entitlement check, not a runtime
    # concept-gating test.
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("NORTHSTAR_OWNER_TEST_MODE", "1")
    st, r = _state(tmp_path)
    try:
        eff = st.entitlements.entitlements_for_org(r["organization_id"], ctx=_ctx(r))
        assert eff["export_enabled"] is True and eff["advanced_reports"] is True
        vctx = _ctx(r, role=VIEWER)
        assert st.entitlements.entitlements_for_org(r["organization_id"], ctx=vctx)["advanced_reports"] is False
    finally:
        st.close()


def test_bypass_audit_contents(monkeypatch, tmp_path):
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("NORTHSTAR_OWNER_TEST_MODE", "1")
    st, r = _state(tmp_path)
    try:
        org = r["organization_id"]
        limit = int(st.entitlements.entitlements_for_org(org)["max_jobs_per_month"])
        _set_usage(st, org, limit)
        st.entitlements.enforce_max_jobs(_ctx(r))            # triggers quota_bypass audit
        st.entitlements.enforce_feature(_ctx(r), FEATURE)    # triggers entitlement_bypass audit

        rows = st.repos.audit.list({})
        quota = [x for x in rows if x.get("action") == "owner_test_mode.quota_bypass"]
        ent = [x for x in rows if x.get("action") == "owner_test_mode.entitlement_bypass"]
        assert quota and ent
        meta = quota[0].get("after_meta")
        if isinstance(meta, str):
            meta = json.loads(meta)
        assert meta["owner_test_mode"] is True
        assert meta["feature"] == "max_jobs_per_month"
        assert meta["reason"] == "monthly_job_limit_exceeded"
        assert quota[0].get("actor_user_id") == r["user_id"]
        assert quota[0].get("organization_id") == org
        assert quota[0].get("occurred_at")
    finally:
        st.close()