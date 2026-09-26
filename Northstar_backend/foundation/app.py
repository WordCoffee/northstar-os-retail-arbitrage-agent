"""Standalone foundation FastAPI app (for tests and optional mounting).

Mounting into the main app is a single additive ``include_router`` call; this
module lets the foundation be exercised in isolation without touching main.py.

Canonical frontend (1C-06/D01): the React/Vite production build in
``northstar-os-ui/dist`` is served loopback-only at ``/ui/`` with an SPA
fallback. The legacy/demo Analyst's Desk shell under ``/northstar-os`` is
documented as legacy and NOT the canonical frontend.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .api.state import FoundationState
from .api.router import router as foundation_router
from .authn import assert_startup_posture

_BASE = Path(__file__).resolve().parent.parent.parent
UI_DIST = _BASE / "northstar-os-ui" / "dist"


def create_app(db_path: Optional[str] = None) -> FastAPI:
    # Enforce auth/bind posture at startup (amendment G1/G2). Fail-closed.
    assert_startup_posture()
    state = FoundationState.build(db_path)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.foundation = state
        try:
            yield
        finally:
            state.close()

    app = FastAPI(title="Northstar OS Foundation", version="foundation-1",
                  lifespan=lifespan)
    app.state.foundation = state
    app.include_router(foundation_router)

    # Canonical React/Vite UI (loopback-only production build). Hash routing
    # keeps deep links client-side; the index fallback covers direct loads.
    if UI_DIST.exists():
        app.mount("/ui/assets", StaticFiles(directory=str(UI_DIST / "assets")),
                  name="ui-assets")

        @app.get("/ui/{full_path:path}", include_in_schema=False)
        def serve_ui(full_path: str):
            candidate = UI_DIST / full_path
            if full_path and candidate.is_file():
                return FileResponse(str(candidate))
            return FileResponse(str(UI_DIST / "index.html"))

        @app.get("/ui", include_in_schema=False)
        def serve_ui_root():
            return FileResponse(str(UI_DIST / "index.html"))

    @app.middleware("http")
    async def authz_denial_audit(request, call_next):
        """1C-05: log denied authorization attempts (401/403/404 on the
        foundation API) WITHOUT exposing sensitive object data.

        This is an explicit, audited exception to the GET-side-effect rule: it
        writes an AUDIT record (never a job/provider/ledger write) so every
        denied authorization attempt is attributable.
        """
        response = await call_next(request)
        path = request.url.path
        if path.startswith("/api/v1/foundation") and response.status_code in (401, 403, 404):
            st = getattr(request.app.state, "foundation", None)
            if st is not None and hasattr(st, "repos"):
                code = None
                try:
                    body = response.body
                    if body:
                        import json as _json
                        d = _json.loads(body)
                        code = (d.get("detail") or {}).get("code") if isinstance(d, dict) else None
                except Exception:  # noqa: BLE001
                    code = None
                try:
                    from .audit import AuditService
                    ctx = getattr(request.state, "ctx", None)
                    AuditService(st.repos).record(
                        action="authz.denied",
                        actor_user_id=getattr(ctx, "user_id", None),
                        actor_role=getattr(ctx, "effective_role", None),
                        organization_id=getattr(ctx, "effective_organization_id", None),
                        resource_type="api",
                        after_meta={"method": request.method, "path": path,
                                    "status": response.status_code,
                                    "code": code},
                        result="denied")
                except Exception:  # noqa: BLE001 - audit failure must not break the response
                    pass
        return response

    @app.middleware("http")
    async def security_headers(request, call_next):
        """Frontend security posture (1C-06/D13): CSP, framing, sniffing,
        referrer, and cache-controls. Authenticated shell HTML is never
        cached; hashed static assets may be cached."""
        response = await call_next(request)
        path = request.url.path
        if path.startswith("/ui"):
            response.headers["X-Frame-Options"] = "DENY"
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["Referrer-Policy"] = "no-referrer"
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; "
                "script-src 'self'; "
                "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
                "font-src 'self' https://fonts.gstatic.com; "
                "img-src 'self' data:; "
                "connect-src 'self'; "
                "frame-ancestors 'none'; "
                "base-uri 'self'; "
                "form-action 'self'"
            )
            if path == "/ui" or path.startswith("/ui/") and not path.startswith("/ui/assets"):
                # Authenticated shell — never cached.
                response.headers["Cache-Control"] = "no-store"
            elif path.startswith("/ui/assets/"):
                # Hashed static assets — cacheable.
                response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        return response
    return app


app = create_app()