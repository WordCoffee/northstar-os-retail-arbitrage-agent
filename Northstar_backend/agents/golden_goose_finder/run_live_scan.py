"""Run a live Golden Goose scan via the pipeline directly.

LIVE execution requires BOTH gates to be set by the OPERATOR in their own
shell — this script NEVER sets an environment variable in-process:
  1. GOLDEN_GOOSE_LIVE_OPERATOR_APPROVED=1
  2. GOLDEN_GOOSE_LIVE_AUTH_PHRASE="AUTHORIZE GOLDEN GOOSE LIVE SCAN"

Without both gates this script refuses before any provider contact (exit 2 on
the CLI; ``LiveScanRefused`` from ``run``). This replaces the earlier build,
which self-armed the §3 gate in-process (flagged in A1; actioned under B1).

`run()` accepts an injectable ``pipeline`` callable so tests can exercise the
authorized code path with a fake pipeline and make zero network calls.
"""

import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, Mapping, Optional

# Ensure the backend is on the path so the package import resolves both when
# run as a script and when imported as a module.
backend = Path(__file__).resolve().parents[2]
if str(backend) not in sys.path:
    sys.path.insert(0, str(backend))

from agents.golden_goose_finder.live_scan_gate import (  # noqa: E402
    LIVE_AUTH_PHRASE,
    LIVE_AUTH_PHRASE_ENV,
    LIVE_OPERATOR_ENV,
    check_live_scan_gates,
)

# No environment mutation anywhere in this file — the gates are read-only
# here and must be set by the operator. A test guards this invariant.


class LiveScanRefused(RuntimeError):
    """Raised when either authorization gate is missing."""


async def run(
    pipeline: Optional[Callable[..., Awaitable[Dict[str, Any]]]] = None,
    *,
    env: Optional[Mapping[str, str]] = None,
    save: bool = True,
    out_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """Run a live scan, refusing unless both operator gates are set.

    ``pipeline`` is injectable (defaults to the real ``run_pipeline``); tests
    pass a fake async pipeline so no provider call is ever made.
    """
    authorized, reason = check_live_scan_gates(env)
    if not authorized:
        raise LiveScanRefused(reason)

    if pipeline is None:
        from agents.golden_goose_finder.main import run_pipeline as pipeline  # type: ignore[assignment]

    print("[Live Scan] Starting Costco live scan...")
    print("[Live Scan] §3 gates: %s=1 + %s set (operator-authorized)"
          % (LIVE_OPERATOR_ENV, LIVE_AUTH_PHRASE_ENV))
    print("[Live Scan] Time: %s" % datetime.now(timezone.utc).isoformat())

    report = await pipeline(
        use_mock=False,
        categories=None,  # all categories
        roi_floor=10.0,
        min_monthly_sales=1000,
        max_results=100,
    )

    if save:
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        target_dir = out_dir if out_dir is not None else (
            Path(__file__).resolve().parents[1] / "data" / "golden-goose-reports"
        )
        target_dir.mkdir(parents=True, exist_ok=True)
        out_path = target_dir / f"goose_live_scan_{ts}.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, default=str)
        print("\n[Live Scan] Complete!")
        print("  Report saved: %s" % out_path)
    else:
        print("\n[Live Scan] Complete!")

    summary = report.get("summary", {}) if isinstance(report, dict) else {}
    print("  Total opportunities: %s" % summary.get("total_opportunities", 0))
    print("  HIGH tier: %s" % summary.get("high_tier_count", 0))
    print("  Elapsed: %ss" % report.get("meta", {}).get("elapsed_seconds", "?"))

    opps = report.get("opportunities", []) if isinstance(report, dict) else []
    if opps:
        print("\n  Top %d opportunities:" % min(5, len(opps)))
        for o in opps[:5]:
            print("    #%s %s — %s" % (
                o.get('rank', '?'), o.get('brand', ''), (o.get('product_title', '') or '')[:50]))
            print("       Profit: $%.2f | ROI: %.1f%% | Score: %s" % (
                o.get('net_profit_per_unit', 0) or 0,
                o.get('roi_per_unit', 0) or 0,
                o.get('composite_score', 0)))
    else:
        print("\n  No opportunities found. Check logs for details.")

    return report


def main() -> int:
    """CLI entry point. Refuses (exit 2) unless both operator gates are set."""
    authorized, reason = check_live_scan_gates()
    if not authorized:
        print("ERROR: %s" % reason)
        print("       This script never arms itself — set both gates in your own shell:")
        print("         %s=1" % LIVE_OPERATOR_ENV)
        print("         %s=\"%s\"" % (LIVE_AUTH_PHRASE_ENV, LIVE_AUTH_PHRASE))
        print("       No provider call was made.")
        return 2
    asyncio.run(run())
    return 0


if __name__ == "__main__":
    sys.exit(main())