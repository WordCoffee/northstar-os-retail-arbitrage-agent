"""Shared serving for the canonical React/Vite frontend (1C-06/D01).

The production build in ``northstar-os-ui/dist`` is served at ``/ui`` with
hash routing and an SPA index fallback, so deep links load directly. Both the
main app and the standalone foundation app mount the same helper so the
frontend contract stays identical everywhere.

No-op when the build is absent (returns False), so offline/dev harnesses
without a frontend build still start cleanly.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

_BASE = Path(__file__).resolve().parent.parent
UI_DIST = _BASE / "northstar-os-ui" / "dist"


def mount_ui(app: Any) -> bool:
    """Mount ``/ui/assets`` plus the ``/ui`` SPA fallback on ``app``.

    Returns True when the build exists and the routes were mounted, False
    otherwise (callers may degrade silently).
    """
    if not UI_DIST.exists():
        return False

    app.mount(
        "/ui/assets",
        StaticFiles(directory=str(UI_DIST / "assets")),
        name="ui-assets",
    )

    @app.get("/ui/{full_path:path}", include_in_schema=False)
    def serve_ui(full_path: str):
        candidate = UI_DIST / full_path
        if full_path and candidate.is_file():
            return FileResponse(str(candidate))
        return FileResponse(str(UI_DIST / "index.html"))

    @app.get("/ui", include_in_schema=False)
    def serve_ui_root():
        return FileResponse(str(UI_DIST / "index.html"))

    return True