"""Operator-only private-alpha gate (Phase H / H1).

When ``NORTHSTAR_PRIVATE_ALPHA=1`` the API is locked to an explicit email
allowlist (``NORTHSTAR_ALPHA_ALLOWLIST``, comma-separated). This is the
in-app half of the two-layer lock: Cloudflare Access is the edge half.

Fail-closed: if private alpha is ON and the allowlist is EMPTY, every
non-public ``/api/*`` request is blocked (a misconfiguration locks the door
rather than opening it).

Public (never gated): health, the plan catalog, legal docs, and all static
assets / shells — so probes, the marketing catalog, and the SPA itself load.
Everything else under ``/api/*`` requires an allowlisted identity.
"""

from __future__ import annotations

import logging
import os
from typing import Optional, Set, Tuple

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)

# Paths that stay reachable even in private alpha (prefix match).
PUBLIC_PATH_PREFIXES = (
    "/health",
    "/api/health",
    "/api/v1/plans",
    "/legal",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/static",
    "/autothink",
    "/northstar-os",
    "/landing",
    "/favicon",
)

# Static shells served at the root are always reachable (they are UI only;
# their data calls are what the gate protects).
PUBLIC_EXACT_PATHS = ("/", "/workbench", "/northstar-os", "/northstar-os/")

_warned_empty_allowlist = False


def _env_flag(name: str, default: bool = False) -> bool:
    raw = str(os.getenv(name, "") or "").strip().lower()
    if not raw:
        return default
    return raw in ("1", "true", "yes", "on")


def private_alpha_enabled() -> bool:
    """True when the operator-only private-alpha lock is active."""
    return _env_flag("NORTHSTAR_PRIVATE_ALPHA", default=False)


def alpha_allowlist() -> Set[str]:
    """Lowercased allowlisted emails (empty set => fail closed)."""
    raw = str(os.getenv("NORTHSTAR_ALPHA_ALLOWLIST", "") or "")
    return {e.strip().lower() for e in raw.split(",") if e.strip()}


def is_allowlisted(email: Optional[str]) -> bool:
    if not email:
        return False
    return str(email).strip().lower() in alpha_allowlist()


def is_public_path(path: str) -> bool:
    p = path or "/"
    if p in PUBLIC_EXACT_PATHS:
        return True
    return any(p.startswith(prefix) for prefix in PUBLIC_PATH_PREFIXES)


def identity_email_from_auth_header(auth_header: Optional[str]) -> Optional[str]:
    """Best-effort email from a ``Bearer <jwt>`` header. Never raises.

    Presence/validity only — no credential value is logged.
    """
    if not auth_header or not auth_header.lower().startswith("bearer "):
        return None
    token = auth_header.split(" ", 1)[1].strip()
    if not token:
        return None
    try:
        import auth as _auth
        payload = _auth.decode_token(token)
        if payload.get("type") != "access":
            return None
        return payload.get("email")
    except Exception:
        return None


def decide(method: str, path: str, email: Optional[str]) -> Tuple[bool, str]:
    """Return ``(blocked, reason)`` for a request under the gate policy.

    Pure and deterministic (no I/O) so it is directly unit-testable.
    """
    if not private_alpha_enabled():
        return False, "alpha_off"
    if is_public_path(path):
        return False, "public_path"
    if not alpha_allowlist():
        return True, "empty_allowlist_fail_closed"
    if is_allowlisted(email):
        return False, "allowlisted"
    return True, "not_allowlisted"


class AlphaGateMiddleware(BaseHTTPMiddleware):
    """Reject non-allowlisted API traffic while private alpha is active."""

    async def dispatch(self, request, call_next):
        global _warned_empty_allowlist
        path = request.url.path
        email = identity_email_from_auth_header(request.headers.get("authorization"))
        blocked, reason = decide(request.method, path, email)

        if blocked:
            if reason == "empty_allowlist_fail_closed" and not _warned_empty_allowlist:
                _warned_empty_allowlist = True
                logger.critical(
                    "PRIVATE ALPHA is ON but NORTHSTAR_ALPHA_ALLOWLIST is empty — "
                    "all API traffic is blocked (fail-closed). Set the allowlist."
                )
            return JSONResponse(
                status_code=403,
                content={
                    "contract": "bff/v1",
                    "request_id": "req_alpha_gate",
                    "status": "error",
                    "data": None,
                    "error": {
                        "code": "private_alpha_locked",
                        "message": (
                            "Northstar OS is in private alpha and is locked to "
                            "authorized accounts."
                        ),
                    },
                    "meta": {"service": "alpha_gate", "reason": reason},
                },
            )

        return await call_next(request)
