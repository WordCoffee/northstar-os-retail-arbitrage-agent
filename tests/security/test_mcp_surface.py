"""Phase 6: MCP surface — exactly three gateway tools, disabled by default."""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def _talk(messages: list) -> list:
    payload = "\n".join(json.dumps(m) for m in messages) + "\n"
    proc = subprocess.run(
        [sys.executable, "-m", "northstar.gateway.mcp_server"],
        input=payload,
        capture_output=True,
        text=True,
        cwd=str(REPO),
        timeout=60,
    )
    assert proc.returncode == 0, proc.stderr
    return [json.loads(line) for line in proc.stdout.splitlines() if line.strip()]


def test_only_three_tools_exposed():
    responses = _talk(
        [
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        ]
    )
    assert responses[0]["result"]["serverInfo"]["name"] == "northstar-gateway"
    tools = [t["name"] for t in responses[1]["result"]["tools"]]
    assert tools == ["fetch_page", "extract", "markdown_dump"]


def test_amazon_call_denied_with_no_fetch():
    responses = _talk(
        [
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "fetch_page",
                    "arguments": {"task_id": "t1", "url": "http://www.amazon.com/"},
                },
            }
        ]
    )
    result = responses[0]["result"]
    assert result["isError"] is True
    assert "amazon_blocked" in result["content"][0]["text"]


def test_unknown_method_returns_error():
    responses = _talk([{"jsonrpc": "2.0", "id": 9, "method": "bogus"}])
    assert "error" in responses[0]


def test_config_entry_is_disabled_by_default():
    text = (REPO / "opencode.jsonc").read_text(encoding="utf-8")
    match = re.search(r'"northstar-gateway"\s*:\s*\{[^}]*\}', text)
    assert match, "northstar-gateway config entry missing"
    block = match.group(0)
    # Dual-flag: V2 reads "disabled", V1 reads "enabled" (file is V1-shaped).
    assert '"enabled": false' in block
    assert '"disabled": true' in block
    assert "northstar.gateway.mcp_server" in block


def test_skills_exist_with_binding_rules():
    banned = ("<script", "curl ", "wget ", "eval(", "subprocess")
    for skill in ("northstar-data-rules", "northstar-collector"):
        path = REPO / ".opencode" / "skills" / skill / "SKILL.md"
        text = path.read_text(encoding="utf-8")
        lower = text.lower()
        assert "amazon" in lower
        assert "untrusted" in lower
        assert "operator" in lower
        for phrase in banned:
            assert phrase not in lower, f"{skill} contains banned phrase: {phrase}"
