"""Hosted browser session transport for the Foundation app (P2-T5b).

Canonical hosted transport: ONE HttpOnly session cookie (no access token is ever
returned to JavaScript / localStorage). CSRF uses a double-submit token cookie
(``ns_csrf``, readable by the SPA) echoed in the ``X-CSRF-Token`` header on
state-changing requests, plus a same-origin Origin check.

Never logs or returns credentials, hashes, or full tokens.
"""
from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional
from urllib.parse import urlsplit

import jwt

from .authn import jwt_audience, jwt_issuer, jwt_secret, is_production_like, AuthError

SESSION_COOKIE = "ns_session"
CSRF_COOKIE = "ns_csrf"
SESSION_PATH = "/api/v1/foundation"   # narrowly scoped to the Foundation API
CSRF_PATH = "/"                        # readable by the SPA document
DEFAULT_TTL_SECONDS = 3600
_UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def mint_access_token(*, user_id: str, org_id: Optional[str], role: Optional[str],
                      ttl_seconds: int = DEFAULT_TTL_SECONDS):
    """Mint an access JWT in the EXACT shape the Foundation validator requires."""
    secret = jwt_secret()
    if not secret:
        raise AuthError("no_signing_key_configured", "no signing key is configured")
    now = datetime.now(timezone.utc)
    exp = now + timedelta(seconds=ttl_seconds)
    jti = secrets.token_urlsafe(16)
    payload = {
        "sub": user_id,
        "type": "access",
        "iat": now,
        "exp": exp,
        "jti": jti,
        "tenant_id": org_id,
        "role": role,
    }
    iss = jwt_issuer()
    aud = jwt_audience()
    if iss:
        payload["iss"] = iss
    if aud:
        payload["aud"] = aud
    token = jwt.encode(payload, secret, algorithm="HS256")
    return token, jti, exp


def session_cookie_kwargs(value: str, *, max_age: int = DEFAULT_TTL_SECONDS) -> dict:
    return {
        "key": SESSION_COOKIE, "value": value, "max_age": max_age,
        "path": SESSION_PATH, "httponly": True, "secure": is_production_like(),
        "samesite": "strict",
    }


def new_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def csrf_cookie_kwargs(value: str, *, max_age: int = DEFAULT_TTL_SECONDS) -> dict:
    return {
        "key": CSRF_COOKIE, "value": value, "max_age": max_age,
        "path": CSRF_PATH, "httponly": False, "secure": is_production_like(),
        "samesite": "strict",
    }


def csrf_ok(request) -> bool:
    """Double-submit + same-origin check for cookie-authenticated unsafe methods."""
    if request.method.upper() not in _UNSAFE_METHODS:
        return True
    cookie = request.cookies.get(CSRF_COOKIE)
    header = request.headers.get("x-csrf-token")
    if not cookie or not header or not secrets.compare_digest(cookie, header):
        return False
    origin = request.headers.get("origin")
    if origin:
        if urlsplit(origin).netloc != request.headers.get("host", ""):
            return False
    return True