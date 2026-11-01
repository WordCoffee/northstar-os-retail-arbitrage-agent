"""Controlled executor proof: a real local model must author one small fix.

The model gets a task and a workspace, and must issue read/ast_edit actions through
the strict protocol. Acceptance is external and behavioural: the module is imported
and called, not merely inspected for text.

    python tools/executor_proof.py --model qwen2.5-coder:3b

Writes state/evidence/executor_proof_<model>.json. Nothing in the repository is
touched: the workspace is a disposable directory under state/.
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

MODULE = '''"""Arithmetic helpers used by the executor proof."""


def add(a, b):
    """Return the sum of two numbers."""
    return a - b


def double(n):
    """Return twice n."""
    return add(n, n)
'''

TASK = (
    "Northstar_backend/calc.py has one behavioural defect: add(a, b) returns a - b. "
    "Make add return the sum of its two arguments. Change only that function in that "
    "file - do not touch double() and do not rewrite the file. "
    "state is checked by calling add(2, 3); it must return 5."
)


def _load_module(path: Path):
    spec = importlib.util.spec_from_file_location("proof_calc", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def behavioural_acceptance(path: Path):
    def check():
        if not path.is_file():
            return False, "calc.py missing"
        try:
            module = _load_module(path)
        except Exception as exc:  # noqa: BLE001 - a broken module is a failed check
            return False, f"import failed: {type(exc).__name__}: {exc}"
        try:
            got = module.add(2, 3)
        except Exception as exc:  # noqa: BLE001
            return False, f"add raised {type(exc).__name__}: {exc}"
        if got != 5:
            return False, f"add(2, 3) == {got!r}, expected 5"
        return True, "add(2, 3) == 5"
    return check


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--model", default="qwen2.5-coder:3b")
    ap.add_argument("--max-steps", type=int, default=6)
    ap.add_argument("--out", default="")
    args = ap.parse_args(argv)

    ws_root = ROOT / "state" / "tmp_executor_proof"
    if ws_root.exists():
        shutil.rmtree(ws_root)
    (ws_root / "Northstar_backend").mkdir(parents=True, exist_ok=True)
    target = ws_root / "Northstar_backend" / "calc.py"
    target.write_text(MODULE, encoding="utf-8")

    workspace = Workspace(ws_root, allow_paths=["Northstar_backend/calc.py"],
                          read_paths=["Northstar_backend/calc.py"],
                          run_allowlist=[["python", "-c"]])
    model = OllamaChatModel(model=args.model, timeout_s=240, max_tokens=700)
    agent = CodingAgent(workspace, model, max_steps=args.max_steps, max_repairs=1,
                        acceptance=behavioural_acceptance(target),
                        required_artifact="Northstar_backend/calc.py",
                        max_protocol_errors=6,
                        allowed_tools=["read", "ast_edit", "run", "finish"])

    started = time.time()
    result = agent.run(TASK)
    elapsed = round(time.time() - started, 2)
    ok, detail = behavioural_acceptance(target)()

    record = {
        "model": args.model,
        "task": "fix add(a,b) to return a + b",
        "ok": bool(result.ok),
        "acceptance_after_run": {"ok": ok, "detail": detail},
        "steps": result.steps,
        "protocol_errors": result.protocol_errors,
        "scope_rejections": result.scope_rejections,
        "error": result.error,
        "elapsed_s": elapsed,
        "module_after": target.read_text(encoding="utf-8")[:600],
        "transcript": [{"tool": h.get("tool"), "ok": h.get("ok"),
                        "output": str(h.get("output"))[:200]}
                       for h in result.transcript],
    }
    payload = json.dumps(record, indent=2)
    out = Path(args.out) if args.out else (
        ROOT / "state" / "evidence" / f"executor_proof_{args.model.replace(':', '_')}.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(payload, encoding="utf-8")
    print(payload)
    return 0 if (result.ok and ok) else 1


if __name__ == "__main__":
    raise SystemExit(main())
