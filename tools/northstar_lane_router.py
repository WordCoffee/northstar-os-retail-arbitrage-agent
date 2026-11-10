#!/usr/bin/env python3
"""NorthstarOS lane router.

One OpenAI-compatible endpoint (127.0.0.1:8090/v1) in front of the two llama.cpp
lanes. OpenCode sees both model ids under one provider; a request for either id
makes the router stop the resident lane, start the requested one, and forward.

Only one 27B fits in 16 GB VRAM, so switching lanes is explicit and serialized.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HOST = "127.0.0.1"
PORT = int(os.environ.get("NORTHSTAR_ROUTER_PORT", "8090"))
SERVER = os.path.expandvars(r"%USERPROFILE%\.config\northstar-llm\bin\llama-server.exe")
MODEL_DIR = os.path.expandvars(r"%USERPROFILE%\models\northstar-moe")

LANES = {
    "northstaros-27b-coder": {
        "file": "Qwen3.8-27B-IQ4_XS_4BPW.gguf",
        "port": 8080,
        "kv": "q8_0",
    },
    "northstaros-thinking": {
        "file": "Qwen3.8-27B-IQ4_XS_4BPW.gguf",
        "port": 8080,
        "kv": "q8_0",
    },
}

_lock = threading.Lock()
_current: str | None = None

#: The model's Jinja template accepts only these three values; anything else
#: raises inside the template and llama-server answers 500.
_REASONING_EFFORTS = {"low", "medium", "xhigh"}


def _normalize(payload: dict) -> dict:
    """Map client effort names onto the ones the template accepts."""
    effort = payload.get("reasoning_effort")
    if effort is not None:
        value = str(effort).lower()
        if value in _REASONING_EFFORTS:
            payload["reasoning_effort"] = value
        elif value in {"high", "max"}:
            payload["reasoning_effort"] = "xhigh"
        elif value in {"none", "minimal", "off"}:
            payload["reasoning_effort"] = "low"
        else:
            payload.pop("reasoning_effort", None)
    return payload


def _health(port: int, timeout: float = 2.0) -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=timeout) as r:
            return b'"ok"' in r.read(200)
    except Exception:  # noqa: BLE001
        return False


def _stop_all() -> None:
    try:
        subprocess.run(["taskkill", "/F", "/IM", "llama-server.exe"],
                       capture_output=True, timeout=30)
    except Exception:  # noqa: BLE001
        pass
    time.sleep(3)


def _start(model: str) -> bool:
    lane = LANES[model]
    path = os.path.join(MODEL_DIR, lane["file"])
    if not os.path.exists(path):
        return False
    argv = [
        SERVER, "-m", path, "--alias", model, "-ngl", "99", "-c", "17408",
        "-fa", "on", "-ctk", lane["kv"], "-ctv", lane["kv"], "-np", "1",
        "--jinja", "-b", "2048", "-ub", "512",
        "--spec-type", "draft-mtp", "--spec-draft-n-max", "8",
        "--spec-draft-p-min", "0.8", "--temp", "0.1",
        "--host", HOST, "--port", str(lane["port"]),
    ]
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    # Same pre-flight as the launcher: background GPU consumers can eat the
    # ~1.2 GiB this model leaves free and turn a load into cudaMalloc OOM.
    for hog in ("SoundTune", "MSI.TerminalServer", "LEDKeeper2", "DCv2",
                "msedgewebview2", "PhoneExperienceHost"):
        try:
            subprocess.run(["taskkill", "/F", "/IM", f"{hog}.exe"],
                           capture_output=True, timeout=15)
        except Exception:  # noqa: BLE001
            pass
    subprocess.Popen(argv, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     creationflags=flags)
    deadline = time.time() + 300
    while time.time() < deadline:
        if _health(lane["port"]):
            return True
        time.sleep(2)
    return False


def ensure(model: str) -> bool:
    """Make the requested lane resident. Returns False on an unknown model."""
    global _current
    if model not in LANES:
        return False
    with _lock:
        port = LANES[model]["port"]
        if _current == model and _health(port):
            return True
        if _health(port):
            _current = model
            return True
        _stop_all()
        _current = None
        ok = _start(model)
        if ok:
            _current = model
        return ok


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):  # noqa: D401 - quiet by design
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def _json(self, code: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):  # noqa: N802
        if self.path.rstrip("/") in ("/health", ""):
            self._json(200, {"status": "ok"})
            return
        if self.path.rstrip("/") == "/v1/models":
            self._json(200, {"object": "list", "data": [
                {"id": m, "object": "model", "owned_by": "northstar"}
                for m in LANES
            ]})
            return
        self._json(404, {"error": {"message": "not found"}})

    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            payload = json.loads(raw.decode("utf-8"))
        except Exception:  # noqa: BLE001
            self._json(400, {"error": {"message": "invalid json"}})
            return
        model = str(payload.get("model") or "")
        payload = _normalize(payload)
        raw = json.dumps(payload).encode("utf-8")
        sys.stderr.write(json.dumps({"path": self.path, "model": model,
                                     "keys": sorted(payload.keys())}) + "\n")
        if not payload.get("messages"):
            self._json(400, {"error": {
                "message": "messages must be a non-empty array"}})
            return
        if not ensure(model):
            self._json(503, {"error": {
                "message": f"lane {model!r} is not available "
                           f"(known: {', '.join(LANES)})"}})
            return
        port = LANES[model]["port"]
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}{self.path}",
            data=raw,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=1800) as r:
                body = r.read()
                self.send_response(r.status)
                ctype = r.headers.get("Content-Type", "application/json")
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
        except urllib.error.HTTPError as exc:
            detail = exc.read() or b"{}"
            self.send_response(exc.code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(detail)))
            self.end_headers()
            self.wfile.write(detail)
        except Exception as exc:  # noqa: BLE001
            self._json(502, {"error": {"message": f"lane error: {exc}"}})


def main() -> int:
    if not os.path.exists(SERVER):
        print(f"llama-server not found: {SERVER}", file=sys.stderr)
        return 2
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"lane router on http://{HOST}:{PORT}/v1  models={', '.join(LANES)}", flush=True)
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
