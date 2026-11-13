"""The research log: what the seller looked up, and what was actually observed.

Product Finder reads the candidate cache; it never remembered what the seller was working on. A
lookup lived in React state, so a reload started the work over — that is the "no query → persist →
read" half of the launch gate (G1) for research.

This store is deliberately small and honest:

* keyed by ASIN, one record per product, last observation wins;
* it records **what the client saw**, plus when, and whether the cache had an observation at all —
  `status: "no_observation"` is a real record, not a failure, because "I researched this and the
  cache has nothing" is a fact worth keeping;
* no metric is invented here: the store copies fields, it never computes them;
* JSON with an atomic write, the same pattern as `market_snapshot_store`, so a half-written file
  cannot exist.

    research_store.save_item({"asin": "B0...", "status": "observed", "row": {...}})
"""
from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parent
DEFAULT_PATH = ROOT / "data" / "research-tracked.json"

#: Fields a row may carry from the client. Anything else is dropped, so the store cannot become a
#: dumping ground for a page's internal state.
ROW_FIELDS = ("asin", "title", "brand", "category", "price", "rank", "offers", "buybox",
              "margin", "monthlySales", "rating", "reviews", "reasons", "status", "cached")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def store_path() -> Path:
    raw = os.environ.get("NORTHSTAR_RESEARCH_STORE") or ""
    path = Path(raw) if raw else DEFAULT_PATH
    if not path.is_absolute():
        path = ROOT / path
    return path


def _read(path: Path) -> Dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"schema_version": 1, "items": {}}
    if not isinstance(data, dict) or not isinstance(data.get("items"), dict):
        return {"schema_version": 1, "items": {}}
    return data


def _write(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temp = tempfile.mkstemp(prefix="research_", suffix=".json", dir=str(path.parent))
    os.close(handle)
    Path(temp).write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(temp, path)


def normalise(asin: Optional[str]) -> str:
    return str(asin or "").strip().upper()


def save_item(payload: Dict[str, Any], path: Optional[Path] = None) -> Dict[str, Any]:
    """Persist one researched product. Returns the stored record."""
    target = Path(path or store_path())
    asin = normalise(payload.get("asin"))
    if not asin:
        raise ValueError("asin is required")
    row = payload.get("row") if isinstance(payload.get("row"), dict) else {}
    clean = {key: row.get(key) for key in ROW_FIELDS if key in row}
    observed = str(payload.get("status") or ("observed" if clean.get("title") not in (None, "UNKNOWN")
                                             else "no_observation"))
    record = {
        "asin": asin,
        "status": observed,
        "note": str(payload.get("note") or "")[:500],
        "row": clean,
        "query": str(payload.get("query") or "")[:200],
        "saved_at": _now(),
        "source": "product-finder (client-observed; no field is computed here)",
    }
    data = _read(target)
    data.setdefault("items", {})[asin] = record
    data["generated_at"] = record["saved_at"]
    _write(target, data)
    return record


def list_items(path: Optional[Path] = None) -> List[Dict[str, Any]]:
    data = _read(Path(path or store_path()))
    items = list((data.get("items") or {}).values())
    items.sort(key=lambda item: str(item.get("saved_at") or ""), reverse=True)
    return items


def get_item(asin: str, path: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    data = _read(Path(path or store_path()))
    return (data.get("items") or {}).get(normalise(asin))


def delete_item(asin: str, path: Optional[Path] = None) -> bool:
    target = Path(path or store_path())
    data = _read(target)
    key = normalise(asin)
    if key not in (data.get("items") or {}):
        return False
    data["items"].pop(key, None)
    _write(target, data)
    return True


__all__ = ["ROW_FIELDS", "delete_item", "get_item", "list_items", "save_item", "store_path"]
