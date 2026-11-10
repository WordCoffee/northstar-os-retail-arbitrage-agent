"""Disposable capability screen for one installed lane.

A candidate must: read its target, identify a symbol from what it read, author a
small behavioural correction, pass an independent behavioural check, and stay in
scope. Nothing here touches the repository: the workspace lives under state/.

    python tools/screen_lane.py --model bojo:gpu-orig --native-tools
    python tools/screen_lane.py --model qwen2.5-coder:3b

Writes state/evidence/screen_<model>_<attempt>.json. Exit 0 = screened.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "Northstar_backend"))

from agent_kernel.coding_agent import CodingAgent   # noqa: E402
from agent_kernel.coding_tools import Workspace     # noqa: E402
from agent_kernel.local_model import OllamaChatModel  # noqa: E402

MODULE = '''"""Inventory limits used by the screen."""


def summarise(rows):
    """Count usable rows by state.

    A row is usable when it is a dict with a string 'state'. Unusable rows are
    skipped silently, so a caller cannot tell a clean file from a damaged one.
    """
    counts = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        state = row.get("state")
        if not isinstance(state, str) or not state:
            continue
        counts[state] = counts.get(state, 0) + 1
    return counts
'''

CHECK = '''"""Behavioural check for summarise()."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from limits import summarise

rows = [
    {"state": "approved"},
    {"state": "approved"},
    {"state": "denied"},
    "not-a-row",
    {"state": None},
    {},
]
result = summarise(rows)
ok = (result.get("approved") == 2 and result.get("denied") == 1
      and result.get("skipped") == 3 and result.get("total") == 3)
print(json.dumps({"ok": ok, "result": result}))
sys.exit(0 if ok else 1)
'''

TASK = (
    "src/limits.py has one behavioural defect: summarise() silently drops rows it "
    "cannot use, so the caller cannot tell a clean file from a damaged one. Read the "
    "file, then make summarise() also report how many rows it skipped and the total it "
    "counted. The result must keep the approved/denied counts, add 'skipped' for every "
    "unusable row, and add 'total' = approved + denied - that is, the COUNTED rows only, "
    "so skipped rows are NOT included in 'total'. Run `python check.py` to verify - it is "
    "read-only. Change only src/limits.py.")


def summarise_verdict(got):
    """Score the candidate's result. A non-dict (or a raise) is a failure, not a crash."""
    if not isinstance(got, dict):
        return False, {"result": repr(got)[:120],
                       "reason": f"returned {type(got).__name__}, expected dict"}
    ok = (got.get("approved") == 2 and got.get("denied") == 1
          and got.get("skipped") == 3 and got.get("total") == 3)
    return ok, got


def _accept(path: Path):
    def check():
        try:
            spec = importlib.util.spec_from_file_location("screen_limits", path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            rows = [{"state": "approved"}, {"state": "approved"}, {"state": "denied"},
                    "not-a-row", {"state": None}, {}]
            got = module.summarise(rows)
        except Exception as exc:  # noqa: BLE001 - a broken candidate is a failed check
            return False, json.dumps({"error": f"{type(exc).__name__}: {str(exc)[:120]}"})
        ok, detail = summarise_verdict(got)
        return ok, json.dumps(detail)
    return check


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--model", required=True)
    ap.add_argument("--native-tools", action="store_true")
    ap.add_argument("--max-steps", type=int, default=10)
    ap.add_argument("--attempt", type=int, default=1)
    args = ap.parse_args(argv)

    slug = "".join(ch if ch.isalnum() else "_" for ch in args.model)
    root = ROOT / "state" / f"tmp_screen_{slug}"
    if root.exists():
        shutil.rmtree(root)
    (root / "src").mkdir(parents=True)
    (root / "src" / "limits.py").write_text(MODULE, encoding="utf-8")
    (root / "check.py").write_text(CHECK, encoding="utf-8")

    target = root / "src" / "limits.py"
    workspace = Workspace(root, allow_paths=["src/limits.py"],
                          read_paths=["src/limits.py", "check.py"],
                          run_allowlist=[["python", "check.py"]])
    model = OllamaChatModel(model=args.model, timeout_s=240, max_tokens=900,
                            native_tools=args.native_tools,
                            tool_names=["read", "ast_edit", "run", "finish"],
                            num_ctx=8192)
    agent = CodingAgent(workspace, model, max_steps=args.max_steps, max_repairs=1,
                        acceptance=_accept(target), required_artifact="src/limits.py",
                        max_protocol_errors=8,
                        allowed_tools=["read", "ast_edit", "run", "finish"])
    started = time.time()
    result = agent.run(TASK)
    elapsed = round(time.time() - started, 2)
    ok, detail = _accept(target)()

    record = {"model": args.model, "native_tools": args.native_tools,
              "attempt": args.attempt, "screened": bool(result.ok and ok),
              "agent_ok": bool(result.ok), "behaviour_ok": ok, "behaviour": detail,
              "steps": result.steps, "protocol_errors": result.protocol_errors,
              "scope_rejections": result.scope_rejections, "error": result.error,
              "elapsed_s": elapsed,
              "transcript": [{"tool": h.get("tool"), "ok": h.get("ok"),
                              "output": str(h.get("output"))[:180]}
                             for h in result.transcript]}
    out = ROOT / "state" / "evidence" / f"screen_{slug}_{args.attempt}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(record, indent=2), encoding="utf-8")
    print(json.dumps(record, indent=2))
    return 0 if record["screened"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
