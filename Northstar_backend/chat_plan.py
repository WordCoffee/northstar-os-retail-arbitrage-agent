"""Plan / DAG reconstruction for the V3 S5 AutothinK plan visualiser.

There is no persisted agent "plan" object. What the turn loop actually records is
ordered and honest: each assistant message's `parts_json`, plus a `chat_tool_
calls` ledger row per tool execution (with `step_index` for exact order). This
module reconstructs a **linear** plan graph from exactly that evidence:

    prompt ──▶ step 0 ──▶ step 1 ──▶ … ──▶ answer

It invents nothing: the tool loop is bounded and sequential (`MAX_TOOL_STEPS`),
so a chain is the true shape. No hidden dependency edges are fabricated, and the
caveats say so. Pure and offline — takes rows in, returns a graph out.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional


def _elapsed_ms(started: Any, ended: Any) -> Optional[int]:
    if not started or not ended:
        return None
    try:
        a = datetime.fromisoformat(str(started).replace("Z", "+00:00"))
        b = datetime.fromisoformat(str(ended).replace("Z", "+00:00"))
        return max(int((b - a).total_seconds() * 1000), 0)
    except (ValueError, TypeError):
        return None


def _label(text: Any, limit: int = 120) -> str:
    s = " ".join(str(text or "").split())
    return s[:limit]


def build_plan(messages: List[Dict[str, Any]],
               tool_calls: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Reconstruct a session's plan graph from messages + tool-call rows."""
    msgs = sorted(messages or [], key=lambda m: str(m.get("created_at") or ""))
    calls = list(tool_calls or [])

    def _calls_for(mid: str) -> List[Dict[str, Any]]:
        mine = [c for c in calls if c.get("message_id") == mid]
        return sorted(mine, key=lambda c: (
            c.get("step_index") if c.get("step_index") is not None else 10 ** 9,
            str(c.get("created_at") or "")))

    nodes: List[Dict[str, Any]] = []
    edges: List[List[str]] = []
    turns: List[Dict[str, Any]] = []
    prev: Optional[str] = None
    pending_user: Optional[str] = None

    def _link(src: Optional[str], dst: str) -> None:
        if src is not None:
            edges.append([src, dst])

    for m in msgs:
        mid = str(m.get("id"))
        role = m.get("role")
        if role != "assistant":
            node_id = f"m:{mid}"
            nodes.append({"id": node_id, "kind": "prompt", "message_id": mid,
                          "label": _label(m.get("content")) or "(empty prompt)",
                          "at": m.get("created_at")})
            _link(prev, node_id)
            prev = node_id
            pending_user = mid
            continue

        turn = {"user_message_id": pending_user, "assistant_message_id": mid,
                "steps": [], "status": (m.get("usage_json") or {}).get("status")
                if isinstance(m.get("usage_json"), dict) else None}
        for c in _calls_for(mid):
            cid = str(c.get("id"))
            node_id = f"t:{cid}"
            result = c.get("result_json") if isinstance(c.get("result_json"), dict) else {}
            nodes.append({
                "id": node_id, "kind": "tool", "message_id": mid,
                "call_id": cid, "name": c.get("name"), "status": c.get("status"),
                "ok": bool(result.get("ok")) if result else None,
                "summary": _label(result.get("summary"), 200),
                "step_index": c.get("step_index"),
                "started_at": c.get("started_at"), "ended_at": c.get("ended_at"),
                "elapsed_ms": _elapsed_ms(c.get("started_at"), c.get("ended_at")),
            })
            _link(prev, node_id)
            prev = node_id
            turn["steps"].append(node_id)

        answer_id = f"m:{mid}"
        nodes.append({"id": answer_id, "kind": "answer", "message_id": mid,
                      "label": _label(m.get("content")) or "(no text)",
                      "at": m.get("created_at")})
        _link(prev, answer_id)
        prev = answer_id
        turns.append(turn)
        pending_user = None

    return {
        "nodes": nodes,
        "edges": edges,
        "turns": turns,
        "step_count": sum(1 for n in nodes if n["kind"] == "tool"),
        "caveats": [
            "Reconstructed from recorded tool calls; the agent's tool loop is sequential.",
            "No hidden dependency edges are implied — the graph is a chain, as the loop is.",
        ],
    }
