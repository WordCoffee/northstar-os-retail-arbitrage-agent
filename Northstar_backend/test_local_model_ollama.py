"""Ollama native chat adapter: JSON mode, think-off, widening retry."""
from __future__ import annotations

import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent_kernel.local_model import OllamaChatModel, make_local_model


def _server(responses):
    seen = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            length = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(length).decode("utf-8"))
            seen.append(body)
            content = responses[min(len(seen) - 1, len(responses) - 1)]
            payload = json.dumps({"message": {"role": "assistant", "content": content}}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://127.0.0.1:{server.server_address[1]}", seen


def test_ollama_chat_model_requests_json_with_thinking_off():
    server, url, seen = _server(['{"tool":"list","args":{"path":"."}}'])
    try:
        model = OllamaChatModel(base_url=url, model="bojo", max_tokens=64)
        assert model("list the root") == '{"tool":"list","args":{"path":"."}}'
    finally:
        server.shutdown()
    assert seen[0]["format"] == "json"
    assert seen[0]["think"] is False
    assert seen[0]["options"]["num_predict"] == 64


def test_ollama_chat_model_widens_the_budget_after_an_empty_answer():
    server, url, seen = _server(["", '{"tool":"finish","args":{}}'])
    try:
        model = OllamaChatModel(base_url=url, model="bojo", max_tokens=64, retries=1)
        assert "finish" in model("finish")
    finally:
        server.shutdown()
    assert len(seen) == 2
    assert seen[1]["options"]["num_predict"] == 128


def test_make_local_model_ollama_provider():
    server, url, _seen = _server(["{}"])
    try:
        model = make_local_model(provider="ollama", base_url=url, model="bojo",
                                 max_tokens=32)
        assert model("x") == "{}"
    finally:
        server.shutdown()
