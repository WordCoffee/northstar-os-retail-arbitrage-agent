"""Worker/deployment configuration for the shared creative pipeline.

Machine-specific settings (device assignment, ComfyUI URL, concurrency, retention)
live in ``shared/creative-deployment.json`` and are kept separate from the
workflow/model registry so the same workflows run unchanged on a multi-GPU
rendering server.

This module exposes the interfaces the router/jobs need now (device assignment,
worker health, bounded queue size) without building a distributed platform.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = REPO_ROOT / "shared" / "creative-deployment.json"


def config() -> Dict[str, Any]:
    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"schema": "missing", "workers": [], "policy": {}}


def policy() -> Dict[str, Any]:
    p = dict(config().get("policy", {}))
    p.setdefault("heavy_concurrency", 1)
    p.setdefault("queue_max", 32)
    p.setdefault("job_timeout_seconds", 1800)
    return p


def workers() -> List[Dict[str, Any]]:
    return list(config().get("workers", []))


def enabled_workers() -> List[Dict[str, Any]]:
    return [w for w in workers() if w.get("enabled", True)]


def worker_for_capability(capability: str) -> Optional[Dict[str, Any]]:
    for w in enabled_workers():
        if capability in (w.get("capabilities") or []):
            return w
    return None


def health() -> Dict[str, Any]:
    """Best-effort health for each configured worker (no secrets)."""
    from . import comfy_client
    out = []
    for w in workers():
        up = False
        try:
            up = comfy_client.ComfyClient(base_url=w.get("comfyui_url"), timeout=1.5).is_up()
        except Exception:
            up = False
        out.append({"id": w.get("id"), "device": w.get("device"),
                    "url": w.get("comfyui_url"), "up": up,
                    "capabilities": w.get("capabilities", []),
                    "max_concurrency": w.get("max_concurrency", 1)})
    return {"workers": out, "policy": policy()}
