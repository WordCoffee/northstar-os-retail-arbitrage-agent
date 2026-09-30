"""Golden Goose Top-5 selection (Master Plan P5-T3).

Pure, deterministic selection of the top ``n`` opportunities by ``resale_score``
ONLY among those that qualify. NEVER padded: if fewer than ``n`` qualify, fewer
are returned and every excluded candidate carries its blocking gate.

Qualification (all required):
  * match/decision state at QUALIFIED_FOR_REVIEW or better
  * policy_exclusion_flag == 0
  * economics_complete is True
  * net_per_unit >= floor (default $5.00)
"""
from __future__ import annotations

import hashlib
import json
from typing import Optional

from .golden_goose_decision import (
    QUALIFIED_FOR_REVIEW, ECONOMICS_COMPLETE, APPROVAL_REQUIRED, PURCHASE_READY,
)

DEFAULT_N = 5
DEFAULT_FLOOR = 5.00
ELIGIBLE_STATES = {QUALIFIED_FOR_REVIEW, ECONOMICS_COMPLETE, APPROVAL_REQUIRED,
                   PURCHASE_READY}


def _blocking_reason(c: dict, floor: float) -> Optional[str]:
    """Precedence-ordered blocking gate, or None if the candidate qualifies."""
    if int(c.get("policy_exclusion_flag") or 0) != 0:
        return "policy_exclusion"
    state = c.get("state")
    if state not in ELIGIBLE_STATES:
        return "below_qualified_for_review"
    if not bool(c.get("economics_complete")):
        return "economics_incomplete"
    net = c.get("net_per_unit")
    if net is None:
        return "net_unknown"
    try:
        if float(net) < float(floor):
            return "below_net_floor"
    except (TypeError, ValueError):
        return "net_unknown"
    return None


def _inputs_hash(candidates: list) -> str:
    payload = sorted(
        ({"item_id": c.get("item_id"), "resale_score": c.get("resale_score"),
          "state": c.get("state")} for c in candidates),
        key=lambda d: str(d["item_id"]))
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()


def select_top5(candidates: list, *, n: int = DEFAULT_N, floor: float = DEFAULT_FLOOR) -> dict:
    cands = list(candidates or [])
    eligible, blocked = [], []
    for c in cands:
        reason = _blocking_reason(c, floor)
        if reason is None:
            eligible.append(c)
        else:
            blocked.append({"item_id": c.get("item_id"), "blocking_gate": reason})

    # Deterministic: score desc, then item_id asc.
    def _score(c):
        try:
            return float(c.get("resale_score") or 0.0)
        except (TypeError, ValueError):
            return 0.0
    eligible_sorted = sorted(eligible, key=lambda c: (-_score(c), str(c.get("item_id"))))

    selected = eligible_sorted[:max(0, int(n))]
    return {
        "selected": selected,
        "selected_count": len(selected),
        "qualifying_count": len(eligible_sorted),
        "considered_count": len(cands),
        "blocked": blocked,
        "padded": False,
        "n": int(n),
        "floor": float(floor),
        "inputs_hash": _inputs_hash(cands),
        "note": ("fewer than n qualified; nothing padded" if len(selected) < int(n) else ""),
    }