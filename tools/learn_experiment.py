"""Cold vs pattern-informed local attempt on three fresh fixtures.

The question: does the fix-pattern store measurably help the local lane? Three
small silent-skip defects are seeded in disposable fixtures; each runs twice with
qwen3.5:4b (native tools): once cold, once with the stored pattern statement.

Scores: protocol-valid turns, correct target symbol, behavioural pass, steps.
"""
from __future__ import annotations

import importlib.util
import json
import shutil
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "Northstar_backend"))
sys.path.insert(0, str(ROOT / "tools"))

import fix_patterns as fp                                    # noqa: E402
from agent_kernel.coding_agent import CodingAgent            # noqa: E402
from agent_kernel.coding_tools import Workspace              # noqa: E402
from agent_kernel.local_model import OllamaChatModel         # noqa: E402

FIXTURES = {
    "inventory": {
        "module": "inventory.py",
        "fn": "summarise_rows",
        "rows": "[{\"state\": \"approved\"}, {\"state\": \"approved\"}, {\"state\": \"denied\"}, \"junk\", {\"state\": None}]",
    },
    "events": {
        "module": "events.py",
        "fn": "count_events",
        "rows": "[{\"kind\": \"open\"}, {\"kind\": \"close\"}, \"junk\", {\"kind\": \"\"}]",
    },
    "sensors": {
        "module": "sensors.py",
        "fn": "tally_samples",
        "rows": "[{\"unit\": \"c\"}, {\"unit\": \"c\"}, 42, {\"unit\": None}]",
    },
}

TEMPLATE = '''"""Fixture module."""


def {fn}(rows):
    """Count usable rows."""
    counts = {{}}
    for row in rows:
        if not isinstance(row, dict):
            continue
        key = row.get("{key}")
        if not isinstance(key, str) or not key:
            continue
        counts[key] = counts.get(key, 0) + 1
    return counts
'''


def _fixture(root: Path, name: str) -> Dict[str, Any]:
    spec = FIXTURES[name]
    key = "state" if name == "inventory" else ("kind" if name == "events" else "unit")
    module = spec["module"]
    fn = spec["fn"]
    (root / "src").mkdir(parents=True)
    (root / "src" / module).write_text(TEMPLATE.format(fn=fn, key=key), encoding="utf-8")
    rows = spec["rows"]
    (root / "check.py").write_text(
        "import json, sys\n"
        f"sys.path.insert(0, 'src')\n"
        f"from {module[:-3]} import {fn}\n"
        f"rows = {rows}\n"
        f"got = {fn}(rows)\n"
        "counted = sum(v for k, v in got.items() if k != 'skipped')\n"
        "ok = got.get('skipped', None) is not None and counted > 0\n"
        "print(json.dumps({'ok': ok, 'result': got}))\n"
        "sys.exit(0 if ok else 1)\n", encoding="utf-8")
    return {"name": name, "module": module, "fn": fn, "key": key}


def _accept(path: Path, fn: str, rows: List[Any]):
    def check():
        try:
            spec = importlib.util.spec_from_file_location("fixture", path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            got = getattr(module, fn)(rows)
        except Exception as exc:  # noqa: BLE001
            return False, f"{type(exc).__name__}: {exc}"
        if not isinstance(got, dict):
            return False, f"returned {type(got).__name__}"
        counted = sum(v for k, v in got.items() if k != "skipped")
        return (got.get("skipped") is not None and counted > 0), json.dumps(got)
    return check


def run(name: str, *, informed: bool, hint: str, max_steps: int = 8) -> Dict[str, Any]:
    root = ROOT / "state" / "tmp_learn" / name
    if root.exists():
        shutil.rmtree(root)
    info = _fixture(root, name)
    rows = eval(FIXTURES[name]["rows"])  # noqa: S307 - fixture literals defined above
    task = (
        f"src/{info['module']} has one behavioural defect: {info['fn']}() silently drops "
        "rows it cannot use, so a caller cannot tell a clean file from a damaged one. "
        f"Read the file, then make {info['fn']}() also report how many rows it skipped. "
        "It must keep returning a dict with the same keys as before (the counts) PLUS a "
        "new integer key 'skipped' for every unusable row - a dict, not a tuple and not "
        "a second return value. Run `python check.py` to verify - it is read-only. "
        f"Change only src/{info['module']}.")
    if informed and hint:
        task += f"\n\nPATTERN from an accepted fix of this class: {hint}"
    ws = Workspace(root, allow_paths=[f"src/{info['module']}"],
                   read_paths=[f"src/{info['module']}", "check.py"],
                   run_allowlist=[["python", "check.py"]])
    model = OllamaChatModel(model="qwen3.5:4b", timeout_s=240, max_tokens=700,
                            native_tools=True,
                            tool_names=["read", "ast_edit", "run", "finish"],
                            num_ctx=8192)
    agent = CodingAgent(ws, model, max_steps=max_steps, max_repairs=0,
                        acceptance=_accept(root / "src" / info["module"], info["fn"], rows),
                        required_artifact=f"src/{info['module']}",
                        max_protocol_errors=8,
                        allowed_tools=["read", "ast_edit", "run", "finish"])
    started = time.time()
    result = agent.run(task)
    ok, detail = _accept(root / "src" / info["module"], info["fn"], rows)()
    edits = [h for h in result.transcript if h.get("tool") == "ast_edit" and h.get("ok")]
    symbol_ok = any(info["fn"] in str(h.get("output")) for h in result.transcript) or bool(edits)
    return {"fixture": name, "informed": informed, "behavioural_pass": bool(ok),
            "agent_ok": bool(result.ok), "steps": result.steps,
            "protocol_errors": result.protocol_errors,
            "scope_rejections": result.scope_rejections,
            "edits_applied": len(edits), "detail": detail[:120],
            "elapsed_s": round(time.time() - started, 2)}


def main() -> int:
    hint = fp.hint("silent-skip-counter")
    rows = []
    for name in FIXTURES:
        rows.append(run(name, informed=False, hint=hint))
        rows.append(run(name, informed=True, hint=hint))
    cold = [r for r in rows if not r["informed"]]
    warm = [r for r in rows if r["informed"]]
    summary = {
        "runs": rows,
        "cold": {"pass": sum(1 for r in cold if r["behavioural_pass"]),
                 "mean_steps": round(sum(r["steps"] for r in cold) / len(cold), 2),
                 "protocol_errors": sum(r["protocol_errors"] for r in cold)},
        "informed": {"pass": sum(1 for r in warm if r["behavioural_pass"]),
                     "mean_steps": round(sum(r["steps"] for r in warm) / len(warm), 2),
                     "protocol_errors": sum(r["protocol_errors"] for r in warm)},
        "hint_used": bool(hint),
    }
    out = ROOT / "state" / "evidence" / "learning_experiment_20261102.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
