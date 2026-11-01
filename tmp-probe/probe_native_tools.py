"""Interface probe: does the installed lane support native tool calling, and does
it produce a usable tool call when the schema is supplied through the API rather
than embedded in a JSON-text prompt?

Read-only against the local daemon. No repository changes.
"""
import json
import sys
import time
import urllib.request

OLLAMA = "http://127.0.0.1:11434"

TOOLS = [{
    "type": "function",
    "function": {
        "name": "read",
        "description": "Read one file from the workspace.",
        "parameters": {
            "type": "object",
            "properties": {"path": {"type": "string", "description": "workspace-relative path"}},
            "required": ["path"],
        },
    },
}, {
    "type": "function",
    "function": {
        "name": "ast_edit",
        "description": "Replace the body of a Python function in a file.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "op": {"type": "string", "enum": ["replace_function_body"]},
                "target": {"type": "string"},
                "source": {"type": "string"},
            },
            "required": ["path", "op", "target", "source"],
        },
    },
}]


def post(path, payload, timeout=180):
    req = urllib.request.Request(OLLAMA + path, data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def show(model):
    req = urllib.request.Request(OLLAMA + "/api/show",
                                 data=json.dumps({"model": model}).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode())


def probe(model):
    out = {"model": model}
    try:
        info = show(model)
        out["capabilities"] = info.get("capabilities")
        out["parameters"] = [l for l in str(info.get("parameters") or "").splitlines()
                             if l.strip()][:6]
    except Exception as exc:  # noqa: BLE001
        out["show_error"] = str(exc)[:120]

    payload = {
        "model": model,
        "messages": [{"role": "user",
                      "content": "Read the file Northstar_backend/calc.py so you can fix add()."}],
        "tools": TOOLS,
        "stream": False,
        "options": {"num_predict": 160, "temperature": 0.1},
    }
    t0 = time.time()
    try:
        res = post("/api/chat", payload)
        msg = res.get("message") or {}
        out["elapsed_s"] = round(time.time() - t0, 2)
        out["tool_calls"] = msg.get("tool_calls")
        out["content"] = str(msg.get("content") or "")[:160]
        out["native_ok"] = bool(msg.get("tool_calls"))
    except Exception as exc:  # noqa: BLE001
        out["elapsed_s"] = round(time.time() - t0, 2)
        out["error"] = f"{type(exc).__name__}: {str(exc)[:160]}"
        out["native_ok"] = False
    return out


if __name__ == "__main__":
    models = sys.argv[1:] or ["qwen2.5-coder:3b", "bojo:gpu-orig", "qwen2.5vl:7b"]
    report = [probe(m) for m in models]
    print(json.dumps(report, indent=2))
