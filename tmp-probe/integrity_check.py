"""Installation integrity: coherent text, structured JSON, native tool call."""
import json
import sys
import urllib.request

OLLAMA = "http://127.0.0.1:11434"
MODEL = sys.argv[1] if len(sys.argv) > 1 else "qwen2.5-coder:7b"


def post(path, payload, timeout=240):
    req = urllib.request.Request(OLLAMA + path, data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def show():
    return post("/api/show", {"model": MODEL})


out = {"model": MODEL}
info = show()
out["capabilities"] = info.get("capabilities")
out["parameters"] = [l.strip() for l in str(info.get("parameters") or "").splitlines() if l.strip()][:8]
out["context_length_hint"] = "see parameters / model_info"

# 1. coherent sentence
gen = post("/api/generate", {"model": MODEL, "prompt":
           "Reply with exactly one short sentence explaining what a Python function is.",
           "stream": False, "think": False,
           "options": {"num_predict": 96, "temperature": 0.1},
           "keep_alive": "10m"})
out["sentence"] = str(gen.get("response") or "").strip()[:200]
out["sentence_ok"] = len(out["sentence"].split()) >= 4

# 2. structured JSON
chat = post("/api/chat", {"model": MODEL, "messages": [{"role": "user", "content":
            "Return a JSON object with the keys ok (true) and color (\"blue\"). Nothing else."}],
            "stream": False, "format": "json", "think": False,
            "options": {"num_predict": 96}})
content = str((chat.get("message") or {}).get("content") or "").strip()
out["json_raw"] = content[:200]
try:
    parsed = json.loads(content)
    out["json_ok"] = isinstance(parsed, dict) and parsed.get("color") == "blue"
except ValueError:
    out["json_ok"] = False

# 3. native tool call
TOOLS = [{
    "type": "function",
    "function": {
        "name": "read_file",
        "description": "Read one file from the workspace.",
        "parameters": {"type": "object",
                       "properties": {"path": {"type": "string",
                                               "description": "workspace-relative path"}},
                       "required": ["path"]},
    },
}]
tc = post("/api/chat", {"model": MODEL,
                        "messages": [{"role": "user",
                                      "content": "Read the file Northstar_backend/calc.py."}],
                        "tools": TOOLS, "stream": False,
                        "options": {"num_predict": 120, "temperature": 0.1}})
msg = tc.get("message") or {}
calls = msg.get("tool_calls") or []
out["tool_calls"] = calls
out["content_when_tools"] = str(msg.get("content") or "")[:160]
out["native_tool_ok"] = bool(calls) and str(
    ((calls[0] or {}).get("function") or {}).get("name") or "") == "read_file"

print(json.dumps(out, indent=2))
