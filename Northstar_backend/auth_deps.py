"""FastAPI authentication dependencies — OAuth2 + JWT integration.

Provides `get_current_user` dependency for protected routes and
`require_plan` factory for plan-gated endpoints.

Usage in main.py:
    from auth_deps import get_current_user, require_plan

    @app.get("/api/v1/products")
    def list_products(user = Depends(get_current_user)):
        ...

    @app.post("/api/v1/listings/generate")
    def gen_listing(user = Depends(require_plan("scout"))):
        ...
"""

import os
import sys
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer

sys.path.insert(0, os.path.dirname(__file__))
import auth

# Same cookie name the Foundation login sets (foundation/auth_session.py).
# Duplicated rather than imported to keep this module importable on its own.
_SESSION_COOKIE_NAME = "ns_session"

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


async def get_current_user(token: Optional[str] = Depends(oauth2_scheme)) -> dict:
    """Validate JWT and return user payload.

    For the demo/launch phase, requests without a token get a
    read-only 'foundation' user so the UI works without auth setup.
    B2: the returned dict carries `role` + `tenant_id` (demo fallback =
    member/anonymous, least privilege). Unknown roles fail closed to member.
    """
    if not token:
        # Demo mode — allow unauthenticated read-only access
        return {
            "id": "anonymous",
            "email": "demo@northstar.local",
            "plan": "foundation",
            "role": auth.ROLE_MEMBER,
            "tenant_id": "anonymous",
            "is_demo": True,
        }

    try:
        payload = auth.decode_token(token)
    except auth.jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except auth.jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
        )

    user = auth.get_user(payload["sub"])
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    # B2: role/tenant come from the token (never the request body); unknown
    # roles fail closed to the lowest tenant role.
    role = payload.get("role")
    user["role"] = role if auth.is_valid_role(role) else auth.ROLE_MEMBER
    user["tenant_id"] = payload.get("tenant_id") or user.get("id")
    return user


def require_role(minimum_role: str):
    """Dependency factory: require a minimum TENANT role (fail closed).

    Unknown minimum_role => deny. `admin` is a separate axis and does NOT
    satisfy tenant-role checks (least privilege).
    """
    async def _check(user: dict = Depends(get_current_user)) -> dict:
        if not auth.has_role(user, minimum_role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient role for this action.",
            )
        return user

    return _check


async def require_admin(user: dict = Depends(get_current_user)) -> dict:
    """Dependency: require the platform `admin` role (fail closed).

    Admin is least-privilege: callers must use `auth.admin_account_view` and
    must never return security-sensitive fields.
    """
    if not auth.is_admin(user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator role required.",
        )
    return user


def _dev_shim_identity(request: Request) -> Optional[dict]:
    """Resolve the local-development identity shim, or None.

    Honoured only when the process runs in development and the *effective*
    client is loopback. An explicit ``X-User-Id`` is used when present; with no
    header the REAL app (main.py) may opt in via ``app.state.dev_auto_session``
    (set after it provisions the demo identity), in which case the demo identity
    is returned. Everything else returns None so ``require_session`` fails
    closed: a hosted process, a forwarded/remote client, or an isolated app that
    did not opt in never reaches this branch.
    """
    try:
        from foundation.authn import (
            dev_shim_enabled,
            effective_client_host,
            is_loopback_host,
        )
    except Exception:  # noqa: BLE001 - no foundation module available => no shim
        return None
    if not dev_shim_enabled():
        return None
    user_id = (request.headers.get("X-User-Id") or "").strip()
    # A bare Request (tests, internal calls) has no ASGI "app" scope; a missing
    # app means no auto-demo session, not a crash.
    app = request.scope.get("app") if hasattr(request, "scope") else None
    auto_demo = bool(getattr(getattr(app, "state", None),
                            "dev_auto_session", False))
    if not user_id:
        if not auto_demo:
            return None
        user_id = "demo-t2"
    if not is_loopback_host(effective_client_host(request)):
        return None
    role = (request.headers.get("X-Role") or "").strip()
    if not auth.is_valid_role(role):
        role = auth.ROLE_MEMBER
    org_id = (request.headers.get("X-Org-Id") or "").strip()
    if not org_id:
        org_id = "org-t2" if user_id == "demo-t2" else user_id
    return {
        "id": user_id,
        "email": "",
        "plan": "foundation",
        "role": role,
        "tenant_id": org_id,
        "is_demo": True,
        "dev_shim": True,
    }


async def require_session(request: Request) -> dict:
    """STRICT session dependency: no anonymous fallback, ever.

    Unlike :func:`get_current_user` (which returns a read-only demo identity so
    the public read surface works before sign-in), this dependency refuses with
    401 unless a real session is presented:

      * an ``Authorization: Bearer <jwt>`` access token, or
      * the HttpOnly ``ns_session`` cookie minted by the Foundation login.

    The cookie path is resolved against the **Foundation** store (its session
    registry, for revocation) — NOT against the legacy ``auth.py`` SQLite user
    table, which is a different database and does not hold Foundation users.
    Crossing the two was the original defect here: a perfectly valid hosted
    session was refused 401 because the legacy lookup found no matching row.

    The returned dict always carries ``id``, ``tenant_id`` and ``role``. A
    session whose organization cannot be resolved is refused, not silently
    scoped to a shared bucket.
    """
    token = None
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[len("Bearer "):].strip()
    if not token:
        token = request.cookies.get(_SESSION_COOKIE_NAME) or None
    if not token:
        # Dev-only identity shim. The Foundation router already honours the
        # X-User-Id shim in local development (foundation/api/deps.py), but the
        # legacy strict dependency did not, so Design Studio, the shell and every
        # other require_session route returned "Authentication required." to a
        # dev session that the rest of the app had already accepted. That split
        # is what put the browser in a sign-in loop on /home.
        #
        # The guard is deliberately identical to the Foundation one and narrow:
        # ENVIRONMENT=development AND a loopback peer AND an explicit header.
        # A hosted/production process, or any forwarded/remote client, still
        # fails closed below and never sees this branch. This is also exactly
        # the documented DEV-ONLY LOCALHOST EXCEPTION in AGENTS.md.
        shim = _dev_shim_identity(request)
        if shim is not None:
            return shim
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # The cookie and the bearer may be signed by different issuers, so try the
    # Foundation store first for a cookie and the legacy path for a bearer.
    if request.cookies.get(_SESSION_COOKIE_NAME) and not auth_header.startswith("Bearer "):
        user = _resolve_foundation_cookie(token)
        if user is not None:
            return user
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid session.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = auth.decode_token(token)
    except auth.jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except auth.jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid session.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type.",
        )

    user = auth.get_user(payload["sub"])
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found.",
        )

    role = payload.get("role")
    user["role"] = role if auth.is_valid_role(role) else auth.ROLE_MEMBER
    user["tenant_id"] = payload.get("tenant_id") or user.get("id")
    if not user.get("tenant_id"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session has no resolved organization.",
        )
    user["session_jti"] = payload.get("jti")
    return user


def _app_foundation_state():
    """The FoundationState the app already built at startup, if any.

    Reusing it matters for two reasons: it avoids opening a second database
    connection on every authenticated request, and — without a shared
    ``FOUNDATION_DB_URL`` — ``FoundationState.build()`` would silently create a
    fresh throwaway SQLite DB, so a session revoked by a logout would still
    validate. That was the defect this helper fixes.
    """
    try:
        import main
        state = getattr(getattr(main, "app", None), "state", None)
        return getattr(state, "foundation", None) if state is not None else None
    except Exception:  # pragma: no cover - main not importable
        return None


def _resolve_foundation_cookie(token: str, state=None) -> Optional[dict]:
    """Validate an HttpOnly Foundation session cookie.

    Returns a user dict carrying ``id``, ``tenant_id`` and ``role``, or None
    when the token is invalid, expired, or its session row is revoked. Never
    reads or returns a secret.
    """
    import jwt as _jwt
    from foundation.authn import jwt_secret, jwt_issuer, jwt_audience

    if state is None:
        state = _app_foundation_state()
    if state is None:
        try:
            from foundation.api.state import FoundationState
            state = FoundationState.build()
        except Exception:  # pragma: no cover - store unavailable
            return None

    secret = jwt_secret()
    if not secret:
        return None
    # PyJWT's API: issuer/audience are KEYWORD ARGUMENTS, not entries in the
    # options dict. Passing them in `options` does nothing, and leaving
    # `verify_aud` at its default True while the token carries an `aud` claim
    # makes decode raise InvalidAudienceError — which the caller then reports
    # as a generic invalid session. That was the original defect here: a real
    # verification failure silently looked like an authentication failure.
    issuer = jwt_issuer()
    audience = jwt_audience()
    kwargs = {"algorithms": ["HS256"]}
    if issuer:
        kwargs["issuer"] = issuer
    if audience:
        kwargs["audience"] = audience
    else:
        kwargs["options"] = {"verify_aud": False}
    try:
        payload = _jwt.decode(token, secret, **kwargs)
    except _jwt.InvalidTokenError:
        return None

    if payload.get("type") != "access":
        return None

    user_id = payload.get("sub")
    org_id = payload.get("tenant_id")
    role = payload.get("role")

    # Server-side revocation, fail closed: a session row must EXIST and must
    # not be revoked. Checking only "is it revoked" would let a token that was
    # never registered sail through — which is exactly how a logout could be
    # bypassed. The login route registers every real session, so requiring a
    # row costs nothing and closes that hole.
    try:
        jti = payload.get("jti")
        if not jti:
            return None
        row = state.repos.sessions.by_jti(jti)
        if row is None or row.get("revoked_at"):
            return None
    except Exception:  # pragma: no cover - store unavailable
        return None

    if not user_id or not org_id:
        # A session with no resolved organization is refused, not scoped to a
        # shared bucket.
        return None

    return {
        "id": user_id,
        "email": payload.get("email"),
        "plan": payload.get("plan") or "foundation",
        # The Foundation role vocabulary (organization_owner / organization_member
        # / platform_admin) is NOT the legacy tenant vocabulary
        # (owner/operator/member). Preserve the real role verbatim — silently
        # rewriting it to the legacy default loses the operator's actual
        # authority — and expose a legacy-compatible alias separately for the
        # routes that still use auth.has_role().
        "role": role or auth.ROLE_MEMBER,
        "legacy_role": _legacy_role(role),
        "tenant_id": org_id,
        "session_jti": payload.get("jti"),
        "source": "foundation_session_cookie",
    }


def _legacy_role(foundation_role: Optional[str]) -> str:
    """Map a Foundation role onto the legacy tenant vocabulary, least privilege."""
    mapping = {
        "organization_owner": auth.ROLE_OWNER,
        "organization_member": auth.ROLE_MEMBER,
        "platform_admin": auth.ROLE_MEMBER,  # a separate axis, never a tenant role
    }
    return mapping.get(foundation_role or "", auth.ROLE_MEMBER)


def require_plan(minimum_plan: str):
    """Factory that returns a dependency requiring a minimum subscription plan.

    Plan hierarchy: foundation < scout < mover < autothink
    """
    plan_order = {"foundation": 0, "scout": 1, "mover": 2, "autothink": 3}
    min_level = plan_order.get(minimum_plan, 0)

    async def _check(user: dict = Depends(get_current_user)) -> dict:
        user_plan = user.get("plan", "foundation")
        user_level = plan_order.get(user_plan, 0)
        if user_level < min_level:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Plan '{user_plan}' does not include this feature. "
                       f"Upgrade to '{minimum_plan}' or higher.",
            )
        return user

    return _check
