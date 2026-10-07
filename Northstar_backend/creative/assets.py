"""Local creative asset registry.

A small, file-backed index over the storage layer. Every generated creative
asset (mockups, scene renders, bundles) can be registered with metadata and then
listed, grouped into variant sets, and packaged into export bundles.

Index file: ``assets.json`` in the media root (configurable via
``NORTHSTAR_ASSET_INDEX``). No database, no external service — this is the
"asset store" the Creative Studio room was missing.
"""

from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import storage


def _stamp() -> str:
    return time.strftime("%Y%m%d_%H%M%S")


def _index_path() -> Path:
    env = os.environ.get("NORTHSTAR_ASSET_INDEX")
    if env:
        return Path(env)
    return storage._local_root() / "assets.json"


def load_index() -> Dict[str, Any]:
    p = _index_path()
    if p.exists():
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(data, dict) and isinstance(data.get("assets"), list):
                return data
        except Exception:
            pass
    return {"version": 1, "assets": []}


def save_index(index: Dict[str, Any]) -> None:
    p = _index_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(index, indent=2), encoding="utf-8")


def register(
    *,
    key: str,
    url: Optional[str] = None,
    kind: str = "image",
    product: Optional[str] = None,
    container: Optional[str] = None,
    tags: Optional[List[str]] = None,
    meta: Optional[Dict[str, Any]] = None,
    asset_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Register (or update) an asset. Idempotent on ``key``."""
    index = load_index()
    existing = next((a for a in index["assets"] if a.get("key") == key), None)
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    if existing:
        existing.update({
            "url": url or existing.get("url"),
            "kind": kind or existing.get("kind"),
            "product": product if product is not None else existing.get("product"),
            "container": container if container is not None else existing.get("container"),
            "tags": tags if tags is not None else existing.get("tags", []),
            "meta": {**existing.get("meta", {}), **(meta or {})},
            "updated_at": now,
        })
        asset = existing
    else:
        asset = {
            "id": asset_id or f"AS-{uuid.uuid4().hex[:8].upper()}",
            "key": key,
            "url": url or f"/api/creative/file/{Path(key).name}",
            "kind": kind,
            "product": product,
            "container": container,
            "tags": tags or [],
            "meta": meta or {},
            "created_at": now,
            "updated_at": now,
        }
        index["assets"].append(asset)
    save_index(index)
    return asset


def register_file(path: str | os.PathLike, **kwargs: Any) -> Dict[str, Any]:
    p = Path(path)
    key = p.name
    kwargs.setdefault("url", f"/api/creative/file/{key}")
    return register(key=key, **kwargs)


def list_assets(*, kind: Optional[str] = None, product: Optional[str] = None,
                container: Optional[str] = None, limit: int = 500) -> List[Dict[str, Any]]:
    assets = load_index()["assets"]
    if kind:
        assets = [a for a in assets if a.get("kind") == kind]
    if product:
        assets = [a for a in assets if a.get("product") == product]
    if container:
        assets = [a for a in assets if a.get("container") == container]
    assets = sorted(assets, key=lambda a: a.get("created_at", ""), reverse=True)
    return assets[: max(1, limit)]


def get(asset_id: str) -> Optional[Dict[str, Any]]:
    return next((a for a in load_index()["assets"] if a.get("id") == asset_id), None)


def sets() -> List[Dict[str, Any]]:
    """Variant sets — group assets by (product, container)."""
    groups: Dict[str, Dict[str, Any]] = {}
    for a in load_index()["assets"]:
        if a.get("kind") == "bundle":
            continue
        key = f"{a.get('product') or 'unassigned'} / {a.get('container') or 'any container'}"
        g = groups.setdefault(key, {"set": key, "product": a.get("product"),
                                    "container": a.get("container"), "count": 0,
                                    "asset_ids": []})
        g["count"] += 1
        g["asset_ids"].append(a["id"])
    return sorted(groups.values(), key=lambda g: -g["count"])


def scan(*, subdir: str = "", kinds: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """Register any media files on disk that are not yet in the index."""
    kinds = kinds or {".png": "image", ".jpg": "image", ".jpeg": "image",
                      ".webp": "image", ".zip": "bundle"}
    index = load_index()
    known = {a.get("key") for a in index["assets"]}
    root = storage._local_root()
    added = 0
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        ext = p.suffix.lower()
        if ext not in kinds:
            continue
        key = str(p.relative_to(root)).replace("\\", "/")
        if key in known or p.name == "assets.json":
            continue
        register(key=key, url=f"/api/creative/file/{p.name}",
                 kind=kinds[ext], meta={"source": "scan"})
        added += 1
    return {"ok": True, "added": added, "total": len(load_index()["assets"])}
