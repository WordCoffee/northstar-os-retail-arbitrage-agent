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


def _apply_media_flag_from_env_file() -> None:
    """Targeted, NON-SECRET read of the repo-root .env so this CLI's gate reading
    matches the running app (which loads .env at startup). Only the
    MEDIA_GEN_LIVE line is read; no other value is ever read or printed."""
    import os
    if str(os.getenv("MEDIA_GEN_LIVE", "") or "").strip():
        return
    try:
        for line in (_ROOT / ".env").read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("MEDIA_GEN_LIVE="):
                os.environ["MEDIA_GEN_LIVE"] = line.split("=", 1)[1].strip()
                return
    except OSError:
        return


from Northstar_backend import local_image_engine as lie  # noqa: E402


def main(argv=None) -> int:
    _apply_media_flag_from_env_file()
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
