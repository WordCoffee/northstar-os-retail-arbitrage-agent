"""Run a live Golden Goose scan via the pipeline directly.

Sets GOLDEN_GOOSE_LIVE_OPERATOR_APPROVED=1 (§3 approval logged 2026-09-17)
and runs the full Costco → Amazon matching pipeline.
"""

import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Set the §3 gate
os.environ["GOLDEN_GOOSE_LIVE_OPERATOR_APPROVED"] = "1"

# Ensure the backend is on the path
backend = Path(__file__).resolve().parents[2]
if str(backend) not in sys.path:
    sys.path.insert(0, str(backend))


async def run():
    from agents.golden_goose_finder.main import run_pipeline

    print("[Live Scan] Starting Costco live scan...")
    print("[Live Scan] §3 gate: GOLDEN_GOOSE_LIVE_OPERATOR_APPROVED=1")
    print(f"[Live Scan] Time: {datetime.now(timezone.utc).isoformat()}")

    report = await run_pipeline(
        use_mock=False,
        categories=None,  # all categories
        roi_floor=10.0,
        min_monthly_sales=1000,
        max_results=100,
    )

    # Save the report
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out_dir = Path(__file__).resolve().parents[1] / "data" / "golden-goose-reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"goose_live_scan_{ts}.json"

    with open(out_path, "w") as f:
        json.dump(report, f, indent=2, default=str)

    print(f"\n[Live Scan] Complete!")
    print(f"  Report saved: {out_path}")
    print(f"  Total opportunities: {report.get('summary', {}).get('total_opportunities', 0)}")
    print(f"  HIGH tier: {report.get('summary', {}).get('high_tier_count', 0)}")
    print(f"  Elapsed: {report.get('meta', {}).get('elapsed_seconds', '?')}s")

    # Print top opportunities
    opps = report.get("opportunities", [])
    if opps:
        print(f"\n  Top {min(5, len(opps))} opportunities:")
        for o in opps[:5]:
            print(f"    #{o.get('rank', '?')} {o.get('brand', '')} — {o.get('product_title', '')[:50]}")
            print(f"       Profit: ${o.get('net_profit_per_unit', 0):.2f} | ROI: {o.get('roi_per_unit', 0):.1f}% | Score: {o.get('composite_score', 0)}")
    else:
        print("\n  No opportunities found. Check logs for details.")

    return report


if __name__ == "__main__":
    asyncio.run(run())
