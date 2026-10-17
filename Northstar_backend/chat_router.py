"""Design Studio — Simple-mode chat core (S1).

The chat transport for the Master Brain shell: sessions, message history, and
a streaming turn endpoint (SSE). Event vocabulary (fixed from day one so S2
tools need no wire change):

    start · notice · thinking · token · tool-start · tool-progress ·
    tool-end · asset · error · done

Honesty boundaries (house rules):
  • No fabricated replies — an offline engine persists the REAL fallback text
    plus an error event.
  • A cancelled, failed, or client-abandoned turn is persisted with its true
    status (done | cancelled | error) in usage_json — partial answers are
    stored as partial, never dressed up as complete.
  • Every frame carries the turn id that produced it.
  • Tool events are defined here but only emitted once the tool loop (S2)
    exists; nothing pretends tools ran.
"""

from __future__ import annotations

import json
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from data_layer import get_northstar_db
from design_studio_api import studio_account
import chat_adapter

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


def turn_event_stream(db, account_id: str, session: Dict[str, Any], user_content: str,
                      *, think: bool = True, model: Optional[str] = None,
                      events: Optional[Iterable[Dict[str, Any]]] = None,
                      cancel_event: Optional[threading.Event] = None):
    """Sync generator of SSE frames for one turn.

    `events` injects a scripted adapter stream (tests); production passes None
    and the real UnifiedLLMAdapter stream is used. `cancel_event` is optional
    for tests; production registers a turn-scoped event.

    Persistence guarantee: whatever text the turn produced is written exactly
    once, on EVERY exit path — completion, cancel, adapter error, or client
    disconnect mid-stream — with the true status recorded in usage_json.
    (No yields in `finally`; a generator cannot yield while closing.)
    """
    turn_id = uuid.uuid4().hex
    own_event = cancel_event is None
    if own_event:
        cancel_event = register_turn(turn_id)

    thinking_parts: List[str] = []
    content_parts: List[str] = []
    status = "done"
    cancelled = False
    usage = None
    error_reason = None
    saw_done = False
    persisted = False

    def _persist(final_status: str) -> Optional[str]:
        thinking_text = "".join(thinking_parts)
        content_text = "".join(content_parts)
        if final_status == "error" and not content_text:
            content_text = chat_adapter.offline_notice(error_reason or "unknown")
        if not (thinking_text or content_text):
            return None  # a cut turn that produced nothing is not a message
        parts: List[Dict[str, Any]] = []
        if thinking_text:
            parts.append({"type": "thinking", "text": thinking_text})
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
        })

        history = db.chat.messages.list_by_session(
            session.get("id"), account_id=account_id, limit=200)
        messages = chat_adapter.build_chat_messages(history, session.get("focus_json"))
        events_iter = events if events is not None else chat_adapter.stream_turn(
            messages, model=model, think=think,
            should_cancel=cancel_event.is_set,
        )

        for ev in events_iter:
            etype = ev.get("type") if isinstance(ev, dict) else None
            if etype == "thinking":
                delta = str(ev.get("delta") or "")
                thinking_parts.append(delta)
                yield sse_frame("thinking", {"turn_id": turn_id, "delta": delta})
            elif etype == "content":
                delta = str(ev.get("delta") or "")
                content_parts.append(delta)
                yield sse_frame("token", {"turn_id": turn_id, "delta": delta})
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

        if not saw_done and status == "done":
            # The event stream ended without a done frame — the turn was cut
            # (adapter vanished, client cancel raced the socket). Honest status.
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
            "message_id": mid,
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
        "tools": "S2",
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
