"""Tool Execution Gateway (V3 REA inject — OpenBot pattern).

A SINGLE interception point for every tool/shell action an agent attempts.
The OpenBot concept, adapted to this stack and its guardrails:

  1. POLICY — a deny-list of tool names that can execute arbitrary code, touch
     credentials, or reach the network. None are registered today; the list is
     the enforceable boundary, so a future tool cannot silently widen it.
  2. AUDIT — every attempt (allowed AND denied) is written to `tool_audit`
     before execution, plus an `executed` row with the outcome + latency.
  3. EXECUTE — the gateway delegates to `chat_tools.run_tool` (validate →
     execute). No handler is reachable without passing through here.
  4. HONEST RESULTS — denials return the same shape as a normal tool failure
     (`ok:false` + reason), so the model can react instead of crashing.

Hardware telemetry daemon tie-in: the daemon is read-only by construction and
registers NO tools, so it cannot be driven to execute anything. The gateway is
what makes that guarantee enforceable for agent-initiated actions — every
agent tool call is gated and logged, and the telemetry path stays a passive
observer.
"""

from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import chat_tools

# Deny-list: tools that can execute arbitrary code, touch credentials, or
# reach the network are NEVER allowed from an agent turn.
DENY_LIST = frozenset({
    "shell", "exec", "eval", "bash", "sh",
    "credential_read", "credential_write",
    "file_write", "file_delete",
    "network_fetch", "network_post",
})


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def audit_tool_attempt(db, account_id: str, tool: str, decision: str,
                       reason: str = "", detail: str = "") -> None:
    """Best-effort audit write. A logging failure must never break a turn."""
    try:
        db.tool_audit.create({
            "account_id": account_id,
            "tool": tool,
            "decision": decision,
            "reason": reason,
            "detail": str(detail)[:2000],
            "created_at": _now(),
        })
    except Exception:  # noqa: BLE001 - audit must never break the turn
        pass


def is_denied(name: str) -> bool:
    return name in DENY_LIST


def run_tool_gated(db, account_id: str, name: str, raw_args: Any,
                   ctx: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Policy check → audit → execute → audit. Never raises."""
    if name in DENY_LIST:
        audit_tool_attempt(db, account_id, name, "denied", "tool is on the gateway deny-list")
        return {"ok": False, "summary": f"Tool '{name}' is not permitted.",
                "error": "blocked by the tool execution gateway (deny-list)", "assets": []}
    if name not in chat_tools.TOOLS:
        audit_tool_attempt(db, account_id, name, "denied", "unknown tool")
        return chat_tools.run_tool(name, raw_args, ctx)
    audit_tool_attempt(db, account_id, name, "allowed")
    started = time.monotonic()
    result = chat_tools.run_tool(name, raw_args, ctx)
    elapsed_ms = int((time.monotonic() - started) * 1000)
    audit_tool_attempt(db, account_id, name, "executed",
                       detail={"ok": bool(result.get("ok")), "elapsed_ms": elapsed_ms})
    return result
