"""Local-safe observability: structured events with redaction.

Never logs API keys, tokens, auth headers, or raw credentials.
"""
from __future__ import annotations

import json
import logging
import sys
import time
import uuid
from contextlib import contextmanager
from typing import Any, Iterator, Optional

_FORBIDDEN_KEYS = {
    "password", "secret", "token", "api_key", "apikey", "authorization",
    "refresh_token", "access_token", "credential", "private_key", "session",
    "cookie", "set-cookie", "x-api-key",
}


def new_id() -> str:
    return str(uuid.uuid4())


def redact(data: Any) -> Any:
    if isinstance(data, dict):
        out = {}
        for k, v in data.items():
            if str(k).lower() in _FORBIDDEN_KEYS:
                out[k] = "[REDACTED]"
            else:
                out[k] = redact(v)
        return out
    if isinstance(data, list):
        return [redact(v) for v in data]
    return data


class FoundationLogger:
    def __init__(self, name: str = "northstar.foundation", level: int = logging.INFO) -> None:
        self.logger = logging.getLogger(name)
        if not self.logger.handlers:
            h = logging.StreamHandler(sys.stdout)
            h.setFormatter(logging.Formatter("%(message)s"))
            self.logger.addHandler(h)
        self.logger.setLevel(level)

    def event(self, *, event: str, request_id: Optional[str] = None,
              run_id: Optional[str] = None, organization_id: Optional[str] = None,
              module: Optional[str] = None, duration_ms: Optional[float] = None,
              result: Optional[str] = None, error_class: Optional[str] = None,
              provider: Optional[str] = None,
              cost_status: Optional[str] = None, **extra: Any) -> None:
        payload = {
            "event": event,
            "request_id": request_id,
            "run_id": run_id,
            "organization_id": organization_id,
            "module": module,
            "duration_ms": duration_ms,
            "result": result,
            "error_class": error_class,
            "provider": provider,
            "cost_status": cost_status,
        }
        payload.update(extra)
        self.logger.info(json.dumps(redact(payload), default=str))


@contextmanager
def timed(logger: FoundationLogger, *, event: str, **fields: Any) -> Iterator[dict]:
    start = time.perf_counter()
    ctx: dict = {"result": "success", "error_class": None}
    try:
        yield ctx
    except Exception as e:  # noqa: BLE001
        ctx["result"] = "failure"
        ctx["error_class"] = type(e).__name__
        raise
    finally:
        duration_ms = round((time.perf_counter() - start) * 1000, 3)
        logger.event(event=event, duration_ms=duration_ms,
                     result=ctx.get("result"),
                     error_class=ctx.get("error_class"), **fields)