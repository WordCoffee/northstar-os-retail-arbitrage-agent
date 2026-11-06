"""The MCP client is an egress path: it must refuse a shell and refuse Amazon.

Two separate controls, both applied *before* anything is spawned:

  * the server command must be an executable or a script path - ``cmd``,
    ``powershell``, ``bash`` and ``sh`` are refused;
  * every absolute ``http(s)://`` URL argument is screened by
    ``tools/egress_guard.check()`` before the tool call is dispatched.

The "nothing was spawned" proofs put a counter on the real spawn entry point
(``mcp.client.stdio.stdio_client``), so a refusal that still launched a child
process fails the test instead of being asserted in prose.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import mcp_client as mc  # noqa: E402

FIXTURE = str(ROOT / "tests" / "fixtures" / "mcp_echo_server.py")


@pytest.fixture
def spawns(monkeypatch):
    """Count real stdio spawns; a refusal must happen before this is reached."""
    from mcp.client import stdio as stdio_mod

    launched = []
    real = stdio_mod.stdio_client

    def counting(*args, **kwargs):
        launched.append(args)
        return real(*args, **kwargs)

    monkeypatch.setattr(stdio_mod, "stdio_client", counting)
    return launched


def _last_audit():
    lines = mc.AUDIT_LOG.read_text(encoding="utf-8").strip().splitlines()
    return json.loads(lines[-1])


@pytest.mark.parametrize("command", [
    "cmd",
    "cmd.exe",
    r"C:\Windows\System32\cmd.exe",
    "powershell",
    "powershell.exe",
    r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe",
    "pwsh",
    "bash",
    "/bin/sh",
    "sh.exe",
])
def test_shell_wrapper_command_is_refused(command, spawns):
    with pytest.raises(mc.McpRefused) as caught:
        mc.list_tools(command, ["/c", FIXTURE], timeout=5)
    assert "shell_wrapper_refused" in str(caught.value)
    assert spawns == [], "a refused command must not spawn a server"


def test_empty_command_is_refused(spawns):
    with pytest.raises(mc.McpRefused) as caught:
        mc.list_tools("   ", [], timeout=5)
    assert "empty_command" in str(caught.value)
    assert spawns == [], "an empty command must not spawn a server"


def test_shell_refusal_is_written_to_the_audit_line(spawns):
    with pytest.raises(mc.McpRefused):
        mc.list_tools("powershell.exe", ["-c", "echo hi"], timeout=5)
    record = _last_audit()
    assert record["action"] == "list_tools"
    assert record["status"] == "refused"
    assert record["command"] == "powershell.exe"
    assert "shell_wrapper_refused" in record["error"]


def test_amazon_url_argument_is_refused_before_dispatch(spawns):
    with pytest.raises(mc.McpRefused) as caught:
        mc.call_tool("fetch_url", {"url": "https://www.amazon.com/dp/B0TEST"},
                     command=sys.executable, args=[FIXTURE], timeout=30)
    assert "amazon_refused" in str(caught.value)
    assert spawns == [], "the tool call must be refused before a server is spawned"


def test_refusal_audit_records_the_tool_and_the_argument_screened(spawns):
    with pytest.raises(mc.McpRefused):
        mc.call_tool("fetch_url", {"url": "https://www.amazon.com/dp/B0TEST"},
                     command=sys.executable, args=[FIXTURE], timeout=30)
    record = _last_audit()
    assert record["action"] == "call_tool"
    assert record["tool"] == "fetch_url"
    assert record["status"] == "refused"
    checked = record["arguments_checked"]
    assert checked, "the audit line must say which argument was checked"
    assert checked[0]["path"] == "arguments.url"
    assert checked[0]["decision"] == "refused"
    assert "amazon.com" in checked[0]["reason"]


def test_a_nested_amazon_url_is_found(spawns):
    arguments = {"pages": ["https://example.com/ok",
                           {"next": "http://smile.amazon.com/x"}]}
    with pytest.raises(mc.McpRefused) as caught:
        mc.call_tool("fetch_url", arguments,
                     command=sys.executable, args=[FIXTURE], timeout=30)
    assert "amazon_refused" in str(caught.value)
    assert spawns == []


def test_a_url_in_the_server_arguments_is_screened(spawns):
    with pytest.raises(mc.McpRefused):
        mc.list_tools(sys.executable, ["--url", "https://amazon.de/x"], timeout=5)
    assert spawns == []


def test_no_guard_means_no_url_dispatch(monkeypatch, spawns):
    monkeypatch.setattr(mc, "_EGRESS_GUARD", None)
    monkeypatch.setattr(mc, "_EGRESS_GUARD_FAILED", True)
    with pytest.raises(mc.McpRefused) as caught:
        mc.call_tool("fetch_url", {"url": "https://example.com/ok"},
                     command=sys.executable, args=[FIXTURE], timeout=30)
    assert "egress_guard_unavailable" in str(caught.value)
    assert spawns == [], "an unverifiable URL must not be dispatched"


def test_an_allowed_url_is_recorded_and_still_reaches_the_server(spawns):
    out = mc.call_tool("echo", {"text": "https://github.com/block/goose"},
                       command=sys.executable, args=[FIXTURE], timeout=120)
    assert "HTTPS://GITHUB.COM/BLOCK/GOOSE" in str(out["content"])
    assert out["egress_checked"][0]["decision"] == "allowed"
    assert len(spawns) == 1


def test_fixture_server_still_lists_and_calls_a_tool(spawns):
    listed = mc.list_tools(sys.executable, [FIXTURE], timeout=120)
    assert {t["name"] for t in listed["server_tools"]} == {"add", "echo"}
    assert listed["tool_count"] == 2

    out = mc.call_tool("add", {"a": 2, "b": 3},
                       command=sys.executable, args=[FIXTURE], timeout=120)
    assert out["called"] == "add"
    assert out["is_error"] is False
    assert "5" in str(out["content"])
    assert len(spawns) == 2, "the governed path must still launch a real server per call"
