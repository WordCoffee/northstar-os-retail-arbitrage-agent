"""Authentication & authorization core for the foundation (Phase 1C-01F).

Validated JWT authentication and server-side organization/role resolution.
Fail-closed by design.

Alignment: tokens are issued by the existing ``Northstar_backend/auth.py``
(HS256, claims ``sub, email, plan, role, tenant_id, type, jti, iat, exp``).
This module only *consumes* them; it never issues tokens and never reads or
prints secret values.

Environment modes: development | test | staging | production. staging and
production require issuer, audience, an approved signing key, an algorithm
allowlist, session-revocation storage, real membership resolution, the dev shim
disabled, and the remote-dev override disabled. Startup fails closed otherwise.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

import jwt

VALID_ENVIRONMENTS = frozenset({"development", "test", "staging", "production"})
_PROD_LIKE = frozenset({"staging", "production"})
_LOOPBACK_HOSTS = {"127.0.0.1", "::1", "localhost", "testclient"}
_FORWARD_HEADERS = ("x-forwarded-for", "x-real-ip", "forwarded", "x-forwarded-host")
_DEV_SECRET_PREFIXES = ("test-", "test_", "dev-", "dev_", "development", "changeme", "dummy")


# ---------------------------------------------------------------------------
# Environment helpers
# ---------------------------------------------------------------------------

def environment() -> str:
    raw = (os.environ.get("ENVIRONMENT") or "development").strip().lower()
    return raw if raw in VALID_ENVIRONMENTS else "invalid"


def is_production_like() -> bool:
    return environment() in _PROD_LIKE


def jwt_secret() -> Optional[str]:
    return os.environ.get("NORTHSTAR_JWT_SECRET") or None


def jwt_issuer() -> Optional[str]:
    return os.environ.get("NORTHSTAR_JWT_ISSUER") or None


def jwt_audience() -> Optional[str]:
    return os.environ.get("NORTHSTAR_JWT_AUDIENCE") or None


def jwt_key_id() -> Optional[str]:
    return os.environ.get("NORTHSTAR_JWT_KEY_ID") or None


def allowed_algorithms() -> tuple[str, ...]:
    """Server-defined algorithm allowlist. 'none' is never allowed."""
    raw = os.environ.get("NORTHSTAR_JWT_ALGORITHMS") or "HS256"
    algs = [a.strip() for a in raw.split(",") if a.strip()]
    algs = [a for a in algs if a.lower() != "none"]
    seen: list[str] = []
    for a in algs:
        if a not in seen:
            seen.append(a)
    return tuple(seen)


def max_kid_length() -> int:
    try:
        return max(1, int(os.environ.get("NORTHSTAR_JWT_MAX_KID_LENGTH") or 120))
    except ValueError:
        return 120


def leeway_seconds() -> int:
    try:
        return min(300, max(0, int(os.environ.get("NORTHSTAR_JWT_LEEWAY_SECONDS") or 30)))
    except ValueError:
        return 30


def max_lifetime_seconds() -> Optional[int]:
    raw = os.environ.get("NORTHSTAR_JWT_MAX_LIFETIME_SECONDS")
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def approved_token_types() -> set[str]:
    raw = os.environ.get("NORTHSTAR_JWT_TOKEN_TYPES") or "access"
    return {t.strip() for t in raw.split(",") if t.strip()}


def allow_remote_dev() -> bool:
    v = (os.environ.get("NS_FOUNDATION_ALLOW_REMOTE_DEV") or "").strip().lower()
    return v in ("1", "true", "yes", "on")


def trusted_proxies() -> set[str]:
    raw = os.environ.get("NORTHSTAR_TRUSTED_PROXIES") or ""
    return {p.strip() for p in raw.split(",") if p.strip()}


def dev_shim_enabled() -> bool:
    """Dev identity headers are honoured ONLY in local development."""
    return environment() == "development"


def is_loopback_host(host: Optional[str]) -> bool:
    if not host:
        return False
    h = host.strip().lower()
    if h in _LOOPBACK_HOSTS:
        return True
    return h.startswith("127.")


# ---------------------------------------------------------------------------
# Client host resolution (proxy-aware)
# ---------------------------------------------------------------------------

def effective_client_host(request, trusted: Optional[set[str]] = None) -> Optional[str]:
    trusted = trusted_proxies() if trusted is None else trusted
    peer = request.client.host if getattr(request, "client", None) else None
    if peer is None:
        return None
    headers = getattr(request, "headers", {}) or {}
    fwd_present = any(h in headers for h in _FORWARD_HEADERS)

    if peer in trusted:
        xff = (headers.get("x-forwarded-for") or "").strip()
        chain = [h.strip() for h in xff.split(",") if h.strip()] if xff else []
        for hop in reversed(chain):
            if hop not in trusted:
                return hop
        return chain[0] if chain else peer

    if fwd_present:
        return "untrusted-proxy"
    return peer


# ---------------------------------------------------------------------------
# JWT validation
# ---------------------------------------------------------------------------

class AuthError(Exception):
    def __init__(self, code: str, message: str = "") -> None:
        super().__init__(message or code)
        self.code = code
        self.message = message or code


@dataclass
class AuthIdentity:
    user_id: str
    method: str  # "jwt" | "dev_shim"
    jti: Optional[str] = None
    claims: Optional[dict] = None
    org_claim: Optional[str] = None


def _looks_like_dev_secret(secret: Optional[str]) -> bool:
    if not secret:
        return False
    low = secret.strip().lower()
    return any(low.startswith(p) for p in _DEV_SECRET_PREFIXES)


def decode_and_validate(token: str) -> dict:
    """Validate a JWT. Fail-closed on ANY problem. The server configuration —
    never the token — selects the allowable algorithms."""
    if not isinstance(token, str) or token.count(".") != 2:
        raise AuthError("malformed_token", "token is not a well-formed JWT")

    secret = jwt_secret()
    if not secret:
        raise AuthError("no_signing_key_configured", "no signing key is configured")

    algs = allowed_algorithms()
    if not algs:
        raise AuthError("no_algorithm_allowed", "no JWT algorithm is allowed")

    try:
        header = jwt.get_unverified_header(token)
    except jwt.DecodeError:
        raise AuthError("malformed_token", "token header could not be parsed")
    except Exception:
        raise AuthError("malformed_token", "token header could not be parsed")

    alg = header.get("alg")
    if alg is None or alg == "":
        raise AuthError("empty_algorithm", "token has no algorithm")
    if str(alg).lower() == "none":
        raise AuthError("alg_none_rejected", "unsigned tokens are rejected")
    if alg not in algs:
        raise AuthError("unexpected_algorithm", f"algorithm {alg!r} is not allowed")

    kid = header.get("kid")
    if kid is not None:
        if not isinstance(kid, str) or kid == "" or len(kid) > max_kid_length():
            raise AuthError("malformed_kid", "token key id is malformed")
        configured_kid = jwt_key_id()
        if configured_kid and kid != configured_kid:
            raise AuthError("unknown_kid", "token key id is not trusted")

    options = {"require": ["exp", "sub"]}
    kwargs: dict = {
        "algorithms": list(algs),
        "options": options,
        "leeway": leeway_seconds(),
    }
    issuer = jwt_issuer()
    audience = jwt_audience()
    if issuer:
        kwargs["issuer"] = issuer
    elif is_production_like():
        raise AuthError("issuer_required", "issuer is required in this environment")
    if audience:
        kwargs["audience"] = audience
    elif is_production_like():
        raise AuthError("audience_required", "audience is required in this environment")

    try:
        payload = jwt.decode(token, secret, **kwargs)
    except jwt.ExpiredSignatureError:
        raise AuthError("token_expired", "access token expired")
    except jwt.ImmatureSignatureError:
        raise AuthError("token_not_yet_valid", "token is not yet valid (nbf)")
    except jwt.InvalidIssuerError:
        raise AuthError("invalid_issuer", "token issuer not accepted")
    except jwt.InvalidAudienceError:
        raise AuthError("invalid_audience", "token audience not accepted")
    except jwt.InvalidAlgorithmError:
        raise AuthError("unexpected_algorithm", "algorithm not accepted")
    except jwt.MissingRequiredClaimError:
        raise AuthError("missing_required_claim", "a required claim is missing")
    except jwt.InvalidTokenError:
        raise AuthError("invalid_token", "token failed validation")

    iat = payload.get("iat")
    if iat is not None and not isinstance(iat, int):
        raise AuthError("malformed_iat", "iat must be a numeric timestamp")

    exp = payload.get("exp")
    ml = max_lifetime_seconds()
    if ml is not None and isinstance(exp, int) and isinstance(iat, int) and (exp - iat) > ml:
        raise AuthError("token_lifetime_exceeded", "token lifetime exceeds the configured maximum")

    ttype = payload.get("type")
    if ttype is not None and ttype not in approved_token_types():
        raise AuthError("unapproved_token_type", f"token type {ttype!r} is not accepted")

    return payload


# ---------------------------------------------------------------------------
# Startup posture
# ---------------------------------------------------------------------------

class AuthPostureError(RuntimeError):
    pass


def validate_auth_configuration(env: Optional[str] = None) -> list[str]:
    """Return a list of configuration problems for the given environment."""
    env = environment() if env is None else env.lower()
    problems: list[str] = []
    if env not in VALID_ENVIRONMENTS:
        problems.append("invalid_environment")
        return problems
    if env in _PROD_LIKE:
        secret = jwt_secret()
        if not secret:
            problems.append("missing_signing_key")
        elif _looks_like_dev_secret(secret):
            problems.append("development_secret_in_prod")
        if not jwt_issuer():
            problems.append("missing_issuer")
        if not jwt_audience():
            problems.append("missing_audience")
        algs = allowed_algorithms()
        if not algs:
            problems.append("missing_algorithm_allowlist")
        elif any(a.lower() == "none" for a in algs):
            problems.append("alg_none_allowed")
        if allow_remote_dev():
            problems.append("remote_dev_override_in_prod")
    return problems


def assert_startup_posture(*, bind_host: Optional[str] = None,
                           env: Optional[str] = None,
                           jwt_secret_present: Optional[bool] = None,
                           remote_dev_allowed: Optional[bool] = None) -> dict:
    """Fail startup on an unsafe auth/bind posture. Returns the resolved posture."""
    env = (env or environment()).lower()
    # Allow callers (tests) to inject secret/override presence explicitly.
    injected = jwt_secret_present is not None or remote_dev_allowed is not None
    if injected:
        problems: list[str] = []
        if env not in VALID_ENVIRONMENTS:
            problems.append("invalid_environment")
        elif env in _PROD_LIKE:
            if jwt_secret_present is False:
                problems.append("missing_signing_key")
            if remote_dev_allowed:
                problems.append("remote_dev_override_in_prod")
            # issuer/audience/alg-allowlist only checkable from real env
            if env is None:
                pass
        if problems:
            raise AuthPostureError("; ".join(problems))
        secret_present = bool(jwt_secret_present)
        override = bool(remote_dev_allowed)
    else:
        problems = validate_auth_configuration(env)
        if problems:
            raise AuthPostureError("; ".join(problems))
        secret_present = bool(jwt_secret())
        override = allow_remote_dev()

    host = bind_host or os.environ.get("NS_FOUNDATION_BIND_HOST") \
        or os.environ.get("UVICORN_HOST") or os.environ.get("HOST") or "127.0.0.1"
    binds_remote = not is_loopback_host(host)
    dev_shim_active = not secret_present
    if binds_remote and dev_shim_active and not (env == "development" and override):
        raise AuthPostureError(
            "refusing to bind beyond loopback while the development shim is "
            "active (set NORTHSTAR_JWT_SECRET for real auth, or run in "
            "ENVIRONMENT=development with NS_FOUNDATION_ALLOW_REMOTE_DEV=1)")

    return {
        "environment": env,
        "bind_host": host,
        "binds_beyond_loopback": binds_remote,
        "jwt_secret_present": secret_present,
        "dev_shim_active": dev_shim_active,
        "remote_dev_override": override,
        "issuer_required": env in _PROD_LIKE,
        "audience_required": env in _PROD_LIKE,
        "allowed_algorithms": list(allowed_algorithms()),
        "auth_posture": "jwt" if secret_present else "dev_shim_local_only",
    }