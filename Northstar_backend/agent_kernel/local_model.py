"""Model callable for the bounded coding agent, backed by the local llama.cpp lane.

The agent loop in ``coding_agent.py`` expects ``Model = Callable[[str], str]``:
one prompt in, one JSON tool object out. This module supplies that callable over
the OpenAI-compatible endpoint of ``llama-server`` (default 127.0.0.1:8080).

Thinking is disabled by default. The 27B reasons inside ``<think>`` when it is
enabled and will spend a small token budget there instead of emitting the JSON
object the loop needs; the caller can opt back in per instance.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any, Dict, Optional


class ModelError(RuntimeError):
    """The worker answered but produced no usable content."""


DEFAULT_BASE_URL = "http://127.0.0.1:8080"
DEFAULT_MODEL = "northstaros-27b-coder"

#: Constrains every agent turn to one well-formed tool object. Without it the
#: model occasionally answers with prose or a truncated JSON, which the loop has
#: to reject as a protocol error (measured: 14 wasted steps in one run).
TOOL_CALL_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "required": ["tool"],
    "additionalProperties": False,
    "properties": {
        "tool": {"enum": ["list", "read", "grep", "write", "write_many",
                          "apply_patch", "ast_edit", "ast_edit_batch",
                          "run", "finish"]},
        "args": {"type": "object", "additionalProperties": True},
    },
}


def _post_json(url: str, payload: Dict[str, Any], timeout_s: float) -> Dict[str, Any]:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        return json.loads(resp.read().decode("utf-8"))


def health(base_url: str = DEFAULT_BASE_URL, timeout_s: float = 3.0) -> bool:
    """True when the worker answers /health with status ok."""
    try:
        with urllib.request.urlopen(base_url.rstrip("/") + "/health", timeout=timeout_s) as r:
            data = json.loads(r.read().decode("utf-8"))
        return str(data.get("status") or "").lower() == "ok"
    except Exception:  # noqa: BLE001 - a health probe never raises
        return False


class LlamaCppModel:
    """Prompt -> text over llama-server's /v1/chat/completions."""

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        model: str = DEFAULT_MODEL,
        *,
        timeout_s: float = 600.0,
        max_tokens: int = 600,
        temperature: float = 0.15,
        disable_thinking: bool = True,
        retries: int = 1,
        schema: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_s = float(timeout_s)
        self.max_tokens = int(max_tokens)
        self.temperature = float(temperature)
        self.disable_thinking = bool(disable_thinking)
        self.retries = max(0, int(retries))
        self.schema = schema

    def payload(self, prompt: str) -> Dict[str, Any]:
        body: Dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": "user", "content": str(prompt)}],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "stream": False,
        }
        if self.disable_thinking:
            body["chat_template_kwargs"] = {"enable_thinking": False}
        if self.schema:
            body["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": "tool_call", "schema": self.schema},
            }
        return body

    def __call__(self, prompt: str) -> str:
        url = f"{self.base_url}/v1/chat/completions"
        last: Optional[Exception] = None
        for attempt in range(self.retries + 1):
            try:
                out = _post_json(url, self.payload(prompt), self.timeout_s)
            except urllib.error.URLError as exc:
                last = exc
                if attempt < self.retries:
                    continue
                raise ModelError(f"worker unreachable at {url}: {exc}") from exc
            choices = out.get("choices") or [{}]
            message = (choices[0] or {}).get("message") or {}
            text = str(message.get("content") or "").strip()
            if text:
                return text
            reasoning = str(message.get("reasoning_content") or "").strip()
            last = ModelError(
                "worker returned no content"
                + (f" (reasoning_chars={len(reasoning)})" if reasoning else "")
            )
            if attempt < self.retries:
                # Retry once with a wider budget: a reasoning-only answer means
                # the thinking block ate max_tokens.
                self.max_tokens = min(4096, self.max_tokens * 2)
                self.disable_thinking = True
                continue
        raise last or ModelError("worker returned no content")


def make_local_model(**overrides: Any) -> LlamaCppModel:
    """Build a model callable from TYS_CODING_* env vars plus explicit overrides."""
    params: Dict[str, Any] = {
        "base_url": os.environ.get("TYS_CODING_URL", DEFAULT_BASE_URL),
        "model": os.environ.get("TYS_CODING_MODEL", DEFAULT_MODEL),
        "timeout_s": float(os.environ.get("TYS_CODING_TIMEOUT_S", "600")),
        "max_tokens": int(os.environ.get("TYS_CODING_MAX_TOKENS", "4096")),
        "schema": TOOL_CALL_SCHEMA,
    }
    params.update(overrides)
    return LlamaCppModel(**params)
