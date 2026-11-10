"""Local eval harness for the two things that regress silently.

1. **Tool-call parsing** — the model's one-JSON-action contract. A prose answer,
   two actions, an unknown tool or a missing argument must be refused with the
   right code; a valid action must parse.
2. **Memory retrieval** — recall@3 on a seeded set, hashed or semantic.

No cloud judge, no model download. `--live` additionally asks Bojo for N tool
choices and measures the parse rate end to end (slow on CPU; opt-in).

    python tools/bojo_eval.py --semantic --out reports/bojo_eval_20261104.json
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "Northstar_backend"))

from agent_kernel import tool_protocol as tp  # noqa: E402
from tys_ops import memory  # noqa: E402

SEED_TEXTS = [
    ("gpu", "The render lane takes the GPU lock before it starts."),
    ("video", "The free tier keeps no video and prompts a download."),
    ("aplus", "The A+ header module is 970 by 600 pixels."),
    ("identity", "The ship gate requires identity pHash at most 24 and SSIM at least 0.40."),
    ("campaign", "Tys Assistant files work orders and runs bounded campaigns."),
    ("brain", "The master brain resolves the user profile before acting."),
]
QUERIES = [
    ("which lane takes the GPU lock", "gpu"),
    ("does the free tier keep video", "video"),
    ("A+ header size", "aplus"),
    ("identity threshold", "identity"),
    ("who runs bounded campaigns", "campaign"),
    ("what resolves the user profile", "brain"),
]

TOOL_CASES = [
    (True, '{"tool":"read","args":{"path":"a.py"}}', "valid read"),
    (True, '{"tool":"finish","args":{"summary":"done"}}', "valid finish"),
    (False, "I will read the file now.", "prose, no JSON"),
    (False, '{"tool":"read","args":{"path":"a.py"}} {"tool":"run","args":{"cmd":["ls"]}}',
     "two actions"),
    (False, '{"tool":"rm_rf","args":{}}', "unknown tool"),
    (False, '{"tool":"read","args":{}}', "missing required arg"),
    (False, '{"tool":"read","args":{"path":"a.py"}', "truncated JSON"),
    (True, '{"tool":"read","args":{"path":"a.py"},"notes":["check"]}',
     "extra top-level notes are allowed"),
]


def _schema_ok(action: Any) -> bool:
    schema = tp._SCHEMA.get(getattr(action, "tool", ""))
    if not schema:
        return False
    args = getattr(action, "args", {}) or {}
    return all(key in args for key, (_, required) in schema.items() if required)


def run_tools() -> Dict[str, Any]:
    correct = 0
    rows: List[Dict[str, Any]] = []
    for should_parse, text, note in TOOL_CASES:
        try:
            action = tp.parse_action(text)
            parsed, code = _schema_ok(action), "" if _schema_ok(action) else "schema"
        except tp.ActionError as exc:
            action, parsed, code = None, False, exc.code
        ok = parsed is should_parse
        correct += int(ok)
        rows.append({"case": note, "expected_parse": should_parse,
                     "parsed": parsed, "code": code, "ok": ok,
                     "tool": getattr(action, "tool", None)})
    return {"cases": len(TOOL_CASES), "correct": correct,
            "accuracy": round(correct / len(TOOL_CASES), 3), "rows": rows}


def run_memory(*, semantic: bool) -> Dict[str, Any]:
    index = memory.MemoryIndex(str(ROOT / "state" / "eval_memory.db"), semantic=semantic)
    account = "eval"
    for key, text in SEED_TEXTS:
        index.remember_text(account, text, source=f"seed:{key}")
    hits_total = 0
    rows = []
    for query, expected in QUERIES:
        hits = index.search(account, query, k=3)
        texts = " ".join(hit["text"] for hit in hits).lower()
        hit = expected.lower() in texts or any(
            expected.lower() in (h["source"] or "") for h in hits)
        hits_total += int(hit)
        rows.append({"query": query, "expected": expected,
                     "hit": bool(hit), "hits": len(hits),
                     "semantic": bool(hits and hits[0].get("semantic"))})
    result = {"queries": len(QUERIES), "hits": hits_total,
              "recall_at_3": round(hits_total / len(QUERIES), 3),
              "semantic": index.semantic, "semantic_reason": index.semantic_reason,
              "rows": rows}
    index.close()
    return result


def run_live(prompts: int = 8) -> Dict[str, Any]:
    """Ask the local Bojo for one action per prompt and measure parseability."""
    import urllib.request

    schema = tp.json_schemas()
    tasks = ["list the repository root", "read Northstar_backend/tys_api.py",
             "search for GPU lock", "write a file with the word ok",
             "run python -c print(1)", "finish with a summary",
             "grep for memory in tys_ops", "read the state file"]
    parsed = 0
    rows = []
    for task in tasks[:prompts]:
        payload = {
            "model": "bojo:latest",
            "messages": [{"role": "user", "content": (
                "You are Tys. Reply with exactly one JSON action. "
                f"Task: {task}")}],
            "tools": schema, "stream": False, "options": {"temperature": 0.1},
        }
        req = urllib.request.Request(
            "http://127.0.0.1:11434/api/chat", data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=180) as response:
                data = json.loads(response.read().decode("utf-8"))
            content = ((data.get("message") or {}).get("content") or "").strip()
            try:
                tp.parse_action(content)
                ok, code = True, ""
                parsed += 1
            except tp.ActionError as exc:
                ok, code = False, exc.code
        except Exception as exc:  # noqa: BLE001
            content, ok, code = "", False, f"transport:{type(exc).__name__}"
        rows.append({"task": task, "ok": ok, "code": code,
                     "content": content[:200]})
    return {"prompts": len(rows), "parsed": parsed,
            "parse_rate": round(parsed / max(1, len(rows)), 3), "rows": rows}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--semantic", action="store_true",
                    help="use qwen3-embedding + sqlite-vec for the memory suite")
    ap.add_argument("--live", action="store_true", help="call Bojo for tool calls")
    ap.add_argument("--out", default="reports/bojo_eval_20261104.json")
    args = ap.parse_args(argv)
    started = time.time()
    report = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "suite": "bojo",
        "tools": run_tools(),
        "memory": run_memory(semantic=args.semantic),
        "seconds": None,
    }
    if args.live:
        report["live"] = run_live()
    report["seconds"] = round(time.time() - started, 1)
    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k not in ("tools", "memory", "live")},
                     indent=2))
    print("tools", report["tools"]["accuracy"], "memory",
          report["memory"]["recall_at_3"],
          "semantic", report["memory"]["semantic"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
