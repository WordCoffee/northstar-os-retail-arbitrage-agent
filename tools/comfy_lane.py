"""A render lane owns ComfyUI for its lifetime: start fresh, work, stop, prove it stopped.

Folded fix (WORK ORDER 3 item 3): *ComfyUI starts fresh per render lane and stops after;
stop trusting `free_comfy()`.* The reason is measured: this build answers `/free` with 200
and releases nothing, so an acknowledgement is not a release. A process that exits is.

    from comfy_lane import lane
    result = lane(lambda: render(prompt), vram=free_gb)

    python tools/comfy_lane.py --status
    python tools/comfy_lane.py --stop
"""
from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
COMFY_HOME = Path(os.environ.get("COMFY_HOME", r"C:\Users\T2Hol\ComfyUI"))
COMFY_URL = os.environ.get("COMFY_URL", "http://127.0.0.1:8188")
EVIDENCE = ROOT / "state" / "gpu" / "comfy_lanes.jsonl"

#: The models that may be resident when a heavy render starts. They are measured,
#: unloaded before the lane takes the GPU, and reloaded from `finally` afterwards.
OLLAMA_WATCHLIST = ("bojo:latest", "qwen3-embedding:0.6b")
OLLAMA_URL_DEFAULT = "http://127.0.0.1:11434"
RESERVE_GB = 1.0


def reachable(url: str = COMFY_URL, *, timeout: float = 2.0) -> bool:
    try:
        with urllib.request.urlopen(url.rstrip("/") + "/system_stats", timeout=timeout):
            return True
    except Exception:  # noqa: BLE001 - unreachable is the normal state between lanes
        return False


def port_open(host: str = "127.0.0.1", port: int = 8188, *, timeout: float = 1.0) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(timeout)
        return sock.connect_ex((host, port)) == 0


def _log(row: Dict[str, Any]) -> None:
    """Append a row to the lane journal. ``NS_LANE_JOURNAL`` redirects it (tests)."""
    target = Path(os.environ.get("NS_LANE_JOURNAL") or EVIDENCE)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), **row}) + "\n")


# ---------------------------------------------------------------- measurements
def gpu_snapshot(timeout: float = 20.0) -> Dict[str, Any]:
    """One nvidia-smi read, recorded before and after every lane.

    This is the measurement the budget is judged against; a static table cannot
    know that another lane is holding 7 GB.
    """
    import shutil

    smi = shutil.which("nvidia-smi")
    if not smi:
        return {"ok": False, "reason": "nvidia-smi not found"}
    try:
        out = subprocess.run(
            [smi, "--query-gpu=memory.total,memory.used,memory.free,utilization.gpu",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.SubprocessError) as exc:
        return {"ok": False, "reason": f"{type(exc).__name__}: {exc}"}
    if out.returncode != 0:
        return {"ok": False, "reason": (out.stderr or "query failed").strip()[:300]}
    parts = [part.strip() for part in (out.stdout or "").strip().split(",")]
    try:
        total, used, free_mb, util = (int(parts[0]), int(parts[1]),
                                      int(parts[2]), int(parts[3]))
    except (IndexError, ValueError):
        return {"ok": False, "reason": f"unparsable nvidia-smi output: {parts!r}"}
    return {"ok": True, "total_mb": total, "used_mb": used, "free_mb": free_mb,
            "util_pct": util, "free_gb": round(free_mb / 1024, 2),
            "used_gb": round(used / 1024, 2)}


def ollama_url() -> str:
    """The Ollama client URL. A bind address (0.0.0.0) is normalised to loopback."""
    raw = (os.environ.get("TY_OLLAMA_URL") or os.environ.get("OLLAMA_HOST") or "").strip()
    if not raw:
        return OLLAMA_URL_DEFAULT
    if "://" not in raw:
        raw = "http://" + raw
    parsed = urllib.parse.urlsplit(raw)
    host = parsed.hostname or "127.0.0.1"
    if host in ("0.0.0.0", "::", "[::]", "localhost"):
        host = "127.0.0.1"
    return f"http://{host}:{parsed.port or 11434}"


def ollama_ps(timeout: float = 10.0) -> Dict[str, Any]:
    """What Ollama holds resident right now, as a recorded before/after snapshot."""
    try:
        with urllib.request.urlopen(ollama_url() + "/api/ps", timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8", "replace") or "{}")
    except (urllib.error.URLError, OSError, ValueError) as exc:
        return {"ok": False, "models": [], "resident": [],
                "reason": f"{type(exc).__name__}: {exc}"}
    models: List[Dict[str, Any]] = []
    for row in payload.get("models") or []:
        size_vram = int(row.get("size_vram") or 0)
        models.append({"name": row.get("name"),
                       "size_vram_gb": round(size_vram / 1024 ** 3, 2)})
    return {"ok": True, "models": models,
            "resident": [m["name"] for m in models if m.get("name")]}


def _post_json(url: str, payload: Dict[str, Any], timeout: float = 180.0) -> Dict[str, Any]:
    request = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", "replace")
        return {"ok": True, "body": body[-500:]}
    except (urllib.error.URLError, OSError, ValueError) as exc:
        return {"ok": False, "reason": f"{type(exc).__name__}: {exc}"}


def record_render(fields: Dict[str, Any]) -> None:
    """Append one authoritative row per rendered brief to the lane journal.

    It nests the lane row (all snapshots, unload/reload, budget) beside the
    upscaler the pipeline actually used, so one JSON line answers "what happened
    for this render".
    """
    _log({"event": "render", **fields})


def _wait_residency(tag: str, present: bool, timeout: float = 20.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if (tag in (ollama_ps().get("resident") or [])) is present:
            return True
        time.sleep(0.5)
    return False


def unload_model(tag: str, timeout: float = 20.0) -> Dict[str, Any]:
    """Free one resident model now. Verified by /api/ps no longer listing it."""
    result = _post_json(ollama_url() + "/api/generate",
                        {"model": tag, "keep_alive": 0})
    verified = _wait_residency(tag, present=False, timeout=timeout) if result.get("ok") else False
    return {"tag": tag, "api_ok": bool(result.get("ok")), "verified": verified,
            "reason": result.get("reason", "")}


def reload_model(tag: str, *, keep_alive: str = "10m", timeout: float = 120.0) -> Dict[str, Any]:
    """Put a model that was resident before the lane back, and verify it is listed."""
    if "embedding" in tag.lower():
        path, payload = "/api/embeddings", {"model": tag, "prompt": "warm-up",
                                           "keep_alive": keep_alive}
    else:
        path, payload = "/api/generate", {"model": tag, "prompt": "",
                                          "keep_alive": keep_alive}
    result = _post_json(ollama_url() + path, payload, timeout=timeout)
    verified = _wait_residency(tag, present=True, timeout=min(timeout, 60.0)) if result.get("ok") else False
    return {"tag": tag, "api_ok": bool(result.get("ok")), "verified": verified,
            "reason": result.get("reason", "")}


def budget_verdict(free_gb: Optional[float], needed_gb: Optional[float],
                   reserve_gb: float = RESERVE_GB) -> Dict[str, Any]:
    """Would the model fit the *measured* free VRAM, keeping the reserve?

    A missing measurement or a missing model need is a refusal when the caller
    states a need: an unmeasured budget is not a passed budget.
    """
    reserve = float(reserve_gb)
    if free_gb is None:
        return {"ok": False, "checked": True, "free_gb": None, "needed_gb": needed_gb,
                "reserve_gb": reserve,
                "reason": "no VRAM measurement; refusing to guess the headroom"}
    if needed_gb is None:
        return {"ok": True, "checked": False, "free_gb": float(free_gb),
                "needed_gb": None, "reserve_gb": reserve,
                "reason": "no model need stated; budget not claimed"}
    free, need = float(free_gb), float(needed_gb)
    headroom = round(free - need, 2)
    ok = headroom >= reserve
    return {"ok": ok, "checked": True, "free_gb": free, "needed_gb": need,
            "reserve_gb": reserve, "headroom_gb": headroom,
            "reason": (f"fits: {free} GB free - {need} GB needed = {headroom} GB "
                       f">= {reserve} GB reserve" if ok else
                       f"refused: {free} GB free - {need} GB needed = {headroom} GB "
                       f"< {reserve} GB reserve")}


def _start() -> Dict[str, Any]:
    """Start ComfyUI detached, with a cold cache, and return the exact pid it got."""
    python = COMFY_HOME / "venv" / "Scripts" / "python.exe"
    main = COMFY_HOME / "main.py"
    if not python.exists() or not main.exists():
        return {"ok": False, "reason": f"ComfyUI not found under {COMFY_HOME}"}
    creation = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    try:
        proc = subprocess.Popen(
            [str(python), str(main), "--listen", "127.0.0.1", "--port", "8188",
             "--cache-none"],
            cwd=str(COMFY_HOME), creationflags=creation,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError as exc:
        return {"ok": False, "reason": f"{type(exc).__name__}: {exc}"}
    return {"ok": True, "pid": proc.pid, "process": proc}


def _wait_ready(*, timeout: float = 180.0) -> Dict[str, Any]:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if reachable():
            return {"ok": True, "seconds": round(timeout - (deadline - time.time()), 1)}
        time.sleep(1.0)
    return {"ok": False, "reason": f"ComfyUI did not answer within {timeout}s"}


def _stop(pid: Optional[int], *, timeout: float = 30.0) -> Dict[str, Any]:
    """Terminate the lane's process and wait for the port to close. Verification, not hope."""
    if not pid:
        return {"ok": False, "reason": "no pid to stop"}
    try:
        subprocess.run(["taskkill", "/PID", str(int(pid)), "/T", "/F"],
                       capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.SubprocessError) as exc:
        return {"ok": False, "reason": f"{type(exc).__name__}: {exc}", "pid": pid}
    deadline = time.time() + timeout
    while time.time() < deadline:
        if not port_open():
            return {"ok": True, "pid": pid, "stopped": True,
                    "seconds": round(timeout - (deadline - time.time()), 1)}
        time.sleep(0.5)
    return {"ok": False, "pid": pid, "reason": "port 8188 still open after taskkill"}


def lane(work: Callable[[], Any], *, start: Callable[[], Dict[str, Any]] = _start,
         ready: Callable[[], Dict[str, Any]] = _wait_ready,
         stop: Callable[[Optional[int]], Dict[str, Any]] = _stop,
         vram: Optional[Callable[[], float]] = None,
         snapshot: Optional[Callable[[], Dict[str, Any]]] = None,
         ps: Optional[Callable[[], Dict[str, Any]]] = None,
         unload: Optional[Callable[[str], Dict[str, Any]]] = None,
         reload: Optional[Callable[[str], Dict[str, Any]]] = None,
         needed_gb: Optional[float] = None,
         watchlist: Optional[List[str]] = None,
         reserve_gb: Optional[float] = None,
         role: str = "lane",
         timeout: float = 180.0) -> Dict[str, Any]:
    """Start, work, stop. The stop and the reload happen in `finally`, once each.

    The lane owns the GPU, so it proves what it found and what it left:

    * a `nvidia-smi` snapshot before anything starts, again after the residents
      are unloaded (the number the budget is judged on), after the work, and
      after the lane stopped;
    * `ollama ps` before, after unload, after reload;
    * every resident model on the watchlist is unloaded (keep_alive 0, verified
      by `/api/ps`), then reloaded after ComfyUI has stopped and verified again;
    * the model is only loaded when `measured_free_gb - needed_gb >= reserve`.

    One JSON row per render is appended to ``state/gpu/comfy_lanes.jsonl``.
    """
    if reachable():
        _log({"event": "refused", "reason": "already_running"})
        return {"ok": False, "refused": True,
                "reason": ("ComfyUI is already running; a lane starts its own instance so "
                           "it can prove it stopped the one it used")}

    snapshot = snapshot or gpu_snapshot
    ps = ps or ollama_ps
    unload = unload or unload_model
    reload = reload or reload_model
    watchlist = list(OLLAMA_WATCHLIST if watchlist is None else watchlist)
    if reserve_gb is None:
        try:
            import gpu_budget  # noqa: PLC0415 - one source for the reserve

            reserve = float(gpu_budget.RESERVE_GB)
        except Exception:  # noqa: BLE001 - the documented default is the fallback
            reserve = RESERVE_GB
    else:
        reserve = float(reserve_gb)

    started_at = time.time()
    row: Dict[str, Any] = {"event": "lane", "role": role,
                           "needed_gb": needed_gb, "reserve_gb": reserve,
                           "watchlist": watchlist, "stopped": None}
    outcome: Dict[str, Any] = {"ok": False}
    pid: Optional[int] = None
    reload_needed: List[str] = []
    try:
        row["gpu_before"] = snapshot()
        row["ollama_ps_before"] = ps()
        residents = list((row["ollama_ps_before"] or {}).get("resident") or [])
        row["resident_before"] = residents
        reload_needed = [tag for tag in watchlist if tag in residents]

        unloaded: List[Dict[str, Any]] = []
        for tag in reload_needed:
            unloaded.append(unload(tag))
        row["unloaded"] = unloaded
        after_unload = ps()
        row["ollama_ps_after_unload"] = after_unload
        still_resident = [tag for tag in reload_needed
                          if tag in (after_unload.get("resident") or [])]
        row["unload_verified"] = {item.get("tag"): bool(item.get("verified"))
                                  for item in unloaded}
        row["gpu_ready"] = row["gpu_before"] if not unloaded else snapshot()
        if unloaded:
            # An unloaded model releases VRAM asynchronously; measuring immediately reads the
            # old number and refuses a render that would fit. Two short samples, keep the best.
            import time as _time  # noqa: PLC0415

            best = row["gpu_ready"]
            for _ in range(3):
                _time.sleep(2.0)
                current = snapshot()
                if (current.get("free_gb") or 0) > (best.get("free_gb") or 0):
                    best = current
            row["gpu_ready"] = best
            row["gpu_settle_samples"] = 3
        if still_resident:
            outcome = {"ok": False, "refused": True,
                       "reason": (f"could not unload {still_resident}; refusing so the "
                                  f"render has the VRAM")}
            return outcome

        free_gb = (row["gpu_ready"] or {}).get("free_gb")
        verdict = budget_verdict(free_gb, needed_gb, reserve)
        row["budget"] = verdict
        if not verdict["ok"]:
            outcome = {"ok": False, "refused": True,
                       "reason": f"budget: {verdict['reason']}", "budget": verdict}
            return outcome

        started = start()
        row["start"] = {"ok": bool(started.get("ok")), "pid": started.get("pid"),
                        "reason": started.get("reason")}
        if not started.get("ok"):
            outcome = {"ok": False, "reason": started.get("reason")}
            return outcome
        pid = started.get("pid")
        try:
            ready_result = ready()
            row["ready"] = ready_result
            if not ready_result.get("ok"):
                outcome = {"ok": False, "reason": ready_result.get("reason")}
                return outcome
            row["gpu_before_work"] = snapshot()
            outcome = {"ok": True, "result": work()}
            row["gpu_after_work"] = snapshot()
            return outcome
        finally:
            row["stopped"] = stop(pid)
            pid = None
    finally:
        if pid is not None:  # safety net: only if the inner finally did not run
            row["stopped"] = stop(pid)
        row["gpu_after"] = snapshot()
        reloaded: List[Dict[str, Any]] = []
        for tag in reload_needed:
            try:
                reloaded.append(reload(tag))
            except Exception as exc:  # noqa: BLE001 - a failed restore is recorded
                reloaded.append({"tag": tag, "verified": False,
                                 "reason": f"{type(exc).__name__}: {exc}"})
        row["reloaded"] = reloaded
        row["reload_verified"] = {item.get("tag"): bool(item.get("verified"))
                                  for item in reloaded}
        row["ollama_ps_after"] = ps()
        row["gpu_after_reload"] = snapshot()
        before_gb = float(vram() or 0.0) if vram else (
            (row.get("gpu_before") or {}).get("free_gb"))
        after_gb = float(vram() or 0.0) if vram else (
            (row.get("gpu_after") or {}).get("free_gb"))
        row["vram_before_gb"] = before_gb
        row["vram_after_gb"] = after_gb
        row["vram_freed_gb"] = (None if before_gb is None or after_gb is None
                                else round(after_gb - before_gb, 2))
        row["seconds"] = round(time.time() - started_at, 1)
        row["work_ok"] = bool(outcome.get("ok"))
        _log(row)
        outcome["lane"] = row


def status() -> Dict[str, Any]:
    return {"url": COMFY_URL, "reachable": reachable(), "port_open": port_open(),
            "home": str(COMFY_HOME)}


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(description="ComfyUI render lane")
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--stop", action="store_true")
    parser.add_argument("--pid", type=int, default=0)
    ns = parser.parse_args(argv)

    if ns.stop:
        result = _stop(ns.pid or None)
        print(json.dumps(result, indent=2))
        return 0 if result.get("ok") else 1
    print(json.dumps(status(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
