"""Index the FastAPI surface that is actually mounted by ``Northstar_backend/main.py``.

The repository contains historical copies (``_main_dbg*.py``) and scripts that also
declare routes. Indexing every ``*.py`` therefore invents endpoints that are not
served. This module indexes only the modules ``main.py`` imports and includes, so a
citation such as ``Northstar_backend/main.py:1842`` is a real citation.

Public surface:
    routes()      -> list[Route]   (verb, path, file, line)
    find(verb, path) -> Route|None
    tools()       -> dict[str, dict]   chat_tools.TOOLS, by name
    bojo_tools()  -> list[str]         handlers registered in bojo_tools_registry
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "Northstar_backend"

# main.py's own app plus every module it includes a router from (main.py lines 52-163
# and 2952-3032). Backups and one-off scripts are deliberately absent.
MODULES = (
    "main.py",
    "agents/golden_goose_finder/main.py",
    "design_studio_api.py",
    "design_studio_print.py",
    "design_studio_async.py",
    "design_studio_agent.py",
    "design_studio_scenes.py",
    "design_studio_openapi.py",
    "text_fidelity.py",
    "design_studio_compose.py",
    "design_studio_aplus.py",
    "product_picture_api.py",
    "social_frames_api.py",
    "video_ad_api.py",
    "listing_image_api.py",
    "aplus_page_api.py",
    "chat_router.py",
    "chat_voice.py",
    "cie_router.py",
    "tys_api.py",
    "shell_router.py",
    "seo_router.py",
    "corpus_router.py",
    "design_studio_lanes.py",
    "studio_dashboard.py",
    "adpilot_api.py",
    "local_screen_api.py",
    "foundation/api/router.py",
    "noncreative_reads.py",
    "ops_router.py",
    "studio_upload_router.py",
    "bojo_tools_ops.py",
)

_DECORATOR = re.compile(
    r"@(?P<obj>\w+)\.(?P<verb>get|post|put|patch|delete|websocket)\(\s*[\"'](?P<path>[^\"']*)[\"']"
)
_PREFIX = re.compile(r"APIRouter\([^)]*prefix\s*=\s*[\"'](?P<prefix>[^\"']*)[\"']")


@dataclass(frozen=True)
class Route:
    verb: str
    path: str
    file: str
    line: int

    @property
    def ref(self) -> str:
        return f"{self.file}:{self.line}"


def _prefix_of(text: str) -> str:
    match = _PREFIX.search(text)
    return match.group("prefix").rstrip("/") if match else ""


def _join(prefix: str, path: str) -> str:
    if not path:
        return prefix or "/"
    if path.startswith(prefix + "/") or path == prefix:
        return path
    return f"{prefix}/{path.lstrip('/')}"


def routes() -> List[Route]:
    found: List[Route] = []
    for rel in MODULES:
        path = BACKEND / rel
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        prefix = _prefix_of(text)
        for number, line in enumerate(text.splitlines(), 1):
            match = _DECORATOR.search(line)
            if not match:
                continue
            found.append(
                Route(
                    verb=match.group("verb").upper(),
                    path=_join(prefix, match.group("path")),
                    file=f"Northstar_backend/{rel}",
                    line=number,
                )
            )
    return found


def find(verb: str, path: str, routes_: Optional[Iterable[Route]] = None) -> Optional[Route]:
    pool = list(routes_ if routes_ is not None else routes())
    verb = verb.upper()
    for route in pool:
        if route.path == path and route.verb == verb:
            return route
    return None


def paths() -> Dict[str, List[Route]]:
    out: Dict[str, List[Route]] = {}
    for route in routes():
        out.setdefault(route.path, []).append(route)
    return out


def tools() -> Dict[str, dict]:
    """chat_tools.TOOLS, imported from the backend package."""
    import json
    import subprocess
    import sys

    code = (
        "import json,sys;"
        "sys.path.insert(0, r'" + str(BACKEND) + "');"
        "import chat_tools;"
        "print(json.dumps(sorted(chat_tools.TOOLS)))"
    )
    out = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, timeout=120
    )
    if out.returncode != 0:
        raise RuntimeError(f"chat_tools import failed: {out.stderr.strip()[:400]}")
    return {name: {} for name in json.loads(out.stdout.strip().splitlines()[-1])}


def bojo_tools() -> List[str]:
    import json
    import subprocess
    import sys

    code = (
        "import json,sys;"
        "sys.path.insert(0, r'" + str(BACKEND) + "');"
        "import bojo_tools_registry as b;"
        "print(json.dumps(b.names()))"
    )
    out = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, timeout=120
    )
    if out.returncode != 0:
        raise RuntimeError(f"bojo_tools_registry import failed: {out.stderr.strip()[:400]}")
    return json.loads(out.stdout.strip().splitlines()[-1])
