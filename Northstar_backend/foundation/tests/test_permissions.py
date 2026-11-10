"""Permissions + modes tests (owner decision 5)."""
from __future__ import annotations

from Northstar_backend.foundation.context import build_context, PreviewContext
from Northstar_backend.foundation.permissions import (
    has_permission, evaluate, permissions_for_role,
    PERM_VIEW, PERM_DRAFT, PERM_RUN_LOCAL, PERM_REQUEST_REFRESH, PERM_APPROVE,
    PERM_MANAGE_TEAM, PERM_MANAGE_ORG, PERM_VIEW_AUDIT, PERM_PREVIEW,
    PERM_WRITE_EXTERNAL, PERM_PURCHASE, PERM_VIEW_LEDGER, PERM_VIEW_PROVIDERS,
    PERM_VIEW_APPROVALS,
)
from Northstar_backend.foundation.enums import Role, Environment, ViewContext


def test_viewer_can_view_only():
    assert has_permission(Role.VIEWER.value, PERM_VIEW)
    assert not has_permission(Role.VIEWER.value, PERM_DRAFT)


def test_viewer_blocked_from_billing_providers_approvals_audit():
    """1C-05: viewer is read-only and must NOT access billing/ledger, provider
    configuration, or administrative approval/audit metadata."""
    assert not has_permission(Role.VIEWER.value, PERM_VIEW_LEDGER)
    assert not has_permission(Role.VIEWER.value, PERM_VIEW_PROVIDERS)
    assert not has_permission(Role.VIEWER.value, PERM_VIEW_APPROVALS)
    assert not has_permission(Role.VIEWER.value, PERM_VIEW_AUDIT)
    assert permissions_for_role(Role.VIEWER.value) == {PERM_VIEW}


def test_operator_can_view_ledger_providers_approvals():
    assert has_permission(Role.OPERATOR.value, PERM_VIEW_LEDGER)
    assert has_permission(Role.OPERATOR.value, PERM_VIEW_PROVIDERS)
    assert has_permission(Role.OPERATOR.value, PERM_VIEW_APPROVALS)
    assert not has_permission(Role.OPERATOR.value, PERM_MANAGE_ORG)


def test_owner_and_admin_hold_all_operational_permissions():
    for role in (Role.ORGANIZATION_OWNER.value, Role.ORGANIZATION_ADMIN.value,
                 Role.INTERNAL_PLATFORM_ADMIN.value):
        assert has_permission(role, PERM_VIEW_LEDGER)
        assert has_permission(role, PERM_VIEW_PROVIDERS)
        assert has_permission(role, PERM_VIEW_APPROVALS)


def test_analyst_can_draft_and_run_local():
    assert has_permission(Role.ANALYST.value, PERM_DRAFT)
    assert has_permission(Role.ANALYST.value, PERM_RUN_LOCAL)
    assert not has_permission(Role.ANALYST.value, PERM_APPROVE)


def test_operator_can_approve_and_preview():
    assert has_permission(Role.OPERATOR.value, PERM_APPROVE)
    assert has_permission(Role.OPERATOR.value, PERM_PREVIEW)
    assert not has_permission(Role.OPERATOR.value, PERM_MANAGE_ORG)


def test_owner_can_manage_org_and_request_purchase():
    assert has_permission(Role.ORGANIZATION_OWNER.value, PERM_MANAGE_ORG)
    assert has_permission(Role.ORGANIZATION_OWNER.value, PERM_PURCHASE)


def test_sandbox_blocks_external_write():
    ctx = build_context(role=Role.ORGANIZATION_OWNER.value, environment=Environment.SANDBOX.value)
    allowed, reason = evaluate(ctx, PERM_WRITE_EXTERNAL)
    assert not allowed
    assert reason == "sandbox_blocks_external_write"


def test_production_allows_external_write_permission():
    ctx = build_context(role=Role.ORGANIZATION_OWNER.value,
                        environment=Environment.PRODUCTION.value)
    allowed, _ = evaluate(ctx, PERM_WRITE_EXTERNAL)
    assert allowed


def test_preview_cannot_elevate_role():
    # real viewer previewing as owner -> effective role stays viewer
    preview = PreviewContext(preview_id="p1", actor_user_id="u1",
                             target_organization_id="org2",
                             target_role=Role.ORGANIZATION_OWNER.value)
    ctx = build_context(role=Role.VIEWER.value, preview=preview)
    assert ctx.effective_role == Role.VIEWER.value
    assert not has_permission(ctx.effective_role, PERM_MANAGE_ORG)


def test_preview_can_only_downgrade_role():
    preview = PreviewContext(preview_id="p1", actor_user_id="u1",
                             target_organization_id="org2",
                             target_role=Role.VIEWER.value)
    ctx = build_context(role=Role.ORGANIZATION_OWNER.value, preview=preview)
    assert ctx.effective_role == Role.VIEWER.value


def test_preview_blocks_writes():
    preview = PreviewContext(preview_id="p1", actor_user_id="u1",
                             target_organization_id="org2", read_only=True)
    ctx = build_context(role=Role.ORGANIZATION_OWNER.value, preview=preview)
    assert ctx.is_preview
    assert not ctx.allow_write()
    allowed, reason = evaluate(ctx, PERM_WRITE_EXTERNAL)
    assert not allowed
    assert reason == "preview_read_only"


def test_three_dimensions_are_independent():
    preview = PreviewContext(preview_id="p1", actor_user_id="u1",
                             target_organization_id="org2")
    ctx = build_context(role=Role.OPERATOR.value, organization_id="org1",
                        environment=Environment.SANDBOX.value, preview=preview)
    assert ctx.is_sandbox is True
    assert ctx.role == Role.OPERATOR.value
    assert ctx.view_context == ViewContext.AUDITED_CUSTOMER_PREVIEW.value
    assert ctx.effective_organization_id == "org2"