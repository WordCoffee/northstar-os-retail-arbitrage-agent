"""Synthetic 24 KB contract round-trip through the Go lane.

The point is throughput, not the fix: a 24 KB module must produce a real, applicable
edit inside 90 seconds, and the edit must land on disk. The lane sends only the target
function (extracted by AST), so the prompt stays small even when the file does not.
"""
from __future__ import annotations

import ast
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import go_author as ga

PAD = "# filler line to reach a realistic module size, unchanged by this unit\n"


def make_module(path: Path, target: str) -> None:
    body = ["\"\"\"Synthetic module for the transport contract.\"\"\"\n"]
    for i in range(60):
        body.append(f"def helper_{i}(x):\n    return x + {i}\n\n")
    body.append(f"def {target}(value):\n"
                "    \"\"\"Return the value clamped to at most 10.\"\"\"\n"
                "    return value\n")
    for i in range(300):
        body.append(PAD)
    path.write_text("".join(body), encoding="utf-8")


def extract(path: Path, symbol: str) -> str:
    text = path.read_text(encoding="utf-8")
    tree = ast.parse(text)
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == symbol:
            return ast.get_source_segment(text, node) or ""
    return ""


def main() -> int:
    work = ROOT / "state" / "tmp_transport"
    work.mkdir(parents=True, exist_ok=True)
    target = work / "synthetic.py"
    make_module(target, "clamp_max")
    size = target.stat().st_size
    task = {"id": "transport-synthetic", "write_paths": ["state/tmp_transport/synthetic.py"],
            "objective": "make clamp_max actually clamp: return 10 when the value is above 10"}
    excerpt = extract(target, "clamp_max")
    prompt = ga._prompt(task["objective"],
                        "state/tmp_transport/synthetic.py",
                        excerpt + "\n\n" + f"(the full file is {size} bytes; this is the only "
                                           "function you may change)")
    started = time.time()
    turn = ga._run(prompt, session="transport-synthetic")
    elapsed = round(time.time() - started, 1)
    result = {"file_bytes": size, "prompt_bytes": len(prompt), "elapsed_s": elapsed,
              "rc": turn.get("returncode"), "cost_usd": turn.get("cost_usd"),
              "reply_head": str(turn.get("text") or "")[:160]}
    ok = False
    try:
        obj = ga._extract(turn.get("text") or "")
        err = ga._apply(str(obj.get("path") or ""), str(obj.get("search") or ""),
                        str(obj.get("replace") or ""), task)
        result["apply_error"] = err
        if not err:
            text = target.read_text(encoding="utf-8")
            ok = "return 10" in text or "min(" in text
            result["applied"] = ok
    except (ValueError, json.JSONDecodeError) as exc:
        result["apply_error"] = f"unusable reply: {exc}"
    result["under_90s"] = elapsed < 90
    result["ok"] = bool(ok and elapsed < 90)
    out = ROOT / "state" / "evidence" / "transport_synthetic.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
