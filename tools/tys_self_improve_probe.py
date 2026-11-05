"""Bounded self-improvement probe: can Ty's coding lane actually program?

Runs one objective through the real loop (``agent_kernel.coding_runner`` ->
``CodingAgent`` -> llama-server on :8080) with an **independent** acceptance
check the model cannot edit: the assertions live in an inline ``python -c``
command, not in a test file inside the workspace.

    python tools/tys_self_improve_probe.py
    python tools/tys_self_improve_probe.py --workspace exports/probe --steps 10

Exit code 0 only when the workspace command exits 0 AND the required artifact
exists. That is the same evidence standard the repo uses for real builds.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "Northstar_backend"))

from agent_kernel.coding_runner import CodingTask, run_coding_task  # noqa: E402
from agent_kernel.local_model import DEFAULT_BASE_URL, health  # noqa: E402

OBJECTIVE = (
    "Create a Python module `unit_convert.py` in the workspace root. It must "
    "define to_slug(text: str) -> str, which lowercases the text, replaces every "
    "run of characters that are not a-z or 0-9 with a single '-', and strips "
    "leading and trailing '-'. Also define KIB, MIB, GIB as the ints 1024, "
    "1048576 and 1073741824. No third-party imports. Do not create or modify any "
    "test file."
)

ACCEPTANCE = [
    "python",
    "-c",
    "import unit_convert as u;"
    "cases=[('Hello World','hello-world'),('  A  B  ','a-b'),"
    "('Foo_Bar.Baz!','foo-bar-baz'),('--x--','x'),('','')];"
    "bad=[(i,u.to_slug(i),e) for i,e in cases if u.to_slug(i)!=e];"
    "ints=(u.KIB,u.MIB,u.GIB)==(1024,1048576,1073741824);"
    "print('bad',bad,'ints',ints);"
    "raise SystemExit(0 if not bad and ints else 1)",
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workspace", default=str(ROOT / "exports" / "tys_self_improve_probe"))
    ap.add_argument("--steps", type=int, default=10)
    ap.add_argument("--json", default=str(ROOT / "state" / "evidence"
                                          / "tys_self_improve_probe" / "result.json"))
    args = ap.parse_args()

    base = os.environ.get("TYS_CODING_URL", DEFAULT_BASE_URL)
    if not health(base):
        print(f"FAIL: coding worker not healthy on {base}", file=sys.stderr)
        return 2

    workspace = Path(args.workspace)
    workspace.mkdir(parents=True, exist_ok=True)
    for stale in ("unit_convert.py",):
        p = workspace / stale
        if p.exists():
            p.unlink()

    task = CodingTask(objective=OBJECTIVE, workspace=str(workspace),
                      commands=[ACCEPTANCE], required_files=["unit_convert.py"],
                      max_steps=args.steps, max_repairs=1)
    t0 = time.time()
    result = run_coding_task(task)
    secs = round(time.time() - t0, 1)
    data = result.to_dict()
    data["seconds"] = secs

    written = sorted(p.name for p in workspace.iterdir() if p.is_file())
    print(f"[probe] ok={result.ok} steps={data.get('steps')} {secs}s")
    print(f"[probe] workspace files: {written}")
    artifact = workspace / "unit_convert.py"
    data["artifact_exists"] = artifact.is_file()
    data["artifact_bytes"] = artifact.stat().st_size if artifact.is_file() else 0
    print(f"[probe] artifact: {data['artifact_exists']} ({data['artifact_bytes']} bytes)")

    out = Path(args.json)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(f"[probe] wrote {out}")
    return 0 if (result.ok and data["artifact_exists"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
