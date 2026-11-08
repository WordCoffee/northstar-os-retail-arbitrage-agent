"""Guarded transport for the discovery lane.

Every request goes through ``tools.web_research.guard()`` **before** a socket is
opened.  That is the hardcoded Amazon blocklist plus the scheme/host checks, and
it is the same code path the rest of the bench uses, so this lane cannot become
a second, ungoverned outbound path.

What this module adds over ``web_research._http``: the HTTP status and response
headers (GitHub quota is read from ``X-RateLimit-Remaining``), gzip decoding,
and a scout journal.  Failures are exceptions, never empty lists.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:  # pragma: no cover - import bootstrap
    sys.path.insert(0, str(ROOT))

from tools.web_research import Refused, Transport, guard  # noqa: E402

from . import config  # noqa: E402

JOURNAL = ROOT / "logs" / "scout.jsonl"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class ScoutTransport(RuntimeError):
    """The request could not be completed.  Never a result, never a pass."""

    def __init__(self, message: str, *, url: str = "", status: Optional[int] = None):
        super().__init__(message)
        self.url = url
        self.status = status


@dataclass
class Response:
    url: str
    status: int
    headers: Dict[str, str] = field(default_factory=dict)
    body: bytes = b""
    method: str = "GET"

    def json(self) -> Any:
        try:
            return json.loads(self.body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ScoutTransport(f"bad_json: {exc}", url=self.url, status=self.status) from exc

    def text(self) -> str:
        return self.body.decode("utf-8", "replace")

    def header(self, name: str, default: str = "") -> str:
        return self.headers.get(name.lower(), default)


def _journal(record: Dict[str, Any]) -> None:
    try:
        JOURNAL.parent.mkdir(parents=True, exist_ok=True)
        with JOURNAL.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"at": _now(), **record}, ensure_ascii=False) + "\n")
    except OSError:  # journaling must never take the lane down
        pass


def request(url: str, *, method: str = "GET", timeout: float = 25.0,
            headers: Optional[Dict[str, str]] = None,
            allow_status: tuple = ()) -> Response:
    """Fetch one URL.  Raises ``Refused`` (before transport) or ``ScoutTransport``."""
    guard(url)  # Amazon blocklist first, always
    request_headers = {
        "User-Agent": config.UA,
        "Accept-Encoding": "gzip",
    }
    request_headers.update({str(k): str(v) for k, v in (headers or {}).items()})
    req = urllib.request.Request(url, headers=request_headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            raw = response.read()
            status = int(response.status)
            response_headers = {str(k).lower(): str(v) for k, v in response.headers.items()}
    except urllib.error.HTTPError as exc:
        body = b""
        try:
            body = exc.read() or b""
        except OSError:
            pass
        status = int(exc.code)
        response_headers = {str(k).lower(): str(v) for k, v in (exc.headers or {}).items()}
        if response_headers.get("content-encoding") == "gzip" and body:
            try:
                body = gzip.decompress(body)
            except OSError:
                pass
        _journal({"action": "http", "url": url, "method": method, "status": status,
                  "bytes": len(body), "error": "http_error"})
        if status in allow_status:
            return Response(url=url, status=status, headers=response_headers,
                            body=body, method=method)
        raise ScoutTransport(f"http_{status}: {url}", url=url, status=status) from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        _journal({"action": "http", "url": url, "method": method,
                  "status": "error", "error": str(exc)[:300]})
        raise ScoutTransport(f"unreachable: {exc}", url=url) from exc

    if response_headers.get("content-encoding") == "gzip" and raw:
        try:
            raw = gzip.decompress(raw)
        except OSError:
            pass
    _journal({"action": "http", "url": url, "method": method, "status": status,
              "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()})
    return Response(url=url, status=status, headers=response_headers, body=raw, method=method)


def get_json(url: str, *, timeout: float = 25.0,
             headers: Optional[Dict[str, str]] = None) -> Response:
    response = request(url, headers=headers, timeout=timeout)
    json.loads(response.body.decode("utf-8"))  # validate here, not at the caller
    return response


def quote(value: str) -> str:
    return urllib.parse.quote_plus(str(value))


__all__ = ["Refused", "Transport", "ScoutTransport", "Response", "request", "get_json", "quote"]
