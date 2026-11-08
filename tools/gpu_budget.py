"""GPU budget manager: use the 5080 fully, not recklessly.

PATCH 1 item 4 in the director work order. The rules this module enforces:

* plan each session to fill **80-90 %** of the 16 GB by choosing the largest
  quantization / context / batch that fits;
* **hard ceiling ~92 %**, with at least **1 GB** free for Windows and the display;
* system RAM is the tighter limit: keep at least **2 GB** free and no swap thrash;
* per-role budgets, idle models unloaded, and `nvidia-smi` checked before and after
  every load;
* "usable" means no OOM, no UI lag, latency inside budget - the caller measures
  latency, this module refuses to claim it.

Everything here is read-or-unload; nothing loads a model except ``load()``, and
``load()`` is always paired with a before/after snapshot.

    python tools/gpu_budget.py --snapshot
    python tools/gpu_budget.py --load qwen2.5vl:7b --role vision
    python tools/gpu_budget.py --unload qwen2.5vl:7b
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "state" / "gpu"
LOCK = STATE / "lock.json"
LOG = STATE / "budget.jsonl"

OLLAMA_ENV = ("TY_OLLAMA_URL", "OLLAMA_HOST")


def base_url() -> str:
    """The Ollama **client** URL, normalised.

    Measured trap: `OLLAMA_HOST` is a bind address on this box (`0.0.0.0`), not a
    URL, so using it raw produced `<urlopen error unknown url type: 0.0.0.0>` and
    every load looked like a refusal. A bind address is normalised to loopback.
    """
    raw = ""
    for name in OLLAMA_ENV:
        value = (os.environ.get(name) or "").strip()
        if value:
            raw = value
            break
    if not raw:
        return "http://127.0.0.1:11434"
    if "://" not in raw:
        raw = "http://" + raw
    import urllib.parse

    parsed = urllib.parse.urlsplit(raw)
    host = parsed.hostname or "127.0.0.1"
    if host in ("0.0.0.0", "::", "[::]", "localhost"):
        host = "127.0.0.1" if host != "localhost" else "127.0.0.1"
    port = parsed.port or 11434
    return f"http://{host}:{port}"

TOTAL_VRAM_GB = 16.0
TARGET_LOW = 0.80
TARGET_HIGH = 0.90
CEILING = 0.92
RESERVE_GB = 1.0
RAM_FLOOR_GB = 2.0

#: Per-role budgets in GB of VRAM. A role is a *job*, not a model: Bojo and the
#: router share the light budget, the vision and GUI models the heavy one. The
#: numbers are ceilings, not targets - the sampler picks the largest quant that
#: fits inside the ceiling.
ROLE_BUDGET_GB = {
    "bojo": 3.0,
    "router": 3.0,
    "coder": 6.0,
    "vision": 7.0,
    "gui_grounding": 7.0,
    "embeddings": 2.0,
    "image_flux": 12.0,
    "image_t2i": 12.0,
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _log(row: Dict[str, Any]) -> None:
    STATE.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"at": _now(), **row}, ensure_ascii=False) + "\n")


def snapshot() -> Dict[str, Any]:
    """One nvidia-smi read: total, used and free MB, plus utilisation."""
    smi = shutil.which("nvidia-smi")
    if not smi:
        return {"ok": False, "reason": "nvidia-smi not found"}
    out = subprocess.run(
        [smi, "--query-gpu=name,memory.total,memory.used,memory.free,utilization.gpu",
         "--format=csv,noheader,nounits"],
        capture_output=True, text=True, timeout=20)
    if out.returncode != 0:
        return {"ok": False, "reason": (out.stderr or "query failed").strip()[:300]}
    parts = [part.strip() for part in (out.stdout or "").strip().split(",")]
    try:
        total, used, free_vram, util = (int(parts[1]), int(parts[2]),
                                        int(parts[3]), int(parts[4]))
    except (IndexError, ValueError):
        return {"ok": False, "reason": f"unparsable nvidia-smi output: {parts!r}"}
    return {"ok": True, "gpu": parts[0], "total_mb": total, "used_mb": used,
            "free_mb": free_vram, "util_pct": util,
            "used_frac": round(used / total, 3) if total else None,
            "free_gb": round(free_vram / 1024, 2)}


def ram() -> Dict[str, Any]:
    try:
        import ctypes

        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                        ("ullTotalPhys", ctypes.c_ulonglong),
                        ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong),
                        ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong),
                        ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]

        stat = MEMORYSTATUSEX()
        stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
        return {"ok": True,
                "free_gb": round(stat.ullAvailPhys / 1024 ** 3, 2),
                "total_gb": round(stat.ullTotalPhys / 1024 ** 3, 2)}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "reason": str(exc)}


def verdict(snap: Optional[Dict[str, Any]] = None,
            mem: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Is the current state inside the budget? A refusal names the reason."""
    snap = snap or snapshot()
    mem = mem or ram()
    problems: List[str] = []
    if not snap.get("ok"):
        problems.append(f"no VRAM reading: {snap.get('reason')}")
    else:
        if snap["used_frac"] > CEILING:
            problems.append(f"VRAM at {snap['used_frac']:.0%} > ceiling {CEILING:.0%}")
        if snap["free_gb"] < RESERVE_GB:
            problems.append(f"{snap['free_gb']} GB VRAM free < {RESERVE_GB} GB reserve")
    if mem.get("ok") and mem["free_gb"] < RAM_FLOOR_GB:
        problems.append(f"{mem['free_gb']} GB RAM free < {RAM_FLOOR_GB} GB floor")
    return {"ok": not problems, "problems": problems, "vram": snap, "ram": mem}


def _ollama(path: str, payload: Dict[str, Any], timeout: float = 120.0) -> Dict[str, Any]:
    req = urllib.request.Request(
        base_url() + path, data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", "replace")
        return {"ok": True, "body": body[-2000:]}
    except (urllib.error.URLError, OSError, ValueError) as exc:
        return {"ok": False, "reason": f"{type(exc).__name__}: {exc}"}


def unload(model: str) -> Dict[str, Any]:
    """Free the model's VRAM now (keep_alive 0). The model stays on disk."""
    result = _ollama("/api/generate", {"model": model, "keep_alive": 0})
    _log({"event": "unload", "model": model, "ok": result.get("ok")})
    return result


def load(model: str, *, role: str = "", keep_alive: str = "10m") -> Dict[str, Any]:
    """Load a model only if the budget allows it, and prove it with snapshots."""
    before = snapshot()
    gate = verdict(before)
    if not gate["ok"]:
        _log({"event": "load_refused", "model": model, "role": role,
              "problems": gate["problems"]})
        return {"ok": False, "reason": "budget", "problems": gate["problems"],
                "before": before}
    result = _ollama("/api/generate",
                     {"model": model, "prompt": "", "keep_alive": keep_alive})
    after = snapshot()
    post = verdict(after)
    _log({"event": "load", "model": model, "role": role, "ok": result.get("ok"),
          "before": before, "after": after, "problems": post["problems"]})
    return {"ok": bool(result.get("ok")) and post["ok"], "loaded": result.get("ok"),
            "problems": post["problems"], "before": before, "after": after}


def fits(role: str, model_gb: float) -> Dict[str, Any]:
    """Would this role's model fit inside its budget and the ceiling?"""
    budget = ROLE_BUDGET_GB.get(role)
    snap = snapshot()
    if budget is None:
        return {"ok": False, "reason": f"unknown role {role!r}"}
    if not snap.get("ok"):
        return {"ok": False, "reason": snap.get("reason")}
    available = min(budget, snap["free_gb"] - RESERVE_GB)
    return {"ok": model_gb <= available, "role": role, "model_gb": model_gb,
            "budget_gb": budget, "free_gb": snap["free_gb"],
            "available_gb": round(available, 2)}


def lock(role: str, ttl_s: int = 3600) -> Dict[str, Any]:
    """One heavy local job at a time. A second claim is refused, not queued."""
    state = {}
    try:
        state = json.loads(LOCK.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        state = {}
    if state and time.time() - float(state.get("ts") or 0) < ttl_s:
        if int(state.get("pid") or 0) and state.get("pid") != os.getpid():
            return {"ok": False, "reason": "gpu_locked", "held_by": state}
    STATE.mkdir(parents=True, exist_ok=True)
    LOCK.write_text(json.dumps({"role": role, "pid": os.getpid(), "ts": time.time(),
                                "at": _now()}, indent=2) + "\n", encoding="utf-8")
    return {"ok": True, "role": role}


def unlock(role: str = "") -> Dict[str, Any]:
    try:
        LOCK.unlink()
    except OSError:
        pass
    return {"ok": True, "released": role or "any"}


def headroom(models: Optional[List[str]] = None) -> Dict[str, Any]:
    """Load every model in the list together, record VRAM/RAM, then always unload.

    D1 asks for the number, not a claim: the vision model and Bojo must fit at the
    same time. The unload runs in ``finally`` so a refusal or an exception cannot
    leave the GPU occupied.
    """
    models = models or ["qwen2.5vl:7b", "bojo:latest"]
    steps: List[Dict[str, Any]] = [{"start": snapshot(), "ram": ram()}]
    try:
        for model in models:
            steps.append({"load": model, "result": load(model, role="headroom")})
            steps.append({"after": model, "vram": snapshot(), "ram": ram()})
    finally:
        for model in models:
            steps.append({"unload": model, "result": unload(model)})
    end = {"vram": snapshot(), "ram": ram()}
    loads = [step["result"] for step in steps if "load" in step]
    return {"ok": all(bool(step.get("loaded")) for step in loads),
            "models": models, "steps": steps, "final": end}


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="GPU budget manager")
    parser.add_argument("--snapshot", action="store_true")
    parser.add_argument("--headroom", action="store_true",
                        help="load the vision model and Bojo together, measure, unload")
    parser.add_argument("--models", default="",
                        help="comma-separated models for --headroom")
    parser.add_argument("--load")
    parser.add_argument("--unload")
    parser.add_argument("--role", default="")
    args = parser.parse_args(argv)

    if args.headroom:
        chosen = [m.strip() for m in args.models.split(",") if m.strip()] or None
        print(json.dumps(headroom(chosen), indent=2))
        return 0
    if args.unload:
        print(json.dumps(unload(args.unload), indent=2))
        return 0
    if args.load:
        print(json.dumps(load(args.load, role=args.role), indent=2))
        return 0
    print(json.dumps({"verdict": verdict(), "budgets": ROLE_BUDGET_GB,
                      "ceilings": {"target": [TARGET_LOW, TARGET_HIGH],
                                   "ceiling": CEILING, "reserve_gb": RESERVE_GB,
                                   "ram_floor_gb": RAM_FLOOR_GB}}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
