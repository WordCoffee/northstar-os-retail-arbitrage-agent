"""The package vet must refuse on malware and never pass on a failed check.

A supply-chain check that returns "clear" when it could not reach the advisory
service is worse than no check: it converts an unknown into a green light. Every
case below pins a way it could do that.

The OSV endpoint is overridden with a local server, so these run offline.
"""
from __future__ import annotations

import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import vet_package as vp  # noqa: E402


def _server(payload, *, status: int = 200, raw: bytes | None = None):
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            length = int(self.headers.get("Content-Length") or 0)
            self.rfile.read(length)
            body = raw if raw is not None else json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://127.0.0.1:{server.server_address[1]}/v1/query"


def test_a_clean_package_is_clear():
    server, url = _server({"vulns": []})
    try:
        out = vp.vet("requests", "PyPI", "2.31.0", endpoint=url)
    finally:
        server.shutdown()
    assert out["ok"] is True and out["verdict"] == "clear"
    assert out["malicious"] == [] and out["vulnerabilities"] == []


def test_a_mal_advisory_refuses_and_names_the_id():
    server, url = _server({"vulns": [{"id": "MAL-2024-1234"}, {"id": "GHSA-aaaa"}]})
    try:
        out = vp.vet("evil-pkg", "PyPI", endpoint=url)
    finally:
        server.shutdown()
    assert out["ok"] is False and out["verdict"] == "malicious"
    assert out["malicious"] == ["MAL-2024-1234"]
    # A CVE-style advisory is a risk decision, not malware: reported, not fatal.
    assert out["vulnerabilities"] == ["GHSA-aaaa"]


def test_an_ordinary_vulnerability_does_not_refuse():
    server, url = _server({"vulns": [{"id": "CVE-2020-0001"}, {"id": "GHSA-bbbb"}]})
    try:
        out = vp.vet("old-lib", "PyPI", "0.1", endpoint=url)
    finally:
        server.shutdown()
    assert out["ok"] is True
    assert out["vulnerabilities"] == ["CVE-2020-0001", "GHSA-bbbb"]


def test_an_unreachable_endpoint_is_a_refusal_not_a_pass():
    with pytest.raises(vp.VetError, match="osv_unreachable"):
        vp.vet("requests", "PyPI", endpoint="http://127.0.0.1:1/v1/query", timeout=1.0)


def test_a_bad_payload_is_a_refusal_not_a_pass():
    server, url = _server(None, raw=b"not json")
    try:
        with pytest.raises(vp.VetError, match="osv_bad_json"):
            vp.vet("requests", "PyPI", endpoint=url)
    finally:
        server.shutdown()


def test_a_missing_name_or_unknown_ecosystem_is_refused():
    with pytest.raises(vp.VetError, match="package_name_missing"):
        vp.vet("", "PyPI")
    with pytest.raises(vp.VetError, match="unknown_ecosystem"):
        vp.vet("requests", "NotARealEcosystem")


def test_the_cli_exit_code_distinguishes_clear_from_malicious():
    server, url = _server({"vulns": [{"id": "MAL-2024-9"}]})
    try:
        assert vp.main(["--name", "x", "--ecosystem", "PyPI", "--endpoint", url]) == 1
    finally:
        server.shutdown()
    server, url = _server({"vulns": []})
    try:
        assert vp.main(["--name", "x", "--ecosystem", "PyPI", "--endpoint", url]) == 0
    finally:
        server.shutdown()
