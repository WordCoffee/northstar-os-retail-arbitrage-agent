"""Lane leases: one GPU holder, one browser holder, many CPU tasks.

The box has 16 GB RAM, 16 GB VRAM and a hard render floor of 4096 MB free. Three
things routinely want the same resources - a render, a vision check, a coding
loop - and the failure mode we already hit is a render *failing* because the
brain was resident. A lease turns that into a **deferral**: the cycle asks, is
told no with a reason, and requeues instead of burning an attempt.

    python tools/lanes.py status
    python tools/lanes.py acquire gpu --cycle 12
    python tools/lanes.py release gpu

State: state/lanes/<lane>.json  {holder_cycle, taken_at, taken_ts, ttl_s}

A lease is advisory across processes, so it is deliberately simple: O_EXCL create,
TTL expiry, and a JSON body for diagnosis. Nothing here can deadlock the loop: an
expired lease is always reclaimable.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

ROOT = Path(__file__).resolve().parents[1]
LANES = ROOT / "state" / "lanes"

LANE_TTL_S = {"gpu": 30 * 60, "browser": 30 * 60, "cpu": 6 * 3600}
#: Floors. Below these the lane *defers*; it never weakens the floor to proceed.
GPU_MIN_FREE_MB = int(os.environ.get("LANE_GPU_MIN_FREE_MB", "4096"))
RAM_MIN_FREE_MB = int(os.environ.get("LANE_RAM_MIN_FREE_MB", "3000"))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def vram_free_mb() -> Optional[int]:
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.free", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=15, check=False)
        return int(out.stdout.strip().splitlines()[0])
    except Exception:  # noqa: BLE001 - unknown means "cannot prove headroom"
        return None


def ram_free_mb() -> Optional[int]:
    try:
        import ctypes

        class MS(ctypes.Structure):
            _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                        ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]

        stat = MS()
        stat.dwLength = ctypes.sizeof(MS)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
        return int(stat.ullAvailPhys / 1048576)
    except Exception:  # noqa: BLE001
        return None


def _path(lane: str) -> Path:
    return LANES / f"{lane}.json"


def status(lane: str) -> Dict[str, Any]:
    path = _path(lane)
    if not path.is_file():
        return {"lane": lane, "held": False}
    try:
        body = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"lane": lane, "held": False, "note": "unreadable lease (treated as free)"}
    age = time.time() - float(body.get("taken_ts") or 0)
    if age > float(body.get("ttl_s") or LANE_TTL_S.get(lane, 1800)):
        return {"lane": lane, "held": False, "expired": True, **body}
    return {"lane": lane, "held": True, "age_s": round(age, 1), **body}


def headroom(lane: str) -> Dict[str, Any]:
    """Can this lane start right now, and if not, why (a deferral, not a failure)."""
    if lane == "gpu":
        free = vram_free_mb()
        ram = ram_free_mb()
        if free is None:
            return {"ok": False, "reason": "vram_unknown",
                    "detail": "cannot prove headroom; a render must not guess"}
        if free < GPU_MIN_FREE_MB:
            return {"ok": False, "reason": "vram_below_floor", "free_mb": free,
                    "floor_mb": GPU_MIN_FREE_MB}
        if ram is not None and ram < RAM_MIN_FREE_MB:
            return {"ok": False, "reason": "ram_below_floor", "free_mb": ram,
                    "floor_mb": RAM_MIN_FREE_MB}
        return {"ok": True, "vram_free_mb": free, "ram_free_mb": ram}
    return {"ok": True}


def acquire(lane: str, *, cycle: int, ttl_s: Optional[int] = None) -> Dict[str, Any]:
    if lane not in LANE_TTL_S:
        raise ValueError(f"unknown lane {lane!r}")
    LANES.mkdir(parents=True, exist_ok=True)
    current = status(lane)
    if current.get("held"):
        return {"ok": False, "reason": "lane_held", "holder": current}
    room = headroom(lane)
    if not room.get("ok"):
        return {"ok": False, "reason": room["reason"], "detail": room}
    body = {"lane": lane, "holder_cycle": cycle, "taken_at": _now(),
            "taken_ts": time.time(), "ttl_s": int(ttl_s or LANE_TTL_S[lane]), "headroom": room}
    path = _path(lane)
    try:
        fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        # Race: someone took it between status() and here. Expire-and-retry once.
        existing = status(lane)
        if existing.get("held"):
            return {"ok": False, "reason": "lane_held", "holder": existing}
        try:
            path.unlink()
        except OSError:
            pass
        try:
            fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            return {"ok": False, "reason": "lane_held", "holder": status(lane)}
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(json.dumps(body, indent=2))
    return {"ok": True, **body}


def release(lane: str, *, reason: str = "") -> Dict[str, Any]:
    path = _path(lane)
    if not path.is_file():
        return {"ok": True, "lane": lane, "note": "already free"}
    body = {}
    try:
        body = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        pass
    try:
        path.unlink()
    except OSError as exc:
        return {"ok": False, "lane": lane, "error": str(exc)}
    return {"ok": True, "lane": lane, "released": body.get("holder_cycle"), "reason": reason}


def all_status() -> Dict[str, Any]:
    return {lane: status(lane) for lane in ("gpu", "cpu", "browser")}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Lane leases.")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    p_acq = sub.add_parser("acquire")
    p_acq.add_argument("lane", choices=("gpu", "cpu", "browser"))
    p_acq.add_argument("--cycle", type=int, required=True)
    p_acq.add_argument("--ttl", type=int, default=0)
    p_rel = sub.add_parser("release")
    p_rel.add_argument("lane", choices=("gpu", "cpu", "browser"))
    p_rel.add_argument("--reason", default="")
    ns = parser.parse_args(argv)

    if ns.cmd == "status":
        print(json.dumps({"lanes": all_status(),
                          "headroom": {"gpu": headroom("gpu")}}, indent=2))
        return 0
    if ns.cmd == "acquire":
        out = acquire(ns.lane, cycle=ns.cycle, ttl_s=ns.ttl or None)
        print(json.dumps(out, indent=2))
        return 0 if out.get("ok") else 1
    if ns.cmd == "release":
        out = release(ns.lane, reason=ns.reason)
        print(json.dumps(out, indent=2))
        return 0 if out.get("ok") else 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
