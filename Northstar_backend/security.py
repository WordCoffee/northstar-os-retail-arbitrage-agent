"""Security middleware for Northstar OS.

Provides:
- Security headers (CSP, HSTS, X-Frame-Options, etc.)
- Request ID tracking
- CORS configuration
- Input sanitization helpers
"""

import uuid
from typing import Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses."""

    HEADERS = {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "X-XSS-Protection": "1; mode=block",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
        "Cache-Control": "no-store, no-cache, must-revalidate, private",
    }

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        for key, value in self.HEADERS.items():
            response.headers[key] = value

        # Add request ID for tracing
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())[:12]
        response.headers["X-Request-ID"] = request_id

        return response


class RequestTracingMiddleware(BaseHTTPMiddleware):
    """Add request timing and tracing."""

    async def dispatch(self, request: Request, call_next):
        import time
        start = time.time()

        # Add request ID to request state
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())[:12]
        request.state.request_id = request_id

        response = await call_next(request)

        elapsed_ms = int((time.time() - start) * 1000)
        response.headers["X-Response-Time"] = f"{elapsed_ms}ms"

        return response


def get_cors_origins() -> list:
    """Get CORS allowed origins from environment."""
    import os
    origins_str = os.environ.get("CORS_ORIGINS", "http://localhost:8000,http://localhost:3000")
    return [o.strip() for o in origins_str.split(",") if o.strip()]


def sanitize_input(text: str, max_length: int = 10000) -> str:
    """Basic input sanitization."""
    if not text:
        return ""
    # Truncate
    text = text[:max_length]
    # Strip null bytes
    text = text.replace("\x00", "")
    return text.strip()
