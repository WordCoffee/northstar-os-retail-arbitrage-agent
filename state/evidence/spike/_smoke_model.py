"""Smoke probe: does the local Ollama coding lane answer in the agent's protocol?

Run:  python state/evidence/spike/_smoke_model.py [model]
Prints latency + the raw reply so the spike record can cite a real call.
"""
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
sys.path.insert(0, os.path.join(ROOT, "Northstar_backend"))

from agent_kernel.local_model import make_local_model  # noqa: E402

PROMPT = (
    "You are the Northstar OS coding worker. Reply with exactly ONE JSON "
    "object per turn: no prose, no markdown fences.\n\n"
    'ACTIONS (only these are accepted: read, ast_edit, finish):\n'
    '{"tool":"read","args":{"path":"sample.py"}}\n'
    '{"tool":"ast_edit","args":{"path":"sample.py","op":"replace_function_body",'
    '"target":"add","source":"return a + b + 1"}}\n'
    '{"tool":"finish","args":{"summary":"..."}}\n\n'
    "TASK:\nMake add() return a + b + 1.\n\nNext JSON object:"
)


def main() -> int:
    model_name = sys.argv[1] if len(sys.argv) > 1 else os.environ.get(
        "TYS_CODING_MODEL", "qwen2.5-coder:7b")
    model = make_local_model(provider="ollama", model=model_name)
    t0 = time.time()
    out = model(PROMPT)
    dt = time.time() - t0
    payload = json.loads(out) if out.strip().startswith("{") else {"raw": out}
    print(json.dumps({"model": model_name, "latency_s": round(dt, 2),
                      "parsed": {k: payload.get(k) for k in ("tool", "args")},
                      "raw": out[:400]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
