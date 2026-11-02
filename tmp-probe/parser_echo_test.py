"""Would the runtime lift <tool_call> tags if the model emitted them verbatim?

No tools array is sent, so the template's tool instructions are absent and the model
is only asked to echo a block. If the tags come back as plain content, the parser is
not lifting them for this artifact.
"""
import json
import sys
import urllib.request

OLLAMA = "http://127.0.0.1:11434"
MODEL = sys.argv[1] if len(sys.argv) > 1 else "qwen2.5-coder:7b-parser-f16"
PROMPT = (
    "Repeat the following block exactly, character for character, and nothing else:\n"
    "<tool_call>\n"
    '{"name": "read_file", "arguments": {"path": "Northstar_backend/calc.py"}}\n'
    "</tool_call>")

payload = {"model": MODEL, "messages": [{"role": "user", "content": PROMPT}],
           "stream": False, "options": {"temperature": 0.0, "num_predict": 120}}
req = urllib.request.Request(OLLAMA + "/api/chat", data=json.dumps(payload).encode(),
                             headers={"Content-Type": "application/json"}, method="POST")
with urllib.request.urlopen(req, timeout=180) as r:
    res = json.loads(r.read().decode())
msg = res.get("message") or {}
print(json.dumps({"model": MODEL, "tool_calls": msg.get("tool_calls"),
                  "content": str(msg.get("content") or "")[:240]}, indent=2))
