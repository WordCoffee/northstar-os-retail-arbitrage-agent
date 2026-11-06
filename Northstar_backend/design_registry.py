"""A design is a thing you keep, not a thing you regenerate.

The complaint this answers: "it's the same product image that you've already
used", "when generating random products it should be new designs each time",
"only keep designs, and keep designing the same design when a user asks for it".

Those are three rules about identity, and none of them can be honoured without a
record of what a design *is*:

  * a new random product must mint a NEW design (never quietly reuse the last
    plate, which is how a Shiitake pouch ended up under a Lion's Mane headline);
  * a request for "the same design" must resolve the SAME record and only vary
    the scene, angle or format around it;
  * an A+ page must draw all of its imagery from that one design, so every module
    is a different view of the same product rather than the same file repeated.

The record is deliberately small and local: a JSON file per design under
``state/designs/``. No database, no service, no cloud. Each design keeps its
assets (plate, logo, label render), its brand palette, the prompt/spec that
produced it, and a version list so "keep designing this one" is traceable.

    reg = DesignRegistry()
    d = reg.create(brand="Mogra Organics", product="Lion's Mane 6 oz",
                   plate="renders/.../plate.png", logo="renders/.../logo.png",
                   palette={"field": "#F4F0E6", "ink": "#1E3A2F"})
    reg.get(d["id"])            # the same design
    reg.latest("Mogra Organics")  # what the operator was last working on
    reg.add_version(d["id"], asset="renders/.../v2.png", note="scene change")
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
DESIGNS = ROOT / "state" / "designs"


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _key(brand: str, product: str) -> str:
    raw = f"{brand.strip().lower()}|{product.strip().lower()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


class DesignRegistry:
    def __init__(self, root: Optional[Path] = None):
        self.root = Path(root) if root else DESIGNS
        self.root.mkdir(parents=True, exist_ok=True)

    # ---------------------------------------------------------------- internals
    def _path(self, design_id: str) -> Path:
        return self.root / f"{design_id}.json"

    def _read(self, path: Path) -> Dict[str, Any]:
        return json.loads(path.read_text(encoding="utf-8"))

    def _write(self, record: Dict[str, Any]) -> Dict[str, Any]:
        record["updated_at"] = _now()
        # Second-granularity ISO strings are not a sort key: two designs created
        # in the same second tie, and "latest" becomes arbitrary (measured).
        record["updated_ts"] = time.time()
        self._path(record["id"]).write_text(
            json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
        return record

    @staticmethod
    def _store_asset(source: Path, design_id: str, kind: str) -> str:
        """Copy an asset into the design's own folder so the record is self-contained."""
        folder = DESIGNS / design_id
        folder.mkdir(parents=True, exist_ok=True)
        target = folder / f"{kind}{Path(source).suffix or '.png'}"
        shutil.copyfile(source, target)
        return str(target.relative_to(ROOT)).replace("\\", "/")

    # --------------------------------------------------------------------- api
    def create(self, *, brand: str, product: str, plate: Optional[Path] = None,
               logo: Optional[Path] = None, label: Optional[Path] = None,
               palette: Optional[Dict[str, str]] = None, prompt: str = "",
               source: str = "generated") -> Dict[str, Any]:
        """Mint a NEW design. Two calls never return the same id."""
        if not brand.strip() or not product.strip():
            raise ValueError("a design needs a brand and a product name")
        design_id = "dsg_" + uuid.uuid4().hex[:12]
        record: Dict[str, Any] = {
            "id": design_id,
            "brand": brand.strip(),
            "product": product.strip(),
            "key": _key(brand, product),
            "palette": dict(palette or {}),
            "prompt": str(prompt or ""),
            "source": source,
            "created_at": _now(),
            "created_ts": time.time(),
            "version": 1,
            "assets": {},
            "versions": [],
        }
        for kind, path in (("plate", plate), ("logo", logo), ("label", label)):
            if path and Path(path).is_file():
                record["assets"][kind] = self._store_asset(Path(path), design_id, kind)
        record["versions"].append({"version": 1, "at": record["created_at"],
                                   "note": "created", "assets": dict(record["assets"])})
        return self._write(record)

    def get(self, design_id: str) -> Optional[Dict[str, Any]]:
        path = self._path(design_id)
        return self._read(path) if path.is_file() else None

    def list(self, *, brand: str = "") -> List[Dict[str, Any]]:
        rows = []
        for path in sorted(self.root.glob("dsg_*.json")):
            try:
                row = self._read(path)
            except (OSError, ValueError):
                continue
            if brand and row.get("brand", "").strip().lower() != brand.strip().lower():
                continue
            rows.append(row)
        rows.sort(key=lambda r: r.get("updated_ts") or r.get("created_ts") or 0,
                  reverse=True)
        return rows

    def latest(self, brand: str = "", product: str = "") -> Optional[Dict[str, Any]]:
        rows = self.list(brand=brand)
        if product:
            rows = [r for r in rows
                    if r.get("product", "").strip().lower() == product.strip().lower()]
        return rows[0] if rows else None

    def find_same(self, *, brand: str, product: str) -> Optional[Dict[str, Any]]:
        """The design a "keep designing this" request resolves to, or None.

        Deliberately explicit: a caller must ask for the same design. A new
        request that does not ask gets a new design, which is what stops the
        last plate being silently reused for a different product.
        """
        rows = [r for r in self.list(brand=brand)
                if r.get("key") == _key(brand, product)]
        return rows[0] if rows else None

    def add_version(self, design_id: str, *, asset: Optional[Path] = None,
                    note: str = "", palette: Optional[Dict[str, str]] = None
                    ) -> Dict[str, Any]:
        record = self.get(design_id)
        if record is None:
            raise KeyError(f"design not found: {design_id}")
        record["version"] = int(record.get("version") or 1) + 1
        if palette:
            record.setdefault("palette", {}).update(palette)
        if asset and Path(asset).is_file():
            stored = self._store_asset(Path(asset), design_id,
                                       f"plate_v{record['version']}")
            record["assets"]["plate"] = stored
        record["versions"].append({"version": record["version"], "at": _now(),
                                   "note": str(note or "")[:200],
                                   "assets": dict(record["assets"])})
        return self._write(record)

    def resolve_asset(self, design_id: str, kind: str = "plate") -> Optional[Path]:
        record = self.get(design_id)
        if not record:
            return None
        rel = (record.get("assets") or {}).get(kind)
        if not rel:
            return None
        path = ROOT / rel
        return path if path.is_file() else None
