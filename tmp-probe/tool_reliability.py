"""Native tool-call reliability for one lane: 3 prompts, structured calls only."""
import json
import sys
import urllib.request

OLLAMA = "http://127.0.0.1:11434"
MODEL = sys.argv[1] if len(sys.argv) > 1 else "qwen2.5-coder:7b"

TOOLS = [{
    "type": "function",
    "function": {
        "name": "read_file",
        "description": "Read one file from the workspace.",
        "parameters": {"type": "object",
                       "properties": {"path": {"type": "string"}},
                       "required": ["path"]},
    },
}]

PROMPTS = [
    "Read the file Northstar_backend/calc.py.",
    "Use the read_file tool to read Northstar_backend/calc.py. Call the tool; do not explain.",
    "Call read_file with path=Northstar_backend/calc.py",
]


def post(payload, timeout=240):
    req = urllib.request.Request(OLLAMA + "/api/chat", data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


out = []
for prompt in PROMPTS:
    payload = {"model": MODEL, "messages": [{"role": "user", "content": prompt}],
               "tools": TOOLS, "stream": False,
               "options": {"temperature": 0.0, "num_predict": 200}}
    try:
        res = post(payload)
        msg = res.get("message") or {}
        calls = msg.get("tool_calls") or []
        first = (calls[0] or {}) if calls else {}
        fn = (first.get("function") or {})
        out.append({"prompt": prompt[:60],
                    "tool_calls": bool(calls),
                    "name": fn.get("name"),
                    "arguments": fn.get("arguments"),
                    "content_head": str(msg.get("content") or "")[:120]})
    except Exception as exc:  # noqa: BLE001
        out.append({"prompt": prompt[:60], "error": f"{type(exc).__name__}: {str(exc)[:120]}"})

print(json.dumps(out, indent=2))
print("structured_calls:", sum(1 for o in out if o.get("tool_calls")), "of", len(out))
