"""Connector interface (D11 / A18).

One shape for every source: ``search(query, limit) -> list[raw hit]``.
``parse(payload, query)`` is pure and is what the offline tests exercise, so a
recorded payload can be replayed without a socket.

A raw hit carries, at minimum:
``source, url, title, licence, fetched_at`` plus ``stars``/``downloads`` when
the source publishes them.  Normalisation (A19) turns it into a finding.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def raw_hit(*, source: str, identity: str, url: str, title: str,
            licence: str, fetched_at: Optional[str] = None,
            stars: Optional[int] = None, downloads: Optional[int] = None,
            description: str = "", version: Optional[str] = None,
            kind: str = "item", ecosystem: Optional[str] = None,
            **extra: Any) -> Dict[str, Any]:
    """Build one uniform raw hit.  Unknowns stay ``None``; never invented."""
    hit: Dict[str, Any] = {
        "source": source,
        "identity": identity,
        "url": url,
        "title": title,
        "licence": licence or "unknown",
        "fetched_at": fetched_at or now(),
        "stars": stars,
        "downloads": downloads,
        "description": description or "",
        "version": version,
        "kind": kind,
        "ecosystem": ecosystem,
    }
    hit.update({key: value for key, value in extra.items() if value not in (None, "", [], {})})
    return hit


def _int(value: Any) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


class Connector:
    """Base connector.  ``fetch`` does network; ``parse`` is pure."""

    name = "base"
    kind = "item"
    ecosystem: Optional[str] = None
    last_payload: Optional[Any] = None

    def fetch(self, query: str, limit: int) -> Any:  # pragma: no cover - network
        raise NotImplementedError

    def parse(self, payload: Any, query: str = "") -> List[Dict[str, Any]]:
        raise NotImplementedError

    def search(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        payload = self.fetch(query, limit)
        self.last_payload = payload
        return self.parse(payload, query=query)

    def trim(self, payload: Any, keep: int = 3) -> Any:
        """Fixture-size reduction.  Preserves real values, only drops items."""
        return payload

    def record(self, query: str, limit: int = 3) -> Dict[str, Any]:
        payload = self.fetch(query, limit)
        return {
            "source": self.name,
            "query": query,
            "recorded_at": now(),
            "payload": self.trim(payload),
        }
