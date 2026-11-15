"""Open-licensed reference media from Openverse, with licence and size gates.

No Amazon, no key. The transport is injected for tests; the default is the public API. A
refusal (bad licence, too small, gateway error) is named in the result, never dropped.

    python -m tools.ty_toolkit.openverse --query "ceramic mug" --limit 5
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence

API = "https://api.openverse.org/v1/images/"
ALLOWED = ("cc0", "by", "by-sa")
DEFAULT_MIN_SIDE = 800

Transport = Callable[[str, Dict[str, Any]], "tuple[int, Dict[str, Any]]"]


def _default_transport(url: str, params: Dict[str, Any]) -> "tuple[int, Dict[str, Any]]":
    query = urllib.parse.urlencode(params)
    request = urllib.request.Request(f"{url}?{query}", headers={"User-Agent": "NorthstarOS/toolkit"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return int(response.status), json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return int(exc.code), {"error": f"HTTP {exc.code}"}
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        return 0, {"error": f"{type(exc).__name__}: {exc}"}


def _row(item: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": str(item.get("id") or ""),
        "title": str(item.get("title") or ""),
        "creator": str(item.get("creator") or ""),
        "licence": str(item.get("license") or "").lower(),
        "licence_version": str(item.get("license_version") or ""),
        "licence_url": str(item.get("license_url") or ""),
        "source": str(item.get("source") or ""),
        "page_url": str(item.get("foreign_landing_url") or item.get("creator_url") or ""),
        "url": str(item.get("url") or ""),
        "thumbnail": str(item.get("thumbnail") or ""),
        "width": item.get("width"),
        "height": item.get("height"),
    }


def search(query: str, *, page_size: int = 5, min_side: int = DEFAULT_MIN_SIDE,
           licences: Sequence[str] = ALLOWED,
           transport: Optional[Transport] = None) -> Dict[str, Any]:
    """Search Openverse and keep only openly licensed rows at or above ``min_side``."""
    text = str(query or "").strip()
    if not text:
        return {"ok": False, "reason": "query is empty"}
    allowed = {str(name).lower() for name in licences}
    fetch = transport or _default_transport
    status, payload = fetch(API, {"q": text, "page_size": max(1, min(int(page_size), 20)),
                                  "license": ",".join(sorted(allowed))})
    if status != 200 or not isinstance(payload, dict) or payload.get("error"):
        reason = (payload or {}).get("error") if isinstance(payload, dict) else None
        return {"ok": False, "status": status,
                "reason": f"openverse HTTP {status or 'error'}: {reason or 'no detail'}"}
    kept: List[Dict[str, Any]] = []
    refused: List[Dict[str, Any]] = []
    for item in payload.get("results") or []:
        if not isinstance(item, dict):
            continue
        row = _row(item)
        if row["licence"] not in allowed:
            refused.append({"id": row["id"], "reason": f"licence {row['licence'] or 'unknown'}"})
            continue
        width, height = row.get("width"), row.get("height")
        if not isinstance(width, int) or not isinstance(height, int) or min(width, height) < min_side:
            refused.append({"id": row["id"], "reason": f"size {width}x{height} < {min_side}px"})
            continue
        kept.append(row)
    return {"ok": True, "query": text, "min_side": min_side, "count": len(kept),
            "rows": kept, "refused": refused,
            "note": "Openverse public API; licence + licence URL + source page on every row."}


def _default_fetcher(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "NorthstarOS/toolkit"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read()


def download(row: Dict[str, Any], dest_dir: str | Path, *, fetcher: Optional[Callable[[str], bytes]] = None) -> Dict[str, Any]:
    """Download one row to ``dest_dir``; returns the path, byte count and sha256."""
    url = str(row.get("url") or "")
    if not url:
        return {"ok": False, "reason": "the row carries no image URL"}
    fetch = fetcher or _default_fetcher
    try:
        content = fetch(url)
    except Exception as exc:  # noqa: BLE001 - a fetch failure is a named refusal
        return {"ok": False, "reason": f"download failed: {type(exc).__name__}: {exc}"}
    suffix = Path(urllib.parse.urlsplit(url).path).suffix.lower() or ".jpg"
    stem = re.sub(r"[^A-Za-z0-9_-]+", "-", f"{row.get('id') or 'media'}")[:60]
    target = Path(dest_dir) / f"{stem}{suffix}"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)
    return {"ok": True, "path": str(target), "bytes": len(content),
            "sha256": hashlib.sha256(content).hexdigest(),
            "licence": row.get("licence"), "licence_url": row.get("licence_url")}


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Openverse reference media")
    parser.add_argument("--query", required=True)
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--min-side", type=int, default=DEFAULT_MIN_SIDE)
    ns = parser.parse_args(argv)
    result = search(ns.query, page_size=ns.limit, min_side=ns.min_side)
    print(json.dumps(result, indent=2))
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
