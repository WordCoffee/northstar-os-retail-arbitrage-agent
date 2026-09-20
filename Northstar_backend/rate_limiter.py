"""Rate limiting middleware for Northstar OS.

Token-bucket rate limiter using in-memory storage (Redis-backed in production).
Protects against abuse while allowing legitimate burst traffic.

Limits:
- Anonymous (foundation): 30 req/min
- Scout plan: 60 req/min
- Mover plan: 120 req/min
- AutothinK plan: 300 req/min
"""

import time
from collections import defaultdict
from typing import Dict, Optional, Tuple

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse


class RateLimitMiddleware(BaseHTTPMiddleware):
    """In-memory token bucket rate limiter."""

    PLAN_LIMITS = {
        "foundation": 30,
        "scout": 60,
        "mover": 120,
        "autothink": 300,
    }

    def __init__(self, app, window_seconds: int = 60):
        super().__init__(app)
        self.window_seconds = window_seconds
        self._requests: Dict[str, list] = defaultdict(list)

    def _get_client_id(self, request: Request) -> str:
        """Identify client by IP + user agent hash."""
        forwarded = request.headers.get("X-Forwarded-For")
        ip = forwarded.split(",")[0].strip() if forwarded else (
            request.client.host if request.client else "unknown"
        )
        return ip

    def _get_plan(self, request: Request) -> str:
        """Extract plan from auth token if available."""
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return "foundation"

        try:
            import auth
            token = auth_header[7:]
            payload = auth.decode_token(token)
            return payload.get("plan", "foundation")
        except Exception:
            return "foundation"

    def _is_rate_limited(self, client_id: str, plan: str) -> Tuple[bool, Dict]:
        """Check if client is rate limited. Returns (limited, info)."""
        now = time.time()
        cutoff = now - self.window_seconds

        # Clean old entries
        self._requests[client_id] = [
            t for t in self._requests[client_id] if t > cutoff
        ]

        limit = self.PLAN_LIMITS.get(plan, 30)
        current = len(self._requests[client_id])

        if current >= limit:
            retry_after = int(self._requests[client_id][0] + self.window_seconds - now) + 1
            return True, {
                "limit": limit,
                "remaining": 0,
                "reset_in": retry_after,
                "plan": plan,
            }

        self._requests[client_id].append(now)
        return False, {
            "limit": limit,
            "remaining": limit - current - 1,
            "reset_in": self.window_seconds,
            "plan": plan,
        }

    async def dispatch(self, request: Request, call_next):
        # Local/test builds may disable the edge rate limiter (the shared
        # pytest process counts every TestClient call against one client id,
        # which tripped anonymous 30/min during larger suites). Product limits
        # above remain the deployed default; set NORTHSTAR_DISABLE_RATE_LIMIT=1
        # only in harness/tooling invocations.
        import os
        if os.getenv("NORTHSTAR_DISABLE_RATE_LIMIT", "").strip() == "1":
            return await call_next(request)

        # Skip rate limiting for health checks and static files
        path = request.url.path
        if path in ("/health", "/health/detailed") or path.startswith("/static"):
            return await call_next(request)

        client_id = self._get_client_id(request)
        plan = self._get_plan(request)
        limited, info = self._is_rate_limited(client_id, plan)

        if limited:
            return JSONResponse(
                status_code=429,
                content={
                    "error": "Rate limit exceeded",
                    "detail": f"Max {info['limit']} requests per minute on {plan} plan",
                    "retry_after": info["reset_in"],
                },
                headers={
                    "X-RateLimit-Limit": str(info["limit"]),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(info["reset_in"]),
                    "Retry-After": str(info["reset_in"]),
                },
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(info["limit"])
        response.headers["X-RateLimit-Remaining"] = str(info["remaining"])
        response.headers["X-RateLimit-Reset"] = str(info["reset_in"])
        return response
