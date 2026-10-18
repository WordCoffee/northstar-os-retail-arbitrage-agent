"""Design Studio — Simple-mode chat core (S1/S2).

The chat transport for the Master Brain shell: sessions, message history, and
a streaming turn endpoint (SSE) with a bounded TOOL LOOP (S2). Event
vocabulary (fixed, stable):

    start · notice · thinking · token · tool-start · tool-progress ·
    tool-end · asset · error · done

S2 additions:
  • tools are offered to the local model (Ollama `tools`) when enabled;
    calls are validated (outputguard-style), executed in a worker thread and
    streamed back as tool-start/progress/end frames + asset frames;
  • ComfyUI render progress flows through studio_generation's /ws listener
    into tool-progress frames (pct + label);
  • tool calls + produced assets persist on chat_tool_calls / chat_attachments;
  • the loop is bounded (MAX_TOOL_STEPS) and every failure is an honest
    tool-end {ok:false, error} the model can react to.

Honesty boundaries (house rules):
  • No fabricated replies — an offline engine persists the REAL fallback text
    plus an error event.
  • A cancelled, failed, or client-abandoned turn is persisted with its true
    status (done | cancelled | error) in usage_json — partial stays partial.
  • Tool events are only emitted when a tool actually ran.
"""

from __future__ import annotations

import json
import os
import queue
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Iterable, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from data_layer import get_northstar_db
from design_studio_api import studio_account
import chat_adapter
import chat_tools
from shell_focus import VALID_FOCUS_IDS, tools_for_focus

router = APIRouter(prefix="/api/chat", tags=["chat"])

SSE_EVENT_TYPES = (
    "start", "notice", "thinking", "token",
    "tool-start", "tool-progress", "tool-end",
    "asset", "error", "done",
)

# Live turn registry: cancel is an explicit POST, matched to a live stream by
# turn id. In-process and deliberately non-durable (same doctrine as the
# AutothinK RunRegistry): a server restart voids in-flight turns, and nothing
# pretends otherwise.
_TURNS: Dict[str, threading.Event] = {}
_TURNS_LOCK = threading.Lock()
MAX_TURNS_TRACKED = 200


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def tools_enabled_default() -> bool:
    return os.environ.get("CHAT_TOOLS_ENABLED", "1").strip() != "0"


def sse_frame(event_type: str, payload: Dict[str, Any]) -> str:
    """One SSE frame. Pure — unit-tested without a socket."""
    return f"event: {event_type}\ndata: {json.dumps(payload, default=str)}\n\n"


def register_turn(turn_id: str) -> threading.Event:
    ev = threading.Event()
    with _TURNS_LOCK:
        while len(_TURNS) >= MAX_TURNS_TRACKED:
            oldest = next(iter(_TURNS))
            _TURNS.pop(oldest, None)
        _TURNS[turn_id] = ev
    return ev


def cancel_turn(turn_id: str) -> bool:
    with _TURNS_LOCK:
        ev = _TURNS.get(turn_id)
    if ev is None:
        return False
    ev.set()
    return True


def _drain_turn(turn_id: str) -> None:
    with _TURNS_LOCK:
        _TURNS.pop(turn_id, None)


def _args_for_model(call: Dict[str, Any]) -> Any:
    if call.get("obj_args") is not None:
        return call["obj_args"]
    try:
        return chat_tools.parse_arguments(call.get("raw_args"))
    except chat_tools.ToolValidationError:
        return {}


def turn_event_stream(db, account_id: str, session: Dict[str, Any], user_content: str,
                      *, think: bool = True, model: Optional[str] = None,
                      events: Optional[Any] = None,
                      cancel_event: Optional[threading.Event] = None,
                      tools_enabled: Optional[bool] = None):
    """Sync generator of SSE frames for one turn (tool loop included).

    `events` injects scripted adapter streams: callable(round_idx, messages) ->
    iterable, or a plain iterable used for round 0 (tests). Production passes
    None and the real UnifiedLLMAdapter stream is used with the tool schemas.

    Persistence guarantee: whatever text/tools the turn produced is written
    exactly once on EVERY exit path — completion, cancel, adapter error, or
    client disconnect — with the true status recorded in usage_json.
    """
    turn_id = uuid.uuid4().hex
    own_event = cancel_event is None
    if own_event:
        cancel_event = register_turn(turn_id)
    if tools_enabled is None:
        tools_enabled = tools_enabled_default()

    thinking_parts: List[str] = []
    content_parts: List[str] = []
    tool_parts: List[Dict[str, Any]] = []
    tool_records: List[Dict[str, Any]] = []
    attachment_records: List[Dict[str, Any]] = []
    status = "done"
    cancelled = False
    usage = None
    error_reason = None
    persisted = False

    available_tools = None
    if tools_enabled:
        # The session's focus restricts which tools are offered to the model.
        # The catalogue is server-owned (shell_focus); the UI can only pick an
        # id, never widen the set.
        _focus = session.get("focus_json") if isinstance(session.get("focus_json"), dict) else {}
        available_tools = chat_tools.ollama_tool_schemas(tools_for_focus(_focus.get("mode")))

    def _persist(final_status: str) -> Optional[str]:
        thinking_text = "".join(thinking_parts)
        content_text = "".join(content_parts)
        if final_status == "error" and not content_text:
            content_text = chat_adapter.offline_notice(error_reason or "unknown")
        if not (thinking_text or content_text or tool_parts):
            return None  # a cut turn that produced nothing is not a message
        parts: List[Dict[str, Any]] = []
        if thinking_text:
            parts.append({"type": "thinking", "text": thinking_text})
        parts.extend(tool_parts)
        if content_text:
            parts.append({"type": "text", "text": content_text})
        mid = db.chat.messages.create({
            "account_id": account_id,
            "session_id": session.get("id"),
            "role": "assistant",
            "content": content_text,
            "thinking": thinking_text,
            "parts_json": parts,
            "model": model or chat_adapter.CHAT_MODEL,
            "usage_json": {"status": final_status, "cancelled": cancelled,
                           **(usage or {})},
        })
        for rec in tool_records:
            try:
                db.chat.tool_calls.create({
                    "account_id": account_id,
                    "session_id": session.get("id"),
                    "message_id": mid,
                    "name": rec["name"],
                    "args_json": rec.get("args"),
                    "result_json": rec.get("result"),
                    "status": rec.get("status") or "done",
                    "started_at": rec.get("started_at"),
                    "ended_at": rec.get("ended_at"),
                })
            except Exception:  # noqa: BLE001 - ledger must never break the turn
                pass
        for att in attachment_records:
            try:
                db.chat.attachments.create({
                    "account_id": account_id,
                    "message_id": mid,
                    **att,
                })
            except Exception:  # noqa: BLE001
                pass
        patch: Dict[str, Any] = {"updated_at": _now()}
        if (session.get("title") or "") in ("", "New chat") and user_content.strip():
            patch["title"] = user_content.strip().splitlines()[0][:60]
        db.chat.sessions.update(session.get("id"), patch, account_id=account_id)
        return mid

    try:
        yield sse_frame("start", {
            "turn_id": turn_id,
            "session_id": session.get("id"),
            "model": model or chat_adapter.CHAT_MODEL,
            "think": bool(think),
            "tools": [t["function"]["name"] for t in (available_tools or [])],
        })

        history = db.chat.messages.list_by_session(
            session.get("id"), account_id=account_id, limit=200)
        messages = chat_adapter.build_chat_messages(history, session.get("focus_json"))

        if events is None:
            def _provider(round_idx: int, msgs: List[Dict[str, Any]]):
                return chat_adapter.stream_turn(
                    msgs, model=model, think=think,
                    should_cancel=cancel_event.is_set, tools=available_tools)
        elif callable(events):
            _provider = events
        else:
            round0 = events
            def _provider(round_idx: int, msgs: List[Dict[str, Any]]):
                return round0 if round_idx == 0 else iter(())

        rounds = 0
        while True:
            raw_calls: List[Dict[str, Any]] = []
            saw_done = False
            round_events = _provider(rounds, messages)
            for ev in round_events:
                etype = ev.get("type") if isinstance(ev, dict) else None
                if etype == "thinking":
                    delta = str(ev.get("delta") or "")
                    thinking_parts.append(delta)
                    yield sse_frame("thinking", {"turn_id": turn_id, "delta": delta})
                elif etype == "content":
                    delta = str(ev.get("delta") or "")
                    content_parts.append(delta)
                    yield sse_frame("token", {"turn_id": turn_id, "delta": delta})
                elif etype == "tool_call":
                    raw_calls.append(ev.get("call"))
                elif etype == "notice":
                    yield sse_frame("notice", {
                        "turn_id": turn_id,
                        "code": ev.get("code"),
                        "detail": ev.get("detail"),
                    })
                elif etype == "error":
                    status = "error"
                    error_reason = str(ev.get("reason") or "unknown")
                    yield sse_frame("error", {"turn_id": turn_id, "reason": error_reason})
                    break
                elif etype == "done":
                    saw_done = True
                    cancelled = bool(ev.get("cancelled"))
                    usage = ev.get("usage") if isinstance(ev.get("usage"), dict) else None
                    status = "cancelled" if cancelled else "done"
                    break

            if status == "error" or cancelled:
                break
            if not tools_enabled or not raw_calls:
                break
            if rounds >= chat_tools.MAX_TOOL_STEPS:
                yield sse_frame("notice", {
                    "turn_id": turn_id, "code": "max_tool_steps",
                    "detail": f"Stopped after {rounds} tool rounds (bounded).",
                })
                break
            rounds += 1

            normalized = chat_tools.normalize_tool_calls(raw_calls)
            executed: List[Dict[str, Any]] = []
            for call in normalized:
                call_id = uuid.uuid4().hex[:12]
                started_at = _now()
                yield sse_frame("tool-start", {
                    "turn_id": turn_id, "call_id": call_id,
                    "name": call["name"],
                    "args": (call.get("raw_args") or "")[:2000] or call.get("obj_args"),
                })
                progress_q: "queue.Queue[Dict[str, Any]]" = queue.Queue()

                def _progress(pct, label, _q=progress_q, _cid=call_id):
                    _q.put({"type": "tool-progress", "call_id": _cid, "phase": "running",
                            "pct": pct, "label": label})

                worker_ctx = {
                    "db": db, "account_id": account_id,
                    "session_id": session.get("id"),
                    "project_id": session.get("ds_project_id"),
                    "progress": _progress, "cancel": cancel_event,
                }
                box: Dict[str, Any] = {}
                args_payload = call.get("obj_args") if call.get("obj_args") is not None else call.get("raw_args")

                def _work(_box=box, _call=call, _ctx=worker_ctx, _args=args_payload):
                    try:
                        _box["r"] = chat_tools.run_tool(_call["name"], _args, _ctx)
                    except Exception as exc:  # noqa: BLE001
                        _box["r"] = {"ok": False, "summary": "tool crashed",
                                     "error": str(exc)[:300], "assets": []}

                worker = threading.Thread(target=_work, daemon=True)
                worker.start()
                yield sse_frame("tool-progress", {
                    "turn_id": turn_id, "call_id": call_id,
                    "phase": "running", "pct": None, "label": "queued",
                })
                while True:
                    try:
                        item = progress_q.get(timeout=0.4)
                        yield sse_frame("tool-progress", {
                            "turn_id": turn_id,
                            "call_id": item.get("call_id", call_id),
                            "phase": item.get("phase", "running"),
                            "pct": item.get("pct"),
                            "label": item.get("label"),
                        })
                        continue
                    except queue.Empty:
                        pass
                    if not worker.is_alive():
                        break
                worker.join(timeout=5)
                result = box.get("r") or {"ok": False, "summary": "tool produced no result",
                                          "error": "worker exited without a result", "assets": []}
                yield sse_frame("tool-end", {
                    "turn_id": turn_id, "call_id": call_id, "name": call["name"],
                    "ok": bool(result.get("ok")),
                    "summary": result.get("summary"),
                    "error": result.get("error"),
                    "assets": result.get("assets") or [],
                })
                for a in result.get("assets") or []:
                    if not isinstance(a, dict):
                        continue
                    yield sse_frame("asset", {"turn_id": turn_id, "call_id": call_id, **a})
                    if a.get("id"):
                        attachment_records.append({
                            "asset_id": a["id"],
                            "kind": a.get("kind"),
                            "url": a.get("url"),
                            "provenance_json": {"tool": call["name"]},
                        })
                tool_records.append({
                    "name": call["name"],
                    "args": call.get("obj_args") if call.get("obj_args") is not None else call.get("raw_args"),
                    "result": result,
                    "status": "done" if result.get("ok") else "error",
                    "started_at": started_at,
                    "ended_at": _now(),
                })
                tool_parts.append({
                    "type": "tool", "call_id": call_id, "name": call["name"],
                    "ok": bool(result.get("ok")), "summary": result.get("summary"),
                    "error": result.get("error"),
                    "assets": [a.get("id") for a in (result.get("assets") or [])
                               if isinstance(a, dict) and a.get("id")],
                })
                executed.append({"call": call, "result": result})

            if executed:
                messages.append({
                    "role": "assistant", "content": "",
                    "tool_calls": [{"function": {"name": e["call"]["name"],
                                                 "arguments": _args_for_model(e["call"])}}
                                   for e in executed],
                })
                for e in executed:
                    payload = json.dumps({
                        "ok": e["result"].get("ok"),
                        "summary": e["result"].get("summary"),
                        "error": e["result"].get("error"),
                        "assets": e["result"].get("assets") or [],
                        "data": e["result"].get("data"),
                    }, default=str)
                    messages.append({
                        "role": "tool", "tool_name": e["call"]["name"],
                        "content": payload[:8000],
                    })
            # loop continues to the next round

        if not saw_done and status == "done":
            # The event stream ended without a done frame — the turn was cut.
            status = "cancelled"

        mid = _persist(status)
        persisted = True
        yield sse_frame("done", {
            "turn_id": turn_id,
            "message_id": mid,
            "status": status,
            "cancelled": cancelled,
            "usage": usage,
        })
    except Exception as exc:  # noqa: BLE001 - a broken stream must not vanish silently
        status = "error"
        error_reason = str(exc)[:400]
        try:
            yield sse_frame("error", {"turn_id": turn_id, "reason": error_reason})
        except GeneratorExit:
            raise
        if not persisted:
            mid = _persist("error")
            persisted = True
        yield sse_frame("done", {
            "turn_id": turn_id,
            "message_id": mid if persisted else None,
            "status": status,
            "cancelled": cancelled,
            "usage": usage,
        })
    finally:
        if not persisted:
            # Client disconnected mid-stream (GeneratorExit) or an unhandled
            # BaseException: persist the partial exactly once, no yields here.
            try:
                _persist("cancelled" if status == "done" else status)
            except Exception:  # noqa: BLE001 - persistence must never mask the exit
                pass
        if own_event:
            _drain_turn(turn_id)


# ── API ─────────────────────────────────────────────────────────────────────

class SessionIn(BaseModel):
    title: Optional[str] = Field(None, max_length=120)
    ds_project_id: Optional[str] = Field(None, max_length=80)
    mode: str = Field(default="simple", max_length=20)
    focus: Optional[Dict[str, Any]] = None


class TurnIn(BaseModel):
    content: str = Field(..., min_length=1, max_length=20000)
    think: bool = True
    model: Optional[str] = Field(None, max_length=90)


class SessionPatch(BaseModel):
    title: Optional[str] = Field(None, max_length=120)
    focus: Optional[Dict[str, Any]] = None


@router.get("")
def chat_root(acct: str = Depends(studio_account)):
    """Bare-prefix info route so the base path itself resolves (the UI contract
    test treats a base constant as an API path)."""
    return chat_health(acct)


@router.get("/health")
def chat_health(acct: str = Depends(studio_account)):
    return {
        "ok": True,
        "model": chat_adapter.CHAT_MODEL,
        "think_default": True,
        "events": list(SSE_EVENT_TYPES),
        "tools": chat_tools.tool_names(),
        "tools_enabled": tools_enabled_default(),
        "max_tool_steps": chat_tools.MAX_TOOL_STEPS,
    }


@router.post("/sessions")
def create_session(body: SessionIn, acct: str = Depends(studio_account)):
    db = get_northstar_db()
    sid = db.chat.sessions.create({
        "account_id": acct,
        "title": (body.title or "").strip() or "New chat",
        "ds_project_id": body.ds_project_id,
        "mode": body.mode if body.mode in ("simple", "advanced") else "simple",
        "model": chat_adapter.CHAT_MODEL,
        "focus_json": body.focus,
    })
    return db.chat.sessions.get_by_id(sid, account_id=acct)


@router.get("/sessions")
def list_sessions(limit: int = 50, acct: str = Depends(studio_account)):
    db = get_northstar_db()
    return {"sessions": db.chat.sessions.list_by_account(
        acct, limit=min(max(int(limit), 1), 200))}


@router.get("/sessions/{sid}/messages")
def list_messages(sid: str, limit: int = 500, acct: str = Depends(studio_account)):
    db = get_northstar_db()
    session = db.chat.sessions.get_by_id(sid, account_id=acct)
    if not session:
        return {"session": None, "messages": []}
    return {
        "session": session,
        "messages": db.chat.messages.list_by_session(
            sid, account_id=acct, limit=min(max(int(limit), 1), 1000)),
    }


@router.patch("/sessions/{sid}")
def patch_session(sid: str, body: SessionPatch, acct: str = Depends(studio_account)):
    """Rename a session and/or set its focus (V3 focus rail).

    The focus id is validated against the server-owned catalogue; an unknown id
    is rejected instead of stored. The stored focus_json is injected into the
    system prompt on the next turn and restricts the tool set offered to the
    model (see turn_event_stream)."""
    db = get_northstar_db()
    session = db.chat.sessions.get_by_id(sid, account_id=acct)
    if not session:
        raise HTTPException(status_code=404, detail="Chat session not found")
    patch: Dict[str, Any] = {}
    if body.title is not None:
        title = body.title.strip()
        if not title:
            raise HTTPException(status_code=400, detail="title cannot be empty")
        patch["title"] = title[:120]
    if body.focus is not None:
        mode = body.focus.get("mode")
        if mode and mode not in VALID_FOCUS_IDS:
            raise HTTPException(status_code=400, detail=f"unknown focus '{mode}'")
        patch["focus_json"] = body.focus
    if not patch:
        raise HTTPException(status_code=400, detail="nothing to patch")
    db.chat.sessions.update(sid, patch, account_id=acct)
    return db.chat.sessions.get_by_id(sid, account_id=acct)


@router.post("/sessions/{sid}/turns")
def create_turn(sid: str, body: TurnIn, acct: str = Depends(studio_account)):
    db = get_northstar_db()
    session = db.chat.sessions.get_by_id(sid, account_id=acct)
    if not session:
        # Fail closed: an unknown session never silently creates on POST turn.
        raise HTTPException(status_code=404, detail="Chat session not found")
    db.chat.messages.create({
        "account_id": acct,
        "session_id": sid,
        "role": "user",
        "content": body.content,
    })
    generator = turn_event_stream(
        db, acct, session, body.content, think=body.think, model=body.model)
    return StreamingResponse(
        generator,
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/turns/{turn_id}/cancel")
def cancel(turn_id: str, acct: str = Depends(studio_account)):
    # Turn ids are unguessable (uuid4); cancelling sets a flag on the live
    # stream only. Unknown ids are reported honestly, never pretended.
    ok = cancel_turn(turn_id)
    return {"ok": ok, "turn_id": turn_id}
