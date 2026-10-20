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
import time
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
import tool_gateway
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


def _label_turn(text: str, limit: int = 80) -> str:
    s = " ".join((text or "").split())
    return s[:limit] or "chat turn"


def turn_event_stream(db, account_id: str, session: Dict[str, Any], user_content: str,
                      *, think: bool = True, model: Optional[str] = None,
                      events: Optional[Any] = None,
                      cancel_event: Optional[threading.Event] = None,
                      tools_enabled: Optional[bool] = None,
                      options: Optional[Dict[str, Any]] = None):
    """Sync generator of SSE frames for one turn (tool loop included).

    `events` injects scripted adapter streams: callable(round_idx, messages) ->
    iterable, or a plain iterable used for round 0 (tests). Production passes
    None and the real UnifiedLLMAdapter stream is used with the tool schemas.

    Persistence guarantee: whatever text/tools the turn produced is written
    exactly once on EVERY exit path — completion, cancel, adapter error, or
    client disconnect — with the true status recorded in usage_json.
    """
    turn_id = uuid.uuid4().hex
    # T-7 (Thorn v5.0): a real measurement of this run, recorded once on exit.
    # A measurement that can break a turn is worse than no measurement.
    _t0 = time.perf_counter()
    own_event = cancel_event is None
    if own_event:
        cancel_event = register_turn(turn_id)
    if tools_enabled is None:
        tools_enabled = tools_enabled_default()

    # V3 S5 run ledger: record this turn as a bounded, cancellable run so the
    # AutothinK run panel has honest status. Best-effort; never breaks a turn.
    run_id: Optional[str] = None
    try:
        run_id = db.chat.runs.create({
            "account_id": account_id,
            "session_id": session.get("id"),
            "kind": "chat_turn",
            "label": _label_turn(user_content),
            "status": "running",
            "ref": turn_id,
            "started_at": _now(),
        })
    except Exception:  # noqa: BLE001
        run_id = None

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
        for idx, rec in enumerate(tool_records):
            try:
                db.chat.tool_calls.create({
                    "account_id": account_id,
                    "session_id": session.get("id"),
                    "message_id": mid,
                    "name": rec["name"],
                    "args_json": rec.get("args"),
                    "result_json": rec.get("result"),
                    "status": rec.get("status") or "done",
                    "step_index": rec.get("step_index", idx),
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
            "options": options or {},
            "tools": [t["function"]["name"] for t in (available_tools or [])],
        })

        history = db.chat.messages.list_by_session(
            session.get("id"), account_id=account_id, limit=200)
        messages = chat_adapter.build_chat_messages(history, session.get("focus_json"))
        # Turn options v2: a model-side directive, prepended AFTER history is built so
        # it is never persisted as part of the operator's message.
        if options:
            directive = turn_directive(options)
            if directive:
                messages = [{"role": "system", "content": directive}] + messages

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
            truncated = False
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
                    if ev.get("code") == "output_truncated":
                        truncated = True
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

            if truncated and not content_parts and not cancelled:
                # The budget ran out inside the reasoning block: keep the
                # thinking and say plainly that no answer was written, instead
                # of persisting a silent empty bubble.
                content_parts.append(chat_adapter.truncation_notice(usage))
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
                        _box["r"] = tool_gateway.run_tool_gated(db.chat, account_id, _call["name"], _args, _ctx)
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
                    "step_index": len(tool_records),
                    "started_at": started_at,
                    "ended_at": _now(),
                })
                # AG-UI: a tool may declare an interactive card (title, rows,
                # action). It is appended as a card part so the UI renders an
                # actionable component, not plain text.
                card = (result.get("data") or {}).get("card")
                if isinstance(card, dict) and card.get("title"):
                    part = {
                        "type": "card",
                        "title": str(card.get("title"))[:120],
                        "rows": card.get("rows") or [],
                        "action": card.get("action") or None,
                        "ok": bool(result.get("ok")),
                    }
                    # Additive: a generation-plan card carries its own options and
                    # cost so the operator can cancel/edit/draft/final from the card.
                    for key in ("kind", "plan_id", "job", "media", "options", "steps"):
                        if key in card:
                            part[key] = card[key]
                    tool_parts.append(part)
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
        if run_id:
            try:
                db.chat.runs.finish(run_id, status, account_id=account_id)
            except Exception:  # noqa: BLE001
                pass
        # T-7 lane telemetry: record what this turn actually cost. Measurements only —
        # no routing decision is taken from a single run. A failure here must never
        # affect the turn that is finishing, but it must NOT be invisible either:
        # a silently dead producer is worse than no producer.
        try:
            import lane_telemetry
            focus_mode = None
            fj = session.get("focus_json") if isinstance(session, dict) else None
            if isinstance(fj, dict):
                focus_mode = fj.get("mode")
            elif isinstance(fj, str) and fj:
                try:
                    focus_mode = (json.loads(fj) or {}).get("mode")
                except Exception:  # noqa: BLE001
                    focus_mode = None
            lane_telemetry.record(
                db, f"chat:{model or 'default'}",
                latency_ms=(time.perf_counter() - _t0) * 1000.0,
                ok=(status == "done"),
                tool_calls=len(tool_records),
                task_class=focus_mode,
            )
        except Exception as exc:  # noqa: BLE001 - never break a turn, never hide a break
            import logging as _logging
            _logging.getLogger("northstar.chat").warning(
                "lane telemetry not recorded: %s: %s", type(exc).__name__, exc)
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
    # v2 (Bojo): the composer's switches. All optional; the defaults are v1 behaviour.
    media: str = Field("image", pattern="^(image|video)$")
    thinking: str = Field("standard", pattern="^(off|standard|deep)$")
    style: str = Field("balanced", pattern="^(concise|balanced|detailed)$")
    attachments: List[str] = Field(default_factory=list, max_length=12)


# The switches are model-side instructions, never written into the transcript: the
# operator's own words stay the stored message, and the transcript shows exactly
# what they typed.
_MEDIA_HINT = {
    "image": "Use the still-image lane; the deliverable is one or more images.",
    "video": "Use the video lane; the deliverable is motion, not a still described as video.",
}
_THINKING_HINT = {
    "off": "Answer directly. Do not emit a reasoning trail.",
    "standard": "",
    "deep": ("Think deeply: state assumptions, test edge cases and name the trade-offs "
             "before you commit to an answer."),
}
# Measured on this box (RTX 5080 16 GB, a 3-crate algebra proof): think=True used
# the template's xhigh default — 6,376 thinking tokens, 318 s; think="medium" used
# 2,209 thinking tokens, 141 s, and produced the same verified answer. So the
# composer's "standard" level now maps to a real budget instead of a prompt hint.
# CHAT_THINK_STANDARD="true" restores the old always-xhigh behaviour without a code
# change; "deep" always takes the full default.
_THINK_STANDARD = (os.environ.get("CHAT_THINK_STANDARD", "medium").strip() or "medium")


# A "standard" turn takes the full budget when the request looks like code, a
# proof, or a long brief. This only ever ESCALATES: the operator's explicit
# "deep"/"off" choice always wins, so it can never make an answer shallower than
# the standard tier — the safe direction for accuracy.
_ESCALATE_SIGNALS = (
    "```", "def ", "class ", "import ", "traceback", "stack trace", "refactor",
    "debug", "sql", "regex", "algorithm", "architecture", "root cause", "prove",
    "derive", "audit", "step by step", "design a", "trade-off", "tradeoff",
    "unit test", "compile", "optimi",
)
_ESCALATE_CHARS = 1200


def _auto_escalate(content: str, attachments: int = 0) -> bool:
    text = (content or "").lower()
    if len(text) > _ESCALATE_CHARS or attachments:
        return True
    return any(sig in text for sig in _ESCALATE_SIGNALS)


def _think_level(think: bool, thinking: str, content: str = "", attachments: int = 0):
    """Composer thinking switch -> Ollama think flag/level."""
    if not think or thinking == "off":
        return False
    if thinking == "deep" or _auto_escalate(content, attachments):
        return True
    level = _THINK_STANDARD.lower()
    if level in ("true", "1", "default", "xhigh"):
        return True
    # This template accepts exactly xhigh (default), medium and low; asking for
    # "high" raises a Jinja exception inside Ollama, so normalize in one place.
    if level not in ("low", "medium"):
        return "medium"
    return level


_STYLE_HINT = {
    "concise": "Style: concise. Short paragraphs, no filler.",
    "balanced": "",
    "detailed": "Style: detailed. Cover assumptions, trade-offs and concrete next steps.",
}


def turn_directive(options: Optional[Dict[str, Any]]) -> str:
    """One model-facing instruction block built from the composer switches."""
    o = options or {}
    lines = ["[Bojo turn options]",
             "Requested output: " + _MEDIA_HINT.get(o.get("media"), _MEDIA_HINT["image"])]
    thinking = _THINKING_HINT.get(o.get("thinking"), "")
    if thinking:
        lines.append(thinking)
    style = _STYLE_HINT.get(o.get("style"), "")
    if style:
        lines.append(style)
    atts = [str(a) for a in (o.get("attachments") or []) if a][:12]
    if atts:
        lines.append("Operator attachments (asset ids): " + ", ".join(atts)
                     + ". Treat them as the operator's own artefacts.")
    return "\n".join(lines)


class SessionPatch(BaseModel):
    title: Optional[str] = Field(None, max_length=120)
    focus: Optional[Dict[str, Any]] = None


class ForkIn(BaseModel):
    upto_message_id: Optional[str] = None
    title: Optional[str] = Field(None, max_length=120)


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


@router.post("/sessions/{sid}/fork")
def fork_session(sid: str, body: ForkIn, acct: str = Depends(studio_account)):
    """Fork (rewind) a session — the Claude-Code snapshot pattern, made honest.

    A NEW session copies every message up to and including `upto_message_id`
    (or all messages when omitted). The parent session is NEVER mutated, so a
    rewind can never lose work; the child records its lineage in
    `chat_session_forks`."""
    db = get_northstar_db()
    try:
        out = db.chat.sessions.fork(
            sid, acct, upto_message_id=body.upto_message_id, title=body.title)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if not out:
        raise HTTPException(status_code=404, detail="Chat session not found")
    db.chat.forks.create({
        "account_id": acct,
        "session_id": out["session"]["id"],
        "parent_session_id": sid,
        "forked_from_message_id": body.upto_message_id,
    })
    return out


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
        db, acct, session, body.content,
        think=_think_level(body.think, body.thinking, body.content,
                           len(body.attachments)), model=body.model,
        options={"media": body.media, "thinking": body.thinking,
                 "style": body.style, "attachments": body.attachments})
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


# ── V3 S5 — AutothinK premium surface ───────────────────────────────────────

@router.get("/sessions/{sid}/plan")
def session_plan(sid: str, acct: str = Depends(studio_account)):
    """The session's plan graph (prompt → tool steps → answer), reconstructed.

    Built from the recorded tool-call ledger + message parts. Linear and honest:
    nothing is invented beyond what ran."""
    import chat_plan
    db = get_northstar_db()
    session = db.chat.sessions.get_by_id(sid, account_id=acct)
    if not session:
        raise HTTPException(status_code=404, detail="Chat session not found")
    messages = db.chat.messages.list_by_session(sid, account_id=acct, limit=1000)
    calls = db.chat.tool_calls.list_by_session(sid, account_id=acct)
    plan = chat_plan.build_plan(messages, calls)
    plan["session_id"] = sid
    return plan


@router.get("/sessions/{sid}/artifacts")
def session_artifacts(sid: str, acct: str = Depends(studio_account)):
    """Every build artifact attached to a session, with ds_assets metadata."""
    db = get_northstar_db()
    session = db.chat.sessions.get_by_id(sid, account_id=acct)
    if not session:
        raise HTTPException(status_code=404, detail="Chat session not found")
    items = []
    for att in db.chat.attachments.list_by_session(sid, account_id=acct):
        asset = None
        aid = att.get("asset_id")
        if aid:
            try:
                asset = db.design_studio.assets.get_by_id(aid, account_id=acct)
            except Exception:  # noqa: BLE001 - a missing asset is not a crash
                asset = None
        items.append({
            "asset_id": aid,
            "name": (asset or {}).get("name") or att.get("kind") or "artifact",
            "asset_type": (asset or {}).get("asset_type"),
            "mime_type": (asset or {}).get("mime_type"),
            "size_bytes": (asset or {}).get("size_bytes"),
            "width": (asset or {}).get("width"),
            "height": (asset or {}).get("height"),
            "url": att.get("url"),
            "kind": att.get("kind"),
            "message_id": att.get("message_id"),
            "provenance": att.get("provenance_json"),
            "created_at": att.get("created_at"),
            "present": asset is not None,
        })
    return {"session_id": sid, "artifacts": items}


@router.get("/runs")
def list_runs(status: Optional[str] = None, session_id: Optional[str] = None,
              limit: int = 100, acct: str = Depends(studio_account)):
    """Bounded run ledger (chat turns / tool executions) for the run panel."""
    db = get_northstar_db()
    return {"runs": db.chat.runs.list_by_account(
        acct, status=status, session_id=session_id, limit=min(max(int(limit), 1), 500))}


@router.post("/runs/{run_id}/cancel")
def cancel_run(run_id: str, acct: str = Depends(studio_account)):
    """Cancel an in-flight run. Only a live chat turn can actually be stopped;
    anything else is reported honestly (cancelled=false), never pretended."""
    db = get_northstar_db()
    run = db.chat.runs.get(run_id, account_id=acct)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    stopped = False
    if run.get("status") == "running" and run.get("kind") == "chat_turn" and run.get("ref"):
        stopped = cancel_turn(run["ref"])
        if stopped:
            db.chat.runs.finish(run_id, "cancelled", account_id=acct)
    return {"ok": True, "cancelled": stopped, "run_id": run_id}
