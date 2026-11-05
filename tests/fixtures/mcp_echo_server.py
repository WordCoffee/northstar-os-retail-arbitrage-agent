"""A deliberately trivial MCP server, for proving the client half works.

Not a product surface. Two deterministic tools and one resource, so a client
probe has something to list and something to call without needing the Northstar
backend to be up.

    python tests/fixtures/mcp_echo_server.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "Northstar_backend"))

from mcp.server.mcpserver import MCPServer  # noqa: E402

SERVER = MCPServer(
    "northstar-echo",
    title="Northstar MCP probe fixture",
    description="Deterministic tools used to verify the MCP client path.",
    version="1.0.0",
)


@SERVER.tool(description="Add two integers.")
def add(a: int, b: int) -> dict:
    return {"sum": int(a) + int(b)}


@SERVER.tool(description="Echo a string back, upper-cased.")
def echo(text: str) -> dict:
    return {"echo": str(text).upper()}


def main() -> int:
    SERVER.run("stdio")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
