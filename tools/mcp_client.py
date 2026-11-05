"""Consume an MCP server over stdio.

Northstar has *served* MCP since ``tools/northstar_mcp_server.py`` (six read-only
tools). Nothing could *consume* one, so every MCP server in the ecosystem -
filesystem, git, docs, databases - was unreachable. This is the client half.

The surface is deliberately small, because the protocol is:

    initialize()      handshake
    list_tools()      what the server offers, with input schemas
    call_tool()       run exactly one named tool with JSON arguments
    list_resources()  optional: resources the server publishes
    read_resource()   optional: one resource by URI

Every connection is a short-lived child process with a hard timeout, and every
call is appended to ``logs/mcp_client.jsonl``. A server that fails to start is a
reported failure, never an empty tool list.

CLI:

    python tools/mcp_client.py --arg tools/northstar_mcp_server.py --list
    python tools/mcp_client.py --arg tests/fixtures/mcp_echo_server.py --call add --args '{"a": 2, "b": 3}'
    python tools/mcp_client.py --arg tools/northstar_mcp_server.py --call northstar_health

Exit codes: 0 ok, 2 transport/timeout failure.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

ROOT = Path(__file__).resolve().parents[1]
AUDIT_LOG = ROOT / "logs" / "mcp_client.jsonl"


class McpFailure(RuntimeError):
    """The server could not be reached or the call did not complete."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _log(record: Dict[str, Any]) -> None:
    AUDIT_LOG.parent.mkdir(parents=True, exist_ok=True)
    with AUDIT_LOG.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"at": _now(), **record}, ensure_ascii=False) + "\n")


def _text(content: Sequence[Any]) -> Any:
    """MCP returns a list of content blocks; keep text, note anything else."""
    parts: List[Any] = []
    for block in content:
        text = getattr(block, "text", None)
        if text is not None:
            parts.append(text)
        else:
            parts.append({"type": getattr(block, "type", "unknown")})
    if len(parts) == 1:
        return parts[0]
    return parts


def _params(command: str, args: Sequence[str], cwd: Optional[str]) -> Any:
    from mcp import StdioServerParameters

    return StdioServerParameters(command=command, args=list(args), cwd=cwd)


async def _run(command: str, args: Sequence[str], *,
               cwd: Optional[str] = None,
               tool: Optional[str] = None,
               arguments: Optional[Dict[str, Any]] = None,
               timeout: float = 60.0) -> Dict[str, Any]:
    from mcp import ClientSession
    from mcp.client.stdio import stdio_client

    params = _params(command, args, cwd)

    async def body() -> Dict[str, Any]:
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                listed = await session.list_tools()
                tools = [{"name": t.name, "description": (t.description or "")[:300],
                          "input_schema": getattr(t, "input_schema", None) or
                                          getattr(t, "inputSchema", None)}
                         for t in listed.tools]
                result: Dict[str, Any] = {"server_tools": tools,
                                          "tool_count": len(tools)}
                if tool:
                    call = await session.call_tool(tool, arguments or {})
                    result["called"] = tool
                    result["arguments"] = arguments or {}
                    result["is_error"] = bool(getattr(call, "isError", False))
                    result["content"] = _text(call.content)
                return result

    try:
        return await asyncio.wait_for(body(), timeout=timeout)
    except asyncio.TimeoutError as exc:
        raise McpFailure(f"timeout after {timeout}s: {command} {' '.join(args)}") from exc
    except McpFailure:
        raise
    except Exception as exc:  # noqa: BLE001 - every failure is reported, none hidden
        raise McpFailure(f"{type(exc).__name__}: {exc}") from exc


def list_tools(command: str = sys.executable, args: Sequence[str] = (), *,
               cwd: Optional[str] = None, timeout: float = 60.0) -> Dict[str, Any]:
    out = asyncio.run(_run(command, args, cwd=cwd, timeout=timeout))
    _log({"action": "list_tools", "command": command, "args": list(args),
          "status": "ok", "tool_count": out["tool_count"]})
    return out


def call_tool(tool: str, arguments: Optional[Dict[str, Any]] = None, *,
              command: str = sys.executable, args: Sequence[str] = (),
              cwd: Optional[str] = None, timeout: float = 120.0) -> Dict[str, Any]:
    out = asyncio.run(_run(command, args, cwd=cwd, tool=tool,
                           arguments=arguments or {}, timeout=timeout))
    _log({"action": "call_tool", "command": command, "args": list(args),
          "tool": tool, "status": "error" if out.get("is_error") else "ok",
          "sha256": hashlib.sha256(
              json.dumps(out.get("content"), sort_keys=True, default=str).encode()).hexdigest()})
    return out


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="MCP client over stdio.")
    parser.add_argument("--command", default=sys.executable,
                        help="server executable (default: this Python)")
    parser.add_argument("--arg", action="append", default=[],
                        help="server argument; repeat for each")
    parser.add_argument("--cwd", default=None)
    parser.add_argument("--list", action="store_true", help="list the server's tools")
    parser.add_argument("--call", default=None, help="tool name to call")
    parser.add_argument("--args", default="{}", help="JSON object of tool arguments")
    parser.add_argument("--args-file", default=None,
                        help="read tool arguments from a JSON file (shell-quoting safe)")
    parser.add_argument("--timeout", type=float, default=60.0)
    parser.add_argument("--json", action="store_true")
    ns = parser.parse_args(argv)

    if not ns.list and not ns.call:
        parser.print_help()
        return 2

    try:
        raw_args = ns.args
        if ns.args_file:
            raw_args = Path(ns.args_file).read_text(encoding="utf-8")
        arguments = json.loads(raw_args)
        if not isinstance(arguments, dict):
            raise ValueError("--args must be a JSON object")
        out = asyncio.run(_run(ns.command, ns.arg, cwd=ns.cwd,
                               tool=ns.call, arguments=arguments,
                               timeout=ns.timeout))
    except (McpFailure, ValueError) as exc:
        _log({"action": "connect", "command": ns.command, "args": ns.arg,
              "status": "failed", "error": str(exc)})
        print(f"MCP FAILURE (not a result): {exc}", file=sys.stderr)
        return 2

    _log({"action": "probe", "command": ns.command, "args": ns.arg,
          "status": "ok", "tool_count": out["tool_count"]})
    if ns.json:
        print(json.dumps(out, indent=2, ensure_ascii=False, default=str))
        return 0
    print(f"connected: {out['tool_count']} tool(s)")
    for tool in out["server_tools"]:
        print(f"  - {tool['name']}: {tool['description'][:100]}")
    if ns.call:
        print(f"called {ns.call} -> is_error={out.get('is_error')}")
        print(json.dumps(out.get("content"), indent=2, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
