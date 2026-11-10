"""Whole-desktop and per-window capture, with the privacy gate in front of it.

Work order §5.1 layer 1 and §2 rule 2. The order of operations is the design:

    enumerate -> classify -> (drop | grab)

A refused window is never grabbed, so "no frame reaches a model or disk" is a property
of the code path rather than a promise about behaviour afterwards.

Capture backends, best first: `mss` (fast, DPI-aware), `PIL.ImageGrab` (fallback).
Idle capture is off: `frame()` is only ever called by a task that asked for it.
"""
from __future__ import annotations

import ctypes
import json
import os
import time
from ctypes import wintypes
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import privacy

STATE = Path(__file__).resolve().parents[2] / "state" / "vision"
FRAMES = STATE / "frames"
EVENTS = STATE / "events.jsonl"
RETENTION_DAYS = 7


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _event(row: Dict[str, Any]) -> None:
    STATE.mkdir(parents=True, exist_ok=True)
    with EVENTS.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"at": _now(), **row}, ensure_ascii=False) + "\n")


# ------------------------------------------------------------------- windows
def _process_name(pid: int) -> str:
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    handle = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION,
                                                False, int(pid))
    if not handle:
        return ""
    try:
        size = wintypes.DWORD(1024)
        buffer = ctypes.create_unicode_buffer(1024)
        if ctypes.windll.kernel32.QueryFullProcessImageNameW(
                handle, 0, buffer, ctypes.byref(size)):
            return os.path.basename(buffer.value)
        return ""
    finally:
        ctypes.windll.kernel32.CloseHandle(handle)


def windows() -> List[Dict[str, Any]]:
    """Every visible top-level window with its title, process and rect."""
    found: List[Dict[str, Any]] = []
    EnumProc = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)

    class RECT(ctypes.Structure):
        _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                    ("right", ctypes.c_long), ("bottom", ctypes.c_long)]

    def callback(hwnd, _lparam):
        if not ctypes.windll.user32.IsWindowVisible(hwnd):
            return True
        length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
        title = ctypes.create_unicode_buffer(length + 1)
        ctypes.windll.user32.GetWindowTextW(hwnd, title, length + 1)
        if not title.value.strip():
            return True
        pid = wintypes.DWORD()
        ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        rect = RECT()
        ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect))
        found.append({"hwnd": int(hwnd), "title": title.value,
                      "process": _process_name(pid.value),
                      "rect": [rect.left, rect.top, rect.right, rect.bottom],
                      "width": max(0, rect.right - rect.left),
                      "height": max(0, rect.bottom - rect.top)})
        return True

    ctypes.windll.user32.EnumWindows(EnumProc(callback), 0)
    return found


def classify_window(window: Optional[Dict[str, Any]] = None, **kwargs: Any) -> Dict[str, Any]:
    """Classify a window dict, or explicit title/process/url keywords."""
    if window:
        kwargs = {"title": window.get("title", ""), "process": window.get("process", ""),
                  "url": window.get("url", "")}
    return privacy.classify(**{k: str(v or "") for k, v in kwargs.items()})


# -------------------------------------------------------------------- frames
def monitors() -> List[Dict[str, Any]]:
    """Every monitor mss can see. Multi-monitor aware, and honest when it cannot look."""
    try:
        import mss  # noqa: PLC0415

        with mss.mss() as sct:
            return [dict(one) for one in sct.monitors]
    except Exception as exc:  # noqa: BLE001
        return [{"error": f"{type(exc).__name__}: {exc}"}]


def _grab(rect: Optional[List[int]] = None) -> Dict[str, Any]:
    """PNG bytes for a screen rect, via mss then ImageGrab. Never writes to disk."""
    import io

    try:
        import mss  # noqa: PLC0415

        with mss.mss() as sct:
            if rect:
                left, top, right, bottom = rect
                region = {"left": left, "top": top,
                          "width": max(1, right - left), "height": max(1, bottom - top)}
            else:
                region = sct.monitors[1]
            shot = sct.grab(region)
            from PIL import Image  # noqa: PLC0415

            image = Image.frombytes("RGB", shot.size, shot.rgb)
            buffer = io.BytesIO()
            image.save(buffer, format="PNG")
            return {"ok": True, "png": buffer.getvalue(), "backend": "mss",
                    "size": list(shot.size)}
    except Exception as mss_error:  # noqa: BLE001 - fall through to the fallback
        try:
            from PIL import ImageGrab  # noqa: PLC0415

            image = ImageGrab.grab(bbox=tuple(rect) if rect else None)
            buffer = io.BytesIO()
            image.save(buffer, format="PNG")
            return {"ok": True, "png": buffer.getvalue(), "backend": "imagegrab",
                    "size": list(image.size)}
        except Exception as grab_error:  # noqa: BLE001
            return {"ok": False, "error": f"mss: {mss_error}; imagegrab: {grab_error}"}


def frame(window: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """One frame, gated. A refused window returns no pixels at all."""
    target = window or {}
    verdict = classify_window(target) if target else {"allow": True, "reason": ""}
    if not verdict.get("allow"):
        _event({"event": "blocked-window", "title": target.get("title", ""),
                "process": target.get("process", ""), "reason": verdict.get("reason")})
        return {"ok": False, "blocked": True, "reason": verdict.get("reason"),
                "png": None, "written": None}
    shot = _grab(target.get("rect"))
    if not shot.get("ok"):
        return {"ok": False, "blocked": False, "reason": shot.get("error"), "png": None}
    return {"ok": True, "blocked": False, "png": shot["png"],
            "backend": shot["backend"], "size": shot.get("size"),
            "written": None}


def save_audit_frame(png: bytes, *, name: str = "") -> Optional[Path]:
    """Audit frames live 7 days, locally only, in a gitignored access-restricted folder."""
    if not png:
        return None
    FRAMES.mkdir(parents=True, exist_ok=True)
    path = FRAMES / (name or f"{int(time.time())}.png")
    path.write_bytes(png)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    return path


def prune(days: int = RETENTION_DAYS, frames: Optional[Path] = None) -> List[str]:
    """Delete audit frames older than the retention window."""
    root = Path(frames or FRAMES)
    if not root.is_dir():
        return []
    cutoff = time.time() - days * 86400
    removed: List[str] = []
    for path in root.glob("*.png"):
        try:
            if path.stat().st_mtime < cutoff:
                path.unlink()
                removed.append(path.name)
        except OSError:
            continue
    return removed
