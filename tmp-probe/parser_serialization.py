"""Serialization check: does the runtime lift <tool_call> tags into tool_calls?

If the model emits the exact tag format the template asks for and Ollama still
returns plain content, the PARSER directive is not being applied by this runtime.
"""
import json
import sys
import urllib.request

OLLAMA = "http://127.0.0.1:11434"
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

PROMPT = (
    "Emit the tool call EXACTLY as this format, with the tags and nothing else:\n"
    "<tool_call>\n"
    '{"name": "read_file", "arguments": {"path": "Northstar_backend/calc.py"}}\n'
    "</tool_call>")


def chat(model, tools):
    payload = {"model": model, "messages": [{"role": "user", "content": PROMPT}],
               "stream": False, "options": {"temperature": 0.0, "num_predict": 120}}
    if tools:
        payload["tools"] = TOOLS
    req = urllib.request.Request(OLLAMA + "/api/chat", data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.loads(r.read().decode())


for model in sys.argv[1:] or ["qwen2.5-coder:7b-parser-f16"]:
    res = chat(model, True)
    msg = res.get("message") or {}
    print(json.dumps({"model": model,
                      "tool_calls": msg.get("tool_calls"),
                      "content": str(msg.get("content") or "")[:200]}, indent=2))
