"""Local 27B prompt author: endpoint contract, fail-closed, brief shape."""
from __future__ import annotations

import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import prompt_author as pa


def _server(content: str, *, status: int = 200):
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            length = int(self.headers.get("Content-Length") or 0)
            self.rfile.read(length)
            body = json.dumps({
                "model": "northstaros-27b-coder",
                "choices": [{"message": {"content": content}}],
            }).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, f"http://127.0.0.1:{server.server_address[1]}/v1"


def test_author_prompt_reads_the_local_lane():
    server, url = _server("A pristine blank kraft folding carton, unprinted uniform "
                          "matte board, soft studio light, seamless light-grey background.")
    try:
        out = pa.author_prompt({"format": "box"}, url=url, timeout=5)
    finally:
        server.shutdown()
    assert out["ok"] is True
    assert "blank kraft" in out["prompt"]
    assert out["warnings"] == []


def test_unreachable_lane_raises_instead_of_templating():
    with pytest.raises(pa.PromptAuthorUnavailable):
        pa.author_prompt({}, url="http://127.0.0.1:1/v1", timeout=0.5)


def test_empty_completion_raises():
    server, url = _server("   ")
    try:
        with pytest.raises(pa.PromptAuthorUnavailable):
            pa.author_prompt({}, url=url, timeout=5)
    finally:
        server.shutdown()


def test_type_terms_are_reported_as_warnings():
    server, url = _server("A blank box with a small logo and a label.")
    try:
        out = pa.author_prompt({"format": "box"}, url=url, timeout=5)
    finally:
        server.shutdown()
    assert out["ok"] is True
    assert any("logo" in w for w in out["warnings"])


def test_build_brief_carries_format_geometry_and_constraints():
    job = SimpleNamespace(
        geometry="bottle",
        geometry_dims={"diameter": 60, "height": 200, "label_height": 80,
                       "label_top_offset": 30},
        product={"id": "p", "category": "supplement", "substrate": "amber glass"},
    )
    brief = pa.build_brief(job)
    assert brief["format"] == "bottle"
    assert "bottle" in brief["form"]
    assert brief["geometry"]["diameter_mm"] == 60
    assert brief["geometry"]["label_height_mm"] == 80
    assert any("unprinted" in c for c in brief["constraints"])
    assert "brand name" in " ".join(brief["constraints"]).lower()
