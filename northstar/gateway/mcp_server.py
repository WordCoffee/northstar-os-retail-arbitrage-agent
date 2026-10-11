"""Minimal stdio MCP server (dependency-free) exposing ONLY the gateway tools.

- Classic MCP handshake (legacy protocol); exactly three tools:
  ``fetch_page``, ``extract``, ``markdown_dump`` — nothing else exists.
- Safe defaults: EMPTY source allowlist (every fetch denies until an operator
  configures grants), pinned Lightpanda container driver, robots required.
- The OpenCode entry for this server ships ``"disabled": true`` — it connects
  only when the operator enables it.
"""
from __future__ import annotations

import json
import sys
from typing import Any, Dict, Optional

from northstar.gateway.driver import DockerLightpandaDriver
from northstar.gateway.gateway import GATEWAY_VERSION, LightpandaGateway
from northstar.policy import AuditLog, GrantSet, PolicyKernel, RobotsGate

TOOLS = ("fetch_page", "extract", "markdown_dump")
SERVER_NAME = "northstar-gateway"


def build_gateway() -> LightpandaGateway:
    kernel = PolicyKernel(
        robots=RobotsGate({}),  # fail-closed: no robots text → deny
        grants=GrantSet(),
        audit=AuditLog(),
    )
    return LightpandaGateway(kernel=kernel, driver=DockerLightpandaDriver())


def _tool_specs() -> list:
    url_prop = {"type": "string"}
    task_prop = {"type": "string"}
    return [
        {
            "name": "fetch_page",
            "description": (
                "Fetch a policy-allowed page through Lightpanda Connect. Returns "
                "the page title and bounded content inside an untrusted-data "
                "envelope. Every call is policy-checked and audited."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {"task_id": task_prop, "url": url_prop},
                "required": ["task_id", "url"],
            },
        },
        {
            "name": "extract",
            "description": (
                "Fetch a policy-allowed page and return the paragraphs that "
                "contain the given text (untrusted-data envelope)."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "task_id": task_prop,
                    "url": url_prop,
                    "text": {"type": "string"},
                    "limit": {"type": "integer"},
                },
                "required": ["task_id", "url", "text"],
            },
        },
        {
            "name": "markdown_dump",
            "description": (
                "Fetch a policy-allowed page and return its full sanitized "
                "markdown inside an untrusted-data envelope."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {"task_id": task_prop, "url": url_prop},
                "required": ["task_id", "url"],
            },
        },
    ]


def _error(request_id: Any, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def handle(request: Dict[str, Any], gateway: LightpandaGateway) -> Optional[dict]:
    method = request.get("method")
    request_id = request.get("id")

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": SERVER_NAME, "version": GATEWAY_VERSION},
            },
        }
    if method == "notifications/initialized":
        return None
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": request_id, "result": {"tools": _tool_specs()}}
    if method == "tools/call":
        params = request.get("params") or {}
        name = params.get("name")
        arguments = params.get("arguments") or {}
        if name not in TOOLS:
            return _error(request_id, -32601, f"unknown tool: {name!r}")
        try:
            if name == "extract":
                result = gateway.extract(
                    task_id=str(arguments.get("task_id") or ""),
                    url=str(arguments.get("url") or ""),
                    text=str(arguments.get("text") or ""),
                    limit=int(arguments.get("limit") or 10),
                )
            else:
                tool = getattr(gateway, name)
                result = tool(
                    task_id=str(arguments.get("task_id") or ""),
                    url=str(arguments.get("url") or ""),
                )
        except Exception as exc:  # never leak internals
            return _error(request_id, -32603, f"tool failed: {type(exc).__name__}")
        text = (
            result.envelope
            if result.ok
            else f"DENIED: {result.reason}" + (f" :: {result.detail}" if result.detail else "")
        )
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "content": [{"type": "text", "text": text}],
                "isError": not result.ok,
            },
        }
    return _error(request_id, -32601, f"method not found: {method!r}")


def main() -> int:
    gateway = build_gateway()
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
        except json.JSONDecodeError:
            continue
        response = handle(request, gateway)
        if response is not None:
            sys.stdout.write(json.dumps(response) + "\n")
            sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
