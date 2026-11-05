"""The Northstar MCP server exposes six read-only tools and no path escape."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import northstar_mcp_server as mcp_server  # noqa: E402


def test_server_registers_the_read_only_tools():
    assert mcp_server.SERVER.name == "northstar-os"
    tools = mcp_server.SERVER._tool_manager.list_tools()
    names = {tool.name for tool in tools}
    assert {"northstar_health", "tys_state", "tys_tasks", "memory_search",
            "provider_suite", "render_manifest"} <= names


def test_render_manifest_refuses_paths_outside_renders():
    result = mcp_server.render_manifest("docs/V3_MASTER_PLAN.md")
    assert result["ok"] is False
    assert "outside renders" in result["error"]


def test_provider_suite_returns_the_local_catalog():
    catalog = mcp_server.provider_suite()
    assert catalog.get("active_provider") == "local"
