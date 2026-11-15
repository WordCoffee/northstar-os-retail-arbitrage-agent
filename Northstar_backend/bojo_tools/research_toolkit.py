"""Research/design/improvement tools for Bojo, backed by ``tools/ty_toolkit``.

Four capabilities, each a thin adapter over a pure core:

* ``generate_api_client`` — typed client from an observed HTTP capture (no crawling);
* ``find_reference_media`` — openly licensed reference images from Openverse (licence + size gated);
* ``propose_improvements`` — ranked proactive proposals from measured state (no queue writes);
* ``route_local_model`` — local/mesh model choice with an explicit cloud fallback.

The repo root must be importable because the cores live in ``tools/ty_toolkit``; the backend is
started from ``Northstar_backend``, so the root is added here rather than assumed.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.ty_toolkit import capture as capture_tool  # noqa: E402
from tools.ty_toolkit import mesh_route, openverse, proposals  # noqa: E402

TOOL_GENERATE_CLIENT = "generate_api_client"
TOOL_FIND_MEDIA = "find_reference_media"
TOOL_PROPOSE = "propose_improvements"
TOOL_ROUTE = "route_local_model"


def _bad(tool: str, reason: str) -> Dict[str, Any]:
    return {"ok": False, "tool": tool, "reason": reason}


def generate_api_client(capture: Mapping[str, Any], language: str = "python",
                        name: str = "ApiClient") -> Dict[str, Any]:
    """Generate a typed client from a HAR/JSON capture. It never opens a socket."""
    if not isinstance(capture, Mapping):
        raise TypeError("capture must be a mapping")
    result = capture_tool.generate(dict(capture), language=str(language or "python"),
                                   name=str(name or "ApiClient"))
    if not result.get("ok"):
        return _bad(TOOL_GENERATE_CLIENT, str(result.get("reason") or "capture unusable"))
    return {"ok": True, "tool": TOOL_GENERATE_CLIENT,
            "data": {"language": result["language"], "name": result["name"],
                     "endpoints": result["endpoints"], "code": result["code"]}}


def find_reference_media(query: str, page_size: int = 5, min_side: int = 800) -> Dict[str, Any]:
    """Search Openverse; keep only openly licensed rows at/above the pixel gate."""
    result = openverse.search(str(query or ""), page_size=int(page_size), min_side=int(min_side))
    if not result.get("ok"):
        return _bad(TOOL_FIND_MEDIA, str(result.get("reason") or "openverse refused"))
    return {"ok": True, "tool": TOOL_FIND_MEDIA, "data": result}


def propose_improvements(limit: int = 6) -> Dict[str, Any]:
    """Ranked proposals from scorecards/queue/needs_you. Writes nothing."""
    result = proposals.build(limit=int(limit))
    return {"ok": True, "tool": TOOL_PROPOSE, "data": result}


def route_local_model(task: str, config: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
    """Choose a local or cloud model route; unknown health falls back to cloud, not assumed."""
    result = mesh_route.choose(str(task or ""), dict(config) if isinstance(config, Mapping) else None)
    if not result.get("ok"):
        return _bad(TOOL_ROUTE, str(result.get("reason") or "route refused"))
    return {"ok": True, "tool": TOOL_ROUTE, "data": result}


TOOLS = {
    TOOL_GENERATE_CLIENT: generate_api_client,
    TOOL_FIND_MEDIA: find_reference_media,
    TOOL_PROPOSE: propose_improvements,
    TOOL_ROUTE: route_local_model,
}
