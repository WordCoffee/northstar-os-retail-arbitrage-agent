"""SessionStore — JSON-backed command history for AutothinK.

Auto-loads on server start, persists append-only, and caps history length so
the file stays small. Pure file IO — no network, no credentials.
"""

import json
import os
from datetime import datetime, timezone
from typing import Dict, List, Optional

_DEFAULT_MEMORY_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "memory")
_DEFAULT_PATH = os.path.join(_DEFAULT_MEMORY_DIR, "session-history.json")

MAX_ENTRIES = 50


def _safe_org(org_id: Optional[str]) -> str:
    """Filesystem-safe tenant key. Never empty: unknown tenant == 'anonymous'."""
    raw = (org_id or "").strip().lower()
    if not raw:
        return "anonymous"
    return "".join(c if (c.isalnum() or c in "-_.") else "_" for c in raw)[:64]


def store_path_for_org(org_id: Optional[str], base_dir: Optional[str] = None) -> str:
    """Per-tenant history file. Tenants never share a history store."""
    parent = base_dir or _DEFAULT_MEMORY_DIR
    return os.path.join(parent, "session-history-%s.json" % _safe_org(org_id))


class SessionStore:
    """Tenant-scoped command history for AutothinK.

    One file per organization, so a tenant can never read another tenant's
    entries. Auto-loads on construction, persists append-only, and caps
    history length so the file stays small. Pure file IO — no network, no
    credentials.
    """

    def __init__(self, path: Optional[str] = None, max_entries: int = MAX_ENTRIES):
        self.path = path or _DEFAULT_PATH
        self.max_entries = max_entries
        self._history: List[Dict] = self._load()

    def _load(self) -> List[Dict]:
        if not os.path.exists(self.path):
            return []
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                return data[-self.max_entries:]
            return []
        except (OSError, json.JSONDecodeError):
            return []

    def _save(self) -> None:
        parent = os.path.dirname(self.path)
        if parent and not os.path.isdir(parent):
            os.makedirs(parent, exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self._history[-self.max_entries:], f, ensure_ascii=False, indent=2)

    def all(self) -> List[Dict]:
        return list(self._history)

    def add(self, entry: Dict) -> None:
        stamped = dict(entry)
        stamped.setdefault("timestamp", datetime.now(timezone.utc).isoformat())
        self._history.append(stamped)
        self._history = self._history[-self.max_entries:]
        self._save()

    def clear(self) -> None:
        self._history = []
        if os.path.exists(self.path):
            os.remove(self.path)