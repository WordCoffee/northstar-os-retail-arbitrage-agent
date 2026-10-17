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
CHAT_NUM_PREDICT = int(os.environ.get("CHAT_NUM_PREDICT", "4096"))

CHAT_SYSTEM_PROMPT = (
    "You are the Northstar OS Master Brain in the Creative Studio — the "
    "content-generation copilot for T2 Holdings' brands (Amazon FBA and "
    "retail arbitrage; organic food brands). You help create and refine "
    "packaging designs, product photography, listing images and copy, ad "
    "creatives, and social content. Be concise and concrete. Never invent "
    "product facts, certifications, weights, prices, or legal copy — ask the "
    "operator instead. Packaging text is authored as structured layers, never "
    "painted into images; if asked, explain that and offer the layered "
    "alternative. Mirror the operator's language. Live rendering tools arrive "
    "in S2 — today you plan and answer in chat."
)


def build_chat_messages(history: Iterable[Dict[str, Any]],
                        focus: Optional[Dict[str, Any]] = None,
                        limit: int = CHAT_HISTORY_MAX) -> List[Dict[str, str]]:
    """System prompt (with focus) + the most recent non-empty turns."""
    system = CHAT_SYSTEM_PROMPT
    if focus:
        bits = [f"{k}: {v}" for k, v in sorted(focus.items()) if v]
        if bits:
            system += "\nActive focus — " + "; ".join(bits)
    messages: List[Dict[str, str]] = [{"role": "system", "content": system}]
    rows = [m for m in (history or []) if str(m.get("content") or "").strip()]
    for row in rows[-max(0, int(limit)):]:
        role = row.get("role")
        if role not in ("user", "assistant"):
            continue
        messages.append({"role": role, "content": str(row.get("content") or "")})
    return messages


def stream_turn(messages: List[Dict[str, str]], *, model: Optional[str] = None,
                think: bool = True, should_cancel=None):
    """Thin seam over UnifiedLLMAdapter.stream_chat (mockable in tests)."""
    adapter = UnifiedLLMAdapter()
    yield from adapter.stream_chat(
        messages,
        model=model or CHAT_MODEL,
        think=think,
        should_cancel=should_cancel,
        num_ctx=CHAT_NUM_CTX,
        num_predict=CHAT_NUM_PREDICT,
    )


def offline_notice(reason: str) -> str:
    """The honest fallback text persisted when a turn produced zero tokens."""
    return (
        "[LOCAL FALLBACK] Ollama is unavailable (%s). Start it with: "
        "ollama serve — then resend this message." % (reason or "unknown")
    )
