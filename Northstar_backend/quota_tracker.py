"""Layer 4 - Dual quota tracker (offline, header-driven only).

Per-app, per-phase counters for the 6 RapidAPI pool apps + DataForSEO.
State is persisted to quota_tracker.json. Counters are updated ONLY from
response headers (never estimated). Exhaustion is explicit (set from a
403/429/quota header seen this run, or operator drain).
"""

import json
import os
from datetime import datetime, timezone

QUOTA_PATH = os.environ.get("QUOTA_TRACKER_PATH", "quota_tracker.json")

RAPIDAPI_APPS = [
    "RAPIDAPI_BDC",
    "RAPIDAPI_REALTIME",
    "RAPIDAPI_AXESSO",
    "RAPIDAPI_PRICING",
    "RAPIDAPI_ONLINE",
    "RAPIDAPI_SCOUT",
]
PHASES = ["discovery", "enrichment"]
ALL_APPS = RAPIDAPI_APPS + ["DATAFORSEO"]


def _empty_phase():
    return {"used": 0, "limit": None, "remaining": None, "exhausted": False,
            "last_reset": None, "updated_at": None}


def _empty_state():
    apps = {a: {p: _empty_phase() for p in PHASES} for a in ALL_APPS}
    return {"schema_version": 1, "updated_at": None, "apps": apps}


def load_state(path: str = QUOTA_PATH) -> dict:
    if not os.path.exists(path):
        return _empty_state()
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_state(state: dict, path: str = QUOTA_PATH) -> None:
    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


def _app_phase(state, app, phase):
    return state["apps"][app][phase]


def update_from_headers(app: str, phase: str, headers: dict, path: str = QUOTA_PATH) -> dict:
    """Update counters for (app, phase) strictly from response headers.

    Reads only headers that contain 'limit'/'remaining'/'reset'. Never
    estimates. Returns the updated state.
    """
    state = load_state(path)
    slot = _app_phase(state, app, phase)
    touched = False
    if isinstance(headers, dict):
        for k, v in headers.items():
            kl = k.lower()
            if "remaining" in kl:
                try:
                    slot["remaining"] = int(v)
                    touched = True
                except (TypeError, ValueError):
                    pass
            elif "limit" in kl and "hard" not in kl:
                try:
                    slot["limit"] = int(v)
                    touched = True
                except (TypeError, ValueError):
                    pass
            elif "reset" in kl:
                slot["last_reset"] = v
        # Derive used when both limit and remaining are known (header-derived only).
        if isinstance(slot["limit"], int) and isinstance(slot["remaining"], int):
            slot["used"] = slot["limit"] - slot["remaining"]
    if touched:
        slot["updated_at"] = datetime.now(timezone.utc).isoformat()
        save_state(state, path)
    return state


def mark_exhausted(app: str, phase: str, reason: str = "quota", path: str = QUOTA_PATH) -> dict:
    state = load_state(path)
    slot = _app_phase(state, app, phase)
    slot["exhausted"] = True
    slot["exhausted_reason"] = reason
    slot["updated_at"] = datetime.now(timezone.utc).isoformat()
    save_state(state, path)
    return state


def is_exhausted(app: str, phase: str, state: dict = None, path: str = QUOTA_PATH) -> bool:
    state = state or load_state(path)
    return bool(_app_phase(state, app, phase).get("exhausted"))


def record_used(app: str, phase: str, n: int = 1, path: str = QUOTA_PATH) -> dict:
    """Increment the used counter for a confirmed request (header update is
    preferred; this is only used when no rate-limit header was returned)."""
    state = load_state(path)
    slot = _app_phase(state, app, phase)
    slot["used"] = (slot.get("used") or 0) + n
    slot["updated_at"] = datetime.now(timezone.utc).isoformat()
    save_state(state, path)
    return state
