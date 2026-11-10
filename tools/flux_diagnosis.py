"""Diagnose the FLUX 3 failures on this Blackwell card, in the order the owner set.

The record says FLUX 3 died with `cuDNN plan` and then `aimdo Fault failed: 2`, and that SDXL
reached only 768 while another lane held the GPU. A failure that only appears under contention is
a *headroom* failure, not a broken graph, and the difference matters: one is fixed by unloading a
resident model, the other by changing the stack.

This runs the same render three ways and keeps every snapshot:

1. **with a resident model** (Bojo loaded) — reproduce the failure and capture `nvidia-smi` and
   `ollama ps` at the moment it happens;
2. **after unloading the resident** — the first fix to try, because it costs nothing;
3. **at native resolution** — 1024, not 768 upscaled, so the picture is not a resampling.

    python tools/flux_diagnosis.py --run
"""
from __future__ import annotations

import argparse
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
for _path in (ROOT / "tools", ROOT / "Northstar_backend"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))
OUT = ROOT / "reports" / "ty" / "flux_diagnosis.json"

#: The models a render competes with. Both are reloadable in under a second.
RESIDENTS = ("bojo:latest", "qwen3-embedding:0.6b")
OLLAMA = "http://127.0.0.1:11434"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def versions() -> Dict[str, Any]:
    """Every version that could explain a cuDNN failure, and where it was read from."""
    info: Dict[str, Any] = {"at": _now(), "platform": platform.platform()}
    comfy_python = Path.home() / "ComfyUI" / "venv" / "Scripts" / "python.exe"
    probe = (
        "import json, torch;"
        "print(json.dumps({'torch': torch.__version__,"
        " 'cuda': torch.version.cuda,"
        " 'cudnn': torch.backends.cudnn.version(),"
        " 'available': torch.cuda.is_available(),"
        " 'capability': torch.cuda.get_device_capability(0) if torch.cuda.is_available() else None,"
        " 'device': torch.cuda.get_device_name(0) if torch.cuda.is_available() else None}))"
    )
    for name, exe in (("comfy", comfy_python), ("repo", Path(sys.executable))):
        try:
            out = subprocess.run([str(exe), "-c", probe], capture_output=True, text=True,
                                 timeout=180)
            info[name] = json.loads((out.stdout or "{}").strip().splitlines()[-1]) if out.stdout else {}
        except Exception as exc:  # noqa: BLE001
            info[name] = {"error": f"{type(exc).__name__}: {exc}"}
    try:
        from PIL import Image  # noqa: F401

        import upscale  # noqa: PLC0415

        info["upscaler"] = getattr(upscale, "ACTIVE", None)
    except Exception:  # noqa: BLE001
        info["upscaler"] = None
    return info


def snapshot() -> Dict[str, Any]:
    """`nvidia-smi` and `ollama ps` at this instant."""
    state: Dict[str, Any] = {"at": _now()}
    try:
        out = subprocess.run(["nvidia-smi", "--query-gpu=memory.total,memory.used,memory.free",
                              "--format=csv,noheader,nounits"], capture_output=True, text=True,
                             timeout=30)
        total, used, free = (out.stdout or "").strip().split(",")
        state["vram"] = {"total_mb": int(total), "used_mb": int(used), "free_mb": int(free)}
    except Exception as exc:  # noqa: BLE001
        state["vram"] = {"error": f"{type(exc).__name__}: {exc}"}
    try:
        out = subprocess.run(["ollama", "ps"], capture_output=True, text=True, timeout=60)
        lines = [line for line in (out.stdout or "").splitlines()[1:] if line.strip()]
        state["ollama_ps"] = [line.split()[0] for line in lines]
    except Exception as exc:  # noqa: BLE001
        state["ollama_ps"] = {"error": f"{type(exc).__name__}: {exc}"}
    return state


def _ollama(path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    import urllib.request

    request = urllib.request.Request(
        OLLAMA + path, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(request, timeout=180) as response:
        return json.loads(response.read().decode("utf-8", "replace") or "{}")


def load_resident(model: str) -> Dict[str, Any]:
    try:
        _ollama("/api/generate", {"model": model, "prompt": "ok", "stream": False,
                                  "keep_alive": "10m", "options": {"num_predict": 1}})
        return {"ok": True, "model": model}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "model": model, "error": f"{type(exc).__name__}: {exc}"}


def unload_residents() -> Dict[str, Any]:
    unloaded = []
    for model in RESIDENTS:
        try:
            _ollama("/api/generate", {"model": model, "prompt": "", "stream": False,
                                      "keep_alive": 0})
            unloaded.append(model)
        except Exception:  # noqa: BLE001 - a model that is not loaded cannot be unloaded
            continue
    return {"unloaded": unloaded, "after": snapshot()}


def attempt(label: str, *, model: str, width: int, height: int, steps: int) -> Dict[str, Any]:
    from seller_tester.scene_render import render_scene

    before = snapshot()
    started = datetime.now(timezone.utc)
    try:
        result = render_scene(f"a studio product scene, soft daylight, {label}", model=model,
                              width=width, height=height, steps=steps, seed=7)
        return {"label": label, "model": model, "width": width, "height": height,
                "ok": True, "seconds": result.get("seconds"),
                "image_path": result.get("image_path"),
                "before": before, "after": snapshot(), "at": started.isoformat()}
    except Exception as exc:  # noqa: BLE001 - the failure is the datum
        return {"label": label, "model": model, "width": width, "height": height,
                "ok": False, "error": f"{type(exc).__name__}: {exc}"[:600],
                "before": before, "after": snapshot(), "at": started.isoformat()}


def run() -> Dict[str, Any]:
    payload: Dict[str, Any] = {"at": _now(), "versions": versions(), "attempts": []}
    resident = load_resident("bojo:latest")
    payload["resident_loaded"] = resident
    payload["attempts"].append(attempt("contended-1024", model="flux3", width=1024,
                                       height=1024, steps=8))
    # The recorded failures were at 1536 while another model was resident, so that is the
    # case worth reproducing — 1024 passing with Bojo loaded says the graph is fine and the
    # question is headroom, not correctness.
    payload["attempts"].append(attempt("contended-1536", model="flux3", width=1536,
                                       height=1536, steps=12))
    payload["unload"] = unload_residents()
    payload["attempts"].append(attempt("unloaded-1024", model="flux3", width=1024,
                                       height=1024, steps=12))
    payload["attempts"].append(attempt("unloaded-1536", model="flux3", width=1536,
                                       height=1536, steps=16))
    working = next((row for row in payload["attempts"] if row.get("ok")), None)
    payload["first_working"] = working.get("label") if working else None
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="FLUX 3 diagnosis")
    parser.add_argument("--run", action="store_true")
    ns = parser.parse_args(argv)
    payload = run() if ns.run else {"versions": versions(), "snapshot": snapshot()}
    print(json.dumps({k: payload.get(k) for k in ("first_working", "versions")}, indent=2)[:2500])
    for row in payload.get("attempts") or []:
        print(json.dumps({k: row.get(k) for k in ("label", "ok", "error", "seconds",
                                                  "width", "height")}))
    return 0 if payload.get("first_working") else 1


if __name__ == "__main__":
    raise SystemExit(main())
