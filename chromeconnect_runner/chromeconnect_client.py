"""Chrome Connect client for the runner (P6-T2 wiring).

Talks to ONE persistent Chrome Connect MCP server process over stdio JSON-RPC
and runs tasks through the controller. Replaces the former `html = ""` placeholder.

The runner never drives a browser directly: every call goes through Chrome
Connect, which enforces the domain allowlist, the Amazon blocklist, the profile
lease and the policy kernel. A single persistent process is kept alive so the
transport profile binding (which is session-scoped) can be proven.
"""

from __future__ import annotations

import json
import os
import subprocess
import threading
import time
from typing import Any, Dict, Optional


def _resolve_server() -> str:
    explicit = os.environ.get("CHROMECONNECT_MCP_SERVER")
    if explicit and os.path.exists(explicit):
        return explicit
    candidates = [
        r"C:\Users\T2Hol\OneDrive\Documents\Default Project\scripts\chromecontrol-mcp-server.js",
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    raise FileNotFoundError("chromecontrol-mcp-server.js not found; set CHROMECONNECT_MCP_SERVER")


def _resolve_transport() -> str:
    explicit = os.environ.get("CHROMECONNECT_TRANSPORT_MODULE")
    if explicit and os.path.exists(explicit):
        return explicit
    return r"C:\Users\T2Hol\OneDrive\Documents\Default Project\scripts\chromecontrol-playwright-bridge.js"


class ChromeConnectSession:
    """A persistent stdio session to the Chrome Connect MCP server."""

    def __init__(self):
        self._proc = None
        self._lock = threading.Lock()
        self._buf = ""
        self._id = 0
        self._pending: Dict[int, threading.Event] = {}
        self._results: Dict[int, Any] = {}
        self._reader_thread = None
        self._started = False

    def _start(self):
        if self._started:
            return
        env = dict(os.environ)
        env.setdefault("NORTHSTAR_CDP_HOST", "127.0.0.1")
        env.setdefault("NORTHSTAR_CDP_PORT", "9222")
        env["CHROMECONNECT_TRANSPORT_MODULE"] = _resolve_transport()
        self._proc = subprocess.Popen(
            ["node", _resolve_server()],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            text=True,
            bufsize=1,
        )
        self._reader_thread = threading.Thread(target=self._reader, daemon=True)
        self._reader_thread.start()
        # initialize
        self._request("initialize", {"protocolVersion": "2024-11-05", "capabilities": {},
                                     "clientInfo": {"name": "cc-runner", "version": "1.0"}}, timeout=30)
        self._notify("notifications/initialized", {})
        self._started = True

    def _reader(self):
        while True:
            try:
                line = self._proc.stdout.readline()
            except Exception:
                break
            if line == "":
                break
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except Exception:
                continue
            mid = msg.get("id")
            if mid is not None and mid in self._pending:
                self._results[mid] = msg
                self._pending[mid].set()

    def _request(self, method, params, timeout=120):
        with self._lock:
            self._id += 1
            mid = self._id
            ev = threading.Event()
            self._pending[mid] = ev
            self._proc.stdin.write(json.dumps({"jsonrpc": "2.0", "id": mid, "method": method, "params": params}) + "\n")
            self._proc.stdin.flush()
        if not ev.wait(timeout):
            raise TimeoutError(f"chrome connect did not respond to {method} within {timeout}s")
        msg = self._results.pop(mid, {})
        del self._pending[mid]
        if "error" in msg:
            raise RuntimeError(f"{method} failed: {msg['error']}")
        return msg.get("result")

    def _notify(self, method, params):
        with self._lock:
            try:
                self._proc.stdin.write(json.dumps({"jsonrpc": "2.0", "method": method, "params": params}) + "\n")
                self._proc.stdin.flush()
            except Exception:
                pass

    def fetch_page(self, task: str, url: str, max_steps: int = 4) -> Dict[str, Any]:
        self._start()
        result = self._request("tools/call", {"name": "chromeconnect_run",
                                             "arguments": {"task": task, "url": url,
                                                           "max_steps": max_steps,
                                                           "require_isolated": True}}, timeout=180)
        content = (result or {}).get("content") or []
        text = content[0].get("text") if content and isinstance(content[0], dict) else None
        if not text:
            raise RuntimeError("chrome connect returned no text payload")
        return json.loads(text)

    def fetch_page_text(self, task: str, url: str, max_steps: int = 4) -> str:
        try:
            result = self.fetch_page(task, url, max_steps=max_steps)
        except Exception:
            return ""
        data = result.get("data") or {}
        return str(data.get("text") or data.get("title") or "")

    def close(self):
        try:
            if self._proc:
                self._proc.stdin.close()
                self._proc.wait(timeout=10)
        except Exception:
            try:
                self._proc.kill()
            except Exception:
                pass


# Module-level singleton used by the runner.
_SESSION: Optional[ChromeConnectSession] = None


def get_session() -> ChromeConnectSession:
    global _SESSION
    if _SESSION is None:
        _SESSION = ChromeConnectSession()
    return _SESSION


def fetch_page(task: str, url: str, max_steps: int = 4) -> Dict[str, Any]:
    return get_session().fetch_page(task, url, max_steps=max_steps)


def fetch_page_text(task: str, url: str, max_steps: int = 4) -> str:
    return get_session().fetch_page_text(task, url, max_steps=max_steps)
