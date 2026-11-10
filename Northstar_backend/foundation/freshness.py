"""Observation freshness policy (Master Plan P4-T4).

Every observation carries ``observed_at`` and a per-field maximum age (config).
Semantics for gate purposes:

    within max age        -> OBSERVED   (usable for gates)
    older than max age    -> CACHED     (displayed with age; NOT usable for gates)
    missing / unparseable -> UNKNOWN    (NOT usable for gates)

Config: per-field defaults, overridable via env ``NORTHSTAR_MAX_AGE_<FIELD>_DAYS``.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Optional

OBSERVED = "OBSERVED"
CACHED = "CACHED"
UNKNOWN = "UNKNOWN"

# Field -> default max age in days.
DEFAULT_MAX_AGE_DAYS = {
    "price": 7,
    "bsr": 7,
    "pack": 90,
    "unit_count": 90,
    "net_quantity": 90,
    "package_dimensions": 180,
    "identity_match": 30,
    "default": 30,
}

_ENV_PREFIX = "NORTHSTAR_MAX_AGE_"


def max_age_days(field: str) -> int:
    env_key = _ENV_PREFIX + (field or "default").upper() + "_DAYS"
    raw = os.environ.get(env_key)
    if raw is not None:
        try:
            return max(0, int(raw))
        except (ValueError, TypeError):
            pass
    return DEFAULT_MAX_AGE_DAYS.get(field, DEFAULT_MAX_AGE_DAYS["default"])


def _parse(observed_at) -> Optional[datetime]:
    if not observed_at:
        return None
    try:
        ts = datetime.fromisoformat(str(observed_at).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts


def evaluate(observed_at, field: str = "default", *, now: Optional[datetime] = None) -> dict:
    """Return {state, label, usable_for_gates, age_days, max_age_days}."""
    ts = _parse(observed_at)
    limit = max_age_days(field)
    if ts is None:
        return {"state": UNKNOWN, "label": UNKNOWN, "usable_for_gates": False,
                "age_days": None, "max_age_days": limit}
    ref = now or datetime.now(timezone.utc)
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    age_days = (ref - ts).total_seconds() / 86400.0
    if age_days < 0:
        return {"state": UNKNOWN, "label": UNKNOWN, "usable_for_gates": False,
                "age_days": age_days, "max_age_days": limit}
    if age_days <= limit:
        return {"state": OBSERVED, "label": OBSERVED, "usable_for_gates": True,
                "age_days": round(age_days, 4), "max_age_days": limit}
    return {"state": CACHED, "label": CACHED, "usable_for_gates": False,
            "age_days": round(age_days, 4), "max_age_days": limit}


def gate_state(observed_at, field: str = "default", *, now: Optional[datetime] = None) -> str:
    """State to use for GATE purposes: OBSERVED when usable, else UNKNOWN.

    CACHED is a display label only; beyond max age the gate sees UNKNOWN.
    """
    result = evaluate(observed_at, field, now=now)
    return OBSERVED if result["usable_for_gates"] else UNKNOWN