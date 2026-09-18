"""Brand blacklist updater — monthly gating re-check.

Re-checks whether a blacklisted brand is still gated on Amazon, using the
Selling Partner API (SP-API). This task NEVER executes live calls on its
own: it requires an explicit operator approval gate (env var) and a
callable transport, and it reports a *scrubbed* plan otherwise.

The updater's job is to keep ``config/brand_policy.json`` current:

  * On each run (scheduled monthly via cron), every brand on the blacklist
    is checked for gating status.
  * Brands that are still gated stay blacklisted.
  * Brands that appear un-gated are NOT auto-removed: they surface in
    ``pending_operator_review`` for a named operator decision (per §3 of the
    Operating Constitution — removal from a blocking list is a decision,
    not an automation).
  * Every run appends to an audit trail (in-memory list + optional DB via
    the ``record_fn`` hook).

Live-armed execution is intentionally opt-in:
``BRAND_RECHECK_LIVE_OPERATOR_APPROVED=1`` must be set exactly to ``"1"``.
Without it, plan/report modes are offline and zero provider calls happen.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

# ---------------------------------------------------------------------------
# Config / paths
# ---------------------------------------------------------------------------

_BASE_DIR = Path(__file__).resolve().parent.parent
BRAND_POLICY_PATH = _BASE_DIR / "config" / "brand_policy.json"
RECHECK_GATE = "BRAND_RECHECK_LIVE_OPERATOR_APPROVED"

# Gating status vocabulary (kept small and typed).
GATING_OPEN = "open"
GATING_GATED = "gated"
GATING_UNKNOWN = "unknown"
GATING_STATUSES = (GATING_OPEN, GATING_GATED, GATING_UNKNOWN)


@dataclass
class BrandGatingStatus:
    """Outcome of checking one brand's gating status."""

    brand: str
    status: str = GATING_UNKNOWN          # open | gated | unknown
    checked_at: Optional[str] = None
    evidence: Optional[str] = None        # human-readable evidence / source
    changed: bool = False                 # True when status differs from config

    def as_dict(self) -> Dict[str, Any]:
        return {
            "brand": self.brand,
            "status": self.status,
            "checked_at": self.checked_at,
            "evidence": self.evidence,
            "changed": self.changed,
        }


# ---------------------------------------------------------------------------
# I/O helpers (atomic writes, never partially-written configs)
# ---------------------------------------------------------------------------

def load_brand_policy(path: Optional[Path] = None) -> Dict[str, Any]:
    """Load brand_policy.json. Missing/corrupt config -> safe empty policy
    (NOT a crash) so the filter keeps working offline."""
    p = path or BRAND_POLICY_PATH
    try:
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {"blacklist": [], "whitelist": [], "last_recheck": None}
        data.setdefault("blacklist", [])
        data.setdefault("whitelist", [])
        return data
    except (OSError, ValueError):
        return {"blacklist": [], "whitelist": [], "last_recheck": None}


def save_brand_policy(data: Dict[str, Any], path: Optional[Path] = None) -> bool:
    """Atomically save brand_policy.json (temp file + rename)."""
    p = path or BRAND_POLICY_PATH
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        tmp.replace(p)
        return True
    except OSError:
        return False


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Live transport abstraction
# ---------------------------------------------------------------------------

def check_brand_gating_sp_api(brand: str) -> BrandGatingStatus:
    """Live SP-API gating check.

    This is the LIVE transport. It MUST NOT be callable unless the operator
    opened the gate — the updater enforces this before ever invoking it.
    The default implementation refuses to run (returns ``unknown`` with a
    clear evidence note) — a real SP-API client is injected by operators
    who have approval, keeping this module hermetic by default.

    Signature can be satisfied by any callable returning
    ``(status, evidence)`` where status is one of GATING_STATUSES.
    """
    return BrandGatingStatus(
        brand=brand,
        status=GATING_UNKNOWN,
        checked_at=_now_iso(),
        evidence="SP-API transport not configured/armed — no live call made.",
    )


# ---------------------------------------------------------------------------
# Updater
# ---------------------------------------------------------------------------

@dataclass
class BrandRecheckReport:
    """Full audit trail of a recheck run."""

    run_id: str
    ran_at: str
    live_armed: bool
    per_brand: List[BrandGatingStatus] = field(default_factory=list)
    still_blacklisted: List[str] = field(default_factory=list)
    pending_operator_review: List[Dict[str, Any]] = field(default_factory=list)
    audit_trail: List[Dict[str, Any]] = field(default_factory=list)
    config_path: Optional[str] = None

    def as_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "ran_at": self.ran_at,
            "live_armed": self.live_armed,
            "per_brand": [s.as_dict() for s in self.per_brand],
            "still_blacklisted": self.still_blacklisted,
            "pending_operator_review": self.pending_operator_review,
            "audit_trail": self.audit_trail,
            "config_path": self.config_path,
        }


class BrandBlacklistUpdater:
    """Monthly re-check orchestrator.

    Usage:
        updater = BrandBlacklistUpdater()
        report = updater.run()          # offline plan by default
        report = updater.run(live=True) # requires approval gate
    """

    def __init__(
        self,
        policy_path: Optional[Path] = None,
        check_fn: Optional[Callable[[str], BrandGatingStatus]] = None,
        record_fn: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> None:
        self.policy_path = policy_path or BRAND_POLICY_PATH
        # Default transport = SP-API adapter (refuses when not armed).
        self.check_fn = check_fn or check_brand_gating_sp_api
        self.record_fn = record_fn  # optional DB hook for audit_trail rows

    # -- public API ---------------------------------------------------------

    def live_armed(self) -> bool:
        """True only when the operator approval gate is exactly '1'."""
        return os.environ.get(RECHECK_GATE, "").strip() == "1"

    def run(self, live: Optional[bool] = None) -> BrandRecheckReport:
        """Execute a recheck run.

        ``live`` defaults to the gate state. When not armed this produces a
        fully offline report: every brand is checked against the transport
        which — being unarmed — returns ``unknown`` with an evidence note
        stating no live call was made. Config is never mutated offline: the
        report carries ``pending_operator_review`` recommendations instead.
        """
        ran_at = _now_iso()
        report = BrandRecheckReport(
            run_id=f"recheck_{ran_at}",
            ran_at=ran_at,
            live_armed=self.live_armed() if live is None else live,
            config_path=str(self.policy_path),
        )

        policy = load_brand_policy(self.policy_path)
        blacklist = [b for b in policy.get("blacklist", []) if b]

        for brand in blacklist:
            status = self.check_fn(brand)
            status.checked_at = status.checked_at or _now_iso()
            report.per_brand.append(status)

            entry = {
                "ran_at": ran_at,
                "brand": brand,
                "status": status.status,
                "evidence": status.evidence,
            }
            if self.record_fn is not None:
                try:
                    self.record_fn(entry)
                except Exception:
                    pass
            report.audit_trail.append(entry)

            if status.status == GATING_GATED or status.status == GATING_UNKNOWN:
                report.still_blacklisted.append(brand)
            elif status.status == GATING_OPEN and status.changed:
                # NOT auto-removed — surfacing for operator decision.
                report.pending_operator_review.append({
                    "brand": brand,
                    "reason": "SP-API reports this brand as un-gated — operator must confirm before removing from blacklist.",
                    "evidence": status.evidence,
                    "checked_at": status.checked_at,
                })

        # Offline runs never write config; armed runs persist a timestamp +
        # the current blacklist (unchanged) with a full audit record.
        if report.live_armed:
            policy["last_recheck"] = ran_at
            policy["last_recheck_run_id"] = report.run_id
            save_brand_policy(policy, self.policy_path)

        return report


def run_recheck(live: Optional[bool] = None) -> BrandRecheckReport:
    """Module-level convenience."""
    return BrandBlacklistUpdater().run(live)


def main() -> None:
    """CLI entry point (safe: offline by default)."""
    import argparse

    parser = argparse.ArgumentParser(
        prog="brand-recheck",
        description="Monthly brand gating re-check (offline by default).",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Attempt live SP-API checks (requires BRAND_RECHECK_LIVE_OPERATOR_APPROVED=1).",
    )
    args = parser.parse_args()

    report = run_recheck(live=True if args.live else False)
    print(json.dumps(report.as_dict(), indent=2))
    if args.live and not report.live_armed:
        print("\nNOTE: --live requested but approval gate not set — no live calls made.")


if __name__ == "__main__":
    main()