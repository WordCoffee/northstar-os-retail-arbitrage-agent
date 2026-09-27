"""AutothinK ChromeControl -> Northstar bridge (offline, read-only on CC DB).

Reads the AutothinK ChromeControl durable store (timeline, tabs, pause state) and
mirrors summary evidence into the Northstar canonical database. Never mutates the
ChromeControl database. No network, no browser automation.
"""
from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .store import PipelineStore


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def default_cc_db_path() -> str:
    explicit = os.getenv("NORTHSTAR_CC_DB_PATH")
    if explicit:
        return explicit
    local = os.getenv("LOCALAPPDATA")
    if local:
        return str(Path(local) / "NorthstarOS" / "data" / "northstar.db")
    return str(Path.home() / ".local" / "share" / "northstar-os" / "data" / "northstar.db")


def read_cc_state(cc_db_path: Optional[str] = None) -> Dict[str, Any]:
    """Read AutothinK ChromeControl state read-only. Returns dict; missing DB -> empty."""
    path = cc_db_path or default_cc_db_path()
    if not os.path.exists(path):
        return {"available": False, "cc_db_path": path, "tabs": [], "timeline": [], "pause": None}

    uri = f"file:{Path(path).as_posix()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    out: Dict[str, Any] = {"available": True, "cc_db_path": path}

    def safe(query, params=()):
        try:
            return [dict(r) for r in conn.execute(query, params).fetchall()]
        except sqlite3.Error:
            return []

    out["tabs"] = safe("SELECT * FROM cc_tabs ORDER BY last_seen_at DESC")
    out["timeline"] = safe("SELECT * FROM cc_timeline ORDER BY created_at DESC LIMIT 200")
    pause = safe("SELECT * FROM cc_pause_state WHERE active=1 ORDER BY created_at DESC LIMIT 1")
    out["pause"] = pause[0] if pause else None
    conn.close()
    return out


def sync_to_northstar(store: Optional[PipelineStore] = None, *, cc_db_path: Optional[str] = None) -> Dict[str, Any]:
    """Mirror ChromeControl state into Northstar evidence rows (append-only)."""
    store = store or PipelineStore()
    state = read_cc_state(cc_db_path)
    if not state.get("available"):
        return {"synced": 0, "available": False, "cc_db_path": state.get("cc_db_path")}

    synced = 0
    for t in state.get("tabs", []):
        store.add_evidence(None, None, {
            "source": "chromecontrol", "source_url": t.get("url"),
            "field_name": "cc_tab", "field_value": f"{t.get('service')}:{t.get('observed_login_state')}",
            "evidence_class": "cached_source_snapshot", "capture_status": "captured",
            "limitations": "AutothinK ChromeControl tab registry (no credentials/sessions captured).",
            "metadata": {"target_id": t.get("target_id"), "human_owned": t.get("human_owned")},
        })
        synced += 1
    pause = state.get("pause")
    if pause:
        store.add_evidence(None, None, {
            "source": "chromecontrol", "field_name": "cc_pause_state",
            "field_value": pause.get("pause_state"), "evidence_class": "cached_source_snapshot",
            "capture_status": "captured",
            "limitations": "AutothinK ChromeControl pause state.",
            "metadata": {"reason": pause.get("reason"), "next_action": pause.get("next_action")},
        })
        synced += 1
    return {"synced": synced, "available": True, "cc_db_path": state.get("cc_db_path"),
            "pause_state": (pause or {}).get("pause_state") if pause else None,
            "tab_count": len(state.get("tabs", []))}


def main(argv=None) -> int:
    import sys
    from .cli_common import print_json, print_network_confirmation
    out = sync_to_northstar()
    print_network_confirmation(0)
    print_json(out)
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
