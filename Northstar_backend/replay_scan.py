"""FIXES_50 #29 — replay a saved provider response locally (Phase G).

Usage (from ``Northstar_backend/``):

    python -m replay_scan --from-file data/debug/raw_20260920T140000Z.json.gz

Loads a (gzip'd) JSON payload via the same on-disk scheme the DebugStore saves
(#28/#36), prints a summary, and optionally emits one local metrics line.
Offline by design: nothing here contacts a provider; a missing/invalid file is
a hard error (no silent empty replay).
"""

from __future__ import annotations

import argparse
import gzip
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict


def load_replay_file(path: str | Path) -> Dict[str, Any]:
    """Load a replay file (plain .json or gzip .json.gz)."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError("replay file not found: %s" % path)
    if p.suffix == ".gz" or p.name.endswith(".json.gz"):
        with gzip.open(p, "rt", encoding="utf-8") as fh:
            payload = json.load(fh)
    else:
        with p.open("r", encoding="utf-8") as fh:
            payload = json.load(fh)
    if not isinstance(payload, dict):
        raise ValueError("replay payload must be a JSON object, got %s" % type(payload).__name__)
    return payload


def _summarize(payload: Dict[str, Any]) -> str:
    parts = ["keys=%d" % len(payload)]
    for key in ("asin", "requested_item_id", "provider", "status"):
        if key in payload and payload[key] is not None:
            parts.append("%s=%s" % (key, payload[key]))
    for list_key in ("items", "products", "results", "opportunities"):
        if isinstance(payload.get(list_key), list):
            parts.append("%s=%d" % (list_key, len(payload[list_key])))
    return ", ".join(parts)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="replay_scan",
        description="FIXES_50 #29 — replay a saved provider response locally (offline).",
    )
    parser.add_argument("--from-file", required=True, help="Path to a saved .json / .json.gz response")
    parser.add_argument("--emit-metrics", default=None, metavar="PATH",
                        help="Append one replay metrics line (JSONL) to PATH")
    args = parser.parse_args(argv)

    try:
        payload = load_replay_file(args.from_file)
    except (FileNotFoundError, ValueError, json.JSONDecodeError, OSError) as exc:
        print("ERROR: %s" % exc, file=sys.stderr)
        return 1

    print("REPLAY OK  %s" % args.from_file)
    print("  %s" % _summarize(payload))

    if args.emit_metrics:
        try:
            from agents.golden_goose_finder.gg_observability import MetricsStore
        except ImportError:
            from golden_goose_finder.gg_observability import MetricsStore
        MetricsStore(Path(args.emit_metrics)).emit({
            "event": "replay_scan",
            "source": args.from_file,
            "ts": time.time(),
            "payload_keys": len(payload),
        })
        print("  metrics -> %s" % args.emit_metrics)

    return 0


if __name__ == "__main__":
    sys.exit(main())