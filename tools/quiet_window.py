"""The quiet window: one render, with builders paused and the box as empty as it gets.

The soak measures the loop under load. A render needs the opposite: nothing else running, the
residents unloaded, and a number written down before and after so the result is attributable.

Sequence, each step recorded:

1. wait for the soak to finish (`state/soak.json` `ended_at`), or run now with `--now`;
2. pause builders — `state/director/PAUSE_BUILDERS`, which the launcher already honours;
3. record free RAM and the GPU's free VRAM;
4. unload residents — every Ollama model via `/api/ps` with `keep_alive: 0`, and ComfyUI stopped
   if it is up;
5. start ComfyUI through `tools/start_comfyui.ps1` and wait for `/system_stats`;
6. render one 1024x1024 image through the app's own `/api/design-studio/generate` (the asset is
   persisted by the studio, so this is a real G1 render, not a side-channel);
7. restore — stop the ComfyUI instance this run started, clear `PAUSE_BUILDERS`, record free RAM;
8. write `reports/ty/quiet_window_<stamp>.md` and `state/quiet_window.json`.

    python tools/quiet_window.py --status
    python tools/quiet_window.py --now
    python tools/quiet_window.py --wait          # fires when the soak has ended
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "state" / "quiet_window.json"
SOAK = ROOT / "state" / "soak.json"
PAUSE_BUILDERS = ROOT / "state" / "director" / "PAUSE_BUILDERS"
REPORTS = ROOT / "reports" / "ty"
OLLAMA = "http://127.0.0.1:11434"
COMFY = "http://127.0.0.1:8188"
API = "http://127.0.0.1:8000"
#: Hard cap for the whole window: a hung render must not leave builders paused overnight.
CAP_S = 30 * 60


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _json(url: str, *, method: str = "GET", body: Optional[Dict[str, Any]] = None,
          timeout: int = 30) -> Any:
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(url, data=data, method=method,
                                     headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8", "replace"))


def _reachable(url: str, timeout: int = 3) -> bool:
    try:
        urllib.request.urlopen(url, timeout=timeout)
        return True
    except Exception:  # noqa: BLE001
        return False


def ram() -> Dict[str, Any]:
    try:
        import psutil

        memory = psutil.virtual_memory()
        return {"free_gb": round(memory.available / 1024 ** 3, 2)}
    except Exception as exc:  # noqa: BLE001
        return {"error": f"{type(exc).__name__}: {exc}"}


def vram() -> Dict[str, Any]:
    try:
        out = subprocess.run(["nvidia-smi", "--query-gpu=memory.free,memory.used",
                              "--format=csv,noheader,nounits"], capture_output=True,
                             text=True, timeout=20)
        free, used = [int(x.strip()) for x in out.stdout.strip().split(",")[:2]]
        return {"free_mb": free, "used_mb": used}
    except Exception as exc:  # noqa: BLE001
        return {"error": f"{type(exc).__name__}: {exc}"}


def unload_residents() -> Dict[str, Any]:
    """Evict every Ollama model and stop ComfyUI. Returns what was actually resident."""
    report: Dict[str, Any] = {"ollama": [], "comfyui_stopped": False}
    try:
        resident = (_json(f"{OLLAMA}/api/ps") or {}).get("models") or []
        for model in resident:
            name = model.get("name") or model.get("model")
            report["ollama"].append(name)
            for endpoint in ("/api/generate", "/api/embeddings"):
                try:
                    _json(f"{OLLAMA}{endpoint}", method="POST",
                          body={"model": name, "keep_alive": 0, "prompt": ""}, timeout=30)
                except Exception:  # noqa: BLE001
                    continue
        time.sleep(2)
        report["ollama_after"] = [m.get("name") for m in
                                  (_json(f"{OLLAMA}/api/ps") or {}).get("models") or []]
    except Exception as exc:  # noqa: BLE001
        report["ollama_error"] = f"{type(exc).__name__}: {exc}"
    if _reachable(f"{COMFY}/system_stats"):
        report["comfyui_was_running"] = True
        try:
            subprocess.run(["powershell", "-NoProfile", "-Command",
                            "Get-NetTCPConnection -State Listen -LocalPort 8188 | "
                            "ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }"],
                           capture_output=True, text=True, timeout=60)
            time.sleep(3)
            report["comfyui_stopped"] = not _reachable(f"{COMFY}/system_stats")
        except Exception as exc:  # noqa: BLE001
            report["comfyui_error"] = f"{type(exc).__name__}: {exc}"
    return report


def start_comfyui(timeout_s: int = 300) -> Dict[str, Any]:
    script = ROOT / "tools" / "start_comfyui.ps1"
    if not script.is_file():
        return {"ok": False, "reason": f"{script} is missing"}
    started = time.time()
    subprocess.Popen(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
                      "-File", str(script)], cwd=str(ROOT),
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    while time.time() - started < timeout_s:
        if _reachable(f"{COMFY}/system_stats"):
            return {"ok": True, "seconds": round(time.time() - started, 1)}
        time.sleep(3)
    return {"ok": False, "reason": f"ComfyUI did not answer /system_stats within {timeout_s}s"}


def render(brief: str, *, timeout_s: int = 1800) -> Dict[str, Any]:
    body = {"kind": "image", "brief": brief, "width": 1024, "height": 1024,
            "text_safe": True, "tier": "draft"}
    started = time.time()
    try:
        payload = _json(f"{API}/api/design-studio/generate", method="POST", body=body,
                        timeout=max(30, int(timeout_s)))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:400]
        return {"ok": False, "status": exc.code, "reason": detail}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "reason": f"{type(exc).__name__}: {exc}"}
    data = payload.get("data") if isinstance(payload, dict) and payload.get("contract") == "bff/v1" else payload
    asset = (data or {}).get("asset") or {}
    return {"ok": bool(asset.get("id")), "seconds": round(time.time() - started, 1),
            "asset": {k: asset.get(k) for k in ("id", "name", "asset_type", "mime_type",
                                                "width", "height", "path")}}


def tick(wait: bool) -> Dict[str, Any]:
    """One quiet window. Hard-capped at 30 minutes, with restore in a `finally`.

    The cap covers the **window**, not the waiting: the waiter may sit for a day until the soak
    ends, and only then does the 30-minute clock start. A cap that included the wait would abandon
    the window before it began, which is what the first version did.
    """
    state: Dict[str, Any] = {"started_at": now(), "cap_s": CAP_S, "steps": {}}

    if wait:
        wait_deadline = time.time() + 48 * 3600
        while time.time() < wait_deadline:
            try:
                soak = json.loads(SOAK.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                soak = {}
            if soak.get("ended_at"):
                state["soak_ended_at"] = soak["ended_at"]
                break
            time.sleep(300)
        else:
            state["steps"]["wait"] = {"ok": False,
                                      "reason": "the soak did not end within 48 hours"}
            return state

    started = time.time()
    deadline = started + CAP_S
    state["window_started_at"] = now()

    def remaining() -> float:
        return max(0.0, deadline - time.time())

    PAUSE_BUILDERS.parent.mkdir(parents=True, exist_ok=True)
    PAUSE_BUILDERS.write_text(f"quiet window {state['started_at']}: one render, builders paused\n",
                              encoding="utf-8")
    state["steps"]["pause_builders"] = {"ok": True, "path": str(PAUSE_BUILDERS.relative_to(ROOT))}
    state["ram_before"] = ram()
    state["vram_before"] = vram()

    try:
        state["steps"]["unload"] = unload_residents()
        state["ram_after_unload"] = ram()
        state["vram_after_unload"] = vram()

        if remaining() < 120:
            state["steps"]["start_comfyui"] = {"ok": False,
                                               "reason": "less than two minutes of the cap left"}
        else:
            state["steps"]["start_comfyui"] = start_comfyui(
                timeout_s=int(min(300, remaining() - 60)))

        if not state["steps"]["start_comfyui"].get("ok"):
            state["steps"]["render"] = {"ok": False,
                                        "reason": "engine never came up; nothing rendered"}
        elif remaining() < 60:
            state["steps"]["render"] = {"ok": False,
                                        "reason": "the 30-minute cap left no time to render"}
        else:
            state["steps"]["render"] = render(
                "A 6 oz stand-up pouch of organic lion's mane mushroom powder on a plain white "
                "background, studio lighting, no text",
                timeout_s=int(remaining() - 30))
    except Exception as exc:  # noqa: BLE001 - the window must still restore
        state["steps"]["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        state["steps"]["restore"] = restore()
        state["ram_after"] = ram()
        state["vram_after"] = vram()
        state["ended_at"] = now()
        state["elapsed_s"] = round(time.time() - started, 1)
        state["within_cap"] = state["elapsed_s"] <= CAP_S
        STATE.parent.mkdir(parents=True, exist_ok=True)
        STATE.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
        write_report(state)
    return state


def restore() -> Dict[str, Any]:
    PAUSE_BUILDERS.unlink(missing_ok=True)
    if _reachable(f"{COMFY}/system_stats"):
        subprocess.run(["powershell", "-NoProfile", "-Command",
                        "Get-NetTCPConnection -State Listen -LocalPort 8188 | "
                        "ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }"],
                       capture_output=True, text=True, timeout=60)
    return {"ok": True, "builders_unpaused": True,
            "comfyui_running": _reachable(f"{COMFY}/system_stats")}


def write_report(state: Dict[str, Any]) -> Path:
    render_step = (state.get("steps") or {}).get("render") or {}
    asset = render_step.get("asset") or {}
    lines = [
        "# Quiet window — one render, builders paused",
        "",
        f"Started **{state.get('started_at')}**, ended **{state.get('ended_at')}**. "
        "Builders were paused for the whole window and restored after.",
        "",
        "| step | result |",
        "|---|---|",
        f"| builders paused | {state['steps']['pause_builders']['ok']} |",
        f"| free RAM before | {state.get('ram_before', {}).get('free_gb')} GB |",
        f"| VRAM before | {state.get('vram_before', {}).get('free_mb')} MB free |",
        f"| residents unloaded | {state['steps']['unload'].get('ollama')} "
        f"(after: {state['steps']['unload'].get('ollama_after')}) |",
        f"| ComfyUI started | {state['steps']['start_comfyui'].get('ok')} "
        f"({state['steps']['start_comfyui'].get('seconds')}s) |",
        f"| render | {'ok' if render_step.get('ok') else 'refused'} "
        f"({render_step.get('seconds')}s) |",
        f"| asset id | `{asset.get('id')}` |",
        f"| asset size | {asset.get('width')}x{asset.get('height')} |",
        f"| free RAM after | {state.get('ram_after', {}).get('free_gb')} GB |",
        f"| builders restored | {state['steps']['restore'].get('builders_unpaused')} |",
        "",
    ]
    if not render_step.get("ok"):
        lines += ["## Why the render did not produce an asset", "",
                  f"```\n{str(render_step.get('reason') or render_step)[:1200]}\n```", ""]
    path = REPORTS / f"quiet_window_{datetime.now().strftime('%Y%m%d_%H%M')}.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Quiet window: one render with builders paused")
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--now", action="store_true")
    parser.add_argument("--wait", action="store_true")
    ns = parser.parse_args(argv)
    if ns.status:
        try:
            state = json.loads(STATE.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            state = {"state": "not run"}
        print(json.dumps(state, indent=2)[:3000])
        return 0
    state = tick(wait=ns.wait and not ns.now)
    print(json.dumps({k: v for k, v in state.items() if k != "steps"}, indent=2))
    print("render:", json.dumps(state.get("steps", {}).get("render", {}))[:400])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
