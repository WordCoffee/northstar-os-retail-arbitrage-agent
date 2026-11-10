"""Shared CLI helpers for Costco Non-Kirkland research commands.

Every command must: support --dry-run, log counts/exclusions, log source/freshness,
create an auditable run manifest, never log secrets, and fail closed when requested
live access is not explicitly approved.
"""
from __future__ import annotations

import json
import sys
from typing import Any, Dict, List, Optional


def print_json(obj: Any) -> None:
    print(json.dumps(obj, indent=2, default=str))


def load_json_file(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def parse_bool_flag(value: Optional[str]) -> bool:
    if value is None:
        return False
    return str(value).strip().lower() in ("1", "true", "yes", "on")


def require_args(argv: List[str], required: Dict[str, str]) -> None:
    """required maps flag -> description. Exits(2) if a required flag is missing."""
    for flag, desc in required.items():
        if flag not in argv:
            print(f"error: missing required argument {flag} ({desc})", file=sys.stderr)
            sys.exit(2)


def fail_closed(message: str) -> int:
    print(f"error: {message}", file=sys.stderr)
    print("No provider calls were executed.", file=sys.stderr)
    return 2


def log_source_summary(summary: Optional[Dict[str, Any]]) -> None:
    if not summary:
        return
    print(f"  sources checked:  {summary.get('sources_checked')}")
    print(f"  sources found:    {summary.get('sources_found')}")
    print(f"  total raw records:{summary.get('total_raw_records')}")
    for s in summary.get("sources", []):
        if s.get("exists"):
            print(f"    - {s['source_name']}: {s['raw_record_count']} records ({s['path']})")


def network_calls_confirmation(n: int = 0) -> str:
    """Explicit confirmation string required on every CLI command."""
    return f"Network calls made: {n}"


def print_network_confirmation(n: int = 0) -> None:
    print(network_calls_confirmation(n))