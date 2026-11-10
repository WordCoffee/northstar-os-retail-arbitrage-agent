"""Northstar MCP server — read-only tools over stdio.

Expose the operator's local surfaces to an MCP client without giving it a
browser handle, a shell, or a write path. Every tool is read-only; the server
uses the same local API and SQLite stores as the service.

    python tools/northstar_mcp_server.py

Client config (stdio):
    {"command": "python", "args": ["tools/northstar_mcp_server.py"]}

The server is intentionally thin: it does not replace the admin API, and it
does not expose memory writes or task submission.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "Northstar_backend"
sys.path.insert(0, str(BACKEND))

from mcp.server.mcpserver import MCPServer  # noqa: E402

SERVER = MCPServer(
    "northstar-os",
    title="Northstar OS",
    description="Read-only Northstar OS surfaces: health, Tys tasks, memory, provider suite, renders.",
    version="1.0.0",
)


def _get_json(url: str, *, headers: Optional[Dict[str, str]] = None,
              timeout: float = 10.0) -> Dict[str, Any]:
    import urllib.error
    import urllib.request

    request = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return {"ok": False, "status": exc.code,
                "detail": exc.read().decode("utf-8", "replace")[:400]}
    except Exception as exc:  # noqa: BLE001 - a tool result, not a crash
        return {"ok": False, "status": None, "detail": f"{type(exc).__name__}: {exc}"}


@SERVER.tool(description="Northstar backend health (local loopback).")
def northstar_health() -> Dict[str, Any]:
    return _get_json("http://127.0.0.1:8000/health", timeout=5.0)


@SERVER.tool(description="Tys Assistant state: identity, queue, lane availability.")
def tys_state() -> Dict[str, Any]:
    return _get_json("http://127.0.0.1:8000/api/admin/tys/state",
                     headers={"X-User-Id": "demo-t2", "X-Role": "operator",
                              "X-Org-Id": "org-t2"})


@SERVER.tool(description="List Tys work orders (bounded, read-only).")
def tys_tasks(limit: int = 20) -> Dict[str, Any]:
    limit = max(1, min(int(limit), 100))
    return _get_json(f"http://127.0.0.1:8000/api/admin/tys/tasks?limit={limit}",
                     headers={"X-User-Id": "demo-t2", "X-Role": "operator",
                              "X-Org-Id": "org-t2"})


@SERVER.tool(description="Search long-term memory (semantic when the embedder is up).")
def memory_search(query: str, account: str = "operator", k: int = 5) -> Dict[str, Any]:
    from tys_ops.memory import MemoryIndex

    path = ROOT / "Northstar_backend" / "data" / "tys_memory.db"
    index = MemoryIndex(str(path), semantic=True)
    try:
        return {"account": account, "semantic": index.semantic,
                "hits": index.search(account, str(query), k=max(1, min(int(k), 20)))}
    finally:
        index.close()


@SERVER.tool(description="Provider tool-suite catalog (local/cloud lanes, licences, gates).")
def provider_suite(provider: Optional[str] = None) -> Dict[str, Any]:
    import provider_suite as ps

    try:
        return ps.catalog(active=provider)
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "detail": f"{type(exc).__name__}: {exc}"}


@SERVER.tool(description="Read a render/product-picture manifest under renders/.")
def render_manifest(path: str) -> Dict[str, Any]:
    base = (ROOT / "renders").resolve()
    target = (ROOT / str(path)).resolve()
    if base not in target.parents and target != base:
        return {"ok": False, "error": "path outside renders/"}
    if not target.is_file():
        return {"ok": False, "error": "manifest not found"}
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"ok": False, "error": str(exc)[:300]}
    return {"ok": True, "path": str(target.relative_to(ROOT)), "manifest": data}


def main() -> int:
    SERVER.run("stdio")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
