"""V3 shell context — Simple | Advanced gate + focus modes + hardware telemetry.

The V3 shell (2026-10-18) makes the chat-first Simple view the product's main
surface and treats the room-based Advanced view as a dev-level surface offered
on certain subscription tiers. This router is the single source of truth for:

  • the caller's UI capabilities (advanced_view, autothink_workspace) —
    resolved from the canonical plan catalog (`shared/subscription-plans.json`
    `ui_gates`), the legacy users table, and the Foundation org entitlements;
  • the focus modes the Simple shell may present (server-owned metadata; the
    UI never invents a focus or a tool list);
  • real local hardware telemetry (nvidia-smi + RAM) for the shell's status
    chip. No fabricated numbers: unavailable hardware reports ok=false.

Honesty boundaries:
  • ui_gates are presentation/routing only. They never arm a live/paid action;
    `gates_always_off=true` continues to govern every live gate.
  • The dev-header identity path (X-User-Id / X-Role) is the same local shim
    the SPA already sends under LOCAL_DEV; it can surface the Advanced UI but
    cannot unlock any live action (those stay per-action operator-gated).
  • `_app_foundation_state` reuse avoids opening a second DB connection; a
    resolution failure degrades to the honest UNKNOWN (no capabilities beyond
    the plan catalog), never to a silent grant.
"""

from __future__ import annotations

import ctypes
import os
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
_REPO = os.path.dirname(_HERE)
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

import auth  # noqa: E402
import chat_tools  # noqa: E402
from shell_focus import FOCUS_MODES, focus_by_id, tools_for_focus  # noqa: E402,F401

router = APIRouter(prefix="/api/shell", tags=["shell"])

CONTRACT = "shell/v1"

ADMIN_ROLES = ("admin", "internal_platform_admin")


# ── Identity resolution ─────────────────────────────────────────────────────

async def _identity(request: Request) -> Dict[str, str]:
    """session (strict) → dev-header shim (LOCAL_DEV) → anonymous."""
    try:
        from auth_deps import require_session
        user = await require_session(request)
        return {
            "user_id": str(user.get("id") or ""),
            "org_id": str(user.get("tenant_id") or ""),
            "role": str(user.get("role") or ""),
            "source": "session",
        }
    except HTTPException:
        pass
    except Exception:  # noqa: BLE001 - identity must degrade, never 500 the shell
        pass
    dev_uid = request.headers.get("X-User-Id")
    if dev_uid:
        return {
            "user_id": dev_uid,
            "org_id": request.headers.get("X-Org-Id") or "",
            "role": request.headers.get("X-Role") or "member",
            "source": "dev-header",
        }
    return {"user_id": "", "org_id": "", "role": "member", "source": "anonymous"}


def _org_entitlements(org_id: str) -> Dict[str, Any]:
    """Foundation org entitlements (hosted orgs). UNKNOWN on any failure."""
    if not org_id:
        return {}
    try:
        from auth_deps import _app_foundation_state
        state = _app_foundation_state()
        if not state:
            return {}
        ent = state.entitlements.entitlements_for_org(org_id)
        return {
            "tier": ent.get("tier"),
            "advanced_reports": bool(ent.get("advanced_reports")),
            "export_enabled": bool(ent.get("export_enabled")),
        }
    except Exception:  # noqa: BLE001
        return {}


def resolve_capabilities(identity: Dict[str, str]) -> Dict[str, Any]:
    """Pure resolution of UI capabilities for an identity (unit-testable)."""
    role = identity.get("role") or ""
    is_admin = role in ADMIN_ROLES
    plan = "foundation"
    ui_gates: List[str] = []
    live_gates: List[str] = []
    plan_name = ""
    user_id = identity.get("user_id") or ""
    if user_id:
        try:
            row = auth.get_user(user_id) or {}
            if row.get("plan"):
                plan = row["plan"]
            info = auth.PLAN_ENTITLEMENTS.get(plan) or {}
            ui_gates = list(info.get("ui_gates", []))
            live_gates = list(info.get("gates", []))
            plan_name = info.get("name", "")
        except Exception:  # noqa: BLE001
            pass
    org = _org_entitlements(identity.get("org_id") or "")
    # Hosted beta orgs carry materialized `advanced_reports` (pro/team cohorts);
    # treat that existing entitlement as advanced-view eligible until the org is
    # on a plan-ladder tier that carries the explicit `advanced_view` ui gate.
    advanced = bool(is_admin or "advanced_view" in ui_gates
                    or org.get("advanced_reports"))
    autothink = bool(is_admin or "autothink_workspace" in live_gates
                     or org.get("tier") in ("pro", "team"))
    return {
        "plan": plan,
        "plan_name": plan_name,
        "ui_gates": ui_gates,
        "capabilities": {
            "advanced_view": advanced,
            "autothink_workspace": autothink,
        },
        "org": org or None,
        "is_admin": is_admin,
    }


@router.get("/context")
async def shell_context(request: Request):
    identity = await _identity(request)
    resolved = resolve_capabilities(identity)
    focuses = []
    for f in FOCUS_MODES:
        locked = bool(f.get("requires")) and not resolved["capabilities"].get(f["requires"])
        focuses.append({**f, "locked": locked})
    return {
        "contract": CONTRACT,
        "default_mode": "simple",
        "identity": {
            "source": identity["source"],
            "role": identity["role"],
            "plan": resolved["plan"],
            "plan_name": resolved["plan_name"],
        },
        "capabilities": resolved["capabilities"],
        "org": resolved["org"],
        "focuses": focuses,
    }


# ── Hardware telemetry ──────────────────────────────────────────────────────

_GPU_FIELDS = "name,memory.total,memory.used,utilization.gpu,temperature.gpu"
_HW_CACHE: Dict[str, Any] = {"at": 0.0, "payload": None}
_HW_LOCK = threading.Lock()
HW_TTL_SECONDS = 3.0
# V3 guard: 1.8 GB stays free for the WebGL canvas + compositor; local model
# weights target ≤ 14.2 GB on the 16 GB card.
RESERVE_TARGET_MB = 1800


def _default_gpu_runner() -> subprocess.CompletedProcess:
    kwargs: Dict[str, Any] = {
        "capture_output": True, "text": True, "timeout": 4,
    }
    if os.name == "nt":  # never flash a console window from the server
        kwargs["creationflags"] = 0x08000000  # CREATE_NO_WINDOW
    return subprocess.run(
        ["nvidia-smi", f"--query-gpu={_GPU_FIELDS}", "--format=csv,noheader,nounits"],
        **kwargs)


def parse_gpu_csv(stdout: str) -> List[Dict[str, Any]]:
    """Parse `nvidia-smi --query-gpu=... --format=csv,noheader,nounits` output."""
    gpus: List[Dict[str, Any]] = []
    for line in (stdout or "").splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 5:
            continue

        def _num(raw: str):
            try:
                return float(raw)
            except ValueError:
                return None  # nvidia-smi prints [N/A] on some drivers

        total = _num(parts[1])
        used = _num(parts[2])
        gpus.append({
            "name": parts[0],
            "vram_total_mb": int(total) if total is not None else None,
            "vram_used_mb": int(used) if used is not None else None,
            "util_pct": _num(parts[3]),
            "temp_c": _num(parts[4]),
        })
    return gpus


def read_ram() -> Dict[str, Any]:
    """Total/used RAM in MB. Windows: GlobalMemoryStatusEx; else /proc/meminfo."""
    try:
        if os.name == "nt":
            class _MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]
            stat = _MEMORYSTATUSEX()
            stat.dwLength = ctypes.sizeof(_MEMORYSTATUSEX)
            if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
                return {"ok": False, "reason": "GlobalMemoryStatusEx failed"}
            total_mb = stat.ullTotalPhys // (1024 * 1024)
            avail_mb = stat.ullAvailPhys // (1024 * 1024)
            return {"ok": True, "total_mb": int(total_mb),
                    "used_mb": int(total_mb - avail_mb),
                    "percent": int(stat.dwMemoryLoad)}
        with open("/proc/meminfo", "r", encoding="utf-8") as fh:
            rows = {}
            for line in fh:
                k, _, v = line.partition(":")
                rows[k.strip()] = v.strip()
        total_kb = float((rows.get("MemTotal") or "0 kB").split()[0])
        avail_kb = float((rows.get("MemAvailable") or "0 kB").split()[0])
        total_mb = int(total_kb / 1024)
        avail_mb = int(avail_kb / 1024)
        used_mb = max(0, total_mb - avail_mb)
        return {"ok": True, "total_mb": total_mb, "used_mb": used_mb,
                "percent": int(round(100 * used_mb / total_mb)) if total_mb else None}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "reason": f"ram read failed: {exc}"}


def _governor(gpu: Dict[str, Any]) -> Dict[str, Any]:
    """VRAM-reserve governor (14.2 GB model / 1.8 GB canvas rule, RTX 5080 16 GB).

    recommend DPR for the WebGL canvas: full (1.5) when the 1.8 GB reserve is
    intact, lowered (1.0) when it is not. UNKNOWN when there are no readings —
    the governor never invents a decision on fabricated numbers."""
    gov: Dict[str, Any] = {
        "reserve_target_mb": RESERVE_TARGET_MB,
        "reserve_ok": None,
        "free_mb": None,
        "recommended_dpr": None,
    }
    if gpu.get("ok") and gpu.get("gpus"):
        g0 = gpu["gpus"][0]
        total = g0.get("vram_total_mb")
        used = g0.get("vram_used_mb")
        if total and used is not None:
            free = int(total - used)
            gov["free_mb"] = free
            gov["reserve_ok"] = free >= RESERVE_TARGET_MB
            gov["recommended_dpr"] = 1.5 if free >= RESERVE_TARGET_MB else 1.0
    return gov


def collect_hardware(gpu_runner=None) -> Dict[str, Any]:
    runner = gpu_runner or _default_gpu_runner
    gpu: Dict[str, Any]
    try:
        proc = runner()
        if getattr(proc, "returncode", 1) == 0:
            gpus = parse_gpu_csv(getattr(proc, "stdout", "") or "")
            gpu = {"ok": bool(gpus), "gpus": gpus}
            if not gpus:
                gpu["reason"] = "nvidia-smi returned no GPUs"
        else:
            gpu = {"ok": False, "gpus": [],
                   "reason": (getattr(proc, "stderr", "") or "nvidia-smi failed").strip()[:200]}
    except FileNotFoundError:
        gpu = {"ok": False, "gpus": [], "reason": "nvidia-smi not on PATH"}
    except subprocess.TimeoutExpired:
        gpu = {"ok": False, "gpus": [], "reason": "nvidia-smi timed out"}
    except Exception as exc:  # noqa: BLE001
        gpu = {"ok": False, "gpus": [], "reason": f"gpu read failed: {exc}"}
    return {
        "sampled_at": datetime.now(timezone.utc).isoformat(),
        "gpu": gpu,
        "ram": read_ram(),
        "governor": _governor(gpu),
    }


_HW_DAEMON: Optional[threading.Thread] = None
_HW_DAEMON_LOCK = threading.Lock()


def _hardware_daemon_loop(collect=None, sleep=None) -> None:
    collect = collect or collect_hardware
    sleep = sleep or time.sleep
    while True:
        try:
            payload = collect()
            with _HW_LOCK:
                _HW_CACHE["at"] = time.monotonic()
                _HW_CACHE["payload"] = payload
        except Exception:  # noqa: BLE001 - the daemon degrades, never crashes the app
            pass
        sleep(HW_TTL_SECONDS)


def start_hardware_daemon() -> bool:
    """Start the hardware-telemetry daemon (idempotent).

    A daemon thread keeps the 3 s cache warm so the shell chip + monitor modal
    always read fresh real values without a request paying the nvidia-smi cost.
    Returns True when this call actually started the thread."""
    global _HW_DAEMON
    with _HW_DAEMON_LOCK:
        if _HW_DAEMON is not None and _HW_DAEMON.is_alive():
            return False
        thread = threading.Thread(
            target=_hardware_daemon_loop, daemon=True, name="hw-telemetry")
        thread.start()
        _HW_DAEMON = thread
        return True


@router.get("/hardware")
def hardware():
    now = time.monotonic()
    with _HW_LOCK:
        cached = _HW_CACHE["payload"]
        if cached is not None and (now - _HW_CACHE["at"]) < HW_TTL_SECONDS:
            return cached
    payload = collect_hardware()
    with _HW_LOCK:
        _HW_CACHE["at"] = now
        _HW_CACHE["payload"] = payload
    return payload
