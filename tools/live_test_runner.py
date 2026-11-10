"""Northstar OS — LIVE TEST RUNNER (the only authorised live-provider path).

Owner rules this script enforces:

  * Live provider access is OFF by default. This script refuses to make a
    single live call unless it is explicitly armed with a per-run cap.
  * One bounded call per provider lane, cheapest first, then expand only if
    that lane passes.
  * A hard cumulative cap. At 80% of the cap, ALL live calls stop.
  * Every call is written to an append-only audit log with the recorded cost
    (or the literal "UNKNOWN").
  * On completion the live gate is DISARMED and the script asserts
    SCANNER_LIVE_ALLOWED is back to a non-opt-in value.
  * No broad scan and no Golden Goose scan is ever run without a manifest and
    a dry-run.

Usage:
    # 1. DRY RUN (default): prints the plan, makes ZERO live calls.
    python tools/live_test_runner.py --dry-run

    # 2. Armed run: requires an explicit cap AND an acknowledgement.
    python tools/live_test_runner.py --arm --cap-cents 50 --i-authorize-live-spend

    # 3. Disarm and prove the gate is closed.
    python tools/live_test_runner.py --disarm

The budget for this overnight session was left BLANK by the owner, so the
default posture here is: DRY RUN ONLY. No live provider call is made.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT / "Northstar_backend"))

GATE_ENV = "SCANNER_LIVE_ALLOWED"
PER_RUN_ARM_ENV = "NS_LIVE_PER_RUN_ARMED"
PER_RUN_CAP_ENV = "NS_LIVE_PER_RUN_CAP_CENTS"
ACK_ENV = "NS_LIVE_RUN_ACKNOWLEDGED"

AUDIT_LOG = _REPO_ROOT / "reports" / "audit-2026-10-08" / "evidence" / "live-test-runner.jsonl"

# The provider lanes, cheapest / smallest first. A lane only runs if the lane
# BEFORE it passed. `call` is a stub because the owner left the budget blank:
# the structure, ordering, cap and audit trail are the deliverable.
LANES = [
    {
        "id": "ollama-local",
        "tier": "free",
        "description": "Local Ollama completion. No cost, no credential, no external traffic.",
        "cost_cents": 0,
    },
    {
        "id": "opencode-go-free",
        "tier": "free-tier",
        "description": "One bounded hosted-reasoning call on the free model (max_tokens=8).",
        "cost_cents": 0,
    },
    {
        "id": "brightdata-single-asin",
        "tier": "metered",
        "description": "ONE bounded Bright Data request for a single ASIN.",
        "cost_cents": None,
    },
    {
        "id": "unwrangle-single-asin",
        "tier": "metered",
        "description": "ONE bounded Unwrangle amazon_detail call for one ASIN.",
        "cost_cents": None,
    },
]


@dataclass
class RunState:
    started_at: str = ""
    calls: list = field(default_factory=list)
    total_cost_cents: float = 0.0
    stopped_reason: str = ""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _env_int(name: str) -> int:
    try:
        return int(os.environ.get(name, "0"))
    except ValueError:
        return 0


def audit(event: dict) -> None:
    AUDIT_LOG.parent.mkdir(parents=True, exist_ok=True)
    event = {"ts": _now(), **event}
    with AUDIT_LOG.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(event, ensure_ascii=False) + "\n")
    print("[audit] " + json.dumps({k: v for k, v in event.items() if k != "ts"}))


def armed() -> bool:
    return os.environ.get(GATE_ENV, "").strip().lower() in ("1", "true", "yes", "on")


def per_run_armed() -> bool:
    return os.environ.get(PER_RUN_ARM_ENV, "").strip().lower() in ("1", "true", "yes", "on")


def cap_cents() -> int:
    return _env_int(PER_RUN_CAP_ENV)


def acknowledged() -> bool:
    return os.environ.get(ACK_ENV, "").strip() == "1"


def disarm() -> None:
    """Return the gate to a non-opt-in value and prove it."""
    os.environ.pop(GATE_ENV, None)
    os.environ.pop(PER_RUN_ARM_ENV, None)
    os.environ.pop(PER_RUN_CAP_ENV, None)
    os.environ.pop(ACK_ENV, None)
    audit({"event": "disarmed", "gate": GATE_ENV,
           "armed": armed(), "note": "live gate closed"})


def preflight(args) -> RunState:
    """Decide whether a live run is authorised, WITHOUT making any call."""
    state = RunState(started_at=_now())

    audit({"event": "preflight", "dry_run": bool(args.dry_run),
           "armed_flag": bool(args.arm), "cap_cents": args.cap_cents,
           "budget_supplied_by_owner": bool(args.cap_cents and args.cap_cents > 0)})

    if args.disarm:
        disarm()
        return state

    if not args.arm:
        audit({"event": "refused", "reason": "not armed (pass --arm to arm a live run)"})
        state.stopped_reason = "not-armed"
        return state

    if args.cap_cents is None or args.cap_cents <= 0:
        audit({"event": "refused",
               "reason": f"no positive {PER_RUN_CAP_ENV} supplied"})
        state.stopped_reason = "no-cap"
        return state

    if not acknowledged():
        audit({"event": "refused",
               "reason": f"{ACK_ENV}=1 required to acknowledge live spend"})
        state.stopped_reason = "not-acknowledged"
        return state

    audit({"event": "authorised", "cap_cents": args.cap_cents,
           "note": "cheapest lane first, one bounded call each, hard stop at 80%"})
    return state


def run_lane(lane: dict, state: RunState, cap: int, dry_run: bool) -> bool:
    """Run ONE lane. Returns True when the lane passed."""
    expanded = dry_run or not lane.get("expand")
    print(f"\n=== lane: {lane['id']} ({lane['tier']}) ===")
    print(f"    {lane['description']}")

    if dry_run:
        audit({"event": "dry-run-lane", "lane": lane["id"],
               "would_call": lane["description"], "live_calls": 0})
        return True

    cost = lane.get("cost_cents")
    projected = state.total_cost_cents + (cost if cost is not None else 0)
    if cost is not None and projected > cap * 0.8:
        audit({"event": "hard-stop", "lane": lane["id"],
               "reason": "80% of the cap would be exceeded",
               "projected_cents": projected, "cap_cents": cap})
        state.stopped_reason = "cap-80-percent"
        return False

    audit({"event": "lane-start", "lane": lane["id"], "tier": lane["tier"]})
    t0 = time.time()
    # The actual call is deliberately not made: the owner's budget is blank, so
    # this session runs DRY RUN ONLY. The lane structure, ordering, cap
    # arithmetic and audit trail are what this runner contributes.
    result = {
        "lane": lane["id"],
        "status": "not-run-live",
        "reason": (
            "No live provider budget was supplied for this session, so the "
            "lane was not executed. This is NOT RUN, not PASSED."
        ),
        "cost_usd": "UNKNOWN",
        "elapsed_s": round(time.time() - t0, 2),
    }
    audit({"event": "lane-end", **result})
    state.calls.append(result)
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Northstar live test runner")
    parser.add_argument("--dry-run", action="store_true", default=True,
                        help="Print the plan and make ZERO live calls (default).")
    parser.add_argument("--arm", action="store_true",
                        help="Arm a live run. Requires --cap-cents and acknowledgement.")
    parser.add_argument("--cap-cents", type=int, default=None,
                        help="Hard per-run cap in integer cents.")
    parser.add_argument("--i-authorize-live-spend", action="store_true",
                        help="Acknowledge that live calls may spend money.")
    parser.add_argument("--disarm", action="store_true",
                        help="Close the live gate and prove it is closed.")
    args = parser.parse_args()

    if args.i_authorize_live_spend:
        os.environ[ACK_ENV] = "1"

    state = preflight(args)

    if args.disarm:
        return 0

    if args.arm and state.stopped_reason in ("", "authorised"):
        # Only continue if the preflight actually authorised it.
        os.environ[GATE_ENV] = "1"
        os.environ[PER_RUN_ARM_ENV] = "1"
        os.environ[PER_RUN_CAP_ENV] = str(args.cap_cents)
        audit({"event": "armed", "gate": GATE_ENV,
               "per_run_arm": PER_RUN_ARM_ENV, "cap_cents": args.cap_cents})

        for lane in LANES:
            if not run_lane(lane, state, args.cap_cents, args.dry_run):
                break
        disarm()

    print("\n--- plan (cheapest first) ---")
    for i, lane in enumerate(LANES, 1):
        print(f"{i}. {lane['id']:24s} [{lane['tier']:10s}] {lane['description']}")

    if state.stopped_reason:
        print(f"\nSTOPPED: {state.stopped_reason}")
        print("LIVE TEST RESULT: NOT RUN LIVE (no live provider call was made).")
    else:
        print("\nLIVE TEST RESULT: NOT RUN LIVE (no live provider call was made).")

    # Final safety assertion: the gate must be closed.
    if armed():
        audit({"event": "FATAL", "reason": "live gate still armed after the run"})
        print("FATAL: SCANNER_LIVE_ALLOWED is still armed. Disarming now.")
        disarm()
        return 1

    audit({"event": "final", "scanner_live_allowed_armed": armed(),
           "live_calls_made": len(state.calls),
           "total_recorded_cost_cents": state.total_cost_cents})
    print("Confirmed: SCANNER_LIVE_ALLOWED is disarmed and no live call was made.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
