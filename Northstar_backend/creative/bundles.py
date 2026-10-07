"""Export bundles — package selected creative assets into a ZIP + manifest.

Deterministic and local: reads assets from the storage backend, writes a
``manifest.json`` plus the asset files, stores the ZIP via the storage backend,
and registers the bundle in the asset registry. No external service.
"""

from __future__ import annotations

import io
import json
import time
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import assets, storage


def create_bundle(asset_ids: List[str], *, name: str = "creative-bundle",
                  include_manifest: bool = True) -> Dict[str, Any]:
    by_id = {a["id"]: a for a in assets.load_index()["assets"]}
    chosen = [by_id[i] for i in asset_ids if i in by_id]
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    manifest: Dict[str, Any] = {
        "name": name,
        "created_at": now,
        "asset_count": len(chosen),
        "assets": [{k: a.get(k) for k in ("id", "key", "kind", "url", "product", "container")}
                   for a in chosen],
    }

    backend = storage.get_backend()
    buf = io.BytesIO()
    included = 0
    missing: List[str] = []
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for a in chosen:
            try:
                z.writestr(f"assets/{Path(a['key']).name}", backend.get(a["key"]))
                included += 1
            except Exception:
                missing.append(a["key"])
        if missing:
            manifest["missing"] = missing
        if include_manifest:
            z.writestr("manifest.json", json.dumps(manifest, indent=2, ensure_ascii=False))

    data = buf.getvalue()
    safe = "_".join(name.split())[:60] or "creative-bundle"
    key = f"bundle_{safe}_{time.strftime('%Y%m%d_%H%M%S')}.zip"
    info = backend.put(key, data, "application/zip")
    asset = assets.register(key=key, url=info.get("url") or f"/api/creative/file/{key}",
                            kind="bundle", meta={"asset_count": included, "manifest": manifest})
    return {"ok": True, "bundle": asset, "manifest": manifest, "bytes": len(data),
            "included": included, "requested": len(asset_ids)}
