"""Merge a state fragment into 00_STATE.json — checked by the agent, applied by the operator.

`00_STATE.json` carries an operator `edit` deny in `opencode.json`, so no agent
may rewrite it. That deny is a guardrail, not an obstacle: this tool lets the
registry stay accurate without anyone bypassing it.

    python tools/state_fragment.py --check state/fragments/20261029_install_health.json
        read-only: validates the fragment, refuses on a key clash, prints the
        exact keys that would be added and the resulting file size.

    python tools/state_fragment.py --apply state/fragments/20261029_install_health.json
        operator only. Takes a timestamped backup, writes atomically, re-parses
        the result, and prints what changed.

Exit codes: 0 ok, 1 the fragment or the registry is invalid / a key clashes,
2 usage.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "00_STATE.json"
BACKUPS = ROOT / "backups" / "state"

# Keys this tool will not write, ever. They encode the test baseline and the
# protected-file contract; only a human edits them.
RESERVED = ()


def load_state(path: Path = STATE) -> Tuple[Dict[str, Any], bool]:
    raw = path.read_text(encoding="utf-8-sig")
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError(f"{path.name} is not a JSON object")
    return data, raw.startswith("\ufeff")


def load_fragment(path: Path) -> Dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not data:
        raise ValueError("a fragment must be a non-empty JSON object of top-level keys")
    for key in data:
        if not isinstance(key, str) or not key.strip():
            raise ValueError("every fragment key must be a non-empty string")
        if key in RESERVED:
            raise ValueError(f"{key!r} is reserved and may not be written by a fragment")
    return data


def plan_merge(state: Dict[str, Any], frag: Dict[str, Any],
               overwrite: bool = False) -> Tuple[Dict[str, Any], List[str], List[str]]:
    added = [k for k in frag if k not in state]
    replaced = [k for k in frag if k in state]
    if replaced and not overwrite:
        raise ValueError(
            "these keys already exist in 00_STATE.json: " + ", ".join(replaced)
            + " — pass --overwrite to replace them deliberately")
    merged = dict(state)
    for key, value in frag.items():
        merged[key] = value
    return merged, added, replaced


def check(fragment: Path, overwrite: bool = False) -> int:
    try:
        state, bom = load_state()
        frag = load_fragment(fragment)
        merged, added, replaced = plan_merge(state, frag, overwrite)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"FAIL: {exc}")
        return 1
    rendered = json.dumps(merged, indent=2, ensure_ascii=False)
    json.loads(rendered)  # the merged registry must still parse
    print(json.dumps({
        "registry": str(STATE),
        "registry_keys": len(state),
        "registry_bytes": STATE.stat().st_size,
        "bom_preserved": bom,
        "fragment": str(fragment),
        "would_add": added,
        "would_replace": replaced,
        "merged_keys": len(merged),
        "merged_bytes": len(rendered.encode("utf-8")),
        "status": "OK — fragment applies cleanly (nothing written)",
    }, indent=2))
    return 0


def apply(fragment: Path, overwrite: bool = False) -> int:
    try:
        state, bom = load_state()
        frag = load_fragment(fragment)
        merged, added, replaced = plan_merge(state, frag, overwrite)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"FAIL: {exc}")
        return 1

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    BACKUPS.mkdir(parents=True, exist_ok=True)
    backup = BACKUPS / f"00_STATE_{stamp}.json"
    shutil.copy2(STATE, backup)

    payload = json.dumps(merged, indent=2, ensure_ascii=False)
    tmp = STATE.with_name(f".00_STATE.{uuid.uuid4().hex}.nstmp")
    handle = open(tmp, "w", encoding="utf-8-sig" if bom else "utf-8")
    try:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    finally:
        handle.close()
    os.replace(tmp, STATE)

    reloaded, _ = load_state()
    if set(frag) - set(reloaded):
        print("FAIL: the merge did not land; restore from " + str(backup))
        return 1
    print(json.dumps({"status": "merged", "backup": str(backup),
                      "added": added, "replaced": replaced,
                      "registry_keys": len(reloaded)}, indent=2))
    return 0


def main(argv: List[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("fragment", help="path to a fragment JSON file")
    group = ap.add_mutually_exclusive_group(required=True)
    group.add_argument("--check", action="store_true", help="validate only (read-only)")
    group.add_argument("--apply", action="store_true",
                       help="perform the merge (operator only)")
    ap.add_argument("--overwrite", action="store_true",
                    help="replace existing keys instead of refusing")
    args = ap.parse_args(argv)
    fragment = Path(args.fragment)
    if not fragment.is_absolute():
        fragment = (Path.cwd() / fragment).resolve()
    return check(fragment, args.overwrite) if args.check else apply(fragment, args.overwrite)


if __name__ == "__main__":
    raise SystemExit(main())
