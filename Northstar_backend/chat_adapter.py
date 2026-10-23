"""Design Studio — Simple-mode chat adapter (S1).

Wraps the shared UnifiedLLMAdapter's streaming lane for the chat core: builds
the message list (system + recent history + focus), streams thinking/content
events, and surfaces an honest offline fallback when Ollama is not reachable.
No provider keys, no cost, no network beyond the operator's own Ollama.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from autothink.backend.llm_adapter import (  # noqa: E402
    DEFAULT_LOCAL_MODEL,
    UnifiedLLMAdapter,
    iter_ollama_chat_events,
)

CHAT_MODEL = os.environ.get("CHAT_MODEL") or DEFAULT_LOCAL_MODEL
CHAT_HISTORY_MAX = int(os.environ.get("CHAT_HISTORY_MAX", "16"))
# Chat turns run smaller than AutothinK's long-form 64K window: the 16 GB card
# is shared with ComfyUI, so the chat keeps a lean context and leaves long
# history to the store. Both values are env-overridable.
CHAT_NUM_CTX = int(os.environ.get("CHAT_NUM_CTX", "16384"))
# Measured: `num_predict` counts THINKING tokens too. At 4096 an xhigh turn ran
# out of budget mid-reasoning, Ollama returned done_reason="length" with ZERO
# content, and the turn degraded to the "Ollama is unavailable" notice. 16384
# covers a full deep-reasoning turn (~15k thinking) while still bounding a
# runaway turn to roughly six minutes on this GPU (41 tok/s).
CHAT_NUM_PREDICT = int(os.environ.get("CHAT_NUM_PREDICT", "16384"))
# Optional GPU-layer cap (num_gpu). Unset -> Ollama decides. On this 16 GB box
# a cap keeps the 27B loadable when the desktop/ComfyUI hold memory.
_chat_num_gpu_raw = os.environ.get("CHAT_NUM_GPU", "").strip()
CHAT_NUM_GPU = int(_chat_num_gpu_raw) if _chat_num_gpu_raw.isdigit() else None

# Measured on one hard written proof at medium effort: this discipline took the
# same question from 2,209 thinking tokens / 141 s to 1,157 / 77 s, with every
# verification step still present. At xhigh the model ignores it (5,864 tokens),
# so the level — not the prompt — sets the ceiling. Env: CHAT_REASONING_DISCIPLINE=0.
REASONING_DISCIPLINE = (
    "\nPrivate reasoning discipline (applies to your thinking, never to the "
    "answer): think in at most 10 short steps and keep the reasoning under "
    "roughly 400 words. Never restate the question, never list options you "
    "rejected, never re-check a step you already verified. Do the work once, "
    "then write the answer. The answer itself stays as complete as the task needs."
)
REASONING_DISCIPLINE_ON = os.environ.get(
    "CHAT_REASONING_DISCIPLINE", "1").strip().lower() not in ("0", "false", "off", "no")

_CHAT_SYSTEM_BASE = (
    "You are the Northstar OS Master Brain in the Creative Studio — the "
    "content-generation copilot for T2 Holdings' brands (Amazon FBA and "
    "retail arbitrage; organic food brands). You help create and refine "
    "packaging designs, product photography, listing images and copy, ad "
    "creatives, and social content. Be concise and concrete. Never invent "
    "product facts, certifications, weights, prices, or legal copy — ask the "
    "operator instead. Packaging text is authored as structured layers, never "
    "painted into images: to finish a pack, render the photograph with "
    "generate_image and then call apply_label with the operator's real logo and "
    "copy. That tool IS the layered alternative, so use it instead of only "
    "explaining the limit, and never ask the operator to re-send an attachment "
    "that is already listed in this turn. Mirror the operator's language. You "
    "have local tools (dieline templates, structured briefs, local image "
    "renders, the label compositor, engine status): call them when the operator "
    "asks for a real artifact, and only describe results the tool actually "
    "returned."
)
# Composed into the constant (not appended per turn) so the "no focus -> exactly
# the system constant" contract still holds for every caller.
CHAT_SYSTEM_PROMPT = _CHAT_SYSTEM_BASE + (
    REASONING_DISCIPLINE if REASONING_DISCIPLINE_ON else "")


def knowledge_block(query: str, limit: int = 6, min_score: float = 0.5) -> str:
    """Retrieved selling rules for this turn, or "" when nothing is relevant.

    This is how the improvement loop reaches the model: promoted atoms are
    retrieved per request, never injected wholesale. A retrieval failure must
    never break a chat turn, so every path returns "".
    """
    try:
        import knowledge_pack as kp  # local import: chat stays importable without it
    except Exception:  # noqa: BLE001
        return ""
    try:
        hits = kp.retrieve(query, limit=limit, min_score=min_score)
        if not hits:
            return ""
        return "\n\n" + kp.format_for_prompt([a for _, a in hits], limit=limit)
    except Exception:  # noqa: BLE001
        return ""


def skills_block(query: str) -> str:
    """Markdown skills that route to this turn, or "" when none do.

    Same contract as knowledge_block: a broken skill file never breaks a turn.
    """
    try:
        import skills_plane  # local import: chat stays importable without the directory
    except Exception:  # noqa: BLE001
        return ""
    try:
        return skills_plane.context_block(query)
    except Exception:  # noqa: BLE001
        return ""


DELIVERABLE_ROUTING = (
    "\nDeliverable routing: a photoreal render, 3D mockup, product photo or ad "
    "visual is an IMAGE job -> call creative_plan (media=image), then generate_image "
    "after the operator confirms. create_dieline is print geometry only (SVG/PDF cut "
    "lines) and is never a substitute for a rendered mockup. When the operator says "
    "mockup, render or product photo, they mean the image lane."
)


def build_chat_messages(history: Iterable[Dict[str, Any]],
                        focus: Optional[Dict[str, Any]] = None,
                        limit: int = CHAT_HISTORY_MAX,
                        query: Optional[str] = None) -> List[Dict[str, str]]:
    """System prompt (with focus + retrieved rules) + the most recent turns."""
    system = CHAT_SYSTEM_PROMPT + DELIVERABLE_ROUTING
    if focus:
        from shell_focus import FOCUS_PROMPTS
        mode = str(focus.get("mode") or "")
        if mode in FOCUS_PROMPTS:
            system += "\nActive focus — " + FOCUS_PROMPTS[mode]
        bits = [f"{k}: {v}" for k, v in sorted(focus.items())
                if v and k != "mode"]
        if bits:
            system += "\nContext — " + "; ".join(bits)
    if query:
        system += knowledge_block(str(query))
        system += skills_block(str(query))
    messages: List[Dict[str, str]] = [{"role": "system", "content": system}]
    rows = [m for m in (history or []) if str(m.get("content") or "").strip()]
    for row in rows[-max(0, int(limit)):]:
        role = row.get("role")
        if role not in ("user", "assistant"):
            continue
        messages.append({"role": role, "content": str(row.get("content") or "")})
    return messages


# ── chatter control ─────────────────────────────────────────────────────────
# The model is told not to preamble, but instruction-following is not a
# guarantee. These openers are stripped from the stream itself, so the operator
# never sees them and the stored transcript stays clean. The hold-back only
# engages when the answer actually starts with one of them: a normal answer is
# emitted on the first delta with no added latency.
_PREAMBLE_OPENERS = (
    "sure", "certainly", "absolutely", "of course", "great question",
    "happy to help", "i'd be happy", "i would be happy", "let me",
    "here's", "here is", "as an ai",
)
_SENTENCE_END = re.compile(r"[.!?\n]\s*")
_CLOSING = re.compile(
    r"\s*(?:let me know if you (?:need|have) (?:anything|any questions)[^.!?\n]*[.!?]?"
    r"|hope (?:this|that) helps[^.!?\n]*[.!?]?|feel free to (?:ask|reach out)[^.!?\n]*[.!?]?"
    r"|happy to help further[^.!?\n]*[.!?]?)\s*$", re.I)


def strip_preamble_text(text: str) -> str:
    """Remove a leading acknowledgement from a finished answer."""
    t = (text or "").lstrip()
    low = t.lower()
    for opener in _PREAMBLE_OPENERS:
        if low.startswith(opener):
            m = _SENTENCE_END.search(t)
            if m:
                return t[m.end():].lstrip()
            return text  # no boundary: never delete the whole answer
    return text


def strip_closing_filler(text: str) -> str:
    """Remove trailing 'let me know...' style filler, keep the content."""
    return _CLOSING.sub("", text or "").rstrip()


def strip_preamble_events(events):
    """Drop a leading acknowledgement from a content stream, in place."""
    pending = ""
    decided = False
    for ev in events:
        if not isinstance(ev, dict) or ev.get("type") != "content" or decided:
            yield ev
            continue
        pending += str(ev.get("delta") or "")
        low = pending.lower().lstrip()
        if not low:
            continue
        # Still could become an opener ("Su" -> "Sure"): wait for one more delta.
        if len(low) < 24 and any(op.startswith(low) for op in _PREAMBLE_OPENERS):
            continue
        if any(low.startswith(op) for op in _PREAMBLE_OPENERS):
            m = _SENTENCE_END.search(pending)
            if not m:
                if len(pending) < 240:
                    continue  # keep buffering until the opener's sentence ends
                decided = True
                yield {"type": "content", "delta": pending}
                pending = ""
                continue
            rest = pending[m.end():]
            decided = True
            pending = ""
            if rest:
                yield {"type": "content", "delta": rest}
            continue
        decided = True
        out, pending = pending, ""
        yield {"type": "content", "delta": out}
    if pending:
        yield {"type": "content", "delta": pending}


def stream_turn(messages: List[Dict[str, str]], *, model: Optional[str] = None,
                think: Any = True, should_cancel=None, tools=None):
    """Thin seam over UnifiedLLMAdapter.stream_chat (mockable in tests)."""
    adapter = UnifiedLLMAdapter()
    yield from strip_preamble_events(adapter.stream_chat(
        messages,
        model=model or CHAT_MODEL,
        think=think,
        should_cancel=should_cancel,
        num_ctx=CHAT_NUM_CTX,
        num_predict=CHAT_NUM_PREDICT,
        tools=tools,
        num_gpu=CHAT_NUM_GPU,
    ))


def offline_notice(reason: str) -> str:
    """The honest fallback text persisted when a turn produced zero tokens."""
    return (
        "[LOCAL FALLBACK] Ollama is unavailable (%s). Start it with: "
        "ollama serve — then resend this message." % (reason or "unknown")
    )


def truncation_notice(usage: Optional[Dict[str, Any]] = None) -> str:
    """Honest text when the output budget ran out before an answer was written.

    Distinct from :func:`offline_notice`: Ollama answered, the model simply spent
    the whole budget reasoning (done_reason="length"). Saying "Ollama is
    unavailable" here would be a false diagnosis.
    """
    used = (usage or {}).get("completion_tokens")
    spent = f" ({used} tokens)" if used else ""
    return (
        "[BUDGET REACHED] The model spent its entire output budget reasoning"
        f"{spent} and never wrote the answer. This is a token-limit stop, not an "
        "outage — the thinking above is real. Ask a narrower question, or raise "
        "CHAT_NUM_PREDICT for this lane."
    )
