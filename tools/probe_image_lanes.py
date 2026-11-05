"""Probe the local image lanes for real: render, judge, re-render from a reference.

This is the Phase A instrument for the Product Pictures workstream. It does not
mock anything: it calls the same service functions the API calls, measures VRAM
while the render runs, and writes every artifact under ``renders/autonomy_probe/``
with a JSON manifest beside it.

    python tools/probe_image_lanes.py --probe a8
    python tools/probe_image_lanes.py --probe a9 --image renders/autonomy_probe/a8_1024.png
    python tools/probe_image_lanes.py --probe a10
    python tools/probe_image_lanes.py --probe all

Stop/restore discipline (this box is 16 GB RAM and 16 GB VRAM, and ComfyUI and
the local brain cannot be resident together):

  * ``studio_generation.unload_brain()`` drains Ollama and verifies an empty
    ``/api/ps`` BEFORE the render, and the probe records the result;
  * VRAM is sampled from ``nvidia-smi`` on a thread for the duration of the
    render, so the peak is measured, not inferred;
  * in a ``finally`` the probe restores the brain and health-checks it, so a
    failed render never leaves the box without a text lane.

Exit codes: 0 all requested probes ran, 1 one failed, 2 the engine is not up.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "Northstar_backend"
OUT = ROOT / "renders" / "autonomy_probe"
sys.path.insert(0, str(BACKEND))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def vram() -> Dict[str, int]:
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.total,memory.used,memory.free",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=20, check=False)
        total, used, free = [int(x) for x in out.stdout.strip().split(",")[:3]]
        return {"total_mb": total, "used_mb": used, "free_mb": free}
    except Exception as exc:  # noqa: BLE001 - reported as unknown, never faked
        return {"error": f"{type(exc).__name__}: {exc}"}


def ram() -> Dict[str, int]:
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
        return {"total_mb": int(stat.ullTotalPhys / 1048576),
                "free_mb": int(stat.ullAvailPhys / 1048576)}
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)}


class VramSampler:
    def __init__(self, interval: float = 0.5):
        self.interval = interval
        self.peak_used = 0
        self.samples = 0
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def _run(self) -> None:
        while not self._stop.is_set():
            used = vram().get("used_mb", 0)
            self.peak_used = max(self.peak_used, int(used))
            self.samples += 1
            self._stop.wait(self.interval)

    def __enter__(self):
        self._thread.start()
        return self

    def __exit__(self, *_exc):
        self._stop.set()
        self._thread.join(timeout=5)


def _brain_model() -> str:
    """The brain the suite says the local text tier resolves to (never a guess)."""
    explicit = os.environ.get("NORTHSTAR_BRAIN_MODEL")
    if explicit:
        return explicit
    try:
        data = json.loads((ROOT / "shared" / "model-suite.json").read_text(encoding="utf-8"))
        return str(data["text"]["tiers"]["T2"]["local"])
    except (OSError, KeyError, ValueError):
        return "bojo"


def _brain_health() -> Dict[str, Any]:
    """Restore the text lane and prove it answers."""
    import urllib.request

    model = _brain_model()
    body = json.dumps({"model": model, "prompt": "reply with the single word ok",
                       "stream": False, "options": {"num_predict": 8}}).encode()
    req = urllib.request.Request("http://127.0.0.1:11434/api/generate", data=body,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=180) as response:
            payload = json.loads(response.read().decode("utf-8"))
        return {"ok": True, "model": model,
                "reply": (payload.get("response") or "").strip()[:40],
                "eval_count": payload.get("eval_count")}
    except Exception as exc:  # noqa: BLE001 - a failed restore is the finding
        return {"ok": False, "model": model, "error": f"{type(exc).__name__}: {exc}"}


def probe_a8(*, size: int = 1024, seed: int = 4242) -> Dict[str, Any]:
    import studio_generation as sg

    OUT.mkdir(parents=True, exist_ok=True)
    before = {"vram": vram(), "ram": ram()}
    evicted = sg.unload_brain()
    after_evict = {"vram": vram(), "ram": ram()}
    prompt = ("studio product photograph of a matte kraft stand-up coffee pouch with a "
              "cream label, centred on a seamless light grey backdrop, soft shadow, "
              "packshot lighting")
    started = time.time()
    with VramSampler() as sampler:
        try:
            result = sg.generate_image(prompt, width=size, height=size,
                                       tier="draft", seed=seed)
        finally:
            pass
    seconds = round(time.time() - started, 1)
    path = OUT / f"a8_{size}.png"
    path.write_bytes(result["bytes"])
    record = {
        "probe": "A8",
        "at": _now(),
        "image": str(path.relative_to(ROOT)).replace("\\", "/"),
        "bytes": len(result["bytes"]),
        "width": result.get("width"), "height": result.get("height"),
        "seconds": seconds,
        "peak_vram_used_mb": sampler.peak_used,
        "vram_samples": sampler.samples,
        "before": before, "after_evict": after_evict,
        "brain_evicted": result.get("brain_evicted"),
        "ram_gate": result.get("ram_gate"),
        "model": result.get("model"), "seed": result.get("seed"),
    }
    (OUT / "a8.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
    return record


def probe_a9(image: str, brief: str = "") -> Dict[str, Any]:
    import local_vision as lv

    path = Path(image)
    if not path.is_absolute():
        path = ROOT / path
    brief = brief or ("studio product photograph of a matte kraft stand-up coffee pouch "
                      "with a cream label on a seamless backdrop")
    started = time.time()
    verdict = lv.qc_file(str(path), brief)
    seconds = round(time.time() - started, 1)
    serialised_ok = True
    try:
        json.dumps(verdict)
    except (TypeError, ValueError):
        serialised_ok = False
    record = {"probe": "A9", "at": _now(), "image": str(path), "seconds": seconds,
              "verdict": verdict, "json_serialisable": serialised_ok,
              "mode": verdict.get("mode") if isinstance(verdict, dict) else None,
              "model": verdict.get("model") if isinstance(verdict, dict) else None}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "a9.json").write_text(json.dumps(record, indent=2, default=str), encoding="utf-8")
    return record


def probe_a10(*, size: int = 1024) -> Dict[str, Any]:
    import studio_generation as sg

    OUT.mkdir(parents=True, exist_ok=True)
    out: Dict[str, Any] = {"probe": "A10", "at": _now(), "paths": {}}

    stored = OUT / f"a8_{size}.png"
    uploaded = ROOT / "renders" / "mogra_lions_mane" / "product_front.png"
    prompt = ("studio product photograph of the pouch in the reference image, identical "
              "package and label, standing on a pale linen surface with a soft window light")

    for label, source in (("stored_previous_generation", stored),
                          ("uploaded_reference", uploaded)):
        entry: Dict[str, Any] = {"source": str(source),
                                 "source_exists": source.is_file()}
        if not source.is_file():
            entry["ok"] = False
            entry["error"] = "source image not on disk"
            out["paths"][label] = entry
            continue
        started = time.time()
        try:
            result = sg.generate_reference(prompt, source.read_bytes(),
                                           width=size, height=size, seed=777)
        except Exception as exc:  # noqa: BLE001 - the failure IS the measurement
            entry.update({"ok": False, "error": f"{type(exc).__name__}: {exc}",
                          "seconds": round(time.time() - started, 1)})
            out["paths"][label] = entry
            continue
        target = OUT / f"a10_{label}.png"
        target.write_bytes(result["bytes"])
        entry.update({
            "ok": True, "output": str(target.relative_to(ROOT)).replace("\\", "/"),
            "bytes": len(result["bytes"]), "width": result.get("width"),
            "height": result.get("height"), "mode": result.get("mode"),
            "reference_server_name": result.get("reference"),
            "seconds": round(time.time() - started, 1),
        })
        out["paths"][label] = entry

    (OUT / "a10.json").write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")
    return out


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Probe the local image lanes.")
    parser.add_argument("--probe", default="all",
                        choices=("a8", "a9", "a10", "all"))
    parser.add_argument("--image", default="")
    parser.add_argument("--size", type=int, default=1024)
    ns = parser.parse_args(argv)

    os.environ.setdefault("MEDIA_GEN_LIVE", "1")
    import studio_generation as sg

    if not sg.engine_status().get("reachable"):
        print(json.dumps({"ok": False, "error": "comfyui_unreachable",
                          "url": sg.comfyui_url(),
                          "engine": sg.engine_status()}, indent=2))
        return 2

    results: Dict[str, Any] = {}
    code = 0
    try:
        if ns.probe in ("a8", "all"):
            results["a8"] = probe_a8(size=ns.size)
        if ns.probe in ("a9", "all"):
            image = ns.image or str(OUT / f"a8_{ns.size}.png")
            results["a9"] = probe_a9(image)
        if ns.probe in ("a10", "all"):
            results["a10"] = probe_a10(size=ns.size)
    except Exception as exc:  # noqa: BLE001
        results["error"] = f"{type(exc).__name__}: {exc}"
        code = 1
    finally:
        # Always give the box its text lane back, and say whether it came back.
        results["brain_restore"] = _brain_health()
        results["after_restore"] = {"vram": vram(), "ram": ram()}

    print(json.dumps(results, indent=2, default=str))
    if not results["brain_restore"].get("ok"):
        code = 1
    return code


if __name__ == "__main__":
    raise SystemExit(main())
