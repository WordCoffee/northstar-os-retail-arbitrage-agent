"""Design Studio — Simple-mode chat adapter (S1).

Wraps the shared UnifiedLLMAdapter's streaming lane for the chat core: builds
the message list (system + recent history + focus), streams thinking/content
events, and surfaces an honest offline fallback when Ollama is not reachable.
No provider keys, no cost, no network beyond the operator's own Ollama.
"""

from __future__ import annotations

import os
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

CHAT_SYSTEM_PROMPT = (
    "You are the Northstar OS Master Brain in the Creative Studio — the "
    "content-generation copilot for T2 Holdings' brands (Amazon FBA and "
    "retail arbitrage; organic food brands). You help create and refine "
    "packaging designs, product photography, listing images and copy, ad "
    "creatives, and social content. Be concise and concrete. Never invent "
    "product facts, certifications, weights, prices, or legal copy — ask the "
    "operator instead. Packaging text is authored as structured layers, never "
    "painted into images; if asked, explain that and offer the layered "
    "alternative. Mirror the operator's language. You have local tools "
    "(dieline templates, structured briefs, local image renders, engine "
    "status): call them when the operator asks for a real artifact, and only "
    "describe results the tool actually returned."
)


def build_chat_messages(history: Iterable[Dict[str, Any]],
                        focus: Optional[Dict[str, Any]] = None,
                        limit: int = CHAT_HISTORY_MAX) -> List[Dict[str, str]]:
    """System prompt (with focus) + the most recent non-empty turns."""
    system = CHAT_SYSTEM_PROMPT
    if focus:
        from shell_focus import FOCUS_PROMPTS
        mode = str(focus.get("mode") or "")
        if mode in FOCUS_PROMPTS:
            system += "\nActive focus — " + FOCUS_PROMPTS[mode]
        bits = [f"{k}: {v}" for k, v in sorted(focus.items())
                if v and k != "mode"]
        if bits:
            system += "\nContext — " + "; ".join(bits)
    messages: List[Dict[str, str]] = [{"role": "system", "content": system}]
    rows = [m for m in (history or []) if str(m.get("content") or "").strip()]
    for row in rows[-max(0, int(limit)):]:
        role = row.get("role")
        if role not in ("user", "assistant"):
            continue
        messages.append({"role": role, "content": str(row.get("content") or "")})
    return messages


def stream_turn(messages: List[Dict[str, str]], *, model: Optional[str] = None,
                think: Any = True, should_cancel=None, tools=None):
    """Thin seam over UnifiedLLMAdapter.stream_chat (mockable in tests)."""
    adapter = UnifiedLLMAdapter()
    yield from adapter.stream_chat(
        messages,
        model=model or CHAT_MODEL,
        think=think,
        should_cancel=should_cancel,
        num_ctx=CHAT_NUM_CTX,
        num_predict=CHAT_NUM_PREDICT,
        tools=tools,
        num_gpu=CHAT_NUM_GPU,
    )


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
