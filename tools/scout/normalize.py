"""Normaliser + dedupe (D11 / A19).

Every raw connector hit becomes one finding shape with a canonical licence, a
stable id, and a content hash.  Dedupe is identity-based:
``source:identity``.  Same identity and same hash is a duplicate (counted);
same identity with a different hash is a new *revision* of the same item, and
only the newest revision is kept — the count is reported, never silently lost.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple

from . import licence as licence_engine

REQUIRED = ("source", "url", "title", "licence", "fetched_at")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _sha256(value: Any) -> str:
    body = json.dumps(value, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(body).hexdigest()


def dedupe_key(source: str, identity: str) -> str:
    return f"{source}:{identity}"


def normalise(raw: Dict[str, Any], *, fetched_at: Optional[str] = None) -> Dict[str, Any]:
    """Turn a raw hit into a finding.  Missing required evidence raises."""
    missing = [key for key in ("source", "url", "title") if not str(raw.get(key) or "").strip()]
    if missing:
        raise ValueError(f"raw_hit_missing: {', '.join(missing)}")
    source = str(raw["source"]).strip()
    url = str(raw["url"]).strip()
    title = str(raw["title"]).strip()
    identity = str(raw.get("identity") or url).strip().lower()
    canonical = licence_engine.normalise(raw.get("licence"))
    licence_class = licence_engine.classify(canonical)
    stamp = str(raw.get("fetched_at") or fetched_at or _now())
    content = {
        "title": title,
        "description": str(raw.get("description") or ""),
        "version": raw.get("version"),
        "licence": canonical,
        "stars": raw.get("stars"),
        "downloads": raw.get("downloads"),
    }
    finding: Dict[str, Any] = {
        "id": f"{source}-{hashlib.sha1(dedupe_key(source, identity).encode()).hexdigest()[:12]}",
        "source": source,
        "identity": identity,
        "url": url,
        "title": title,
        "licence": canonical,
        "licence_class": licence_class,
        "commercial_ok": licence_engine.commercial_ok(licence_class),
        "adoptable_licence": licence_engine.is_adoptable_licence(canonical),
        "stars": raw.get("stars"),
        "downloads": raw.get("downloads"),
        "description": str(raw.get("description") or "").strip(),
        "version": raw.get("version"),
        "kind": raw.get("kind") or "item",
        "ecosystem": raw.get("ecosystem"),
        "fetched_at": stamp,
        "content_sha256": _sha256(content),
        "revisions": 1,
    }
    for key, value in raw.items():
        if key in finding or key in ("licence",):
            continue
        if value not in (None, "", [], {}):
            finding[key] = value
    return finding


def dedupe(hits: Iterable[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Collapse by ``source:identity``.  Returns ``(unique, report)``.

    ``report``: ``{"duplicates": n, "revisions": n, "received": n, "kept": n}``.
    """
    unique: Dict[str, Dict[str, Any]] = {}
    duplicates = 0
    revisions = 0
    received = 0
    for hit in hits:
        received += 1
        finding = normalise(hit) if "content_sha256" not in hit else hit
        key = dedupe_key(finding["source"], finding["identity"])
        current = unique.get(key)
        if current is None:
            unique[key] = finding
            continue
        if current["content_sha256"] == finding["content_sha256"]:
            duplicates += 1
            continue
        revisions += 1
        # Keep the newest revision; the count proves the change was seen.
        newer, older = (finding, current) if finding["fetched_at"] >= current["fetched_at"] \
            else (current, finding)
        older["revisions"] = int(older.get("revisions") or 1)
        newer["revisions"] = int(older.get("revisions") or 1) + 1
        unique[key] = newer
    kept = list(unique.values())
    return kept, {"received": received, "kept": len(kept),
                  "duplicates": duplicates, "revisions": revisions}
