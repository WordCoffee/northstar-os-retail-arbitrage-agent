#!/usr/bin/env python3
"""Exception -> AST repair CLI.

    python tools/self_heal.py --traceback err.txt --root . --verify "python -m pytest -q"
    python tools/self_heal.py --traceback err.txt --root . --verify "..." --apply

`--apply` refuses without an isolation runtime (docker/bubblewrap) unless
`--allow-process` is passed (test-only). An optional `--approval` id is enforced
through the local HITL queue; without one the owner's autonomous-zone policy
applies.
"""
from __future__ import annotations

import argparse
import json
import shlex
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "Northstar_backend"))

from agent_kernel import hitl, self_heal  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--traceback", required=True,
                    help="path to the traceback text, or - for stdin")
    ap.add_argument("--root", default=str(ROOT))
    ap.add_argument("--verify", default="", help="sandboxed verification command")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--approval", default="")
    ap.add_argument("--allow-process", action="store_true",
                    help="allow the non-isolating process fallback (test only)")
    ap.add_argument("--timeout", type=float, default=120.0)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    if args.traceback == "-":
        text = sys.stdin.read()
    else:
        text = Path(args.traceback).read_text(encoding="utf-8", errors="replace")
    verify = shlex.split(args.verify) if args.verify else None
    try:
        plan = self_heal.heal(
            text, root=args.root, reasoner=self_heal.local_reasoner,
            verify_cmd=verify, timeout=args.timeout, apply=bool(args.apply),
            require_isolation=not args.allow_process,
            approval_id=args.approval or None)
    except (self_heal.SelfHealError, hitl.ApprovalRequired) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}))
        return 2
    out = dict(plan)
    out["ok"] = True
    if args.json:
        print(json.dumps(out, indent=2))
    else:
        print(f"{out['file']} {out['scope_ms']} ms")
        print(out["diff"][:4000])
        if args.apply:
            print(f"verified={out['verified']} applied={out['applied']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
