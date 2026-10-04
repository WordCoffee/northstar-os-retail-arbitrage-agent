"""Read-only local image-engine status (localhost-only; no install, no arming).

Core module (importable by the foundation readiness route and by the CLI in
``tools/local_image_engine_status.py``). It reports what is present vs missing
for the local ComfyUI *development* lane and the exact owner-gated step each
missing item needs. It NEVER installs, downloads weights, starts an engine, sets
``MEDIA_GEN_LIVE``, opens a port, or contacts a cloud provider.

Truth semantics:
  * "engine installed" != "generation enabled"  -> MEDIA_GEN_LIVE stays the gate.
  * "engine reachable" != "ready for users"     -> local readiness is dev-only.
"""
from __future__ import annotations

import os
import shutil
import socket
import subprocess
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import urlparse

DEFAULT_COMFY_URL = "http://127.0.0.1:8188"
PROBE_TIMEOUT_S = 0.3
COMFYUI_HOME_ENV = "COMFYUI_HOME"

# Expected weight files (from docs/LOCAL_IMAGE_GEN_SETUP.md) and the ComfyUI
# model dirs they may live in. Presence-only; nothing is downloaded.
EXPECTED_WEIGHTS = [
    ("flux1-dev-fp8.safetensors", ["models/unet", "models/diffusion_models"]),
    ("ae.safetensors", ["models/vae"]),
    ("clip_l.safetensors", ["models/clip", "models/text_encoders"]),
    ("t5xxl_fp8_e4m3fn.safetensors", ["models/clip", "models/text_encoders"]),
]


def repo_root() -> Path:
    # Northstar_backend/local_image_engine.py -> repo root is parents[1]
    return Path(__file__).resolve().parents[1]


def candidate_comfyui_homes() -> List[Path]:
    """Common install locations + an explicit COMFYUI_HOME. Never scans the disk."""
    homes: List[Path] = []
    env = (os.getenv(COMFYUI_HOME_ENV, "") or "").strip()
    if env:
        homes.append(Path(env))
    root = repo_root()
    homes += [
        root / "ComfyUI",
        root / "tools" / "ComfyUI",
        Path.home() / "ComfyUI",
        Path("C:/ComfyUI"),
    ]
    seen, out = set(), []
    for h in homes:
        key = str(h).lower()
        if key not in seen:
            seen.add(key)
            out.append(h)
    return out


def resolve_comfyui_home() -> Optional[Path]:
    for h in candidate_comfyui_homes():
        try:
            if h.is_dir() and (h / "main.py").exists():
                return h
        except OSError:
            continue
    for h in candidate_comfyui_homes():
        try:
            if h.is_dir():
                return h
        except OSError:
            continue
    return None


def _endpoint(url: str) -> Optional[tuple]:
    try:
        p = urlparse(url)
        host = p.hostname
        port = p.port or (443 if p.scheme == "https" else 80)
        return (host, int(port)) if host else None
    except (ValueError, TypeError):
        return None


def comfyui_reachable(url: str = DEFAULT_COMFY_URL, timeout: float = PROBE_TIMEOUT_S) -> str:
    """Bounded localhost reachability check: reachable | unreachable | unknown."""
    ep = _endpoint(url)
    if not ep:
        return "unknown"
    try:
        with socket.create_connection(ep, timeout=timeout):
            return "reachable"
    except (OSError, ValueError):
        return "unreachable"


def weights_status(home: Optional[Path]) -> Dict[str, object]:
    if not home:
        return {"found": [], "missing": [w for w, _ in EXPECTED_WEIGHTS], "checked": False}
    found, missing = [], []
    for name, dirs in EXPECTED_WEIGHTS:
        hit = False
        for d in dirs:
            try:
                if (home / d / name).is_file():
                    hit = True
                    break
            except OSError:
                continue
        (found if hit else missing).append(name)
    return {"found": found, "missing": missing, "checked": True}


def gpu_status() -> Dict[str, object]:
    """Best-effort, read-only GPU probe via nvidia-smi. Never raises."""
    exe = shutil.which("nvidia-smi")
    if not exe:
        return {"present": False, "detail": "nvidia-smi not found"}
    try:
        out = subprocess.run(
            [exe, "--query-gpu=name,memory.total", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=3,
        )
        lines = (out.stdout or "").strip().splitlines()
        if out.returncode == 0 and lines:
            return {"present": True, "detail": lines[0].strip()}
        return {"present": False, "detail": "nvidia-smi returned no GPU"}
    except (OSError, subprocess.SubprocessError):
        return {"present": False, "detail": "nvidia-smi probe failed"}


def disk_status(path: Optional[Path] = None) -> Dict[str, object]:
    try:
        u = shutil.disk_usage(str(path or repo_root()))
        return {"free_gb": round(u.free / 1e9, 1), "total_gb": round(u.total / 1e9, 1)}
    except OSError:
        return {"free_gb": None, "total_gb": None}


def media_gate_on() -> bool:
    return str(os.getenv("MEDIA_GEN_LIVE", "") or "").strip() == "1"


def build_local_setup(engine_state: Optional[str] = None) -> Dict[str, object]:
    """Cheap subset for the readiness route (no GPU/disk probing).

    ``engine_state`` lets the caller pass an already-computed reachability value.
    """
    home = resolve_comfyui_home()
    weights = weights_status(home)
    gate = media_gate_on()
    state = engine_state if engine_state in ("reachable", "unreachable", "unknown") else comfyui_reachable()
    return {
        "comfyui_home": str(home) if home else None,
        "comfyui_installed": bool(home),
        "weights_found": len(weights["found"]),
        "weights_expected": len(EXPECTED_WEIGHTS),
        "weights_missing": weights["missing"],
        "engine_reachable": state,
        "media_gate": gate,
        "ready_for_local_generation": bool(home and not weights["missing"] and gate and state == "reachable"),
        "note": "Local dev lane only — installed != enabled; readiness does not activate generation.",
    }


def build_status() -> Dict[str, object]:
    """Full read-only status for the CLI (adds GPU + disk). No install/arming."""
    home = resolve_comfyui_home()
    weights = weights_status(home)
    reachable = comfyui_reachable()
    gate = media_gate_on()

    items = [
        {
            "key": "comfyui_installed", "label": "ComfyUI installed locally",
            "state": "present" if home else "missing",
            "detail": str(home) if home else "not found in common locations",
            "gate": None if home else "install ComfyUI (owner-gated)",
        },
        {
            "key": "weights", "label": "Model weights installed",
            "state": "present" if (weights["found"] and not weights["missing"]) else ("partial" if weights["found"] else "missing"),
            "detail": f"{len(weights['found'])}/{len(EXPECTED_WEIGHTS)} expected files present",
            "gate": None if (weights["found"] and not weights["missing"]) else "download weights (owner-gated)",
        },
        {
            "key": "engine_reachable", "label": "Local engine reachable",
            "state": reachable, "detail": DEFAULT_COMFY_URL,
            "gate": None if reachable == "reachable" else "start ComfyUI (owner-gated)",
        },
        {
            "key": "media_gate", "label": "Media live gate (MEDIA_GEN_LIVE=1)",
            "state": "on" if gate else "off", "detail": "single arming gate",
            "gate": None if gate else "set MEDIA_GEN_LIVE=1 (owner-gated)",
        },
    ]
    ready = bool(home and not weights["missing"] and reachable == "reachable" and gate)
    return {
        "lane": "local-image-dev",
        "ready_for_local_generation": ready,
        "engine_installed": bool(home),
        "generation_enabled": bool(gate),
        "note": "Local readiness is a development signal — it is not production readiness and does not enable generation.",
        "items": items,
        "weights": weights,
        "gpu": gpu_status(),
        "disk": disk_status(),
        "comfyui_home": str(home) if home else None,
    }
