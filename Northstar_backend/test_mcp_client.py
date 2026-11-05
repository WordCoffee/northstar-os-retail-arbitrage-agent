"""The MCP client: a real child process, a real handshake, a real tool call.

This is an integration test on purpose. The prior gap was not "the code is
untested", it was "nothing can consume a server"; a mocked transport would
reproduce exactly the illusion that was wrong.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import mcp_client as mc  # noqa: E402

FIXTURE = str(ROOT / "tests" / "fixtures" / "mcp_echo_server.py")


def test_client_lists_tools_from_a_real_server():
    out = mc.list_tools(sys.executable, [FIXTURE], timeout=120)
    names = {t["name"] for t in out["server_tools"]}
    assert names == {"add", "echo"}
    assert out["tool_count"] == 2
    schema = next(t for t in out["server_tools"] if t["name"] == "add")["input_schema"]
    assert set(schema["properties"]) == {"a", "b"}


def test_client_calls_a_tool_and_gets_the_result():
    out = mc.call_tool("add", {"a": 2, "b": 3},
                       command=sys.executable, args=[FIXTURE], timeout=120)
    assert out["called"] == "add"
    assert out["is_error"] is False
    assert "5" in str(out["content"])


def test_unknown_tool_is_reported_not_swallowed():
    out = mc.call_tool("does_not_exist", {},
                       command=sys.executable, args=[FIXTURE], timeout=120)
    # mcp 2.1.1 returns a server-side tool failure as *content*, not isError.
    # The client must not turn that into a success-looking empty result.
    assert "unknown tool" in str(out["content"]).lower()


def test_server_that_cannot_start_fails_loudly():
    try:
        mc.list_tools(sys.executable, ["does_not_exist_server.py"], timeout=30)
    except mc.McpFailure as exc:
        assert "McpFailure" in str(exc) or "timeout" in str(exc).lower() or str(exc)
    else:  # pragma: no cover - a silent empty list is the failure being prevented
        raise AssertionError("a missing server must not look like an empty tool list")
