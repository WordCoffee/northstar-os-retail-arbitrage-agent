"""Usage meter — per-account per-month action counters (Phase H / H5).

Hard caps are the enforcement; credits are the display meter. Counters are
per-account, per-action, per calendar month (UTC), and reset implicitly when
the month changes. Fail-closed: an unknown action or a missing limit is a
deny, never an allow.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Optional, Tuple

# Actions metered per month (see shared/usage-caps.json).
ACTIONS = (
    "chat_t1",
    "gg_scan",
    "listing",
    "post",
    "image",
    "rank_snapshot",
    "alert",
    "autothink_t2",
    "autothink_t3",
)

# Actions that are NOT metered (deterministic reads / showroom).
UNMETERED = ("showroom_read", "health", "catalog_read")


def current_month(now: Optional[datetime] = None) -> str:
    dt = now or datetime.now(timezone.utc)
    return dt.strftime("%Y-%m")


@dataclass
class UsageMeter:
    """In-memory per-account counters keyed (account, month, action)."""

    limits: Dict[str, Dict[str, int]] = field(default_factory=dict)  # plan -> action -> cap
    _counts: Dict[Tuple[str, str, str], int] = field(default_factory=dict)

    # -- limits ---------------------------------------------------------------
    def set_plan_limits(self, plan: str, caps: Dict[str, int]) -> None:
        self.limits[plan] = dict(caps)

    def limit_for(self, plan: str, action: str) -> Optional[int]:
        return (self.limits.get(plan) or {}).get(action)

    # -- counting -------------------------------------------------------------
    def used(self, account: str, action: str, month: Optional[str] = None) -> int:
        return self._counts.get((account, month or current_month(), action), 0)

    def remaining(self, account: str, plan: str, action: str,
                  month: Optional[str] = None) -> int:
        cap = self.limit_for(plan, action)
        if cap is None:
            return 0
        return max(0, cap - self.used(account, action, month))

    def check(self, account: str, plan: str, action: str,
              month: Optional[str] = None) -> Dict[str, object]:
        """Decide whether an action may proceed. Fail-closed on unknown action."""
        if action not in ACTIONS:
            return {"allowed": False, "reason": "unknown_action", "action": action}
        cap = self.limit_for(plan, action)
        if cap is None:
            return {"allowed": False, "reason": "action_not_in_plan", "action": action,
                    "plan": plan}
        used = self.used(account, action, month)
        allowed = used < cap
        return {
            "allowed": allowed,
            "action": action,
            "plan": plan,
            "used": used,
            "limit": cap,
            "remaining": max(0, cap - used),
            "reason": "ok" if allowed else "cap_reached",
            "upgrade_prompt": None if allowed else (
                "You've reached your %s limit for this month. Upgrade for more." % action
            ),
        }

    def consume(self, account: str, plan: str, action: str,
                n: int = 1, month: Optional[str] = None) -> Dict[str, object]:
        """Check then record. Refuses (no partial charge) when the cap is hit."""
        m = month or current_month()
        decision = self.check(account, plan, action, m)
        if not decision["allowed"]:
            return decision
        if decision["remaining"] < n:
            decision["allowed"] = False
            decision["reason"] = "cap_reached"
            decision["upgrade_prompt"] = (
                "You've reached your %s limit for this month. Upgrade for more." % action
            )
            return decision
        key = (account, m, action)
        self._counts[key] = self._counts.get(key, 0) + n
        decision["used"] = self._counts[key]
        decision["remaining"] = max(0, decision["limit"] - self._counts[key])
        return decision

    def summary(self, account: str, plan: str,
                month: Optional[str] = None) -> Dict[str, object]:
        m = month or current_month()
        caps = self.limits.get(plan) or {}
        return {
            "account": account,
            "plan": plan,
            "month": m,
            "actions": {
                a: {
                    "used": self.used(account, a, m),
                    "limit": caps.get(a),
                    "remaining": (max(0, caps[a] - self.used(account, a, m))
                                  if a in caps else None),
                }
                for a in ACTIONS
            },
        }


def meter_from_caps(path: Optional[str] = None) -> UsageMeter:
    """Build a meter whose limits come from shared/usage-caps.json."""
    import json as _json
    import os as _os
    root = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
    with open(path or _os.path.join(root, "shared", "usage-caps.json"),
              "r", encoding="utf-8") as fh:
        data = _json.load(fh)
    meter = UsageMeter()
    for plan, tier in data["tiers"].items():
        meter.set_plan_limits(plan, tier["caps"])
    return meter
