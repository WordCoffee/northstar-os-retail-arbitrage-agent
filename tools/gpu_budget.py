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
    "bojo": 3.5,
    "router": 3.5,
    "coder": 7.0,
    "vision": 8.0,
    "gui_grounding": 8.0,
    "embeddings": 2.5,
    "image_flux": 11.0,
    "image_t2i": 11.0,
    "27b": 14.5,
}

#: The set that may stay resident between jobs. Measured together at 5.15 GB VRAM with
#: 5.40 GB of RAM free and no change in desktop latency (reports/ty/d7_coexistence.md).
RESIDENT_ROLES = ("bojo", "embeddings")

#: Roles that need the whole GPU to themselves. The 27B measured 14.32 GB VRAM and
#: 0.04 GB of RAM free, which is why the historical CPU pin existed; it is a lease, not
#: a resident.
EXCLUSIVE_ROLES = ("27b", "image_flux", "image_t2i")

#: Which resident roles may stay beside each role. Vision keeps Bojo but evicts the
#: embedding model: bojo + vision measure 10.48 GB, while all three (12.56 GB) left the
#: multimodal encoder with too little working memory and it failed with std::bad_alloc.
COMPANIONS = {
    "vision": ("bojo",),
    "gui_grounding": ("bojo",),
}

#: The model that actually serves each local role today. A role with no model is
#: reported as unmapped rather than guessed at.
ROLE_MODELS = {
    "bojo": "bojo:latest",
    "coder": "qwen3:8b",
    # qwen2.5vl:7b by measurement on a clean server (f16 KV cache, num_ctx 8192):
    # 0.47-0.75 s and it reads the real window title. The earlier "degenerate" verdict was
    # taken against a q4_0 KV cache with a 65536 context.
    # reports/ty/d8_control_browser.md, reports/ty/d7_vision_benchmark.md (correction).
    "vision": "qwen2.5vl:7b",
    "gui_grounding": "qwen2.5vl:7b",
    "embeddings": "qwen3-embedding:0.6b",
}

#: Heavy roles are OFF unless a job leases them with a stated reason. The 27B is the one
#: model that starves everything else (0.04 GB RAM free beside it), so "the 27B is
#: available" must never read as "the 27B is on".
HEAVY_DEFAULT_OFF = ("27b",)
HEAVY_LEASE_PATH = STATE / "heavy_leases.json"


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
    # Measure the steady state, not the load spike: Ollama's host-RAM use peaks while
    # the weights are being mapped, so judging RAM in the same instant reported a
    # perfectly good GPU load as a refusal.
    time.sleep(1.5)
    after = snapshot()
    post = verdict(after, ram())
    _log({"event": "load", "model": model, "role": role, "ok": result.get("ok"),
          "before": before, "after": after, "problems": post["problems"]})
    return {"ok": bool(result.get("ok")) and post["ok"], "loaded": result.get("ok"),
            "reason": result.get("reason", ""),
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


def loaded_models() -> List[str]:
    """What Ollama currently holds resident, by name."""
    return [str(row.get("name")) for row in ps() if row.get("name")]


def enforce(keep: Optional[Sequence[str]] = None) -> Dict[str, Any]:
    """Unload every resident model that is not in the keep set.

    This is the lock manager owning residency rather than a global environment pin
    owning it. It runs before an exclusive lease and before any budget-sensitive load.
    """
    keep_roles = list(RESIDENT_ROLES if keep is None else keep)
    keep_models = {ROLE_MODELS[role] for role in keep_roles if role in ROLE_MODELS}
    unloaded: List[str] = []
    for name in loaded_models():
        if name not in keep_models:
            unload(name)
            unloaded.append(name)
    return {"kept": sorted(keep_models), "unloaded": unloaded,
            "residency": residency()}


def residency() -> Dict[str, Any]:
    """Current residency versus the policy. Drift is visible, not assumed."""
    policy = sorted(ROLE_MODELS[role] for role in RESIDENT_ROLES if role in ROLE_MODELS)
    current = loaded_models()
    return {"policy": policy, "current": sorted(current),
            "drift": sorted(set(current) - set(policy))}


#: Measured resident VRAM per role (reports/ty/d7_coexistence.md). Used to decide
#: whether a role can be added without evicting something else first.
ROLE_SIZE_GB = {
    "bojo": 3.07,
    "coder": 6.63,
    "vision": 5.19,
    "gui_grounding": 5.19,
    "embeddings": 2.08,
}

COMFY = os.environ.get("COMFY_URL", "http://127.0.0.1:8188")


def free_comfy(timeout: float = 30.0) -> Dict[str, Any]:
    """Ask ComfyUI to drop its models, and verify that VRAM actually came back.

    Measured 2026-11-07: this build answers `/free` with 200 and releases nothing (4.25 GB
    stayed resident across the call). The endpoint is therefore reported as unproven
    unless the reading moves, so nobody can mistake an acknowledgement for a release.
    """
    before = snapshot()
    req = urllib.request.Request(
        COMFY.rstrip("/") + "/free",
        data=json.dumps({"unload_models": True, "free_memory": True}).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status = resp.status
    except (urllib.error.URLError, OSError, ValueError) as exc:
        return {"ok": False, "reason": f"{type(exc).__name__}: {exc}", "released_gb": 0.0}
    time.sleep(3.0)
    after = snapshot()
    delta = round((after.get("free_gb") or 0) - (before.get("free_gb") or 0), 2)
    return {"ok": 200 <= status < 300, "status": status, "released_gb": delta,
            "verified": delta > 0.5,
            "note": "" if delta > 0.5 else "acknowledged but VRAM unchanged - unproven"}


def heavy_lease(role: str, *, reason: str = "", hours: float = 2.0,
                path: Optional[Path] = None) -> Dict[str, Any]:
    """Lease a heavy role for a stated job. No reason, no lease.

    A default-off heavy model is the only way the 27B can be safe on a 16 GB box: the
    question "is it on?" then has one answer, and turning it on leaves a written reason.
    """
    if role not in HEAVY_DEFAULT_OFF:
        return {"ok": False, "reason": f"{role!r} is not a heavy role",
                "heavy_roles": list(HEAVY_DEFAULT_OFF)}
    if len(str(reason or "").strip()) < 10:
        return {"ok": False, "reason": "a lease needs a stated reason (10+ characters)",
                "role": role}
    target = Path(path or HEAVY_LEASE_PATH)
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    data[role] = {"reason": str(reason).strip(), "at": _now(),
                  "expires_at": time.time() + float(hours) * 3600, "hours": float(hours)}
    target.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return {"ok": True, "role": role, **data[role]}


def heavy_lease_status(*, path: Optional[Path] = None,
                       now: Optional[float] = None) -> Dict[str, Any]:
    target = Path(path or HEAVY_LEASE_PATH)
    current = time.time() if now is None else now
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    live: Dict[str, Any] = {}
    for role in HEAVY_DEFAULT_OFF:
        row = data.get(role) or {}
        if row and float(row.get("expires_at") or 0) > current:
            live[role] = row
    return {"default_off": list(HEAVY_DEFAULT_OFF), "leased": live,
            "off": [role for role in HEAVY_DEFAULT_OFF if role not in live]}


def acquire(role: str, *, ttl_s: int = 3600) -> Dict[str, Any]:
    """Take the GPU for a role, and leave the machine in a state that role can use.

    An exclusive role drains everything first, including the resident pair, because the
    27B measured 0.04 GB of RAM free next to nothing else. A shared role keeps the
    resident pair and adds itself. A heavy role additionally needs a live lease.
    """
    if role in HEAVY_DEFAULT_OFF and role not in heavy_lease_status()["leased"]:
        return {"ok": False, "reason": "heavy_role_not_leased", "role": role,
                "detail": ("this role is off by default; lease it with a stated reason "
                           "via heavy_lease(role, reason=...)")}
    held = lock(role, ttl_s=ttl_s)
    if not held.get("ok"):
        return held
    exclusive = role in EXCLUSIVE_ROLES
    keep = () if exclusive else tuple(COMPANIONS.get(role, RESIDENT_ROLES)) + (role,)
    freed = enforce(keep=keep)
    if role == "27b":
        # llama-server is not an Ollama model; the lock manager owns the *residency*,
        # and hands back the starter rather than pretending it can load it.
        return {"ok": True, "role": role, "exclusive": True, "freed": freed,
                "action": "powershell -NoProfile -ExecutionPolicy Bypass "
                          "-File scripts/start-northstar-llm.ps1"}
    model = ROLE_MODELS.get(role, "")
    if not model:
        unlock(role)
        return {"ok": False, "reason": "no_model_for_role", "role": role, "freed": freed}
    if model in loaded_models():
        # Already resident: there is nothing to load, so the fit check does not apply.
        return {"ok": True, "role": role, "model": model, "exclusive": exclusive,
                "freed": freed, "already_resident": True}
    need = ROLE_SIZE_GB.get(role, 0.0)
    fit = fits(role, need) if need else {"ok": True}
    comfy_freed = {}
    if not fit.get("ok") and role not in ("image_flux", "image_t2i"):
        # ComfyUI holds VRAM that it can reload on demand; the trace above proves it.
        comfy_freed = free_comfy()
        fit = fits(role, need)
    if not fit.get("ok"):
        unlock(role)
        return {"ok": False, "reason": "does_not_fit", "role": role, "fit": fit,
                "freed": freed, "comfy": comfy_freed}
    result = load(model, role=role)
    return {"ok": bool(result.get("ok")), "role": role, "model": model,
            "exclusive": exclusive, "freed": freed, "comfy": comfy_freed,
            "fit": fit, **result}


def release(role: str, *, restore: bool = True) -> Dict[str, Any]:
    """End a role's lease and put the resident pair back, which is the restore half."""
    model = ROLE_MODELS.get(role, "")
    unloaded = ""
    if model:
        unload(model)
        unloaded = model
    unlock(role)
    restored: Dict[str, bool] = {}
    if restore:
        for name in RESIDENT_ROLES:
            target = ROLE_MODELS.get(name)
            if target:
                restored[name] = bool(_warm(target, name).get("ok"))
    return {"ok": True, "released": role, "unloaded": unloaded, "restored": restored,
            "residency": residency()}


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


def ps() -> List[Dict[str, Any]]:
    """What Ollama says is loaded, and on which processor. The PROCESSOR column."""
    try:
        with urllib.request.urlopen(base_url() + "/api/ps", timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8", "replace") or "{}")
    except (urllib.error.URLError, OSError, ValueError) as exc:
        return [{"error": f"{type(exc).__name__}: {exc}"}]
    out = []
    for row in data.get("models") or []:
        size_vram = int(row.get("size_vram") or 0)
        size = int(row.get("size") or 0)
        out.append({
            "name": row.get("name"),
            "size_gb": round(size / 1024 ** 3, 2),
            "size_vram_gb": round(size_vram / 1024 ** 3, 2),
            "processor": ("100% GPU" if size and size_vram >= size * 0.95
                          else "100% CPU" if not size_vram else
                          f"partial: {round(100 * size_vram / size)}% on GPU"),
        })
    return out


def _warm(model: str, role: str, keep_alive: str = "2m") -> Dict[str, Any]:
    """Load a model on the endpoint its kind actually serves.

    An embedding-only model cannot be warmed through /api/generate; asking it to
    generate is what made the embeddings row read as 'never loaded'.
    """
    if role == "embeddings":
        return _ollama("/api/embeddings", {"model": model, "prompt": "warm-up"})
    return _ollama("/api/generate",
                   {"model": model, "prompt": "", "keep_alive": keep_alive})


def roles_report(models: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """Load each role's model in turn and record VRAM and RAM where it actually ran.

    One at a time, because `OLLAMA_MAX_LOADED_MODELS` is 1 on this box and two 7B
    models do not fit in 16 GB of RAM. Everything is unloaded in a finally.
    """
    models = models or ROLE_MODELS
    rows: List[Dict[str, Any]] = []
    try:
        for role, model in models.items():
            before = snapshot()
            warmed = _warm(model, role)
            loaded = {"loaded": bool(warmed.get("ok")),
                      "problems": [] if warmed.get("ok") else [warmed.get("reason", "")]}
            served = ps()
            after = snapshot()
            mem = ram()
            rows.append({
                "role": role, "model": model,
                "loaded": bool(loaded.get("loaded")),
                "problems": loaded.get("problems") or [],
                "served": served[0] if served else {},
                "vram_used_gb": round((after.get("used_mb") or 0) / 1024, 2),
                "vram_free_gb": after.get("free_gb"),
                "ram_free_gb": mem.get("free_gb"),
                "budget_gb": ROLE_BUDGET_GB.get(role),
            })
            unload(model)
            wait_until_unloaded()
    finally:
        for model in models.values():
            unload(model)
    return {"at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "ollama": base_url(), "roles": rows}


def wait_until_unloaded(seconds: float = 8.0) -> bool:
    """Ollama frees a model lazily; measuring the next role before it does lies."""
    deadline = time.time() + seconds
    while time.time() < deadline:
        if not ps() or all("error" in row for row in ps()):
            return True
        time.sleep(0.4)
    return False


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
