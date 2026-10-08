"""Approved-component + workflow registry (shared creative infrastructure).

Single source of truth for *what may run*: the machine-readable manifest at
``shared/creative-components.json`` lists every model/runtime/font with its
license, commercial status, dependencies, and install path. The router consults
this registry so a quarantined component (e.g. the non-commercial FLUX.1 [dev]
fallback) can never become the default for production output.

Nothing here reads a secret. It only inspects file presence and the manifest.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = REPO_ROOT / "shared" / "creative-components.json"

APPROVED = "approved"
QUARANTINED = "quarantined"

_cache: Optional[Dict[str, Any]] = None


def manifest_path() -> Path:
    return MANIFEST_PATH


def _resolve_install_path(raw: Optional[str]) -> Optional[Path]:
    if not raw:
        return None
    p = Path(raw)
    if not p.is_absolute():
        p = REPO_ROOT / p
    return p


def _load(force: bool = False) -> Dict[str, Any]:
    global _cache
    if _cache is not None and not force:
        return _cache
    try:
        data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover - defensive
        data = {"schema": "missing", "components": [], "error": str(exc)}
    _cache = data
    return data


def reload() -> Dict[str, Any]:
    return _load(force=True)


def components() -> List[Dict[str, Any]]:
    return list(_load().get("components", []))


def component(cid: str) -> Optional[Dict[str, Any]]:
    for c in components():
        if c.get("id") == cid:
            return c
    return None


def _exists(c: Dict[str, Any]) -> bool:
    if not c:
        return False
    p = _resolve_install_path(c.get("install_path"))
    if p is None:
        return bool(c.get("present"))
    if p.is_dir():
        return True
    return p.exists()


def installed(c: Optional[Dict[str, Any]]) -> bool:
    """True when the component's install path exists on disk (or a bundled file)."""
    return _exists(c)


def is_commercial(c: Dict[str, Any]) -> bool:
    return str(c.get("commercial_use", "")).lower() == "allowed"


def is_approved(c: Dict[str, Any]) -> bool:
    return str(c.get("status", "")).lower() == APPROVED


def approved() -> List[Dict[str, Any]]:
    return [c for c in components() if is_approved(c)]


def quarantined() -> List[Dict[str, Any]]:
    return [c for c in components() if str(c.get("status", "")).lower() == QUARANTINED]


def by_role(role: str, *, commercial_only: bool = True) -> List[Dict[str, Any]]:
    out = [c for c in components() if c.get("role") == role and is_approved(c)]
    if commercial_only:
        out = [c for c in out if is_commercial(c)]
    return out


def license_manifest() -> Dict[str, Any]:
    """Compact manifest for the API: role, license, commercial posture, presence."""
    return {
        "schema": _load().get("schema"),
        "policy": _load().get("policy", {}),
        "components": [
            {
                "id": c.get("id"),
                "role": c.get("role"),
                "family": c.get("family"),
                "label": c.get("label"),
                "license": c.get("license"),
                "license_source": c.get("license_source"),
                "commercial_use": c.get("commercial_use"),
                "hosted_use": c.get("hosted_use"),
                "status": c.get("status"),
                "present": installed(c),
                "sha256": c.get("sha256"),
                "restrictions": c.get("restrictions", []),
            }
            for c in components()
        ],
    }


def sha256_of(path: Path, *, chunk: int = 1 << 20) -> Optional[str]:
    try:
        h = hashlib.sha256()
        with open(path, "rb") as fh:
            for block in iter(lambda: fh.read(chunk), b""):
                h.update(block)
        return h.hexdigest()
    except OSError:
        return None


def build_hashes(update: bool = False) -> Dict[str, Optional[str]]:
    """Return {component_id: sha256} for installed components (manifest SHA verification)."""
    out: Dict[str, Optional[str]] = {}
    for c in components():
        p = _resolve_install_path(c.get("install_path"))
        if p is None or p.is_dir() or not p.exists():
            out[c["id"]] = c.get("sha256")
            continue
        digest = sha256_of(p)
        out[c["id"]] = digest
        if update and digest and c.get("sha256") != digest:
            c["sha256"] = digest
    if update:
        data = _load()
        data["components"] = components()
        MANIFEST_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return out


def missing() -> List[str]:
    return [c["id"] for c in components() if not installed(c) and c.get("status") == APPROVED]


def status() -> Dict[str, Any]:
    comps = components()
    return {
        "schema": _load().get("schema"),
        "total": len(comps),
        "installed": sum(1 for c in comps if installed(c)),
        "approved": len(approved()),
        "quarantined": [c["id"] for c in quarantined()],
        "missing_approved": missing(),
        "manifest_path": str(MANIFEST_PATH),
        "manifest_present": MANIFEST_PATH.exists(),
    }
