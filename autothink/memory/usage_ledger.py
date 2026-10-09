"""UsageLedger — per-tenant AutothinK metering.

Append-only JSONL. One event per model run. Cost is recorded ONLY when the
provider reports it; anything else is the literal string "UNKNOWN" and never
an estimate or a zero. Local Ollama runs cost 0 to the operator, which is
still a fact about a real run, not an unknown — but it is recorded as
``cost_usd: 0.0`` only for the local lane, and ``cost_basis: "local, no
provider charge"``.
"""

from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone
from typing import Dict, List, Optional

_DEFAULT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "audit",
    "usage-ledger.jsonl",
)

_LOCK = threading.Lock()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_org(org_id: Optional[str]) -> str:
    raw = (org_id or "").strip().lower()
    if not raw:
        return "anonymous"
    return "".join(c if (c.isalnum() or c in "-_.") else "_" for c in raw)[:64]


class UsageLedger:
    """Tenant-scoped, append-only usage events."""

    def __init__(self, path: Optional[str] = None):
        self.path = path or _DEFAULT_PATH
        parent = os.path.dirname(self.path)
        if parent and not os.path.isdir(parent):
            os.makedirs(parent, exist_ok=True)

    # -- write -----------------------------------------------------------

    def record(self, *, org_id: Optional[str], user_id: Optional[str],
               provider: str, model: Optional[str], tier: Optional[str],
               task_class: Optional[str], prompt_tokens: Optional[int],
               completion_tokens: Optional[int], ok: bool,
               cost_usd: Optional[float] = None,
               cost_basis: Optional[str] = None,
               run_id: Optional[str] = None,
               idempotency_key: Optional[str] = None) -> Dict:
        event = {
            "ts": _now(),
            "org_id": _safe_org(org_id),
            "user_id": user_id or "unknown",
            "run_id": run_id,
            "idempotency_key": idempotency_key,
            "provider": provider,
            "model": model,
            "tier": tier,
            "task_class": task_class,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": (
                (prompt_tokens or 0) + (completion_tokens or 0)
                if (prompt_tokens is not None or completion_tokens is not None)
                else None
            ),
            "ok": bool(ok),
            # Honesty contract: never estimate, never default to 0.
            "cost_usd": cost_usd if cost_usd is not None else "UNKNOWN",
            "cost_basis": cost_basis or "provider did not report a cost",
        }
        line = json.dumps(event, ensure_ascii=False)
        with _LOCK:
            with open(self.path, "a", encoding="utf-8") as fh:
                fh.write(line + "\n")
        return event

    # -- read ------------------------------------------------------------

    def events(self, *, org_id: Optional[str] = None) -> List[Dict]:
        if not os.path.exists(self.path):
            return []
        out: List[Dict] = []
        try:
            with open(self.path, "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        event = json.loads(line)
                    except ValueError:
                        continue
                    if org_id is not None and event.get("org_id") != _safe_org(org_id):
                        continue
                    out.append(event)
        except OSError:
            return []
        return out

    def summary(self, *, org_id: Optional[str] = None) -> Dict:
        """Per-tenant totals. UNKNOWN costs are counted, never summed."""
        events = self.events(org_id=org_id)
        runs = len(events)
        ok_runs = sum(1 for e in events if e.get("ok"))
        tokens = 0
        token_basis_seen = False
        unknown_cost_runs = 0
        known_cost_total = 0.0
        for e in events:
            for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
                pass
            pt = e.get("prompt_tokens") or 0
            ct = e.get("completion_tokens") or 0
            if e.get("prompt_tokens") is not None or e.get("completion_tokens") is not None:
                token_basis_seen = True
                tokens += int(pt) + int(ct)
            cost = e.get("cost_usd")
            if cost == "UNKNOWN" or cost is None:
                unknown_cost_runs += 1
            else:
                known_cost_total += float(cost)
        return {
            "runs": runs,
            "ok_runs": ok_runs,
            "failed_runs": runs - ok_runs,
            "tokens": tokens if token_basis_seen else "UNKNOWN",
            "cost_usd_recorded": known_cost_total,
            "runs_with_unknown_cost": unknown_cost_runs,
        }
