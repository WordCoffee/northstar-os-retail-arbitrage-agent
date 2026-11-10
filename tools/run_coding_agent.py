#!/usr/bin/env python3
"""Run one objective through the bounded coding agent against the local worker.

Example:
  python tools/run_coding_agent.py --workspace exports/agent_ws \
      --objective "Create src/hello.ts ..." \
      --command "npx tsc --noEmit" --required-file src/hello.ts
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "Northstar_backend"))

from agent_kernel.coding_runner import CodingTask, run_coding_task  # noqa: E402
from agent_kernel.local_model import DEFAULT_BASE_URL, health  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workspace", required=True)
    ap.add_argument("--objective", required=True)
    ap.add_argument("--command", action="append", default=[],
                    help="acceptance command (repeatable, space-split)")
    ap.add_argument("--required-file", action="append", default=[])
    ap.add_argument("--max-steps", type=int, default=12)
    ap.add_argument("--max-repairs", type=int, default=1)
    ap.add_argument("--builder", action="store_true",
                    help="force one write_many on the first turn, then verify/repair")
    ap.add_argument("--scaffold", action="store_true",
                    help="create package.json/tsconfig.json when missing")
    args = ap.parse_args()

    base = os.environ.get("TYS_CODING_URL", DEFAULT_BASE_URL)
    if not health(base):
        print(f"coding worker is not healthy on {base}", file=sys.stderr)
        return 2

    task = CodingTask(
        objective=args.objective,
        workspace=args.workspace,
        commands=[c.split() for c in args.command],
        required_files=args.required_file,
        max_steps=args.max_steps,
        max_repairs=args.max_repairs,
        builder=bool(args.builder),
        scaffold=bool(args.scaffold),
    )
    result = run_coding_task(task)
    print(json.dumps(result.to_dict(), indent=2))
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
