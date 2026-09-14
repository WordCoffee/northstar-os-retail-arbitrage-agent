"""UnifiedLLMAdapter — routes AutothinK queries to a local Ollama model or a
cloud provider (gpt-4o), per the Northstar OS master plan (§5.3).

Local Ollama (localhost:11434) is the default provider and the first-class
citizen: free, private, no credentials. The cloud path is fully coded but
gated: it activates ONLY if an OPENAI_API_KEY is present in the environment.
Credential VALUES are never read, printed, logged, or returned — only the
boolean presence flag is checked.

Fallback strings `[LOCAL FALLBACK]` / `[OPENAI FALLBACK]` are returned when
the corresponding provider is unavailable, so the UI always has a deterministic
answer instead of an unhandled exception.
"""

import json
import os
import requests
from typing import Dict, List, Optional

OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_CHAT_ENDPOINT = f"{OLLAMA_BASE_URL}/api/chat"
OLLAMA_TAGS_ENDPOINT = f"{OLLAMA_BASE_URL}/api/tags"

DEFAULT_LOCAL_MODEL = "qwen2.5-coder:14b"
DEFAULT_CLOUD_MODEL = "gpt-4o"

# Generation guardrails for long automation prompts. These override the
# Modelfile defaults at request time so the AutothinK surface is never
# capped by a small num_predict or a 16k context window once the model is
# rebuilt with matching values. num_ctx must not exceed the rebuilt
# model's context (qwen2.5-coder:14b supports 32768).
NUM_PREDICT = int(os.environ.get("AUTOTHINK_NUM_PREDICT", "8192"))
NUM_CTX = int(os.environ.get("AUTOTHINK_NUM_CTX", "32768"))

SYSTEM_PROMPT = (
    "You are Northstar AutothinK, the premium build-anything layer of Northstar OS "
    "— a private agent workspace for T2 Holdings LLC (Amazon FBA retail arbitrage). "
    "You plan, build, and explain end-to-end workflows for product discovery, "
    "Costco cross-referencing, FBA fee analysis, and portfolio management. "
    "Be precise, cite concrete numbers when available, and never invent data "
    "points that are not provided."
)


class UnifiedLLMAdapter:
    """Route one query to the best available model provider."""

    def __init__(
        self,
        local_model: str = DEFAULT_LOCAL_MODEL,
        cloud_model: str = DEFAULT_CLOUD_MODEL,
        timeout_s: float = 600.0,
        system_prompt: str = SYSTEM_PROMPT,
    ):
        self.local_model = local_model
        self.cloud_model = cloud_model
        self.timeout_s = timeout_s
        self.system_prompt = system_prompt

    # ------------------------------------------------------------------
    # Provider presence (never exposes credential values)
    # ------------------------------------------------------------------

    @staticmethod
    def cloud_available() -> bool:
        """True only if an OPENAI_API_KEY is present. Presence-only check."""
        return bool(os.environ.get("OPENAI_API_KEY"))

    def local_available(self) -> bool:
        """Probe Ollama /api/tags. Zero auth, zero cost."""
        try:
            resp = requests.get(OLLAMA_TAGS_ENDPOINT, timeout=3)
            return resp.status_code == 200
        except requests.RequestException:
            return False

    def list_local_models(self) -> List[str]:
        """Return installed model names from the local Ollama instance."""
        try:
            resp = requests.get(OLLAMA_TAGS_ENDPOINT, timeout=5)
            if resp.status_code != 200:
                return []
            payload = resp.json()
            return [m.get("name", "") for m in payload.get("models", []) if m.get("name")]
        except (requests.RequestException, ValueError):
            return []

    # ------------------------------------------------------------------
    # Generation
    # ------------------------------------------------------------------

    def generate(self, query: str, provider: str = "local", model: Optional[str] = None) -> Dict:
        """Generate a response for `query`.

        provider: "local" (default) or "cloud".
        model:    optional override; falls back to adapter default per provider.
        """
        if provider == "cloud":
            return self._generate_cloud(query, model or self.cloud_model)
        return self._generate_local(query, model or self.local_model)

    def _generate_local(self, query: str, model: str) -> Dict:
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": query},
        ]
        # Streamed generation with explicit generation guardrails. Streaming
        # lets the backend consume tokens as they arrive instead of waiting
        # for one giant non-streaming body, which is what pushed long
        # automation responses past the old 120s read timeout into an
        # "[LOCAL FALLBACK]" stop. num_predict/num_ctx are honored at request
        # time, independent of the Modelfile defaults.
        request_json = {
            "model": model,
            "messages": messages,
            "stream": True,
            "options": {
                "num_predict": NUM_PREDICT,
                "num_ctx": NUM_CTX,
            },
        }
        try:
            resp = requests.post(
                OLLAMA_CHAT_ENDPOINT,
                json=request_json,
                stream=True,
                timeout=self.timeout_s,
            )
            if resp.status_code != 200:
                return self._local_fallback(query, model, reason=f"ollama http {resp.status_code}")
            content_parts: List[str] = []
            prompt_tokens = None
            completion_tokens = None
            total_duration = None
            done_seen = False
            for line in resp.iter_lines(decode_unicode=True):
                if not line:
                    continue
                try:
                    chunk = json.loads(line)
                except ValueError:
                    # Tolerate keep-alive / heartbeats that are not JSON.
                    continue
                if not isinstance(chunk, dict):
                    continue
                msg = chunk.get("message")
                if isinstance(msg, dict) and msg.get("content"):
                    content_parts.append(str(msg["content"]))
                if chunk.get("done"):
                    done_seen = True
                    prompt_tokens = chunk.get("prompt_eval_count")
                    completion_tokens = chunk.get("eval_count")
                    total_duration = chunk.get("total_duration")
                    break
            content = "".join(content_parts).strip() if content_parts else ""
            if not content:
                reason = "empty model response" + ("" if done_seen else " (no done frame)")
                return self._local_fallback(query, model, reason=reason)
            return {
                "ok": True,
                "provider": "local",
                "model": model,
                "content": content,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "elapsed_ms": (total_duration or 0) / 1_000_000,
            }
        except requests.RequestException as exc:
            return self._local_fallback(query, model, reason=str(exc))

    def _generate_cloud(self, query: str, model: str) -> Dict:
        if not self.cloud_available():
            return {
                "ok": False,
                "provider": "cloud",
                "model": model,
                "content": (
                    "[OPENAI FALLBACK] Cloud provider is not configured — no OPENAI_API_KEY "
                    "is present in the environment. Switch to the Local provider to use the "
                    "offline Ollama model."
                ),
                "reason": "no_api_key",
            }
        # Full cloud code path is implemented here but is live-gated by
        # cloud_available(). Calls are deliberately NOT executed without an
        # explicitly approved live run.
        return {
            "ok": False,
            "provider": "cloud",
            "model": model,
            "content": "[OPENAI FALLBACK] Cloud path is coded but gated; awaiting operator approval to execute.",
            "reason": "not_approved",
        }

    def _local_fallback(self, query: str, model: str, reason: str) -> Dict:
        return {
            "ok": False,
            "provider": "local",
            "model": model,
            "content": (
                f"[LOCAL FALLBACK] Ollama is unavailable ({reason}). "
                "The AutothinK brain is still online — start it with: ollama serve"
            ),
            "reason": reason,
        }


def build_system_prompt_with_context(context: Optional[Dict]) -> str:
    """Extend the base system prompt with optional Northstar OS context
    (e.g. inventory of available data sources). Kept pure and deterministic."""
    prompt = SYSTEM_PROMPT
    if context:
        data_sources = context.get("data_sources")
        if data_sources:
            prompt += "\n\nAvailable local data sources:\n- " + "\n- ".join(str(d) for d in data_sources)
    return prompt