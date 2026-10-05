"""CLI: local creative media suite status + pipeline plans (offline, unarmed).

Read-only: reports which specialist models are installed for each stage and how
the model-chaining pipeline would be assembled. It never downloads, installs,
loads, generates, or contacts a provider.

Usage:
    python tools/creative_suite_status.py                       # stage/model status
    python tools/creative_suite_status.py --plan ugc_talking_head
    python tools/creative_suite_status.py --json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from Northstar_backend import creative_pipeline as cp  # noqa: E402
from Northstar_backend import local_image_engine as lie  # noqa: E402


def main(argv=None) -> int:
    lie.apply_env_file_media_flag()
    ap = argparse.ArgumentParser(description="Local creative suite status (offline, unarmed).")
    ap.add_argument("--plan", metavar="GOAL", help="plan a pipeline goal")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    if args.plan:
        p = cp.plan_pipeline(args.plan)
        if args.json:
            print(json.dumps(p, indent=2))
            return 0
        if not p.get("known"):
            print(f"unknown goal '{args.plan}' — try one of: {', '.join(p['available_goals'])}")
            return 2
        print(f"Pipeline plan: {p['label']}  (model-chaining, one model at a time)")
        for st in p["steps"]:
            m = st["model"]
            flag = "commercial-safe" if m["commercial_ok"] else "NON-COMMERCIAL"
            print(f"  {st['stage']:>8}: {m['label']} · {m['license']} · {flag} · {m['install_state']}")
        if p["owner_gated_steps"]:
            print("\nOWNER-GATED steps still required:")
            for g in p["owner_gated_steps"]:
                print(f"  - {g}")
        print(f"\nnote: {p['note']}")
        return 0

    status = cp.pipeline_status()
    if args.json:
        print(json.dumps(status, indent=2))
        return 0
    print("Local creative media suite — stage/model status (read-only, nothing installed by this)")
    for st in status["stages"]:
        print(f"\n[{st['install_state']:>9}] {st['label']}")
        for m in st["models"]:
            flag = "commercial-safe" if m["commercial_ok"] else "NON-COMMERCIAL"
            print(f"    [{m['install_state']:>9}] {m['label']} · {m['license']} · {flag} · ~{m['vram_gb']}GB")
    print(f"\nnote: {status['note']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
