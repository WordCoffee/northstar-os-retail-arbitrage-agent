"""bff/v1 envelope middleware (Phase F, Section 1 / D12).

Wraps legacy JSON endpoint responses into the bff/v1 envelope defined in
docs/contracts/BFF_CONTRACT_v1.md, preserving the existing data shape under
``data``. Applies ONLY to the legacy read/write prefixes:

    /api/kirkland/*  /api/suppliers/*  /api/v1/plans  /api/products/*  /api/filters/universal

Skipped (already conformant or intentionally plain):
  /api/golden-goose/* and /api/v1/credits (already bff/v1),
  /legal/*, /health*, /api/v1/auth and /api/v1/admin (left as-is; admin is
  least-privilege plain on purpose, and its envelope additions are not part
  of the D12 legacy sweep).

Design notes:
  - Only 2xx JSON responses are wrapped; HTTP-level errors (HTTPException)
    pass through unchanged — acceptable under BFF_CONTRACT_v1.md §5 (HTTP
    error mapping), and avoids churn on 4xx/5xx contract tests.
  - If a response already carries a "contract" key it is left untouched.
  - Pure ``wrap_payload`` is exported for direct unit testing.
"""

from __future__ import annotations

import secrets
from typing import Any, Dict, Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response

WRAP_PREFIXES = (
    "/api/kirkland/",
    "/api/suppliers",
    "/api/v1/plans",
    "/api/products/",
    "/api/filters/universal",
)

SKIP_PREFIXES = ("/legal", "/health", "/api/golden-goose", "/api/v1/credits",
                 "/api/v1/auth", "/api/v1/admin", "/static", "/api/transcribe", "/api/files", "/api/latest-deals", "/api/data/")
#if needed: exclude already-conformant by content check anyway


def request_id() -> str:
    return "req_" + secrets.token_hex(16)


def wrap_payload(payload: Any, status: int = 200) -> Dict[str, Any]:
    """Wrap a parsed JSON payload into a bff/v1 envelope (status ok/empty)."""
    env_status = "empty" if (status == 200 and payload is None) else "ok"
    return {
        "contract": "bff/v1",
        "request_id": request_id(),
        "status": env_status,
        "data": payload if payload is not None else {},
        "error": None,
        "meta": {"service": "northstar", "version": "v1"},
    }


def _eligible(path: str) -> bool:
    if any(path.startswith(s) for s in SKIP_PREFIXES):
        return False
    return any(path.startswith(s) for s in WRAP_PREFIXES)


class BffEnvelopeMiddleware(BaseHTTPMiddleware):
    """Wrap eligible legacy JSON success responses in the bff/v1 envelope."""

    async def dispatch(self, request, call_next):
        path = request.url.path
        response = await call_next(request)
        if not _eligible(path):
            return response
        if response.status_code < 200 or response.status_code >= 300:
            return response  # errors stay HTTP-level (BFF §5)
        if isinstance(response, (Response,)) and "json" not in (response.headers.get("content-type") or ""):
            return response  # e.g. FileResponse
        try:
            body = b""
            async for chunk in response.body_iterator:
                body += chunk
            text = body.decode("utf-8", "replace")
            if not text.strip():
                return response
            payload = json_loads_safe(text)
            if payload is None or not isinstance(payload, dict) or "contract" in payload:
                return response
            wrapped = wrap_payload(payload, response.status_code)
            return JSONResponse(
                wrapped,
                status_code=response.status_code,
                headers={k: v for k, v in response.headers.items() if k.lower() != "content-length"},
            )
        except Exception:
            return response


def json_loads_safe(text: str) -> Optional[Any]:
    import json
    try:
        return json.loads(text)
    except Exception:
        return None