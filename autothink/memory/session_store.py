"""SessionStore — JSON-backed command history for AutoThink.

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


class SessionStore:
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