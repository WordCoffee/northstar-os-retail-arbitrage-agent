"""CLI: read-only local image-engine status (localhost-only; no install, no arming).

Thin wrapper over ``Northstar_backend/local_image_engine.py`` so the logic has a
single source of truth shared with the readiness route.

Usage:
    python tools/local_image_engine_status.py            # human checklist
    python tools/local_image_engine_status.py --json     # machine JSON

Nothing is installed, downloaded, started, or armed by this command.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Make Northstar_backend importable when run from anywhere.
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


from Northstar_backend import local_image_engine as lie  # noqa: E402


def main(argv=None) -> int:
    lie.apply_env_file_media_flag()  # match the app's gate reading (targeted, non-secret)
    ap = argparse.ArgumentParser(description="Read-only local image-engine status (no install, no arming).")
    ap.add_argument("--json", action="store_true", help="emit JSON")
    args = ap.parse_args(argv)
    status = lie.build_status()
    if args.json:
        print(json.dumps(status, indent=2))
        return 0
    print("Local image-engine status (read-only; nothing is installed or armed)")
    print(f"  ready_for_local_generation: {status['ready_for_local_generation']}")
    for it in status["items"]:
        gate = f"  -> {it['gate']}" if it["gate"] else ""
        print(f"  [{it['state']:>10}] {it['label']}: {it['detail']}{gate}")
    g = status["gpu"]
    print(f"  [{'present' if g['present'] else 'unknown':>10}] GPU: {g['detail']}")
    d = status["disk"]
    print(f"  [{'ok' if d['free_gb'] else 'unknown':>10}] Disk free: {d['free_gb']} GB / {d['total_gb']} GB")
    print(f"  note: {status['note']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
