"""The director's eyes: one probe, one state file, one consumer.

Ty's Vision is not a loop and must never become one. It has no queue, no launcher and no merge
right. What it has is the only honest answer to "does this route render, and does the desktop
actually show it" — and the canonical loop (the director) needs that answer to rank work.

This module is the whole seam:

* `status()` — read-only, cheap, safe to call from a heartbeat every five minutes. It reports the
  PAUSE file, the locked/unlocked state, and whether the last probe is fresh.
* `probe()` — runs the route audit (`tools.vision.ux_audit --run`) **only** when the eyes are
  allowed to act, then writes `state/director/vision.json`. Refuses by name otherwise.
* `queue_hint()` — the consumer side: the routes that still render the generic shell, as a bundle
  the director's re-plan can enqueue.

The refusal is the important part. A probe that runs while `state/vision/PAUSE` exists, or while the
desktop is locked, would be the eyes acting on their own judgement — the exact thing the pause file
exists to stop. So it returns a reason, not a partial result.

    python -m tools.director_vision --status     # read-only, no action
    python -m tools.director_vision --probe      # one probe if allowed
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

ROOT = Path(__file__).resolve().parents[1]
PAUSE = ROOT / "state" / "vision" / "PAUSE"
STATE = ROOT / "state" / "director" / "vision.json"
AUDIT = ROOT / "ty" / "ux_audit.json"
FRESH_S = 6 * 3600


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _relative(path: Path) -> str:
    """A repo-relative path when it is inside the repo, otherwise the absolute one.

    A probe pointed at a path outside the root (a test fixture) must report where it read, not
    raise because the path is not under the repo.
    """
    try:
        return str(path.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path)


def _read(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def foreground() -> Dict[str, Any]:
    """The window that currently has focus, without touching any browser or frame."""
    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return {"title": "", "process": "", "error": "no foreground window"}
        length = user32.GetWindowTextLengthW(hwnd)
        buffer = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buffer, length + 1)
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        process = ""
        try:
            import psutil

            process = psutil.Process(pid.value).name()
        except Exception:  # noqa: BLE001 - a name is nice to have, not required
            process = ""
        return {"title": buffer.value, "process": process, "pid": int(pid.value)}
    except Exception as exc:  # noqa: BLE001 - a probe must never raise into the heartbeat
        return {"title": "", "process": "", "error": f"{type(exc).__name__}: {exc}"}


def blocked_reason() -> Optional[str]:
    """Why the eyes may not act right now, or None when they may."""
    if PAUSE.exists():
        return "state/vision/PAUSE is present: the owner has paused browser work"
    window = foreground()
    title = str(window.get("title") or "")
    process = str(window.get("process") or window.get("process_name") or "")
    if "lock" in process.lower() or "lock screen" in title.lower():
        return f"desktop is locked (foreground {title!r} / {process!r})"
    if window.get("error"):
        return f"foreground could not be read: {window['error']}"
    return None


def status() -> Dict[str, Any]:
    """Read-only. This is what a heartbeat calls; it never acts."""
    state = _read(STATE, {})
    probe_at = state.get("at")
    age = None
    if probe_at:
        try:
            age = round(time.time() - datetime.fromisoformat(probe_at).timestamp(), 1)
        except (TypeError, ValueError):
            age = None
    return {
        "at": _now(),
        "pause": PAUSE.exists(),
        "allowed": blocked_reason() is None,
        "blocked_reason": blocked_reason(),
        "foreground": foreground().get("title"),
        "last_probe_at": probe_at,
        "last_probe_age_s": age,
        "fresh": bool(age is not None and age < FRESH_S),
        "last_state": state.get("state"),
        "rendered": state.get("rendered"),
        "total": state.get("total"),
        "shell_routes": state.get("shell_routes") or [],
    }


def probe(*, force: bool = False) -> Dict[str, Any]:
    """Run the route audit if the eyes are allowed to, then record the truth."""
    reason = blocked_reason()
    if reason and not force:
        payload = {"at": _now(), "state": "refused", "reason": reason}
        _write(payload)
        return payload

    started = time.time()
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "tools.vision.ux_audit", "--run"],
            cwd=str(ROOT), capture_output=True, text=True, timeout=1800,
            encoding="utf-8", errors="replace")
        returncode = proc.returncode
        tail = (proc.stdout or proc.stderr or "").strip().splitlines()[-4:]
    except (OSError, subprocess.SubprocessError) as exc:
        returncode, tail = None, [f"{type(exc).__name__}: {exc}"]

    audit = _read(AUDIT, {})
    anchors = audit.get("anchors") or audit.get("routes") or []
    total = int(audit.get("total") or len(anchors) or 0)
    rendered = int(audit.get("rendered") or 0)
    shell = audit.get("shell_routes") or [
        row.get("id") or row.get("route") for row in anchors
        if str(row.get("kind") or row.get("rendered_by") or "") in ("shell", "chat_shell")
    ]
    payload = {
        "at": _now(),
        "state": "ok" if returncode == 0 else "error",
        "returncode": returncode,
        "seconds": round(time.time() - started, 1),
        "rendered": rendered,
        "total": total,
        "shell_routes": sorted(r for r in shell if r),
        "evidence": _relative(AUDIT),
        "tail": tail,
        "note": ("route truth from Ty's Vision: which advanced-view routes render their own page and "
                 "which still open the generic shell"),
    }
    _write(payload)
    return payload


def _write(payload: Dict[str, Any]) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(STATE)


def queue_hint() -> Optional[Dict[str, Any]]:
    """The consumer side: a bundle the director can enqueue, from fresh route truth."""
    state = _read(STATE, {})
    if state.get("state") != "ok":
        return None
    shell = [r for r in (state.get("shell_routes") or []) if r]
    if not shell:
        return None
    return {
        "unit": "vision-sh-shell-routes",
        "title": (f"{len(shell)} route(s) still open the generic shell instead of their own page: "
                  + ", ".join(shell[:6]) + ("…" if len(shell) > 6 else "")),
        "write_paths": ["northstar-os-ui/src/", "tests/e2e/"],
        "why": ("Ty's Vision route truth (state/director/vision.json): a service that renders the "
                "chat shell is not reachable by click and cannot be sold as its own place"),
        "services": shell,
        "points": 10.0 * min(len(shell), 4),
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="The director's eyes (Ty's Vision)")
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--probe", action="store_true")
    parser.add_argument("--force", action="store_true",
                        help="probe even when paused (only for a deliberate, owner-ordered run)")
    parser.add_argument("--json", action="store_true")
    ns = parser.parse_args(argv)

    if ns.probe:
        payload = probe(force=ns.force)
    else:
        payload = status()
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0 if payload.get("state") in (None, "ok", "refused") else 1


if __name__ == "__main__":
    raise SystemExit(main())
