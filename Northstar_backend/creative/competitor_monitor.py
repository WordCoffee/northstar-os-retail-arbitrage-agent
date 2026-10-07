"""Competitor Monitor — local watch desk with deterministic deltas.

No scraping and no provider: the operator adds competitor entries and records
snapshots (price / title / rank). The monitor reports exactly what changed
between snapshots. It never invents competitor data.

Store: ``competitors.json`` in the media root (``NORTHSTAR_COMPETITORS_INDEX``
overrides).
"""

from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import storage

TRACKED_FIELDS = ("price", "title", "rank", "rating", "review_count", "in_stock")


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _path() -> Path:
    env = os.environ.get("NORTHSTAR_COMPETITORS_INDEX")
    if env:
        return Path(env)
    return storage._local_root() / "competitors.json"


def _load() -> Dict[str, Any]:
    p = _path()
    if p.exists():
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(d, dict) and isinstance(d.get("entries"), list):
                return d
        except Exception:
            pass
    return {"version": 1, "entries": []}


def _save(d: Dict[str, Any]) -> None:
    p = _path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(d, indent=2, ensure_ascii=False), encoding="utf-8")


def add(name: str, *, url: str = "", asin: str = "", notes: str = "") -> Dict[str, Any]:
    d = _load()
    entry = {
        "id": f"CM-{uuid.uuid4().hex[:8].upper()}",
        "name": name, "url": url, "asin": asin, "notes": notes,
        "snapshots": [], "created_at": _now(),
    }
    d["entries"].append(entry)
    _save(d)
    return entry


def list_watch() -> List[Dict[str, Any]]:
    return _load()["entries"]


def get(wid: str) -> Optional[Dict[str, Any]]:
    return next((e for e in _load()["entries"] if e.get("id") == wid), None)


def remove(wid: str) -> bool:
    d = _load()
    before = len(d["entries"])
    d["entries"] = [e for e in d["entries"] if e.get("id") != wid]
    _save(d)
    return len(d["entries"]) < before


def snapshot(wid: str, data: Dict[str, Any]) -> Dict[str, Any]:
    d = _load()
    for e in d["entries"]:
        if e.get("id") == wid:
            snap = {"ts": _now(), **{k: data.get(k) for k in TRACKED_FIELDS if k in data}}
            e.setdefault("snapshots", []).append(snap)
            _save(d)
            return snap
    raise ValueError("watch entry not found")


def deltas(wid: str) -> Dict[str, Any]:
    e = get(wid)
    if not e:
        raise ValueError("watch entry not found")
    snaps = e.get("snapshots", [])
    if len(snaps) < 2:
        return {"id": wid, "changes": [], "count": 0,
                "note": "need at least two snapshots to compute deltas",
                "snapshots": len(snaps)}
    prev, cur = snaps[-2], snaps[-1]
    changes = []
    not_reported = []
    for f in TRACKED_FIELDS:
        if f in cur and f in prev:
            a, b = prev.get(f), cur.get(f)
            if a != b:
                delta = None
                if isinstance(a, (int, float)) and isinstance(b, (int, float)):
                    delta = round(b - a, 4)
                changes.append({"field": f, "from": a, "to": b, "delta": delta})
        elif f in prev and f not in cur:
            not_reported.append(f)   # was tracked, now absent — not a value change
    return {"id": wid, "name": e.get("name"), "count": len(changes),
            "changes": changes, "not_reported": not_reported, "snapshots": len(snaps),
            "from_ts": prev.get("ts"), "to_ts": cur.get("ts")}


def overview() -> List[Dict[str, Any]]:
    out = []
    for e in list_watch():
        try:
            d = deltas(e["id"])
        except ValueError:
            d = {"count": 0, "changes": []}
        out.append({"id": e["id"], "name": e.get("name"), "asin": e.get("asin"),
                    "snapshots": len(e.get("snapshots", [])),
                    "changes": d.get("count", 0),
                    "latest_change": (d.get("changes") or [None])[0]})
    return out
