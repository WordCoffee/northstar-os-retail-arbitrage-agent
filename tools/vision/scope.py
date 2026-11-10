"""Write scope: the project root and the declared roots, and nothing else without a grant.

Work order §2 screen-privacy rule 6. On this laptop Ty reads and writes inside the project
root plus `reports/`, `state/`, `research/` and its worktrees. Writing anywhere else needs a
`GRANT:` entry naming the path. `TY_PC_MODE=1` is *built for* and **not enabled here**.

The check resolves the path before comparing, so `..` cannot walk out of scope.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

ROOT = Path(__file__).resolve().parents[2]
GRANTS = ROOT / "ty" / "vision_grants.json"

DECLARED_ROOTS = ("reports", "state", "research", "state/worktrees", "ty")


def grants(*, path: Optional[Path] = None) -> Dict[str, Any]:
    try:
        data = json.loads(Path(path or GRANTS).read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def pc_mode_enabled(*, env: Optional[Dict[str, str]] = None,
                    grant_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """PC mode needs both the flag and a grant entry. One without the other is off."""
    environment = env if env is not None else os.environ
    flag = str(environment.get("TY_PC_MODE", "")).strip() == "1"
    entry = (grant_data if grant_data is not None else grants()).get("pc_mode") or {}
    granted = bool(entry.get("granted"))
    return {"enabled": flag and granted, "flag": flag, "granted": granted,
            "reason": "" if (flag and granted) else
            ("TY_PC_MODE is not 1" if not flag else "no pc_mode grant recorded")}


def allowed_paths(*, path: Optional[Path] = None) -> List[Path]:
    roots = [ROOT] + [ROOT / name for name in DECLARED_ROOTS]
    for entry in (grants(path=path).get("paths") or []):
        candidate = Path(str(entry.get("path") or ""))
        if str(entry.get("granted")) and str(candidate):
            roots.append(candidate if candidate.is_absolute() else ROOT / candidate)
    return roots


def check(target: str, *, path: Optional[Path] = None,
          env: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """May Ty read or write this path? A refusal names the grant that would fix it."""
    raw = Path(str(target or ""))
    resolved = (raw if raw.is_absolute() else ROOT / raw).resolve()
    mode = pc_mode_enabled(env=env, grant_data=grants(path=path))
    if mode["enabled"]:
        return {"allow": True, "path": str(resolved), "root": "pc_mode",
                "reason": "TY_PC_MODE with a grant"}
    for root in allowed_paths(path=path):
        try:
            root_resolved = Path(root).resolve()
        except OSError:
            continue
        if resolved == root_resolved or root_resolved in resolved.parents:
            return {"allow": True, "path": str(resolved), "root": str(root_resolved),
                    "reason": "inside a declared root"}
    return {"allow": False, "path": str(resolved), "root": "",
            "reason": (f"{resolved} is outside the declared roots; writing there needs a "
                       "GRANT: entry in ty/vision_grants.json naming the path")}
