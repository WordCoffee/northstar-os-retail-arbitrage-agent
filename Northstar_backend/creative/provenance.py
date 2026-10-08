"""Output provenance sidecars for creative assets.

Every produced asset gets a JSON sidecar capturing what ran, on what input, with
which model/workflow/seed/settings, and the applicable license notice. This is
the data needed for reproducibility, audit, and commercial-use review. No secret
values are ever written.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import registry


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_sha256(path: Path) -> Optional[str]:
    try:
        h = hashlib.sha256()
        with open(path, "rb") as fh:
            for block in iter(lambda: fh.read(1 << 20), b""):
                h.update(block)
        return h.hexdigest()
    except OSError:
        return None


def sidecar_for(output_path: str | os.PathLike, *, task: str,
                lane: str, component: Optional[str] = None,
                params: Optional[Dict[str, Any]] = None,
                inputs: Optional[List[str]] = None,
                stages: Optional[List[Dict[str, Any]]] = None,
                extras: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    p = Path(output_path)
    comp = registry.component(component) if component else None
    digest = file_sha256(p) if p.exists() else None
    rec: Dict[str, Any] = {
        "schema": "northstar-creative-provenance-v1",
        "task": task,
        "lane": lane,
        "component": component,
        "license": (comp or {}).get("license"),
        "license_source": (comp or {}).get("license_source"),
        "commercial_use": (comp or {}).get("commercial_use"),
        "notices": (comp or {}).get("notices", []),
        "output": str(p),
        "output_sha256": digest,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "platform": platform.platform(),
        "params": params or {},
        "inputs": [{"path": str(i), "sha256": file_sha256(Path(i)) if Path(i).exists() else None}
                   for i in (inputs or [])],
        "stages": stages or [],
        "extras": extras or {},
    }
    return rec


def write_sidecar(output_path: str | os.PathLike, **kwargs) -> Path:
    rec = sidecar_for(output_path, **kwargs)
    out = Path(output_path)
    side = out.with_suffix(out.suffix + ".json")
    side.write_text(json.dumps(rec, indent=2), encoding="utf-8")
    return side
