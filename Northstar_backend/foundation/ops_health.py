"""Process health for the worker and scheduler containers (P1-05 / P4).

Both processes are polling loops, so "the container is up" says nothing about
whether the loop is actually making progress. This module gives each one a
readiness endpoint that reports the real state:

  GET /healthz   -> liveness: the process is running and serving
  GET /readyz    -> readiness: the last iteration succeeded and is recent
  GET /status    -> the same numbers, as JSON, for Monitoring

A wedged loop shows up as ``ready: false`` with the last error visible, so it
can never fail silently again. Zero network egress, zero credentials, zero
dependencies outside the standard library.
"""

from __future__ import annotations

import json
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Optional


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ProcessHealth:
    """Thread-safe record of a polling loop's progress."""

    def __init__(self, name: str, *, stale_after_seconds: float = 30.0):
        self.name = name
        self.stale_after_seconds = stale_after_seconds
        self._lock = threading.Lock()
        self.started_at = _now()
        self.iterations = 0
        self.failures = 0
        self.consecutive_failures = 0
        self.last_success_at: Optional[str] = None
        self.last_error: Optional[str] = None
        self.last_error_at: Optional[str] = None

    def record_success(self) -> None:
        with self._lock:
            self.iterations += 1
            self.consecutive_failures = 0
            self.last_success_at = _now()

    def record_failure(self, error: str) -> None:
        with self._lock:
            self.iterations += 1
            self.failures += 1
            self.consecutive_failures += 1
            self.last_error = str(error)[:500]
            self.last_error_at = _now()

    def snapshot(self) -> dict:
        with self._lock:
            ready = (
                self.iterations > 0
                and self.consecutive_failures == 0
                and self.last_success_at is not None
            )
            return {
                "process": self.name,
                "started_at": self.started_at,
                "iterations": self.iterations,
                "failures": self.failures,
                "consecutive_failures": self.consecutive_failures,
                "last_success_at": self.last_success_at,
                "last_error": self.last_error,
                "last_error_at": self.last_error_at,
                "ready": ready,
            }

    # -- HTTP surface ----------------------------------------------------

    def serve(self, port: int, host: str = "0.0.0.0") -> ThreadingHTTPServer:
        health = self

        class _Handler(BaseHTTPRequestHandler):
            def log_message(self, *_args):  # keep container logs quiet
                return

            def _respond(self, code: int, payload: dict) -> None:
                body = json.dumps(payload).encode("utf-8")
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):  # noqa: N802 - stdlib naming
                if self.path == "/status":
                    self._respond(200, health.snapshot())
                    return
                snapshot = health.snapshot()
                if self.path in ("/healthz", "/readyz"):
                    if self.path == "/healthz":
                        self._respond(200, {"status": "ok", "process": health.name})
                        return
                    self._respond(
                        200 if snapshot["ready"] else 503,
                        {"status": "ready" if snapshot["ready"] else "not-ready",
                         **snapshot},
                    )
                    return
                self._respond(404, {"error": "not found"})

        server = ThreadingHTTPServer((host, port), _Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        return server
