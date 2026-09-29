"""Foundation API router — `/api/v1/foundation/*`.

Typed contracts, stable error envelope, null-first responses, explicit provenance,
authorization checks. No provider execution, no external writes.
"""
from __future__ import annotations

import os
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field

from ..context import RequestContext
from ..enums import (
    Role, Environment, CapabilitySafetyClass, RiskLevel, ApprovalState,
    ObservationType, IdentifierKind, ViewContext,
)
from ..models import (
    Marketplace, Organization, User, Membership, Observation,
    JobRequest, UsageEvent, ApprovalRequest, PreviewSessionResponse,
    UserContextResponse, ProvenanceMeta,
)
from ..permissions import (
    permissions_for_role, evaluate, PERM_VIEW, PERM_DRAFT, PERM_RUN_LOCAL,
    PERM_REQUEST_REFRESH, PERM_APPROVE, PERM_MANAGE_TEAM, PERM_MANAGE_ORG,
    PERM_VIEW_AUDIT, PERM_PREVIEW, PERM_VIEW_LEDGER, PERM_VIEW_PROVIDERS,
    PERM_VIEW_APPROVALS, PERM_PLATFORM_ADMIN,
)
from ..identity import IdentitySubmission
from ..provenance import make_observation, provenance_meta
from .deps import get_state, get_context, current_auth_posture
from .state import FoundationState

router = APIRouter(prefix="/api/v1/foundation", tags=["foundation"])


# ---- liveness / readiness (public; also serves Monitoring later) -------------

@router.get("/health")
def health() -> dict:
    """Public liveness/readiness probe. No auth, no side effects, no secrets.

    Kept dependency-free so container orchestration and Monitoring can probe it
    even when the database or auth posture is degraded.
    """
    import os as _os
    backend = "postgres" if _os.environ.get("FOUNDATION_DB_URL") else "sqlite"
    return {
        "status": "ok",
        "service": "northstar-foundation",
        "version": "foundation-1",
        "db_backend": backend,
        "environment": _os.environ.get("ENVIRONMENT", "development"),
    }


# ---- helpers -----------------------------------------------------------------

def _err(code: str, message: str, status: int = 400, **details) -> HTTPException:
    return HTTPException(status_code=status,
                         detail={"code": code, "message": message, "details": details})


def _require(ctx: RequestContext, permission: str) -> None:
    allowed, reason = evaluate(ctx, permission)
    if not allowed:
        raise _err("permission_denied", reason, 403, permission=permission)


def _enforce_acceptance(state, ctx):
    from ..beta.acceptance import enforce, AcceptanceError
    try:
        enforce(state, ctx)
    except AcceptanceError as e:
        if e.code == "acceptance_required":
            raise _err("acceptance_required", str(e), 409)
        raise _err(e.code, str(e), 400)


def require_acceptance(state: FoundationState = Depends(get_state),
                       ctx: RequestContext = Depends(get_context)) -> RequestContext:
    """Deny feature use until the actor has accepted the current published
    beta documents (1C-06). No-op when no documents are published."""
    _enforce_acceptance(state, ctx)
    return ctx


_ACCEPTANCE = [Depends(require_acceptance)]


def _iso(dt) -> Optional[str]:
    return dt.isoformat() if isinstance(dt, datetime) else dt


# ---- request bodies ----------------------------------------------------------

class OrgCreate(BaseModel):
    name: str
    slug: str = ""
    environment: str = Environment.PRODUCTION.value


class PreviewStart(BaseModel):
    target_organization_id: str
    target_role: Optional[str] = None
    reason: str


class IdentitySubmit(BaseModel):
    marketplace_id: Optional[str] = None
    asin: Optional[str] = None
    identifiers: list[dict] = Field(default_factory=list)  # [{kind, value}]
    title: Optional[str] = None
    brand: Optional[str] = None
    source: str = "provider"
    source_identifier: Optional[str] = None
    pack_count: Optional[int] = None
    pack_unit: Optional[str] = None
    pack_ambiguous: bool = False
    variation_family_ref: Optional[str] = None


class ObservationSubmit(BaseModel):
    product_id: Optional[str] = None
    candidate_id: Optional[str] = None
    marketplace_id: Optional[str] = None
    provider: Optional[str] = None
    provider_record_id: Optional[str] = None
    observation_type: str = ObservationType.PRICE.value
    observed_value: Optional[object] = None
    currency: Optional[str] = None
    unit: Optional[str] = None
    confidence: Optional[float] = None
    raw_source_ref: Optional[str] = None
    transformation_version: Optional[str] = None
    environment: str = Environment.SANDBOX.value


class JobCreate(BaseModel):
    service: str
    scope_type: Optional[str] = None
    scope_id: Optional[str] = None
    data_types: list[str] = Field(default_factory=list)
    provider_policy: Optional[str] = None
    max_estimated_cost: Optional[float] = None
    idempotency_key: Optional[str] = None
    reason: Optional[str] = None
    priority: int = 5
    environment: str = Environment.SANDBOX.value


class ApprovalCreate(BaseModel):
    capability: str
    safety_class: str = CapabilitySafetyClass.WRITE_EXTERNAL.value
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    change_preview: Optional[dict] = None
    risk_level: str = RiskLevel.MEDIUM.value
    cost_estimate: Optional[float] = None
    idempotency_key: Optional[str] = None


class ApprovalDecide(BaseModel):
    decision: str = ApprovalState.GRANTED.value
    note: Optional[str] = None


class UiPrefBody(BaseModel):
    value: object


class DurableJobCreate(BaseModel):
    job_type: str
    payload: Optional[dict] = None
    payload_schema_version: str = "1.0"
    idempotency_key: Optional[str] = None
    priority: int = 5
    reason: Optional[str] = None
    correlation_id: Optional[str] = None
    service: Optional[str] = None
    environment: Optional[str] = None


class JobCancelBody(BaseModel):
    reason: str = "operator cancelled"


class JobRetryBody(BaseModel):
    reason: str = "operator retry"


class ScheduleCreate(BaseModel):
    job_template: dict
    timezone: str = "UTC"
    cron_expression: Optional[str] = None
    interval_seconds: Optional[int] = None
    enabled: bool = False
    concurrency_policy: Optional[dict] = None
    misfire_policy: str = "skip"
    first_run_at: Optional[str] = None


class ScheduleUpdate(BaseModel):
    enabled: Optional[bool] = None
    cron_expression: Optional[str] = None
    interval_seconds: Optional[int] = None
    job_template: Optional[dict] = None
    concurrency_policy: Optional[dict] = None
    misfire_policy: Optional[str] = None


class ScheduleActionBody(BaseModel):
    enabled: Optional[bool] = None


class KeywordSearchBody(BaseModel):
    query: Optional[str] = None
    limit: int = 50


class ImportDryRunBody(BaseModel):
    file_name: str


class ImportSubmitBody(BaseModel):
    file_name: str
    idempotency_key: Optional[str] = None


class ImportCancelBody(BaseModel):
    reason: str = "operator cancelled"


class LoginBody(BaseModel):
    email: str
    password: str


# ---- context / identity ------------------------------------------------------

@router.get("/me", response_model=UserContextResponse)
def me(state: FoundationState = Depends(get_state),
       ctx: RequestContext = Depends(get_context)):
    orgs = []
    if ctx.user_id:
        for m in state.repos.memberships.for_user(ctx.user_id):
            org = state.repos.organizations.get(m["organization_id"])
            if org:
                orgs.append({"id": org["id"], "name": org["name"], "role": m["role"]})
    role = ctx.effective_role
    return UserContextResponse(
        user_id=ctx.user_id or "",
        email="",
        display_name="",
        organizations=orgs,
        active_organization_id=ctx.effective_organization_id,
        role=role,
        environment=ctx.environment,
        view_context=ctx.view_context,
        permissions=sorted(permissions_for_role(role)) if role else [],
    )


@router.post("/auth/login")
def login(body: LoginBody, request: Request, response: Response,
          state: FoundationState = Depends(get_state)):
    """Email+password login. Sets the HttpOnly session cookie + a double-submit
    CSRF cookie. Never returns an access token to JavaScript (P2-T5b)."""
    from ..auth_session import (
        mint_access_token, session_cookie_kwargs, new_csrf_token,
        csrf_cookie_kwargs, DEFAULT_TTL_SECONDS,
    )
    from ..authn import jwt_secret, environment as auth_environment
    from ..credentials import get_by_email, verify_password
    from .. import login_throttle

    if not jwt_secret():
        # Fail closed everywhere (not just prod-like) rather than 500 on mint.
        raise _err("auth_unconfigured", "authentication is not configured", 503)
    try:
        login_throttle.require_shared(state.db, auth_environment())
    except login_throttle.ThrottleUnavailable as exc:
        raise _err("auth_store_unavailable", str(exc), 503)

    email = (body.email or "").strip().lower()
    client = request.client.host if getattr(request, "client", None) else "unknown"
    rate_key = f"{email}|{client}"
    if not login_throttle.allow(state.db, rate_key):
        raise _err("rate_limited", "too many login attempts; try again later", 429)

    row = get_by_email(state.db, email)
    if not row or not verify_password(body.password, row["password_hash"]):
        state.audit.record(action="auth.login.failed", actor_user_id=None,
                           after_meta={"email": email}, result="denied")
        raise _err("invalid_credentials", "Invalid email or password", 401)

    login_throttle.reset(state.db, rate_key)
    user_id = row["user_id"]
    active = [m for m in state.repos.memberships.for_user(user_id)
              if (m.get("status") or "active") == "active"]
    org_id = active[0]["organization_id"] if active else None
    role = active[0]["role"] if active else None

    token, jti, exp = mint_access_token(user_id=user_id, org_id=org_id, role=role)
    state.repos.sessions.register(jti, user_id, org_id, exp.isoformat())
    response.set_cookie(**session_cookie_kwargs(token, max_age=DEFAULT_TTL_SECONDS))
    response.set_cookie(**csrf_cookie_kwargs(new_csrf_token(), max_age=DEFAULT_TTL_SECONDS))
    state.audit.record(action="auth.login.success", actor_user_id=user_id,
                       organization_id=org_id, after_meta={"email": email})
    return {"ok": True, "user_id": user_id}


@router.post("/auth/logout")
def logout(request: Request, response: Response,
           state: FoundationState = Depends(get_state),
           ctx: RequestContext = Depends(get_context)):
    """Revoke the current session and clear the session + CSRF cookies."""
    from ..auth_session import SESSION_COOKIE, CSRF_COOKIE, SESSION_PATH, CSRF_PATH
    from ..authn import decode_and_validate, AuthError
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        try:
            jti = decode_and_validate(token).get("jti")
        except AuthError:
            jti = None
        if jti:
            state.repos.sessions.revoke(jti, reason="logout")
    response.delete_cookie(SESSION_COOKIE, path=SESSION_PATH)
    response.delete_cookie(CSRF_COOKIE, path=CSRF_PATH)
    state.audit.record(action="auth.logout", actor_user_id=ctx.user_id,
                       organization_id=ctx.effective_organization_id, after_meta={})
    return {"ok": True}


@router.get("/roles")
def roles(ctx: RequestContext = Depends(get_context)):
    out = {}
    for r in Role:
        out[r.value] = sorted(permissions_for_role(r.value))
    return {"roles": out}


@router.get("/environment")
def environment(ctx: RequestContext = Depends(get_context)):
    posture = current_auth_posture()
    return {
        "environment": ctx.environment,
        "view_context": ctx.view_context,
        "is_sandbox": ctx.is_sandbox,
        "is_preview": ctx.is_preview,
        "writes_allowed": ctx.allow_write(),
        "auth_method": ctx.auth_method,
        "auth_posture": posture["auth_posture"],
        "real_authentication_active": posture["real_authentication_active"],
        "remote_blocked_by_default": True,
        # LOCAL-ONLY UI mode: "private_beta" hides the legacy Operations Hub
        # shell in the canonical UI. Set by the local stack; defaults to "full"
        # everywhere else (staging/production unchanged).
        "ui_mode": os.environ.get("NORTHSTAR_UI_MODE", "full"),
    }


@router.get("/ui-mode")
def ui_mode():
    """Public UI-mode signal (no auth) so signed-out clients also land in the
    correct beta entry state. LOCAL-ONLY: set by the local stack; defaults to
    'full' everywhere else."""
    return {"ui_mode": os.environ.get("NORTHSTAR_UI_MODE", "full")}


@router.get("/auth-posture")
def auth_posture(ctx: RequestContext = Depends(get_context)):
    """Authenticated posture report (Phase 1C-01). Requires valid auth."""
    posture = current_auth_posture()
    return {
        **posture,
        "auth_method": ctx.auth_method,
        "blocks": ["all foundation API responses", "preview sessions",
                   "preview-mode state", "any frontend route that calls the API"],
        "dev_headers_ignored_outside_local_development": True,
    }


@router.post("/session/revoke")
def session_revoke(state: FoundationState = Depends(get_state),
                   ctx: RequestContext = Depends(get_context),
                   jti: Optional[str] = Query(default=None)):
    """Revoke a session. Defaults to the caller's own current session; an
    internal platform admin may revoke any session by jti."""
    target = jti
    if not target:
        raise _err("jti_required", "provide the session jti to revoke", 400)
    row = state.repos.sessions.by_jti(target)
    if not row:
        raise _err("not_found", "unknown session", 404)
    is_admin = ctx.effective_role == Role.INTERNAL_PLATFORM_ADMIN.value
    if row["user_id"] != ctx.user_id and not is_admin:
        raise _err("permission_denied", "cannot revoke another user's session", 403)
    state.repos.sessions.revoke(target, reason="operator_revoked")
    state.audit.record(action="session.revoke", actor_user_id=ctx.user_id,
                       actor_role=ctx.effective_role,
                       organization_id=ctx.effective_organization_id,
                       resource_type="session", resource_id=target)
    return {"jti": target, "revoked": True}


# ---- organizations -----------------------------------------------------------

@router.get("/organizations", dependencies=_ACCEPTANCE)
def list_organizations(state: FoundationState = Depends(get_state),
                       ctx: RequestContext = Depends(get_context)):
    _require(ctx, PERM_VIEW)
    if not ctx.user_id:
        return {"items": []}
    items = []
    for m in state.repos.memberships.for_user(ctx.user_id):
        if (m.get("status") or "active") != "active":
            continue
        org = state.repos.organizations.get(m["organization_id"])
        if org:
            org = dict(org)
            org["role"] = m["role"]
            items.append(org)
    return {"items": items}


@router.post("/organizations", status_code=201, dependencies=_ACCEPTANCE)
def create_organization(body: OrgCreate,
                        state: FoundationState = Depends(get_state),
                        ctx: RequestContext = Depends(get_context)):
    _require(ctx, PERM_MANAGE_ORG)
    org = Organization(name=body.name, slug=body.slug or body.name.lower().replace(" ", "-"),
                       environment=body.environment)
    row = state.repos.organizations.add(org)
    state.audit.record(action="organization.create", actor_user_id=ctx.user_id,
                       actor_role=ctx.role, organization_id=org.id,
                       resource_type="organization", resource_id=org.id)
    return row


@router.get("/organizations/{org_id}/memberships", dependencies=_ACCEPTANCE)
def list_memberships(org_id: str, state: FoundationState = Depends(get_state),
                     ctx: RequestContext = Depends(get_context)):
    _require(ctx, PERM_MANAGE_TEAM)
    return {"items": state.repos.memberships.for_org(org_id)}


# ---- customer preview --------------------------------------------------------

@router.post("/preview/start", response_model=PreviewSessionResponse, dependencies=_ACCEPTANCE)
def preview_start(body: PreviewStart, state: FoundationState = Depends(get_state),
                  ctx: RequestContext = Depends(get_context)):
    _require(ctx, PERM_PREVIEW)
    if not ctx.user_id:
        raise _err("no_actor", "preview requires an authenticated actor", 401)
    # The target organization must be authorized for this actor (server-side).
    member_orgs = {m["organization_id"] for m in
                   state.repos.memberships.for_user(ctx.user_id)
                   if (m.get("status") or "active") == "active"}
    is_admin = ctx.effective_role == Role.INTERNAL_PLATFORM_ADMIN.value
    if body.target_organization_id not in member_orgs and not is_admin:
        raise _err("preview_org_denied",
                   "not authorized to preview that organization", 403)
    from ..models import utcnow
    from uuid import uuid4
    preview_id = str(uuid4())
    state.db.insert("preview_sessions", {
        "id": preview_id, "actor_user_id": ctx.user_id,
        "target_organization_id": body.target_organization_id,
        "target_role": body.target_role, "started_at": utcnow().isoformat(),
        "ended_at": None, "reason": body.reason, "read_only": True, "active": True,
    })
    state.audit.record(
        action="preview.start", actor_user_id=ctx.user_id, actor_role=ctx.role,
        organization_id=ctx.organization_id,
        target_organization_id=body.target_organization_id,
        environment=ctx.environment, view_context=ViewContext.AUDITED_CUSTOMER_PREVIEW.value,
        resource_type="preview_session", resource_id=preview_id,
        after_meta={"reason": body.reason, "target_role": body.target_role})
    return PreviewSessionResponse(
        preview_id=preview_id, actor_user_id=ctx.user_id,
        target_organization_id=body.target_organization_id,
        target_role=body.target_role, started_at=utcnow(),
        reason=body.reason, read_only=True, active=True)


@router.post("/preview/end", dependencies=_ACCEPTANCE)
def preview_end(state: FoundationState = Depends(get_state),
                ctx: RequestContext = Depends(get_context),
                preview_id: Optional[str] = Query(default=None)):
    _require(ctx, PERM_PREVIEW)
    pid = preview_id or (ctx.preview.preview_id if ctx.preview else None)
    if not pid:
        raise _err("no_preview", "no active preview to end", 400)
    from ..models import utcnow
    state.db.conn.execute(
        "UPDATE preview_sessions SET active=?, ended_at=? WHERE id=?",
        (False, utcnow().isoformat(), pid))
    state.db.conn.commit()
    state.audit.record(action="preview.end", actor_user_id=ctx.user_id,
                       actor_role=ctx.role, organization_id=ctx.organization_id,
                       view_context=ViewContext.AUDITED_CUSTOMER_PREVIEW.value,
                       resource_type="preview_session", resource_id=pid)
    return {"preview_id": pid, "active": False}


@router.get("/preview/active", dependencies=_ACCEPTANCE)
def preview_active(state: FoundationState = Depends(get_state),
                   ctx: RequestContext = Depends(get_context)):
    if not ctx.preview:
        return {"active": False, "preview": None}
    p = ctx.preview
    return {"active": True, "preview": {
        "preview_id": p.preview_id, "target_organization_id": p.target_organization_id,
        "target_role": p.target_role, "reason": p.reason, "read_only": p.read_only,
    }}


# ---- marketplaces ------------------------------------------------------------

@router.get("/marketplaces", dependencies=_ACCEPTANCE)
def list_marketplaces(state: FoundationState = Depends(get_state),
                      ctx: RequestContext = Depends(get_context)):
    _require(ctx, PERM_VIEW)
    return {"items": state.repos.marketplaces.list()}


# ---- products / identity -----------------------------------------------------

@router.get("/products", dependencies=_ACCEPTANCE)
def list_products(state: FoundationState = Depends(get_state),
                  ctx: RequestContext = Depends(get_context),
                  limit: int = Query(default=50, le=200), offset: int = 0):
    _require(ctx, PERM_VIEW)
    return {"items": state.repos.products.list(limit=limit, offset=offset),
            "total": state.repos.products.count()}


@router.get("/products/{product_id}", dependencies=_ACCEPTANCE)
def get_product(product_id: str, state: FoundationState = Depends(get_state),
                ctx: RequestContext = Depends(get_context)):
    _require(ctx, PERM_VIEW)
    row = state.repos.products.get(product_id)
    if row is None:
        raise _err("not_found", "product not found", 404)
    ids = state.repos.identifiers.list(where={"product_id": product_id})
    pack = None
    if row.get("pack_config_id"):
        pack = state.repos.pack_configs.get(row["pack_config_id"])
    return {"product": row, "identifiers": ids, "pack_config": pack,
            "meta": provenance_meta(make_observation(
                observation_type="product", observed_value=None,
                provenance_class="imported"))}


@router.post("/identity/submit", status_code=201, dependencies=_ACCEPTANCE)
def identity_submit(body: IdentitySubmit, state: FoundationState = Depends(get_state),
                    ctx: RequestContext = Depends(get_context)):
    _require(ctx, PERM_DRAFT)
    mp_id = body.marketplace_id
    if not mp_id:
        mp = state.repos.marketplaces.by_code("amazon.com")
        mp_id = mp["id"] if mp else None
    sub = IdentitySubmission(
        marketplace_id=mp_id or "", asin=body.asin,
        identifiers=[(i.get("kind"), i.get("value")) for i in body.identifiers],
        title=body.title, brand=body.brand, source=body.source,
        source_identifier=body.source_identifier, pack_count=body.pack_count,
        pack_unit=body.pack_unit, pack_ambiguous=body.pack_ambiguous,
        variation_family_ref=body.variation_family_ref,
    )
    result = state.identity.submit(sub)
    state.audit.record(action="identity.submit", actor_user_id=ctx.user_id,
                       actor_role=ctx.role, organization_id=ctx.organization_id,
                       resource_type="catalog_product", resource_id=result.product_id,
                       after_meta={"resolution": result.resolution})
    return {"resolution": result.resolution, "product_id": result.product_id,
            "candidate_id": result.candidate_id, "conflict_id": result.conflict_id,
            "detail": result.detail}


@router.get("/identity/candidates", dependencies=_ACCEPTANCE)
def identity_candidates(state: FoundationState = Depends(get_state),
                        ctx: RequestContext = Depends(get_context)):
    _require(ctx, PERM_VIEW)
    return {"items": state.repos.candidates.list()}


@router.get("/identity/conflicts", dependencies=_ACCEPTANCE)
def identity_conflicts(state: FoundationState = Depends(get_state),
                       ctx: RequestContext = Depends(get_context)):
    _require(ctx, PERM_VIEW)
    return {"items": state.repos.conflicts.list()}


# ---- observations ------------------------------------------------------------

@router.post("/observations", status_code=201, dependencies=_ACCEPTANCE)
def add_observation(body: ObservationSubmit, state: FoundationState = Depends(get_state),
                    ctx: RequestContext = Depends(get_context)):
    _require(ctx, PERM_DRAFT)
    obs = make_observation(
        observation_type=body.observation_type, observed_value=body.observed_value,
        provider=body.provider, provider_record_id=body.provider_record_id,
        product_id=body.product_id, candidate_id=body.candidate_id,
        marketplace_id=body.marketplace_id, currency=body.currency, unit=body.unit,
        confidence=body.confidence, raw_source_ref=body.raw_source_ref,
        transformation_version=body.transformation_version,
        environment=body.environment,
    )
    row = state.repos.observations.add(obs)
    return {"observation": row, "meta": provenance_meta(obs)}


@router.get("/products/{product_id}/observations", dependencies=_ACCEPTANCE)
def product_observations(product_id: str, state: FoundationState = Depends(get_state),
                         ctx: RequestContext = Depends(get_context),
                         observation_type: Optional[str] = None):
    _require(ctx, PERM_VIEW)
    items = state.repos.observations.for_product(product_id, observation_type)
    return {"items": items}


# ---- providers ---------------------------------------------------------------

@router.get("/providers", dependencies=_ACCEPTANCE)
def list_providers(state: FoundationState = Depends(get_state),
                   ctx: RequestContext = Depends(get_context)):
    _require(ctx, PERM_VIEW_PROVIDERS)
    # Provider definitions are global infrastructure (credential_ref_names are
    # NAMES only; actual secrets live in the vault and are never exposed).
    return {"items": state.repos.providers.list()}


@router.get("/providers/{provider_key}", dependencies=_ACCEPTANCE)
def get_provider(provider_key: str, state: FoundationState = Depends(get_state),
                 ctx: RequestContext = Depends(get_context)):
    _require(ctx, PERM_VIEW_PROVIDERS)
    row = state.repos.providers.by_key(provider_key)
    if row is None:
        raise _err("not_found", "provider not found", 404)
    return {"provider": row}


# ---- jobs --------------------------------------------------------------------

@router.post("/jobs", status_code=201, dependencies=_ACCEPTANCE)
def create_job(body: JobCreate, state: FoundationState = Depends(get_state),
               ctx: RequestContext = Depends(get_context)):
    _require(ctx, PERM_REQUEST_REFRESH)
    if not ctx.organization_id:
        raise _err("no_org", "organization context required", 400)
    req = JobRequest(
        organization_id=ctx.effective_organization_id or "",
        user_id=ctx.user_id or "", service=body.service, scope_type=body.scope_type,
        scope_id=body.scope_id, data_types=body.data_types,
        provider_policy=body.provider_policy, max_estimated_cost=body.max_estimated_cost,
        idempotency_key=body.idempotency_key, reason=body.reason,
        priority=body.priority, environment=body.environment,
        requires_approval=bool(body.max_estimated_cost),
    )
    row = state.jobs.request_job(req)
    state.audit.record(action="job.request", actor_user_id=ctx.user_id,
                       actor_role=ctx.role, organization_id=req.organization_id,
                       resource_type="job_request", resource_id=row["id"],
                       environment=body.environment)
    return {"job_request": row}


@router.get("/jobs/{job_request_id}", dependencies=_ACCEPTANCE)
def get_job(job_request_id: str, state: FoundationState = Depends(get_state),
            ctx: RequestContext = Depends(get_context)):
    _require(ctx, PERM_VIEW)
    row = state.repos.job_requests.get(job_request_id)
    if row is None:
        raise _err("not_found", "job request not found", 404)
    runs = state.repos.job_runs.by_request(job_request_id)
    return {"job_request": row, "runs": runs}


@router.get("/jobs/runs/{run_id}", dependencies=_ACCEPTANCE)
def get_run(run_id: str, state: FoundationState = Depends(get_state),
            ctx: RequestContext = Depends(get_context)):
    _require(ctx, PERM_VIEW)
    rows = state.repos.job_runs.list(where={"run_id": run_id})
    if not rows:
        raise _err("not_found", "run not found", 404)
    return {"run": rows[0]}


@router.post("/jobs/runs/{run_id}/cancel", dependencies=_ACCEPTANCE)
def cancel_run(run_id: str, state: FoundationState = Depends(get_state),
               ctx: RequestContext = Depends(get_context)):
    _require(ctx, PERM_REQUEST_REFRESH)
    rows = state.repos.job_runs.list(where={"run_id": run_id})
    if not rows:
        raise _err("not_found", "run not found", 404)
    row = state.jobs.cancel(rows[0]["id"])
    state.audit.record(action="job.cancel", actor_user_id=ctx.user_id,
                       actor_role=ctx.role, organization_id=ctx.organization_id,
                       resource_type="job_run", resource_id=run_id)
    return {"run": row}


# ---- durable jobs (1C-04) -------------------------------------------------

@router.get("/jobs-durable/handler-registry", dependencies=_ACCEPTANCE)
def jobs_durable_handler_registry(state: FoundationState = Depends(get_state),
                                  ctx: RequestContext = Depends(get_context)):
    """Read-only metadata about registered (local/fake) job handlers."""
    _require(ctx, PERM_VIEW)
    return {"handlers": state.jobs_durable.registry.metadata(),
            "only_local_handlers": True}


@router.get("/jobs-durable/queue-posture", dependencies=_ACCEPTANCE)
def jobs_durable_queue_posture(state: FoundationState = Depends(get_state),
                               ctx: RequestContext = Depends(get_context)):
    _require(ctx, PERM_VIEW)
    org_id = ctx.effective_organization_id
    if not org_id:
        raise _err("no_org", "organization context required", 400)
    return state.jobs_durable.queue_posture(org_id)


@router.get("/jobs-durable", dependencies=_ACCEPTANCE)
def jobs_durable_list(state: FoundationState = Depends(get_state),
                      ctx: RequestContext = Depends(get_context),
                      limit: int = Query(default=50, le=200), offset: int = 0,
                      job_state: Optional[str] = Query(default=None, alias="state")):
    _require(ctx, PERM_VIEW)
    org_id = ctx.effective_organization_id
    if not org_id:
        raise _err("no_org", "organization context required", 400)
    return state.jobs_durable.list_jobs(org_id, limit=limit, offset=offset,
                                        state=job_state)


@router.post("/jobs-durable", status_code=201, dependencies=_ACCEPTANCE)
def jobs_durable_create(body: DurableJobCreate,
                        state: FoundationState = Depends(get_state),
                        ctx: RequestContext = Depends(get_context)):
    from ..jobs_durable import JobValidationError
    from ..jobs_handlers import UnknownJobType
    try:
        row = state.jobs_durable.submit(
            ctx, job_type=body.job_type, payload=body.payload,
            payload_schema_version=body.payload_schema_version,
            idempotency_key=body.idempotency_key, priority=body.priority,
            reason=body.reason, correlation_id=body.correlation_id,
            service=body.service, environment=body.environment or ctx.environment)
    except UnknownJobType as e:
        raise _err("unknown_job_type", str(e), 400)
    except JobValidationError as e:
        if e.code == "entitlement_denied":
            raise _err("entitlement_denied", str(e), 403)  # non-revealing
        status = 403 if e.code in ("permission_denied", "membership_inactive") else 400
        raise _err(e.code, str(e), status)
    return row


@router.get("/jobs-durable/{job_id}", dependencies=_ACCEPTANCE)
def jobs_durable_get(job_id: str, state: FoundationState = Depends(get_state),
                     ctx: RequestContext = Depends(get_context)):
    _require(ctx, PERM_VIEW)
    org_id = ctx.effective_organization_id
    if not org_id:
        raise _err("no_org", "organization context required", 400)
    row = state.jobs_durable.get_job(org_id, job_id)
    if row is None:
        raise _err("not_found", "job not found", 404)
    return row


@router.get("/jobs-durable/{job_id}/audit", dependencies=_ACCEPTANCE)
def jobs_durable_audit(job_id: str, state: FoundationState = Depends(get_state),
                       ctx: RequestContext = Depends(get_context)):
    _require(ctx, PERM_VIEW_AUDIT)
    org_id = ctx.effective_organization_id
    if not org_id:
        raise _err("no_org", "organization context required", 400)
    timeline = state.jobs_durable.audit_timeline(org_id, job_id)
    if not timeline:
        raise _err("not_found", "job not found or no timeline", 404)
    return {"items": timeline}


@router.get("/jobs-durable/runs/{run_id}", dependencies=_ACCEPTANCE)
def jobs_durable_run(run_id: str, state: FoundationState = Depends(get_state),
                     ctx: RequestContext = Depends(get_context)):
    _require(ctx, PERM_VIEW)
    org_id = ctx.effective_organization_id
    if not org_id:
        raise _err("no_org", "organization context required", 400)
    row = state.jobs_durable.get_run(org_id, run_id)
    if row is None:
        raise _err("not_found", "run not found", 404)
    return row


@router.post("/jobs-durable/{job_id}/cancel", dependencies=_ACCEPTANCE)
def jobs_durable_cancel(job_id: str, body: JobCancelBody,
                        state: FoundationState = Depends(get_state),
                        ctx: RequestContext = Depends(get_context)):
    from ..jobs_durable import JobValidationError
    try:
        row = state.jobs_durable.cancel(ctx, job_id, reason=body.reason)
    except JobValidationError as e:
        if e.code == "not_found":
            raise _err("not_found", "job not found", 404)  # non-enumerating
        raise _err(e.code, str(e), 409 if e.code == "not_cancellable" else 403)
    return row


@router.post("/jobs-durable/{job_id}/retry", dependencies=_ACCEPTANCE)
def jobs_durable_retry(job_id: str, body: JobRetryBody,
                       state: FoundationState = Depends(get_state),
                       ctx: RequestContext = Depends(get_context)):
    from ..jobs_durable import JobValidationError
    try:
        row = state.jobs_durable.retry(ctx, job_id, reason=body.reason)
    except JobValidationError as e:
        if e.code == "not_found":
            raise _err("not_found", "job not found", 404)  # non-enumerating
        raise _err(e.code, str(e), 409 if e.code == "not_retryable" else 403)
    return row


# ---- schedules (1C-04 / B15) ------------------------------------------------

@router.get("/schedules", dependencies=_ACCEPTANCE)
def schedules_list(state: FoundationState = Depends(get_state),
                   ctx: RequestContext = Depends(get_context),
                   include_archived: bool = False):
    _require(ctx, PERM_VIEW)
    org_id = ctx.effective_organization_id
    if not org_id:
        raise _err("no_org", "organization context required", 400)
    return {"items": state.scheduler.list_schedules(org_id,
                                                    include_archived=include_archived)}


@router.post("/schedules", status_code=201, dependencies=_ACCEPTANCE)
def schedules_create(body: ScheduleCreate, state: FoundationState = Depends(get_state),
                     ctx: RequestContext = Depends(get_context)):
    from ..jobs_scheduler import SchedulerError
    _require(ctx, PERM_REQUEST_REFRESH)
    org_id = ctx.effective_organization_id
    if not org_id:
        raise _err("no_org", "organization context required", 400)
    if not ctx.user_id:
        raise _err("no_actor", "authenticated user required", 401)
    try:
        row = state.scheduler.create_schedule(
            organization_id=org_id, owner_user_id=ctx.user_id,
            job_template=body.job_template, timezone=body.timezone,
            cron_expression=body.cron_expression,
            interval_seconds=body.interval_seconds, enabled=body.enabled,
            concurrency_policy=body.concurrency_policy,
            misfire_policy=body.misfire_policy, first_run_at=body.first_run_at)
    except SchedulerError as e:
        raise _err("schedule_invalid", str(e), 400)
    return row


@router.get("/schedules/posture", dependencies=_ACCEPTANCE)
def schedules_posture(state: FoundationState = Depends(get_state),
                      ctx: RequestContext = Depends(get_context)):
    _require(ctx, PERM_VIEW)
    org_id = ctx.effective_organization_id
    if not org_id:
        raise _err("no_org", "organization context required", 400)
    return state.scheduler.posture(org_id)


@router.get("/schedules/{schedule_id}", dependencies=_ACCEPTANCE)
def schedules_get(schedule_id: str, state: FoundationState = Depends(get_state),
                  ctx: RequestContext = Depends(get_context)):
    _require(ctx, PERM_VIEW)
    org_id = ctx.effective_organization_id
    if not org_id:
        raise _err("no_org", "organization context required", 400)
    row = state.scheduler.get_schedule(org_id, schedule_id)
    if row is None:
        raise _err("not_found", "schedule not found", 404)
    return row


@router.put("/schedules/{schedule_id}", dependencies=_ACCEPTANCE)
def schedules_update(schedule_id: str, body: ScheduleUpdate,
                     state: FoundationState = Depends(get_state),
                     ctx: RequestContext = Depends(get_context)):
    from ..jobs_scheduler import SchedulerError
    _require(ctx, PERM_REQUEST_REFRESH)
    org_id = ctx.effective_organization_id
    if not org_id:
        raise _err("no_org", "organization context required", 400)
    fields = body.model_dump(exclude_none=True)
    try:
        row = state.scheduler.update_schedule(
            organization_id=org_id, schedule_id=schedule_id,
            actor_user_id=ctx.user_id or "", **fields)
    except SchedulerError as e:
        raise _err("not_found", str(e), 404)
    return row


@router.post("/schedules/{schedule_id}/enable", dependencies=_ACCEPTANCE)
def schedules_enable(schedule_id: str, state: FoundationState = Depends(get_state),
                     ctx: RequestContext = Depends(get_context)):
    _require(ctx, PERM_REQUEST_REFRESH)
    org_id = ctx.effective_organization_id
    row = state.scheduler.set_enabled(organization_id=org_id, schedule_id=schedule_id,
                                      enabled=True, actor_user_id=ctx.user_id or "")
    return row


@router.post("/schedules/{schedule_id}/disable", dependencies=_ACCEPTANCE)
def schedules_disable(schedule_id: str, state: FoundationState = Depends(get_state),
                      ctx: RequestContext = Depends(get_context)):
    _require(ctx, PERM_REQUEST_REFRESH)
    org_id = ctx.effective_organization_id
    row = state.scheduler.set_enabled(organization_id=org_id, schedule_id=schedule_id,
                                      enabled=False, actor_user_id=ctx.user_id or "")
    return row


@router.post("/schedules/{schedule_id}/archive", dependencies=_ACCEPTANCE)
def schedules_archive(schedule_id: str, state: FoundationState = Depends(get_state),
                      ctx: RequestContext = Depends(get_context)):
    from ..jobs_scheduler import SchedulerError
    _require(ctx, PERM_REQUEST_REFRESH)
    org_id = ctx.effective_organization_id
    try:
        row = state.scheduler.archive(organization_id=org_id, schedule_id=schedule_id,
                                      actor_user_id=ctx.user_id or "")
    except SchedulerError as e:
        raise _err("not_found", str(e), 404)
    return row


# ---- keyword & SEO intelligence (1C-05) ------------------------------------

def _kw_contracts(state):
    from ..keywords.contracts import KeywordReadContracts
    return KeywordReadContracts(state.repos)


@router.get("/keywords/search", dependencies=_ACCEPTANCE)
def keywords_search(state: FoundationState = Depends(get_state),
                    ctx: RequestContext = Depends(get_context),
                    q: Optional[str] = Query(default=None),
                    limit: int = Query(default=50, le=200)):
    _require(ctx, PERM_VIEW)
    org_id = ctx.effective_organization_id
    if not org_id:
        raise _err("no_org", "organization context required", 400)
    return {"items": _kw_contracts(state).relevant_keywords(org_id, query=q,
                                                            limit=limit)}


@router.get("/keywords/products/{asin}", dependencies=_ACCEPTANCE)
def keywords_by_product(asin: str, state: FoundationState = Depends(get_state),
                        ctx: RequestContext = Depends(get_context)):
    _require(ctx, PERM_VIEW)
    org_id = ctx.effective_organization_id
    if not org_id:
        raise _err("no_org", "organization context required", 400)
    links = state.repos.keyword_links.list(
        where={"organization_id": org_id, "asin": asin})
    keywords = [state.repos.keywords.get(l["keyword_id"]) for l in links]
    return {"asin": asin,
            "keywords": [k for k in keywords if k and k["organization_id"] == org_id],
            "links": links}


@router.get("/keywords/coverage/{keyword_id}", dependencies=_ACCEPTANCE)
def keywords_coverage(keyword_id: str, state: FoundationState = Depends(get_state),
                      ctx: RequestContext = Depends(get_context)):
    _require(ctx, PERM_VIEW)
    org_id = ctx.effective_organization_id
    if not org_id:
        raise _err("no_org", "organization context required", 400)
    return _kw_contracts(state).listing_coverage(org_id, keyword_id)


@router.get("/keywords/gaps", dependencies=_ACCEPTANCE)
def keywords_gaps(state: FoundationState = Depends(get_state),
                  ctx: RequestContext = Depends(get_context)):
    _require(ctx, PERM_VIEW)
    org_id = ctx.effective_organization_id
    if not org_id:
        raise _err("no_org", "organization context required", 400)
    return {"items": _kw_contracts(state).keyword_gaps(org_id)}


@router.get("/keywords/search-terms", dependencies=_ACCEPTANCE)
def keywords_search_terms(state: FoundationState = Depends(get_state),
                          ctx: RequestContext = Depends(get_context),
                          limit: int = Query(default=200, le=500)):
    _require(ctx, PERM_VIEW)
    org_id = ctx.effective_organization_id
    if not org_id:
        raise _err("no_org", "organization context required", 400)
    return {"items": _kw_contracts(state).search_terms(org_id, limit=limit)}


@router.get("/keywords/targets/performance", dependencies=_ACCEPTANCE)
def keywords_target_performance(state: FoundationState = Depends(get_state),
                                ctx: RequestContext = Depends(get_context)):
    _require(ctx, PERM_VIEW)
    org_id = ctx.effective_organization_id
    if not org_id:
        raise _err("no_org", "organization context required", 400)
    return {"items": _kw_contracts(state).target_performance(org_id)}


@router.get("/keywords/harvest-candidates", dependencies=_ACCEPTANCE)
def keywords_harvest(state: FoundationState = Depends(get_state),
                     ctx: RequestContext = Depends(get_context)):
    _require(ctx, PERM_VIEW)
    org_id = ctx.effective_organization_id
    return {"items": _kw_contracts(state).harvest_candidates(org_id)}


@router.get("/keywords/negation-candidates", dependencies=_ACCEPTANCE)
def keywords_negations(state: FoundationState = Depends(get_state),
                       ctx: RequestContext = Depends(get_context)):
    _require(ctx, PERM_VIEW)
    org_id = ctx.effective_organization_id
    return {"items": _kw_contracts(state).negation_candidates(org_id)}


@router.get("/keywords/rank-history/{keyword_id}", dependencies=_ACCEPTANCE)
def keywords_rank_history(keyword_id: str, state: FoundationState = Depends(get_state),
                          ctx: RequestContext = Depends(get_context)):
    _require(ctx, PERM_VIEW)
    org_id = ctx.effective_organization_id
    return {"items": _kw_contracts(state).rank_history(org_id, keyword_id)}


@router.get("/keywords/conflicts", dependencies=_ACCEPTANCE)
def keywords_conflicts(state: FoundationState = Depends(get_state),
                       ctx: RequestContext = Depends(get_context)):
    _require(ctx, PERM_VIEW)
    org_id = ctx.effective_organization_id
    return {"items": state.repos.keyword_conflicts.list(
        where={"organization_id": org_id})}


@router.get("/keywords/sources", dependencies=_ACCEPTANCE)
def keywords_sources(state: FoundationState = Depends(get_state),
                     ctx: RequestContext = Depends(get_context)):
    _require(ctx, PERM_VIEW)
    org_id = ctx.effective_organization_id
    if not org_id:
        raise _err("no_org", "organization context required", 400)
    return state.keywords.sources.source_status(org_id)


@router.post("/keywords/imports/dry-run", dependencies=_ACCEPTANCE)
def keywords_import_dry_run(body: ImportDryRunBody,
                            state: FoundationState = Depends(get_state),
                            ctx: RequestContext = Depends(get_context)):
    from ..keywords.importer import ImportError_
    _require(ctx, PERM_RUN_LOCAL)
    org_id = ctx.effective_organization_id
    if not org_id:
        raise _err("no_org", "organization context required", 400)
    path = state.keywords._resolve_path(body.file_name)
    try:
        result = state.keywords.dry_run(org_id, path)
    except ImportError_ as e:
        raise _err(e.code, str(e), 400)
    return result


@router.post("/keywords/imports", status_code=202, dependencies=_ACCEPTANCE)
def keywords_import_submit(body: ImportSubmitBody,
                           state: FoundationState = Depends(get_state),
                           ctx: RequestContext = Depends(get_context)):
    """Submit a keyword import as a 1C-04 job (never runs inline)."""
    from ..keywords.importer import ImportError_
    from ..jobs_durable import JobValidationError
    _require(ctx, PERM_RUN_LOCAL)
    org_id = ctx.effective_organization_id
    if not org_id:
        raise _err("no_org", "organization context required", 400)
    if not ctx.user_id:
        raise _err("no_actor", "authenticated user required", 401)
    path = state.keywords._resolve_path(body.file_name)
    try:
        registered = state.keywords.sources.register_file(org_id, path)
        sf = registered["source_file"]
        job = state.jobs_durable.submit(
            ctx, job_type="keyword_import",
            payload={"source_file_id": sf["id"], "organization_id": org_id,
                     "submitted_by": ctx.user_id},
            payload_schema_version="1.0",
            idempotency_key=body.idempotency_key,
            reason=f"keyword import {sf['file_name']}")
    except ImportError_ as e:
        raise _err(e.code, str(e), 400)
    except JobValidationError as e:
        raise _err(e.code, str(e), 400)
    return {"job_id": job["id"], "state": job["state"],
            "source_file_id": sf["id"], "file_name": sf["file_name"],
            "status": "submitted", "executes_in_worker": True}


@router.get("/keywords/imports", dependencies=_ACCEPTANCE)
def keywords_imports(state: FoundationState = Depends(get_state),
                     ctx: RequestContext = Depends(get_context)):
    _require(ctx, PERM_VIEW)
    org_id = ctx.effective_organization_id
    if not org_id:
        raise _err("no_org", "organization context required", 400)
    return {"items": state.keywords.batches(org_id)}


@router.get("/keywords/imports/{batch_id}", dependencies=_ACCEPTANCE)
def keywords_import_status(batch_id: str, state: FoundationState = Depends(get_state),
                           ctx: RequestContext = Depends(get_context)):
    from ..keywords.importer import ImportError_
    _require(ctx, PERM_VIEW)
    org_id = ctx.effective_organization_id
    if not org_id:
        raise _err("no_org", "organization context required", 400)
    try:
        return state.keywords.batch_status(org_id, batch_id)
    except ImportError_ as e:
        raise _err(e.code, str(e), 404)


@router.get("/keywords/imports/{batch_id}/rejected", dependencies=_ACCEPTANCE)
def keywords_import_rejected(batch_id: str, state: FoundationState = Depends(get_state),
                             ctx: RequestContext = Depends(get_context)):
    from ..keywords.importer import ImportError_
    _require(ctx, PERM_VIEW)
    org_id = ctx.effective_organization_id
    if not org_id:
        raise _err("no_org", "organization context required", 400)
    try:
        return {"items": state.keywords.rejected_rows(org_id, batch_id)}
    except ImportError_ as e:
        raise _err(e.code, str(e), 404)


@router.post("/keywords/imports/{batch_id}/cancel", dependencies=_ACCEPTANCE)
def keywords_import_cancel(batch_id: str, body: ImportCancelBody,
                           state: FoundationState = Depends(get_state),
                           ctx: RequestContext = Depends(get_context)):
    from ..keywords.importer import ImportError_
    _require(ctx, PERM_RUN_LOCAL)
    org_id = ctx.effective_organization_id
    if not org_id:
        raise _err("no_org", "organization context required", 400)
    try:
        return state.keywords.cancel(org_id, batch_id, actor=ctx.user_id)
    except ImportError_ as e:
        status = 409 if e.code == "not_cancellable" else 404
        raise _err(e.code, str(e), status)


@router.get("/keywords/provenance/{keyword_id}", dependencies=_ACCEPTANCE)
def keywords_provenance(keyword_id: str, state: FoundationState = Depends(get_state),
                        ctx: RequestContext = Depends(get_context)):
    _require(ctx, PERM_VIEW)
    org_id = ctx.effective_organization_id
    kw = state.repos.keywords.get(keyword_id)
    if kw is None or kw["organization_id"] != org_id:
        raise _err("not_found", "keyword not found", 404)
    return {"keyword_id": keyword_id,
            "provenance_class": "imported",
            "source": "local_import",
            "confidence": kw.get("confidence"),
            "freshness_state": kw.get("freshness_state"),
            "created_at": kw.get("created_at")}


@router.get("/keywords/{keyword_id}", dependencies=_ACCEPTANCE)
def keywords_get(keyword_id: str, state: FoundationState = Depends(get_state),
                 ctx: RequestContext = Depends(get_context)):
    _require(ctx, PERM_VIEW)
    org_id = ctx.effective_organization_id
    if not org_id:
        raise _err("no_org", "organization context required", 400)
    kw = state.repos.keywords.get(keyword_id)
    if kw is None or kw["organization_id"] != org_id:
        raise _err("not_found", "keyword not found", 404)
    links = state.repos.keyword_links.list(
        where={"organization_id": org_id, "keyword_id": keyword_id})
    ranks = _kw_contracts(state).rank_history(org_id, keyword_id)
    targets = state.repos.targets.list(
        where={"organization_id": org_id, "keyword_id": keyword_id})
    return {"keyword": kw, "links": links, "rank_history": ranks,
            "targets": targets}


# ---- usage -------------------------------------------------------------------

@router.get("/usage/summary", dependencies=_ACCEPTANCE)
def usage_summary(state: FoundationState = Depends(get_state),
                  ctx: RequestContext = Depends(get_context)):
    _require(ctx, PERM_VIEW_LEDGER)
    org_id = ctx.effective_organization_id or ""
    return state.usage.derived_balance(org_id)


@router.get("/usage/events", dependencies=_ACCEPTANCE)
def usage_events(state: FoundationState = Depends(get_state),
                 ctx: RequestContext = Depends(get_context),
                 limit: int = Query(default=50, le=500)):
    _require(ctx, PERM_VIEW_LEDGER)
    org_id = ctx.effective_organization_id or ""
    return {"items": state.repos.usage.for_org(org_id)[:limit],
            "shadow": True}


# ---- approvals ---------------------------------------------------------------

@router.get("/approvals", dependencies=_ACCEPTANCE)
def list_approvals(state: FoundationState = Depends(get_state),
                   ctx: RequestContext = Depends(get_context)):
    _require(ctx, PERM_VIEW_APPROVALS)
    org_id = ctx.effective_organization_id or ""
    return {"items": state.repos.approvals.list(where={"organization_id": org_id})}


@router.post("/approvals", status_code=201, dependencies=_ACCEPTANCE)
def create_approval(body: ApprovalCreate, state: FoundationState = Depends(get_state),
                    ctx: RequestContext = Depends(get_context)):
    _require(ctx, PERM_DRAFT)
    row = state.approvals.request(
        organization_id=ctx.effective_organization_id or "",
        requested_by_user_id=ctx.user_id or "", capability=body.capability,
        safety_class=body.safety_class, resource_type=body.resource_type,
        resource_id=body.resource_id, change_preview=body.change_preview,
        risk_level=body.risk_level, cost_estimate=body.cost_estimate,
        idempotency_key=body.idempotency_key, environment=ctx.environment)
    return {"approval": row}


@router.post("/approvals/{approval_id}/decide", dependencies=_ACCEPTANCE)
def decide_approval(approval_id: str, body: ApprovalDecide,
                    state: FoundationState = Depends(get_state),
                    ctx: RequestContext = Depends(get_context)):
    _require(ctx, PERM_APPROVE)
    try:
        row = state.approvals.decide(
            approval_request_id=approval_id, decided_by_user_id=ctx.user_id or "",
            decided_by_role=ctx.effective_role or "", decision=body.decision,
            note=body.note)
    except PermissionError as e:
        raise _err("permission_denied", str(e), 403)
    except ValueError as e:
        raise _err("invalid_state", str(e), 409)
    promoted = []
    if body.decision == ApprovalState.GRANTED.value:
        promoted = state.jobs_durable.promote_approved_jobs(approval_id)
    return {"approval": row, "execution": "not_performed_phase_1b",
            "promoted_jobs": promoted}


@router.post("/approvals/{approval_id}/cancel", dependencies=_ACCEPTANCE)
def cancel_approval(approval_id: str, state: FoundationState = Depends(get_state),
                    ctx: RequestContext = Depends(get_context)):
    _require(ctx, PERM_APPROVE)
    try:
        row = state.approvals.cancel(approval_id, ctx.user_id or "")
    except ValueError as e:
        raise _err("invalid_state", str(e), 409)
    return {"approval": row}


# ---- audit -------------------------------------------------------------------

@router.get("/audit", dependencies=_ACCEPTANCE)
def list_audit(state: FoundationState = Depends(get_state),
               ctx: RequestContext = Depends(get_context),
               limit: int = Query(default=100, le=500)):
    _require(ctx, PERM_VIEW_AUDIT)
    org_id = ctx.effective_organization_id or ""
    return {"items": state.repos.audit.for_org(org_id, limit=limit)}


# ---- ui preferences ----------------------------------------------------------

@router.get("/ui/preferences/{key}")
def get_ui_pref(key: str, state: FoundationState = Depends(get_state),
                ctx: RequestContext = Depends(get_context)):
    _require(ctx, PERM_VIEW)
    if not ctx.user_id:
        return {"key": key, "value": None}
    val = state.repos.ui_prefs.get_pref(ctx.user_id, ctx.effective_organization_id, key)
    return {"key": key, "value": val}


@router.put("/ui/preferences/{key}")
def set_ui_pref(key: str, body: UiPrefBody, state: FoundationState = Depends(get_state),
                ctx: RequestContext = Depends(get_context)):
    _require(ctx, PERM_VIEW)
    if not ctx.user_id:
        raise _err("no_user", "user context required", 400)
    state.repos.ui_prefs.set_pref(ctx.user_id, ctx.effective_organization_id,
                                  key, body.value)
    return {"key": key, "value": body.value}


# ---- canonical economics (1C-03) --------------------------------------------

class EconomicsComputeBody(BaseModel):
    input: dict


@router.get("/economics/contract", dependencies=_ACCEPTANCE)
def economics_contract(ctx: RequestContext = Depends(get_context)):
    """Canonical economics contract + formula version (read-only)."""
    _require(ctx, PERM_VIEW)
    from ..economics.versions import FORMULA_VERSION
    from ..economics import enums as _e
    return {
        "formula_version": FORMULA_VERSION,
        "money_type": "Decimal",
        "rounding": {"internal_precision": 34, "currency_quantum": "0.01",
                     "rate_quantum": "0.0001", "default": "ROUND_HALF_UP"},
        "readiness_states": [r.value for r in _e.Readiness],
        "metrics": [m.value for m in _e.MetricName],
    }


@router.post("/economics/compute", dependencies=_ACCEPTANCE)
def economics_compute(body: EconomicsComputeBody,
                      ctx: RequestContext = Depends(get_context)):
    """Authoritative economics. The backend is the ONLY authoritative calculator;
    the frontend must consume this and not define its own formulas."""
    _require(ctx, PERM_VIEW)
    from dataclasses import fields as _fields
    from ..economics import EconomicsInput, compute
    allowed = {f.name for f in _fields(EconomicsInput)}
    data = {k: v for k, v in (body.input or {}).items() if k in allowed}
    return compute(EconomicsInput(**data)).to_dict()


# ---- 1C-06 Lean B2B beta launch controls ------------------------------------

class AcceptanceBody(BaseModel):
    business_use: bool
    age_18_plus: bool


class DocumentPublishBody(BaseModel):
    pass


@router.get("/legal/documents")
def legal_documents_public():
    """Public, versioned beta documents (Privacy Notice, ToS, AUP)."""
    from ..beta import documents as beta_docs
    versions = beta_docs.document_versions()
    return {"items": [
        {"doc_type": dt, "version": v["version"], "title": v["title"],
         "content": v["content"], "content_hash": v["content_hash"],
         "beta_document": True}
        for dt, v in versions.items()]}


@router.get("/legal/documents/{doc_type}/current")
def legal_documents_current(doc_type: str):
    from ..beta import documents as beta_docs
    if doc_type not in beta_docs.DOC_TYPES:
        raise _err("unknown_doc_type", "unknown document type", 404)
    v = beta_docs.document_versions()[doc_type]
    return {"doc_type": doc_type, "version": v["version"], "title": v["title"],
            "content": v["content"], "content_hash": v["content_hash"],
            "beta_document": True}


@router.get("/legal/filesets")
def legal_filesets_public():
    """Subscriber-facing file sets: onboarding, FAQ, support/contact."""
    from ..beta.filesets import file_sets
    return {"items": [
        {"set_id": sid, "version": v["version"], "title": v["title"],
         "content": v["content"]} for sid, v in file_sets().items()]}


@router.get("/legal/filesets/{set_id}")
def legal_fileset(set_id: str):
    from ..beta.filesets import file_sets
    v = file_sets().get(set_id)
    if v is None:
        raise _err("not_found", "file set not found", 404)
    return {"set_id": set_id, "version": v["version"], "title": v["title"],
            "content": v["content"]}


@router.post("/legal/acceptance")
def legal_acceptance_record(body: AcceptanceBody,
                            state: FoundationState = Depends(get_state),
                            ctx: RequestContext = Depends(get_context)):
    """Record acceptance of the current published beta documents."""
    _require(ctx, PERM_VIEW)
    from ..beta.acceptance import record_acceptance, AcceptanceError
    try:
        result = record_acceptance(
            state, ctx, business_use=body.business_use,
            age_18_plus=body.age_18_plus, request_id=ctx.request_id)
    except AcceptanceError as e:
        raise _err(e.code, str(e), 400 if e.code != "acceptance_required" else 409)
    return result


@router.get("/legal/acceptance/status")
def legal_acceptance_status(state: FoundationState = Depends(get_state),
                            ctx: RequestContext = Depends(get_context)):
    _require(ctx, PERM_VIEW)
    from ..beta.acceptance import acceptance_status
    return acceptance_status(state, ctx)


@router.post("/legal/documents/publish")
def legal_documents_publish(state: FoundationState = Depends(get_state),
                            ctx: RequestContext = Depends(get_context)):
    """Owner-only publication of the current beta document set."""
    _require(ctx, PERM_MANAGE_ORG)
    from ..beta.acceptance import publish_documents
    published = publish_documents(state)
    state.audit.record(action="legal.publish", actor_user_id=ctx.user_id,
                       organization_id=ctx.effective_organization_id,
                       after_meta={"documents": published})
    return {"published": published}


@router.get("/beta-status")
def beta_status_endpoint(state: FoundationState = Depends(get_state),
                         ctx: RequestContext = Depends(get_context)):
    """Internal beta readiness record."""
    _require(ctx, PERM_VIEW_LEDGER)
    from ..beta.beta_status import beta_status
    return beta_status(state, ctx)


@router.get("/data-inventory")
def data_inventory_endpoint(state: FoundationState = Depends(get_state),
                            ctx: RequestContext = Depends(get_context)):
    _require(ctx, PERM_VIEW_LEDGER)
    from ..beta.inventory import inventory, completeness_review
    return {"inventory": inventory(), "completeness": completeness_review()}


@router.get("/retention-schedule")
def retention_schedule_endpoint(state: FoundationState = Depends(get_state),
                                ctx: RequestContext = Depends(get_context)):
    _require(ctx, PERM_VIEW_LEDGER)
    from ..beta.retention import schedule
    return schedule()


@router.get("/incident-runbook")
def incident_runbook_endpoint(state: FoundationState = Depends(get_state),
                              ctx: RequestContext = Depends(get_context)):
    _require(ctx, PERM_VIEW_LEDGER)
    from ..beta.incident import runbook
    return runbook()


# ---- 1C-06 master slice: billing / entitlements / invites / signup ----------

class CheckoutBody(BaseModel):
    price_id: str


class WebhookBody(BaseModel):
    payload: dict
    signature: str


class InviteBody(BaseModel):
    email: str
    role: str


class InviteRevokeBody(BaseModel):
    reason: str = "operator revoked"


class SignupBody(BaseModel):
    email: str
    invite_code: str
    display_name: Optional[str] = None


class SuspendBody(BaseModel):
    reason: str = "operator suspended"


# -- Phase A: billing (owner only) --------------------------------------------

@router.post("/billing/checkout", dependencies=_ACCEPTANCE)
def billing_checkout(body: CheckoutBody, state: FoundationState = Depends(get_state),
                     ctx: RequestContext = Depends(get_context)):
    _require(ctx, PERM_MANAGE_ORG)  # owner only
    from ..billing.service import BillingError
    try:
        return state.billing.create_checkout(ctx, price_id=body.price_id)
    except BillingError as e:
        raise _err(e.code, str(e), 400)


@router.get("/billing/checkout/{checkout_id}")
def billing_checkout_page(checkout_id: str,
                          state: FoundationState = Depends(get_state)):
    """The hosted checkout page (redirect target). TEST MODE: no card fields."""
    from ..billing.service import BillingError
    try:
        page = state.billing.checkout_page(checkout_id)
    except BillingError as e:
        raise _err(e.code, str(e), 404)
    from fastapi.responses import HTMLResponse
    html = (
        "<!doctype html><html><body style='font-family:sans-serif;max-width:480px;margin:60px auto'>"
        "<h1>Northstar OS — Test Checkout</h1>"
        f"<p><strong>Plan:</strong> {page['price_label']}</p>"
        f"<p><strong>Tier:</strong> {page['tier']}</p>"
        "<p style='color:#666'>TEST MODE — this redirect-based hosted checkout "
        "collects NO payment card and processes no real payment in the private "
        "beta. Subscription settlement is confirmed via the signed test webhook.</p>"
        "</body></html>")
    return HTMLResponse(html)


@router.get("/billing/status", dependencies=_ACCEPTANCE)
def billing_status(state: FoundationState = Depends(get_state),
                   ctx: RequestContext = Depends(get_context)):
    _require(ctx, PERM_MANAGE_ORG)
    return state.billing.status(ctx.effective_organization_id or "")


@router.post("/billing/cancel", dependencies=_ACCEPTANCE)
def billing_cancel(state: FoundationState = Depends(get_state),
                   ctx: RequestContext = Depends(get_context)):
    _require(ctx, PERM_MANAGE_ORG)
    from ..billing.service import BillingError
    try:
        return state.billing.cancel(ctx, reason="owner cancelled")
    except BillingError as e:
        raise _err(e.code, str(e), 400)


@router.post("/billing/webhook")
def billing_webhook(body: WebhookBody, state: FoundationState = Depends(get_state)):
    """Processor webhook endpoint. Signature-verified; exactly-once. TEST MODE."""
    from ..billing.service import BillingError
    try:
        result = state.billing.handle_webhook(body.payload, body.signature)
    except BillingError as e:
        raise _err(e.code, str(e), 400)
    return result


# -- Phase B: entitlements (centralized, read) ---------------------------------

@router.get("/entitlements", dependencies=_ACCEPTANCE)
def entitlements_view(state: FoundationState = Depends(get_state),
                      ctx: RequestContext = Depends(get_context)):
    _require(ctx, PERM_VIEW)
    org_id = ctx.effective_organization_id or ""
    return state.entitlements.entitlements_for_org(org_id)


# -- Phase C: invites (owner) + signup (public) + suspension -------------------

@router.post("/invites", status_code=201, dependencies=_ACCEPTANCE)
def invites_issue(body: InviteBody, state: FoundationState = Depends(get_state),
                  ctx: RequestContext = Depends(get_context)):
    _require(ctx, PERM_MANAGE_ORG)
    from ..billing.signup import SignupError
    try:
        return state.invites.issue(ctx, email=body.email, role=body.role)
    except SignupError as e:
        raise _err(e.code, str(e), 400)


@router.get("/invites", dependencies=_ACCEPTANCE)
def invites_list(state: FoundationState = Depends(get_state),
                 ctx: RequestContext = Depends(get_context)):
    _require(ctx, PERM_MANAGE_ORG)
    return {"items": state.invites.list(ctx.effective_organization_id or "")}


@router.post("/invites/{invite_id}/revoke", dependencies=_ACCEPTANCE)
def invites_revoke(invite_id: str, body: InviteRevokeBody,
                   state: FoundationState = Depends(get_state),
                   ctx: RequestContext = Depends(get_context)):
    _require(ctx, PERM_MANAGE_ORG)
    from ..billing.signup import SignupError
    try:
        return state.invites.revoke(ctx, invite_id, reason=body.reason)
    except SignupError as e:
        raise _err(e.code, str(e), 404)


@router.post("/accounts/{user_id}/suspend", dependencies=_ACCEPTANCE)
def accounts_suspend(user_id: str, body: SuspendBody,
                     state: FoundationState = Depends(get_state),
                     ctx: RequestContext = Depends(get_context)):
    """Immediate block: sets the account's memberships to suspended, which is
    enforced on EVERY authenticated request (get_context)."""
    _require(ctx, PERM_MANAGE_ORG)
    org_id = ctx.effective_organization_id or ""
    rows = state.repos.memberships.list(
        where={"organization_id": org_id, "user_id": user_id})
    if not rows:
        raise _err("not_found", "account not found", 404)
    state.db.conn.execute(
        "UPDATE memberships SET status='suspended' WHERE organization_id=? AND user_id=?",
        (org_id, user_id))
    state.db.conn.commit()
    state.audit.record(action="account.suspend", actor_user_id=ctx.user_id,
                       organization_id=org_id, resource_type="user",
                       resource_id=user_id,
                       after_meta={"reason": body.reason})
    return {"status": "suspended", "user_id": user_id}


@router.post("/signup", status_code=201)
def signup(body: SignupBody, state: FoundationState = Depends(get_state)):
    """Invite-gated private signup. Non-revealing denial when invalid."""
    from ..billing.signup import SignupError
    try:
        result = state.invites.signup(email=body.email,
                                      invite_code=body.invite_code,
                                      display_name=body.display_name)
    except SignupError as e:
        # NON-REVEALING: identical response whether the invite is invalid,
        # revoked, expired, used, or the email is unlisted.
        raise _err("signup_denied",
                   "signup is not available at this time", 403)
    return result


# ---- 1C-06 subscriber rules: plan & usage / onboarding / support / admin ------

class OnboardBody(BaseModel):
    step: Optional[str] = None


class TicketBody(BaseModel):
    category: str
    severity: str
    subject: str
    description: str


class TriageBody(BaseModel):
    status: Optional[str] = None
    assignee: Optional[str] = None
    internal_note: Optional[str] = None
    tester_visible_note: Optional[str] = None


class AdminLifecycleBody(BaseModel):
    reason: str = "operator action"


class AdminPlanBody(BaseModel):
    cohort: str
    reason: str = "operator plan change"


class AdminOverrideBody(BaseModel):
    feature: str
    value: object
    reason: str
    expires_at: Optional[str] = None
    permanent: bool = False


@router.get("/plan-usage", dependencies=_ACCEPTANCE)
def plan_usage_view(state: FoundationState = Depends(get_state),
                    ctx: RequestContext = Depends(get_context)):
    _require(ctx, PERM_VIEW)
    return state.plan_usage.view(ctx)


@router.get("/onboarding-pack")
def onboarding_pack(state: FoundationState = Depends(get_state)):
    from ..operations.support import SupportService
    return SupportService(state.repos).onboarding_pack()


@router.get("/onboarding", dependencies=_ACCEPTANCE)
def onboarding_status(state: FoundationState = Depends(get_state),
                      ctx: RequestContext = Depends(get_context)):
    _require(ctx, PERM_VIEW)
    return state.support.onboarding_status(ctx.effective_organization_id or "")


@router.post("/onboarding/complete", dependencies=_ACCEPTANCE)
def onboarding_complete(body: OnboardBody,
                        state: FoundationState = Depends(get_state),
                        ctx: RequestContext = Depends(get_context)):
    _require(ctx, PERM_VIEW)
    from ..operations.support import SupportError
    try:
        return state.support.complete_onboarding(
            ctx.effective_organization_id or "", step=body.step,
            actor=ctx.user_id)
    except SupportError as e:
        raise _err(e.code, str(e), 400)


@router.post("/support/tickets", status_code=201, dependencies=_ACCEPTANCE)
def support_submit(body: TicketBody, state: FoundationState = Depends(get_state),
                   ctx: RequestContext = Depends(get_context)):
    _require(ctx, PERM_VIEW)
    from ..operations.support import SupportError
    try:
        return state.support.submit_ticket(
            ctx, category=body.category, severity=body.severity,
            subject=body.subject, description=body.description)
    except SupportError as e:
        raise _err(e.code, str(e), 400)


@router.get("/support/tickets", dependencies=_ACCEPTANCE)
def support_list(state: FoundationState = Depends(get_state),
                 ctx: RequestContext = Depends(get_context)):
    _require(ctx, PERM_VIEW)
    return {"items": state.support.list_tickets(
        ctx.effective_organization_id or "", tester_view=True)}


@router.get("/support/tickets/{ticket_id}", dependencies=_ACCEPTANCE)
def support_get(ticket_id: str, state: FoundationState = Depends(get_state),
                ctx: RequestContext = Depends(get_context)):
    _require(ctx, PERM_VIEW)
    from ..operations.support import SupportError
    try:
        return state.support.get_ticket(ctx.effective_organization_id or "",
                                        ticket_id, tester_view=True)
    except SupportError as e:
        raise _err(e.code, str(e), 404)


@router.post("/support/tickets/{ticket_id}/triage", dependencies=_ACCEPTANCE)
def support_triage(ticket_id: str, body: TriageBody,
                   state: FoundationState = Depends(get_state),
                   ctx: RequestContext = Depends(get_context)):
    _require(ctx, PERM_PLATFORM_ADMIN)
    from ..operations.support import SupportError
    try:
        return state.support.triage(
            ctx, ctx.effective_organization_id or "", ticket_id,
            status=body.status, assignee=body.assignee,
            internal_note=body.internal_note,
            tester_visible_note=body.tester_visible_note)
    except SupportError as e:
        raise _err(e.code, str(e), 404)


# ---- internal admin tools (platform admin only) ------------------------------

def _require_platform(ctx: RequestContext) -> None:
    _require(ctx, PERM_PLATFORM_ADMIN)


@router.post("/admin/orgs/{org_id}/grant", dependencies=_ACCEPTANCE)
def admin_grant(org_id: str, body: AdminLifecycleBody,
                state: FoundationState = Depends(get_state),
                ctx: RequestContext = Depends(get_context)):
    _require_platform(ctx)
    from ..operations.admin import AdminError
    try:
        return state.admin_ops.grant(ctx, org_id, reason=body.reason)
    except AdminError as e:
        raise _err(e.code, str(e), 404)


@router.post("/admin/orgs/{org_id}/plan", dependencies=_ACCEPTANCE)
def admin_plan(org_id: str, body: AdminPlanBody,
               state: FoundationState = Depends(get_state),
               ctx: RequestContext = Depends(get_context)):
    _require_platform(ctx)
    from ..operations.admin import AdminError
    try:
        return state.admin_ops.change_plan(ctx, org_id, cohort=body.cohort,
                                           reason=body.reason)
    except AdminError as e:
        raise _err(e.code, str(e), 404)


@router.post("/admin/orgs/{org_id}/suspend", dependencies=_ACCEPTANCE)
def admin_suspend(org_id: str, body: AdminLifecycleBody,
                  state: FoundationState = Depends(get_state),
                  ctx: RequestContext = Depends(get_context)):
    _require_platform(ctx)
    from ..operations.admin import AdminError
    try:
        return state.admin_ops.suspend(ctx, org_id, reason=body.reason)
    except AdminError as e:
        raise _err(e.code, str(e), 404)


@router.post("/admin/orgs/{org_id}/resume", dependencies=_ACCEPTANCE)
def admin_resume(org_id: str, body: AdminLifecycleBody,
                 state: FoundationState = Depends(get_state),
                 ctx: RequestContext = Depends(get_context)):
    _require_platform(ctx)
    from ..operations.admin import AdminError
    try:
        return state.admin_ops.resume(ctx, org_id, reason=body.reason)
    except AdminError as e:
        raise _err(e.code, str(e), 404)


@router.post("/admin/orgs/{org_id}/downgrade", dependencies=_ACCEPTANCE)
def admin_downgrade(org_id: str, body: AdminLifecycleBody,
                    state: FoundationState = Depends(get_state),
                    ctx: RequestContext = Depends(get_context)):
    _require_platform(ctx)
    from ..operations.admin import AdminError
    try:
        return state.admin_ops.downgrade(ctx, org_id, reason=body.reason)
    except AdminError as e:
        raise _err(e.code, str(e), 404)


@router.post("/admin/orgs/{org_id}/cancel", dependencies=_ACCEPTANCE)
def admin_cancel(org_id: str, body: AdminLifecycleBody,
                 state: FoundationState = Depends(get_state),
                 ctx: RequestContext = Depends(get_context)):
    _require_platform(ctx)
    from ..operations.admin import AdminError
    try:
        return state.admin_ops.cancel(ctx, org_id, reason=body.reason)
    except AdminError as e:
        raise _err(e.code, str(e), 404)


@router.post("/admin/orgs/{org_id}/archive", dependencies=_ACCEPTANCE)
def admin_archive(org_id: str, body: AdminLifecycleBody,
                  state: FoundationState = Depends(get_state),
                  ctx: RequestContext = Depends(get_context)):
    _require_platform(ctx)
    from ..operations.admin import AdminError
    try:
        return state.admin_ops.archive(ctx, org_id, reason=body.reason)
    except AdminError as e:
        raise _err(e.code, str(e), 404)


class AdminNoteBody(BaseModel):
    note: str


@router.post("/admin/orgs/{org_id}/notes", dependencies=_ACCEPTANCE)
def admin_note(org_id: str, body: AdminNoteBody,
               state: FoundationState = Depends(get_state),
               ctx: RequestContext = Depends(get_context)):
    _require_platform(ctx)
    from ..operations.admin import AdminError
    try:
        return state.admin_ops.add_note(ctx, org_id, note=body.note)
    except AdminError as e:
        raise _err(e.code, str(e), 404)


@router.post("/admin/orgs/{org_id}/override", dependencies=_ACCEPTANCE)
def admin_override(org_id: str, body: AdminOverrideBody,
                   state: FoundationState = Depends(get_state),
                   ctx: RequestContext = Depends(get_context)):
    _require_platform(ctx)
    from ..operations.admin import AdminError
    try:
        return state.admin_ops.set_override(
            ctx, org_id, feature=body.feature, value=body.value,
            reason=body.reason, expires_at=body.expires_at,
            permanent=body.permanent)
    except AdminError as e:
        raise _err(e.code, str(e), 404)


@router.get("/admin/orgs/{org_id}/history", dependencies=_ACCEPTANCE)
def admin_history(org_id: str, state: FoundationState = Depends(get_state),
                  ctx: RequestContext = Depends(get_context)):
    _require_platform(ctx)
    from ..operations.admin import AdminError
    try:
        return state.admin_ops.history(org_id)
    except AdminError as e:
        raise _err(e.code, str(e), 404)


@router.get("/admin/dashboard", dependencies=_ACCEPTANCE)
def admin_dashboard(state: FoundationState = Depends(get_state),
                    ctx: RequestContext = Depends(get_context),
                    state_filter: Optional[str] = Query(default=None, alias="state"),
                    tier: Optional[str] = Query(default=None),
                    invite_status: Optional[str] = Query(default=None),
                    onboarding_incomplete: bool = False,
                    nearing_limit: bool = False,
                    suspended: bool = False,
                    severity: Optional[str] = Query(default=None),
                    sort: str = "last_activity"):
    _require_platform(ctx)
    return {"items": state.dashboard.list_orgs(
        state=state_filter, tier=tier, invite_status=invite_status,
        onboarding_incomplete=onboarding_incomplete,
        nearing_limit=nearing_limit, suspended=suspended,
        severity=severity, sort=sort)}


@router.get("/admin/dashboard/export", dependencies=_ACCEPTANCE)
def admin_dashboard_export(state: FoundationState = Depends(get_state),
                           ctx: RequestContext = Depends(get_context),
                           state_filter: Optional[str] = Query(default=None, alias="state"),
                           tier: Optional[str] = Query(default=None)):
    _require_platform(ctx)
    from ..operations.dashboard import DashboardError
    from fastapi.responses import PlainTextResponse
    try:
        payload = state.dashboard.export_csv(state=state_filter, tier=tier)
    except DashboardError as e:
        raise _err(e.code, str(e), 400)
    return PlainTextResponse(payload, media_type="text/csv",
                             headers={"Content-Disposition":
                                      'attachment; filename="tester-status.csv"'})
@router.get("/admin/dashboard/{org_id}", dependencies=_ACCEPTANCE)
def admin_dashboard_detail(org_id: str, state: FoundationState = Depends(get_state),
                           ctx: RequestContext = Depends(get_context)):
    _require_platform(ctx)
    from ..operations.dashboard import DashboardError
    try:
        return state.dashboard.detail(org_id)
    except DashboardError as e:
        raise _err(e.code, str(e), 404)
