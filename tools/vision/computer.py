"""Computer mode: files, processes, windows and app launching, behind scope and grants.

Work order §5.1 layer 7 and §2 rule 6. Everything here is a risk-classed action:

* reading and writing files is `edit_own`, and scope decides whether "own" covers the path;
* listing processes and windows is `observe`;
* launching an app is `edit_own`, because it changes this machine and nothing outside it.

The dedicated low-privilege PC-mode setup is **built, not executed** (`--pc-mode-plan`
prints it). TY_PC_MODE needs both the flag and a grant entry, so a single env var cannot
turn full-filesystem access on by accident.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import capture, privacy, risk, scope


def _verdict(kind: str, target: str, path: str = "") -> Dict[str, Any]:
    return risk.evaluate({"kind": kind, "path": path, "target": target},
                         url="", title="", scope=[str(scope.ROOT)])


def read_text(target: str, *, limit: int = 200_000) -> Dict[str, Any]:
    """Read a file inside scope. The privacy filter applies to the text, not the path."""
    check = scope.check(target)
    if not check["allow"]:
        return {"ok": False, "refused": True, "risk": risk.EDIT_OWN,
                "reason": check["reason"], "path": check["path"]}
    path = Path(check["path"])
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return {"ok": False, "reason": f"{type(exc).__name__}: {exc}", "path": str(path)}
    return {"ok": True, "path": str(path), "bytes": len(text),
            "text": privacy.redact(text[:limit]), "truncated": len(text) > limit}


def write_text(target: str, text: str, *, create: bool = True) -> Dict[str, Any]:
    """Write a file inside scope, after the risk gate and the scope gate both say yes."""
    verdict = _verdict("create_file" if create else "edit_file", target)
    if not verdict["allow"]:
        if verdict.get("needs_you"):
            risk.record_needs_you({"kind": "create_file", "path": target}, verdict)
        return {"ok": False, "refused": True, **verdict}
    check = scope.check(target)
    if not check["allow"]:
        return {"ok": False, "refused": True, "risk": risk.EDIT_OWN,
                "reason": check["reason"], "path": check["path"]}
    path = Path(check["path"])
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(str(text), encoding="utf-8")
    except OSError as exc:
        return {"ok": False, "reason": f"{type(exc).__name__}: {exc}", "path": str(path)}
    return {"ok": True, "path": str(path), "bytes": len(str(text))}


def list_dir(target: str = ".") -> Dict[str, Any]:
    check = scope.check(target)
    if not check["allow"]:
        return {"ok": False, "refused": True, "reason": check["reason"]}
    path = Path(check["path"])
    try:
        rows = [{"name": item.name, "dir": item.is_dir(),
                 "bytes": None if item.is_dir() else item.stat().st_size}
                for item in sorted(path.iterdir())][:500]
    except OSError as exc:
        return {"ok": False, "reason": f"{type(exc).__name__}: {exc}"}
    return {"ok": True, "path": str(path), "entries": rows, "count": len(rows)}


def processes() -> Dict[str, Any]:
    """Running processes, names and pids only — never command lines with secrets."""
    try:
        import psutil  # noqa: PLC0415

        rows = []
        for proc in psutil.process_iter(["pid", "name"]):
            try:
                rows.append({"pid": proc.info["pid"], "name": proc.info["name"] or ""})
            except Exception:  # noqa: BLE001 - a dying process is not an error
                continue
        return {"ok": True, "processes": rows[:400], "count": len(rows)}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "reason": f"{type(exc).__name__}: {exc}"}


def windows() -> Dict[str, Any]:
    """Visible windows, already filtered by the privacy blocklist."""
    try:
        rows = capture.windows()
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "reason": f"{type(exc).__name__}: {exc}"}
    safe = []
    for row in rows:
        verdict = privacy.classify(title=row.get("title", ""),
                                   process=row.get("process", ""))
        if verdict.get("allow"):
            safe.append({"title": row.get("title"), "process": row.get("process"),
                         "hwnd": row.get("hwnd"), "width": row.get("width"),
                         "height": row.get("height")})
    return {"ok": True, "windows": safe, "count": len(safe),
            "blocked": len(rows) - len(safe)}


def launch_app(command: str, *, args: Optional[List[str]] = None) -> Dict[str, Any]:
    """Start an app. `edit_own` risk: it changes this machine and nothing else."""
    verdict = _verdict("launch_app", command)
    if not verdict["allow"]:
        return {"ok": False, "refused": True, **verdict}
    try:
        proc = subprocess.Popen([command, *(args or [])], close_fds=True)
    except OSError as exc:
        return {"ok": False, "reason": f"{type(exc).__name__}: {exc}"}
    return {"ok": True, "pid": proc.pid, "command": command}


PC_MODE_PLAN = {
    "title": "Dedicated Northstar PC mode (built, not executed here)",
    "steps": [
        "net user northstar-ty '<password from the owner>' /add",
        "net localgroup Users northstar-ty /add",
        "create %USERPROFILE%\\NorthstarPC with read/write for northstar-ty only",
        "register the launcher as a scheduled task under northstar-ty (not the owner)",
        "set TY_PC_MODE=1 and add {granted: true, path: 'C:/...'} to ty/vision_grants.json",
    ],
    "guard": ("TY_PC_MODE needs the environment flag AND a grant entry; either one alone "
              "leaves full-filesystem access off"),
    "not_executed": "creating a user and a grant is an owner decision for that machine",
}


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Computer mode (scaffolding)")
    parser.add_argument("--scope-check", default="")
    parser.add_argument("--list", default="")
    parser.add_argument("--processes", action="store_true")
    parser.add_argument("--windows", action="store_true")
    parser.add_argument("--pc-mode-plan", action="store_true")
    ns = parser.parse_args(argv)

    if ns.scope_check:
        print(json.dumps(scope.check(ns.scope_check), indent=2))
    elif ns.list:
        print(json.dumps(list_dir(ns.list), indent=2)[:4000])
    elif ns.processes:
        print(json.dumps({"count": processes().get("count")}, indent=2))
    elif ns.windows:
        print(json.dumps({"count": windows().get("count"),
                          "blocked": windows().get("blocked")}, indent=2))
    elif ns.pc_mode_plan:
        print(json.dumps(PC_MODE_PLAN, indent=2))
    else:
        print(json.dumps({"pc_mode": scope.pc_mode_enabled(),
                          "roots": [str(p) for p in scope.allowed_paths()]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
