"""Live protocol diagnostics for one installed lane, through the real executor.

Not a mock: the model answers, `tool_protocol` parses/validates, the workspace
executes, and the verdict is recorded. Each scenario is small and bounded, and the
model is unloaded afterwards.

    python tools/probe_lane_protocol.py --model qwen2.5-coder:3b

Scenarios
  1. one-step action        - a single valid JSON action is accepted and executed
  2. two-step sequence      - read then a targeted ast_edit, both accepted
  3. invalid-output repair  - prose is rejected with a code, the model recovers
  4. bounded timeout        - a request that exceeds its budget is abandoned and
                              the daemon still serves afterwards
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "Northstar_backend"))

from agent_kernel import tool_protocol as tp            # noqa: E402
from agent_kernel.coding_tools import Workspace        # noqa: E402
from agent_kernel.local_model import OllamaChatModel   # noqa: E402

OLLAMA = "http://127.0.0.1:11434"

MODULE = '''"""Small module used by the protocol probe."""


def add(a, b):
    return a - b


def double(n):
    return add(n, n)
'''

READ_PROMPT = (
    "You are the Northstar OS coding worker. Reply with exactly ONE JSON object, no prose.\n"
    'Schema: {"tool":"read","args":{"path":"<file>"}}\n'
    "TASK: read Northstar_backend/calc.py. Your next JSON object:")

SEQUENCE_PROMPT = (
    "You are the Northstar OS coding worker. Reply with exactly ONE JSON object, no prose.\n"
    'Schema: {"tool":"ast_edit","args":{"path":"Northstar_backend/calc.py",'
    '"op":"replace_function_body","target":"add","source":"<new body WITHOUT the def line>"}}\n'
    "TASK: `add` subtracts but must return a + b. Reply with the ast_edit action. "
    "Your next JSON object:")

PROSE_PROMPT = (
    "Explain in one short sentence what a Python function does. Do not use JSON.")


def _unload(model: str) -> None:
    try:
        req = urllib.request.Request(
            OLLAMA + "/api/generate",
            data=json.dumps({"model": model, "keep_alive": 0, "prompt": ""}).encode(),
            headers={"Content-Type": "application/json"}, method="POST")
        urllib.request.urlopen(req, timeout=20).read()
    except Exception:  # noqa: BLE001 - unloading is best effort and recorded
        pass


def _tokens(text: str) -> int:
    return max(1, len(text) // 4)


def scenario_one_step(model: str, root: Path) -> dict:
    ws = Workspace(root, allow_paths=["Northstar_backend/calc.py"],
                   read_paths=["Northstar_backend/calc.py"])
    t0 = time.time()
    raw = model_call(model, READ_PROMPT)
    out = {"raw_head": raw[:120].replace("\n", " "), "elapsed_s": round(time.time() - t0, 2)}
    try:
        action = tp.validate_action(tp.parse_action(raw), workspace=ws)
        result = ws.execute(action.tool, action.args)
        out.update({"accepted": True, "tool": action.tool, "executed": bool(result.ok),
                    "output_head": str(result.output or result.error)[:80].replace("\n", " ")})
    except tp.ActionError as exc:
        out.update({"accepted": False, "code": exc.code})
    return out


def scenario_two_step(model: str, root: Path) -> dict:
    ws = Workspace(root, allow_paths=["Northstar_backend/calc.py"],
                   read_paths=["Northstar_backend/calc.py"])
    t0 = time.time()
    first = model_call(model, READ_PROMPT)
    second = model_call(model, SEQUENCE_PROMPT)
    out = {"elapsed_s": round(time.time() - t0, 2),
           "first_head": first[:80].replace("\n", " "),
           "second_head": second[:120].replace("\n", " ")}
    tools, codes = [], []
    for raw in (first, second):
        try:
            action = tp.validate_action(tp.parse_action(raw), workspace=ws)
            tools.append(action.tool)
            if action.tool == "ast_edit":
                result = ws.execute(action.tool, action.args)
                out["edit_ok"] = bool(result.ok)
                out["edit_error"] = str(result.error or "")[:120]
        except tp.ActionError as exc:
            codes.append(exc.code)
    out.update({"accepted_tools": tools, "rejected_codes": codes})
    text = (root / "Northstar_backend" / "calc.py").read_text(encoding="utf-8")
    out["add_returns_sum"] = "return a + b" in text.replace(" ", " ").replace("a+b", "a + b")
    return out


def scenario_invalid_repair(model: str, root: Path) -> dict:
    ws = Workspace(root, allow_paths=["Northstar_backend/calc.py"],
                   read_paths=["Northstar_backend/calc.py"])
    prose = model_call(model, PROSE_PROMPT)
    out = {"prose_head": prose[:100].replace("\n", " ")}
    try:
        tp.validate_action(tp.parse_action(prose), workspace=ws)
        out["first_accepted"] = True
    except tp.ActionError as exc:
        out["first_accepted"] = False
        out["code"] = exc.code
        repair = (f"{exc.observation()}\n\nReply with exactly one JSON object:\n"
                  '{"tool":"read","args":{"path":"Northstar_backend/calc.py"}}')
        raw = model_call(model, repair)
        out["repair_head"] = raw[:100].replace("\n", " ")
        try:
            action = tp.validate_action(tp.parse_action(raw), workspace=ws)
            out["recovered"] = action.tool == "read"
        except tp.ActionError as exc2:
            out["recovered"] = False
            out["repair_code"] = exc2.code
    return out


def scenario_timeout(model: str, budget_s: float = 1.5) -> dict:
    payload = {"model": model, "prompt": "Write 400 words about coffee.", "stream": True,
               "keep_alive": "30s", "options": {"num_predict": 2000}}
    t0 = time.time()
    timed_out = False
    try:
        req = urllib.request.Request(OLLAMA + "/api/generate",
                                     data=json.dumps(payload).encode(),
                                     headers={"Content-Type": "application/json"},
                                     method="POST")
        with urllib.request.urlopen(req, timeout=budget_s) as resp:
            resp.read(64)
    except Exception as exc:  # noqa: BLE001 - a timeout is the expected outcome here
        timed_out = ("timed out" in str(exc).lower()
                     or "timeout" in type(exc).__name__.lower())
    elapsed = round(time.time() - t0, 2)
    # The daemon must still answer after the abandoned request.
    alive = False
    try:
        with urllib.request.urlopen(OLLAMA + "/api/tags", timeout=10) as resp:
            alive = resp.status == 200
    except Exception:  # noqa: BLE001
        alive = False
    return {"budget_s": budget_s, "elapsed_s": elapsed, "timed_out": timed_out,
            "daemon_alive_after": alive}


def model_call(name: str, prompt: str) -> str:
    return OllamaChatModel(model=name, timeout_s=180, max_tokens=220)(prompt)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--model", default="qwen2.5-coder:3b")
    ap.add_argument("--out", default="")
    args = ap.parse_args(argv)

    root = ROOT / "state" / "tmp_probe_ws"
    (root / "Northstar_backend").mkdir(parents=True, exist_ok=True)
    (root / "Northstar_backend" / "calc.py").write_text(MODULE, encoding="utf-8")

    report = {"model": args.model, "started_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
              "scenarios": {}}
    try:
        report["scenarios"]["one_step"] = scenario_one_step(args.model, root)
        report["scenarios"]["two_step"] = scenario_two_step(args.model, root)
        report["scenarios"]["invalid_repair"] = scenario_invalid_repair(args.model, root)
        report["scenarios"]["timeout"] = scenario_timeout(args.model)
    finally:
        _unload(args.model)
        report["finished_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        report["tokens_approx"] = _tokens(json.dumps(report))
        payload = json.dumps(report, indent=2)
        if args.out:
            path = Path(args.out)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(payload, encoding="utf-8")
        print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
