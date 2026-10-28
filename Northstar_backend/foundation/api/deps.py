"""API dependencies: real authentication + context (Phase 1C-01).

Authentication order (fail-closed):
  1. ``Authorization: Bearer <jwt>``  -> validate signature/exp/iss/aud, check
     revocation, then resolve organizations and roles from trusted DB records.
  2. No bearer: the development shim is honoured ONLY in local development
     (ENVIRONMENT=development AND effective client is loopback).
  3. Otherwise 401.

Role and organization are ALWAYS resolved from the database (memberships),
never from request headers or token claims. Development identity headers are
ignored outside local development.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import Header, HTTPException, Request

from ..context import RequestContext, PreviewContext, build_context
from ..enums import Environment, Role
from ..observability import new_id
from ..authn import (
    AuthError, decode_and_validate, effective_client_host, is_loopback_host,
    dev_shim_enabled, environment as auth_environment,
)
from .state import FoundationState


def get_state(request: Request) -> FoundationState:
    return request.app.state.foundation


def _auth_401(code: str, message: str = "") -> HTTPException:
    return HTTPException(status_code=401, detail={
        "code": code,
        "message": message or "authentication required",
    })


def _exp_iso(exp) -> Optional[str]:
    if not exp:
        return None
    try:
        return datetime.fromtimestamp(int(exp), tz=timezone.utc).isoformat()
    except (TypeError, ValueError, OverflowError):
        return None


def _active_memberships(state: FoundationState, user_id: str) -> list[dict]:
    """Memberships that are currently active (status == 'active'). Suspended or
    revoked memberships grant nothing (fail-closed)."""
    return [m for m in state.repos.memberships.for_user(user_id)
            if (m.get("status") or "active") == "active"]


def _resolve_org_and_role(state: FoundationState, user_id: str,
                          requested_org: Optional[str]):
    """Resolve (organization_id, role, is_platform_admin) from DB memberships."""
    memberships = _active_memberships(state, user_id)
    by_org = {m["organization_id"]: m for m in memberships}
    is_platform_admin = any(
        m.get("role") == Role.INTERNAL_PLATFORM_ADMIN.value for m in memberships)

    if requested_org:
        if requested_org in by_org:
            return requested_org, by_org[requested_org]["role"], is_platform_admin
        if is_platform_admin:
            return requested_org, Role.INTERNAL_PLATFORM_ADMIN.value, True
        raise HTTPException(status_code=403, detail={
            "code": "cross_organization_access_denied",
            "message": "your account is not a member of the requested organization",
        })
    if memberships:
        m = memberships[0]
        return m["organization_id"], m["role"], is_platform_admin
    return None, None, is_platform_admin


def _load_preview(state: FoundationState, preview_id: Optional[str],
                  actor_user_id: str, is_platform_admin: bool,
                  memberships_org_ids: set) -> Optional[PreviewContext]:
    if not preview_id:
        return None
    row = state.repos.preview_sessions.get(preview_id)
    if not row or not row.get("active"):
        return None
    # Only the actor who started the preview (or a platform admin) may use it.
    if row["actor_user_id"] != actor_user_id and not is_platform_admin:
        raise HTTPException(status_code=403, detail={
            "code": "preview_not_owned",
            "message": "this preview session belongs to another operator",
        })
    # Preview target organization must be authorized for this actor.
    target_org = row["target_organization_id"]
    if target_org not in memberships_org_ids and not is_platform_admin:
        raise HTTPException(status_code=403, detail={
            "code": "preview_org_denied",
            "message": "not authorized to preview the requested organization",
        })
    return PreviewContext(
        preview_id=row["id"], actor_user_id=row["actor_user_id"],
        target_organization_id=target_org, target_role=row.get("target_role"),
        reason=row.get("reason") or "", read_only=bool(row.get("read_only")),
        active=True,
    )


def get_context(
    request: Request,
    authorization: Optional[str] = Header(default=None),
    x_org_id: Optional[str] = Header(default=None),
    x_env: Optional[str] = Header(default=None),
    x_preview_id: Optional[str] = Header(default=None),
    x_user_id: Optional[str] = Header(default=None),
    x_role: Optional[str] = Header(default=None),  # ignored except dev shim
) -> RequestContext:
    state = get_state(request)
    request_id = request.headers.get("x-request-id") or new_id()

    client_host = effective_client_host(request)
    is_local = is_loopback_host(client_host)
    method: Optional[str] = None
    user_id: Optional[str] = None
    jti: Optional[str] = None
    org_claim: Optional[str] = None

    auth_token: Optional[str] = None
    from_cookie = False
    if authorization:
        # --- JWT path (validation executes before any identity header) ---
        if not authorization.lower().startswith("bearer "):
            raise _auth_401("invalid_authorization_header")
        auth_token = authorization.split(" ", 1)[1].strip()
    else:
        # --- Cookie session path (canonical hosted transport, P2-T5b) ---
        from ..auth_session import SESSION_COOKIE
        ck = request.cookies.get(SESSION_COOKIE)
        if ck:
            auth_token = ck
            from_cookie = True

    if auth_token:
        try:
            claims = decode_and_validate(auth_token)
        except AuthError as exc:
            raise _auth_401(exc.code, exc.message)
        user_id = str(claims.get("sub") or "")
        if not user_id:
            raise _auth_401("missing_subject")
        jti = claims.get("jti")
        org_claim = claims.get("tenant_id")
        method = "jwt"
        # Session revocation + register for future revocation.
        if jti:
            if state.repos.sessions.is_revoked(jti):
                raise _auth_401("session_revoked", "this session has been revoked")
            if not state.repos.sessions.by_jti(jti):
                state.repos.sessions.register(
                    jti, user_id, org_claim, _exp_iso(claims.get("exp")))
        # CSRF: cookie-authenticated state-changing requests must double-submit.
        if from_cookie:
            from ..auth_session import csrf_ok
            if not csrf_ok(request):
                raise HTTPException(status_code=403, detail={
                    "code": "csrf_failed", "message": "CSRF validation failed"})
    else:
        # --- Dev shim path: local development only ---
        if dev_shim_enabled() and is_local and x_user_id:
            method = "dev_shim"
            user_id = x_user_id
        else:
            raise _auth_401("authentication_required")

    if not user_id:
        raise _auth_401("missing_subject")

    org_id, role, is_platform_admin = _resolve_org_and_role(
        state, user_id,
        requested_org=(x_org_id or org_claim))
    # 1C-06 subscriber rules: an org in a BLOCKING lifecycle state denies the
    # NEXT authenticated request (not just the next login). Platform admins
    # (the beta operator) are exempt so they can still operate blocked orgs.
    if org_id and not is_platform_admin:
        _block_blocking_lifecycle(state, org_id)
    memberships_org_ids = {m["organization_id"]
                           for m in _active_memberships(state, user_id)}

    # Operating mode (sandbox|production) is a request dimension, not identity.
    env_req = (x_env or "").strip().lower()
    if env_req not in (Environment.SANDBOX.value, Environment.PRODUCTION.value):
        env_req = Environment.PRODUCTION.value

    preview = _load_preview(state, x_preview_id, user_id,
                            is_platform_admin, memberships_org_ids)

    ctx = build_context(
        user_id=user_id,
        organization_id=org_id,
        role=role,
        environment=env_req,
        preview=preview,
        request_id=request_id,
        auth_method=method,
    )
    # Stash for the denial-audit middleware (1C-05) so 403/404 responses can be
    # attributed to the authenticated actor without re-parsing the token.
    request.state.ctx = ctx
    return ctx


def current_auth_posture() -> dict:
    """Report whether real authentication is active (used by /auth-posture)."""
    from ..authn import jwt_secret
    return {
        "auth_posture": "jwt" if jwt_secret() else "dev_shim_local_only",
        "real_authentication_active": bool(jwt_secret()),
        "environment": auth_environment(),
        "remote_blocked_by_default": True,
    }


def _block_blocking_lifecycle(state, org_id: str) -> None:
    """1C-06 subscriber rules: orgs in a blocking lifecycle state deny the next
    authenticated request. Default (no lifecycle record) = active = allowed."""
    from ..operations import lifecycle as lc
    row = state.repos.org_lifecycle.get(org_id)
    if row is None:
        return
    if row["state"] in lc.BLOCKING_STATES:
        from fastapi import HTTPException
        raise HTTPException(status_code=403,
                            detail={"code": "org_lifecycle_blocked",
                                    "message": "access is currently disabled "
                                               "for this account",
                                    "state": row["state"]})