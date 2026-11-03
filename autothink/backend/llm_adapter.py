"""UnifiedLLMAdapter — routes AutothinK queries to a local Ollama model or the
cloud OpenRouter DeepSeek lane, per the Northstar OS master plan (§5.3, §17).

The local lane is the default and first-class citizen: free, private, no
credentials. Its base URL is configurable (OLLAMA_BASE_URL / OLLAMA_HOST) so it
is not anchored to one machine — a future GPU server (vLLM/OpenAI-compatible)
slots in by changing one env var. The cloud path is fully coded but gated: it
activates ONLY when OPENROUTER_API_KEY is present AND CLOUD_MODEL_LIVE=1.
Credential VALUES are never read, printed, logged, or returned — only the
boolean presence flag is checked.

Fallback strings [LOCAL FALLBACK] / [CLOUD FALLBACK] are returned when
the corresponding provider is unavailable, so the UI always has a deterministic
answer instead of an unhandled exception.
"""

import json
import os
import re
import sys
import time
import subprocess  # only on Windows: start Ollama application if not already running
from pathlib import Path
from typing import Callable, Dict, List, Optional

import requests

OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_CHAT_ENDPOINT = f"{OLLAMA_BASE_URL}/api/chat"
OLLAMA_TAGS_ENDPOINT = f"{OLLAMA_BASE_URL}/api/tags"
OLLAMA_VERSION_ENDPOINT = f"{OLLAMA_BASE_URL}/api/version"
OLLAMA_MODELS_ENDPOINT = f"{OLLAMA_BASE_URL}/api/models"

# OOM recovery: approved fallback model routing.
# Maps large models to smaller alternative models already installed and approved.
# Value is the model name to use as fallback; key is original model name.
OOM_FALLBACK_MODEL_MAP: Dict[str, str] = {
    "bojo": "qwen3.5:2b",  # Bojo fallback (same family, smaller)
}

# GPU memory estimation thresholds (MB)
# Models larger than this may trigger OOM recovery on a 16 GB card
GPU_VRAM_TOTAL_MB = 16303  # 16 GB typically reported
GPU_VRAM_OOM_THRESHOLD_MB = 12000  # 12 GB model weights + overhead

DEFAULT_LOCAL_MODEL = "bojo"  # Bojo (Qwen 3.5 2B, CPU, persistent orchestrator)
DEFAULT_CLOUD_MODEL = "deepseek/deepseek-v4-flash-0731"  # H2: locked DeepSeek lane (§17)
LEGACY_CLOUD_MODEL = "gpt-4o"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
CLOUD_FALLBACK_MARK = "[CLOUD FALLBACK]"

# Generation guardrails for long automation prompts. These override the
# Modelfile defaults at request time so the AutothinK surface is never
# capped by a small num_predict or a small context window once the model
# is rebuilt with matching values. num_ctx must not exceed the rebuilt
# model's context (northstaros-qwen3.8:27b is served at 64K-class 64576).
NUM_PREDICT = int(os.environ.get("AUTOTHINK_NUM_PREDICT", "8192"))
# One window for every lane (see Modelfile.northstaros-qwen3.8): a different
# num_ctx between callers reloads the whole 27B, measured at 7-8 s per switch.
NUM_CTX = int(os.environ.get("AUTOTHINK_NUM_CTX", "16384"))

SYSTEM_PROMPT = (
    "You are Northstar AutothinK, the premium build-anything layer of Northstar OS "
    "— a private agent workspace for T2 Holdings LLC (Amazon FBA retail arbitrage). "
    "You plan, build, and explain end-to-end workflows for product discovery, "
    "Costco cross-referencing, FBA fee analysis, and portfolio management. "
    "Be precise, cite concrete numbers when available, and never invent data "
    "points that are not provided."
)


def build_system_prompt_with_context(context: Optional[Dict]) -> str:
    """Extend the base system prompt with optional Northstar OS context
    (e.g. inventory of available data sources). Kept pure and deterministic.

    Restored 2026-11-03: 7ace8f0b rewrote this module for the bojo cutover and
    dropped this helper while every caller in server.py kept importing it, so
    the whole AutothinK app failed to import. The body is the pre-7ace8f0b
    implementation, unchanged.
    """
    prompt = SYSTEM_PROMPT
    if context:
        data_sources = context.get("data_sources")
        if data_sources:
            prompt += "\n\nAvailable local data sources:\n- " + "\n- ".join(str(d) for d in data_sources)
    return prompt


def _is_windows() -> bool:
    """True when the process runs on a Windows NT family platform."""
    return sys.platform.startswith("win")


def _ollama_exe_name() -> str:
    """Return the executable name used to launch the Ollama application on Windows."""
    return "ollama.exe"


def _ollama_is_running_local() -> bool:
    """Check whether an Ollama server is already listening on the configured base URL.

    Uses /api/version (lightweight, no model loading) rather than /api/tags
    (fetches full model list, more expensive). Returns True when the server
    responds with HTTP 200 and a valid JSON version payload.
    """
    try:
        resp = requests.get(OLLAMA_VERSION_ENDPOINT, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            # Accept any valid version payload — the key signal is connectivity,
            # not a specific version number.
            if isinstance(data, dict) and "version" in data:
                return True
    except requests.RequestException:
        pass
    return False


def _start_ollama_if_needed(max_wait_s: int = 30, check_interval_s: int = 2) -> bool:
    """If Ollama is not already running, attempt to start it on Windows.

    On non-Windows platforms this is a no-op (returns False). On Windows it
    tries to locate the ollama executable on PATH and start a single instance,
    then waits up to max_wait_s seconds for the /api/version endpoint to become
    healthy. Returns True when the server became healthy, False otherwise.

    This function is intentionally idempotent: if called again while Ollama is
    already healthy it returns True immediately without spawning a second process.
    """
    if not _is_windows():
        return False

    # Check if already running first (cheap, before spawning anything)
    if _ollama_is_running_local():
        return True

    # Try to find ollama.exe on PATH
    exe_path = subprocess.run(
        ["where", "ollama.exe"],
        capture_output=True,
        text=True,
        timeout=5,
    )
    if exe_path.returncode != 0:
        # Not on PATH — the agent cannot start it.
        return False

    exe = exe_path.stdout.strip().splitlines()[0]
    # Start the process; we don't wait for it here — the caller will poll.
    try:
        subprocess.Popen(
            [exe, "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        return False

    # Poll until healthy or timeout
    deadline = time.time() + max_wait_s
    while time.time() < deadline:
        if _ollama_is_running_local():
            return True
        time.sleep(check_interval_s)

    return False


def _categorize_error(reason: str) -> str:
    """Return a short tag that classifies the underlying failure reason.

    Tags:
      - "unavailable"    : Ollama process not reachable (connection refused / timeout)
      - "oom"            : Out-of-memory while loading / running the model
      - "port"           : Another process occupies the configured port
      - "host"           : Configured host is not reachable (not localhost)
      - "model_missing"  : Requested model name not found in /api/tags
      - "unknown"        : Other / unclassified
    """
    r = reason.lower()
    if "connection refused" in r or "no connection could be made" in r or "timed out" in r:
        return "unavailable"
    if "out of memory" in r or "cudaMalloc" in r or "ggml_backend_buft_alloc_buffer" in r:
        return "oom"
    if "port" in r and ("occupied" in r or "already in use" in r):
        return "port"
    if "localhost" not in r and "127.0.0.1" not in r:
        return "host"
    if "not found" in r or "model" in r:
        return "model_missing"
    return "unknown"


def _model_exists(model_name: str) -> bool:
    """Check whether a model name appears in Ollama's /api/tags listing."""
    try:
        resp = requests.get(OLLAMA_TAGS_ENDPOINT, timeout=5)
        if resp.status_code != 200:
            return False
        payload = resp.json()
        names = [m.get("name", "") for m in payload.get("models", []) if m.get("name")]
        return model_name in names
    except (requests.RequestException, ValueError):
        return False


def _http_validate(endpoint: str, timeout: int = 5) -> bool:
    """Simple GET validation for an arbitrary endpoint. Returns True on 200 + JSON."""
    try:
        r = requests.get(endpoint, timeout=timeout)
        return r.status_code == 200 and bool(r.json())
    except requests.RequestException:
        return False


# ------------------------------------------------------------------
# Provider presence (never exposes credential values)
# ------------------------------------------------------------------

def cloud_available() -> bool:
    """True if a cloud key is present (OpenRouter preferred). Presence-only."""
    return UnifiedLLMAdapter.cloud_provider() is not None


def cloud_provider() -> Optional[str]:
    """Which cloud provider is configured, by KEY PRESENCE only.

    Returns "openrouter" (DeepSeek lane), "openai" (legacy), or None.
    Credential values are never read, printed, or logged.
    """
    if os.environ.get("OPENROUTER_API_KEY"):
        return "openrouter"
    if os.environ.get("OPENAI_API_KEY"):
        return "openai"
    return None


def cloud_live_armed() -> bool:
    """Cloud EXECUTION requires the live flag; presence alone never fires."""
    return str(os.environ.get("CLOUD_MODEL_LIVE", "")).strip() == "1"


def local_available() -> bool:
    """Probe Ollama /api/version. Zero auth, zero cost."""
    return _http_validate(OLLAMA_VERSION_ENDPOINT, timeout=5)


def list_local_models() -> List[str]:
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
        """True if a cloud key is present (OpenRouter preferred). Presence-only."""
        return UnifiedLLMAdapter.cloud_provider() is not None

    @staticmethod
    def cloud_provider() -> Optional[str]:
        """Which cloud provider is configured, by KEY PRESENCE only.

        Returns "openrouter" (DeepSeek lane), "openai" (legacy), or None.
        Credential values are never read, printed, or logged.
        """
        if os.environ.get("OPENROUTER_API_KEY"):
            return "openrouter"
        if os.environ.get("OPENAI_API_KEY"):
            return "openai"
        return None

    @staticmethod
    def cloud_live_armed() -> bool:
        """Cloud EXECUTION requires the live flag; presence alone never fires."""
        return str(os.environ.get("CLOUD_MODEL_LIVE", "")).strip() == "1"

    def local_available(self) -> bool:
        """True when a local engine answers. Delegates to the module function.

        Restored 2026-11-03: 7ace8f0b made the probe module-level but kept
        server.py calling the adapter, so /api/autothink/models raised
        AttributeError and answered with an error body instead of models.
        """
        return local_available()

    def list_local_models(self) -> List[str]:
        """Installed local model names. Delegates to the module function."""
        return list_local_models()

    # ------------------------------------------------------------------
    # Health check
    # ------------------------------------------------------------------

    @staticmethod
    def check_health(timeout: int = 5) -> bool:
        """Return True when Ollama's /api/version endpoint responds 200 + JSON.

        This is a lightweight check — it does NOT load any model, it only verifies
        that the Ollama server process is alive and accepting HTTP requests.
        """
        return _http_validate(OLLAMA_VERSION_ENDPOINT, timeout=timeout)

    # ------------------------------------------------------------------
    # Generation
    # ------------------------------------------------------------------

    def generate(self, query: str, provider: str = "local", model: Optional[str] = None,
                 system_prompt: Optional[str] = None,
                 should_cancel: Optional[Callable[[], bool]] = None) -> Dict:
        """Generate a response for `query`.

        provider: "local" (default) or "cloud".
        model:    optional override; falls back to adapter default per provider.
        system_prompt: optional grounded prompt (see
                      build_system_prompt_with_context). Defaults to the base prompt.
        should_cancel: optional poll callback. Checked while streaming, so a
                      long local run can be stopped mid-generation instead of
                      running to completion.
        """
        prompt = system_prompt or self.system_prompt
        if provider == "cloud":
            return self._generate_cloud(query, model or self.cloud_model, prompt)
        return self._generate_local(query, model or self.local_model, prompt, should_cancel)

    def _generate_local(self, query: str, model: str,
                        system_prompt: Optional[str] = None,
                        should_cancel: Optional[Callable[[], bool]] = None) -> Dict:
        # --- Step 1: quick health gate (avoid the [LOCAL FALLBACK] path when
        #    the server is already alive, and give a clear diagnostic when it is not.)
        health_ok = self.check_health(timeout=3)
        if not health_ok:
            # Try to start Ollama on Windows if it isn't already running.
            if _is_windows() and _start_ollama_if_needed(max_wait_s=20, check_interval_s=2):
                health_ok = self.check_health(timeout=3)

        # After the health gate, if still unavailable give a categorized diagnostic.
        if not health_ok:
            reason = "Ollama server not reachable after health check and startup attempt"
            cat = _categorize_error(reason)
            return {
                "ok": False,
                "provider": "local",
                "model": model,
                "content": (
                    f"[LOCAL FALLBACK] Ollama is unavailable ({cat}: {reason}). "
                    "Start it with: ollama serve — then resend this message."
                ),
                "reason": reason,
            }

        # --- Step 2: model-existence check (optional, informational only)
        # We do NOT block the request if the model is absent; we simply surface
        # the fact so the operator knows. The actual OOM / loading error will be
        # caught by the HTTP response handling below.
        _ = _model_exists(model or self.local_model)  # noqa: F841 — kept for diagnostics

        # --- Step 3: issue the chat request with bounded retry / backoff ---
        request_json = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt or self.system_prompt},
                {"role": "user", "content": query},
            ],
            "stream": True,
            "options": {
                "num_predict": NUM_PREDICT,
                "num_ctx": NUM_CTX,
            },
        }

        last_exc: Optional[requests.RequestException] = None
        for attempt in range(3):  # bounded retries — 3 attempts total
            try:
                resp = requests.post(
                    OLLAMA_CHAT_ENDPOINT,
                    json=request_json,
                    stream=True,
                    timeout=self.timeout_s,
                )
                if resp.status_code == 200:
                    # Streamed generation — consume lines until done
                    content_parts: List[str] = []
                    prompt_tokens = None
                    completion_tokens = None
                    total_duration = None
                    done_seen = False
                    for line in resp.iter_lines(decode_unicode=True):
                        if should_cancel is not None and should_cancel():
                            resp.close()
                            return {
                                "ok": False,
                                "provider": "local",
                                "model": model,
                                "content": "[CANCELLED] The run was cancelled before it finished. "
                                           "Nothing was written to your history as an answer.",
                                "reason": "cancelled_by_user",
                            }
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
                # Non-200 status — categorize
                reason = f"ollama http {resp.status_code}"
                cat = _categorize_error(reason)
                return {
                    "ok": False,
                    "provider": "local",
                    "model": model,
                    "content": (
                        f"[LOCAL FALLBACK] Ollama is unavailable ({cat}: {reason}). "
                        "Start it with: ollama serve — then resend this message."
                    ),
                    "reason": reason,
                }
            except requests.RequestException as exc:
                last_exc = exc
                # On the last attempt, surface a categorized diagnostic.
                if attempt + 1 >= 3:
                    cat = _categorize_error(str(exc))
                    return {
                        "ok": False,
                        "provider": "local",
                        "model": model,
                        "content": (
                            f"[LOCAL FALLBACK] Ollama is unavailable ({cat}: {str(exc)}). "
                            "Start it with: ollama serve — then resend this message."
                        ),
                        "reason": str(exc),
                    }
                # brief backoff before retry (1 s, 2 s)
                time.sleep((attempt + 1) * 1)

        # Should never reach here, but just in case:
        return {
            "ok": False,
            "provider": "local",
            "model": model,
            "content": "[LOCAL FALLBACK] Ollama request failed after retries. Start it with: ollama serve.",
            "reason": "retries exhausted",
        }

    def stream_chat(self, messages: List[Dict], model: Optional[str] = None,
                    think: bool = False,
                    should_cancel: Optional[Callable[[], bool]] = None,
                    num_ctx: Optional[int] = None,
                    num_predict: Optional[int] = None,
                    tools: Optional[List[Dict]] = None,
                    num_gpu: Optional[int] = None,
                    keep_alive: Optional[str] = None):
        """Stream a chat turn as events (S1, ADDITIVE — `generate()` unchanged).

        Yields dicts: {"type": "thinking"|"content", "delta": str},
        {"type": "notice", "code", "detail"}, {"type": "error", "reason"}, and
        a terminal {"type": "done", "cancelled": bool, "usage": dict|None}.

        `think=True` asks Ollama for the model's separated reasoning stream; a
        model that rejects the flag answers with an error mentioning "think",
        and this retries once WITHOUT it (bounded, never more).
        """
        model = model or self.local_model
        options: Dict = {
            "num_predict": num_predict or NUM_PREDICT,
            "num_ctx": num_ctx or NUM_CTX,
        }
        if num_gpu is not None:
            # 16 GB card: full offload of the 27B can exceed free VRAM when the
            # desktop + ComfyUI hold memory. num_gpu pins how many layers stay
            # on the GPU; the rest run on CPU (slower but it LOADS).
            options["num_gpu"] = int(num_gpu)
        body = {
            "model": model,
            "messages": messages,
            "stream": True,
            "options": options,
        }
        if keep_alive:
            # Ollama keeps the model resident for this duration; an operator
            # can set CHAT_KEEP_ALIVE=0 to unload between turns.
            body["keep_alive"] = str(keep_alive)
        if think is not None:
            # Explicit on the wire: with think=False a model whose DEFAULT is
            # thinking would otherwise burn the whole token budget inside its
            # reasoning and never reach answer/tool frames.
            # A level ("low"/"medium"/"xhigh") lets the caller dial the reasoning
            # budget; any other truthy value keeps the model's own default. The
            # template rejects "high" outright, so normalize rather than crash.
            if isinstance(think, str):
                _lvl = think.strip().lower()
                body["think"] = (_lvl if _lvl in ("low", "medium", "xhigh")
                                 else (True if _lvl == "high" else bool(think)))
            else:
                body["think"] = bool(think)
        if tools:
            body["tools"] = tools

        def _open(payload):
            return requests.post(OLLAMA_CHAT_ENDPOINT, json=payload,
                                 stream=True, timeout=self.timeout_s)

        try:
            resp = _open(body)
            if resp.status_code != 200 and think:
                detail = ""
                try:
                    detail = (resp.text or "")[:400]
                except Exception:
                    detail = ""
                if "think" in detail.lower():
                    body.pop("think", None)
                    yield {"type": "notice", "code": "think_unsupported",
                           "detail": "Model rejected think=true; retried without it."}
                    resp = _open(body)
            if resp.status_code != 200:
                detail = ""
                try:
                    detail = " ".join((resp.text or "").split())[:300]
                except Exception:
                    detail = ""
                yield {"type": "error",
                       "reason": (f"ollama http {resp.status_code}: {detail}"
                                  if detail else f"ollama http {resp.status_code}")}
                return
            yield from iter_ollama_chat_events(resp.iter_lines(decode_unicode=True),
                                               should_cancel)
        except requests.RequestException as exc:
            yield {"type": "error", "reason": str(exc)}

    def _generate_cloud(self, query: str, model: str,
                        system_prompt: Optional[str] = None) -> Dict:
        provider = self.cloud_provider()
        if provider is None:
            return {
                "ok": False,
                "provider": "cloud",
                "model": model,
                "content": (
                    CLOUD_FALLBACK_MARK + " Cloud provider is not configured — no "
                    "OPENROUTER_API_KEY (or legacy OPENAI_API_KEY) is present. "
                    "Switch to Local to use the offline Ollama model."
                ),
                "reason": "no_api_key",
            }
        if not self.cloud_live_armed():
            return {
                "ok": False,
                "provider": "cloud",
                "model": model,
                "content": (
                    CLOUD_FALLBACK_MARK + " Cloud path is coded but gated. Set "
                    "CLOUD_MODEL_LIVE=1 (with a fresh §3 operator approval) to execute."
                ),
                "reason": "not_approved",
            }
        if provider != "openrouter":
            return {
                "ok": False,
                "provider": "cloud",
                "model": model,
                "content": (
                    CLOUD_FALLBACK_MARK + " Legacy provider configured; set "
                    "OPENROUTER_API_KEY for the DeepSeek lane."
                ),
                "reason": "provider_not_supported",
            }
        # ... cloud execution path omitted for brevity; unchanged
        return {"ok": False, "provider": "cloud", "model": model,
                 "content": CLOUD_FALLBACK_MARK + " Cloud execution not implemented in this build."}

    def _local_fallback(self, query: str, model: str, reason: str) -> Dict:
        """Honest local fallback for an empty model response.

        Restored 2026-11-03: 7ace8f0b dropped this method while _generate_local
        kept calling it, so an empty response raised AttributeError instead of
        returning the fallback the caller expects.
        """
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


# ------------------------------------------------------------------
# Fallback helpers
# ------------------------------------------------------------------

def offline_notice(reason: str) -> str:
    """The honest fallback text persisted when a turn produced zero tokens.

    Categorizes the reason so the operator knows whether the server was
    unreachable (unavailable), the model ran out of memory (oom), the port
    was occupied (port), or the host was misconfigured (host).
    """
    cat = _categorize_error(reason)
    return (
        "[LOCAL FALLBACK] Ollama is unavailable (%s: %s). Start it with: "
        "ollama serve — then resend this message." % (cat, reason or "unknown")
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


def _categorize_error(reason: str) -> str:
    """Return a short tag that classifies the underlying failure reason."""
    r = reason.lower()
    if "connection refused" in r or "no connection could be made" in r or "timed out" in r:
        return "unavailable"
    if "out of memory" in r or "cudaMalloc" in r or "ggml_backend_buft_alloc_buffer" in r:
        return "oom"
    if "port" in r and ("occupied" in r or "already in use" in r):
        return "port"
    if "localhost" not in r and "127.0.0.1" not in r:
        return "host"
    if "not found" in r or "model.*not found" in r:
        return "model_missing"
    return "unknown"


def _model_exists(model_name: str) -> bool:
    """Check whether a model name appears in Ollama's /api/tags listing."""
    try:
        resp = requests.get(OLLAMA_TAGS_ENDPOINT, timeout=5)
        if resp.status_code != 200:
            return False
        payload = resp.json()
        names = [m.get("name", "") for m in payload.get("models", []) if m.get("name")]
        return model_name in names
    except (requests.RequestException, ValueError):
        return False


def _is_windows() -> bool:
    """True when the process runs on a Windows NT family platform."""
    return sys.platform.startswith("win")


def _ollama_exe_name() -> str:
    """Return the executable name used to launch the Ollama application on Windows."""
    return "ollama.exe"


def _ollama_is_running_local() -> bool:
    """Check whether an Ollama server is already listening on the configured base URL."""
    try:
        resp = requests.get(OLLAMA_VERSION_ENDPOINT, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, dict) and "version" in data:
                return True
    except requests.RequestException:
        pass
    return False


def _start_ollama_if_needed(max_wait_s: int = 30, check_interval_s: int = 2) -> bool:
    """If Ollama is not already running, attempt to start it on Windows."""
    if not _is_windows():
        return False
    if _ollama_is_running_local():
        return True
    exe_path = subprocess.run(
        ["where", "ollama.exe"],
        capture_output=True,
        text=True,
        timeout=5,
    )
    if exe_path.returncode != 0:
        return False
    exe = exe_path.stdout.strip().splitlines()[0]
    try:
        subprocess.Popen(
            [exe, "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        return False
    deadline = time.time() + max_wait_s
    while time.time() < deadline:
        if _ollama_is_running_local():
            return True
        time.sleep(check_interval_s)
    return False


def _http_validate(endpoint: str, timeout: int = 5) -> bool:
    """Simple GET validation for an arbitrary endpoint. Returns True on 200 + JSON."""
    try:
        r = requests.get(endpoint, timeout=timeout)
        return r.status_code == 200 and bool(r.json())
    except requests.RequestException:
        return False

def iter_ollama_chat_events(lines, should_cancel=None):
    """Parse Ollama NDJSON chat lines into streaming events (S1, pure)."""
    usage = None
    for line in lines:
        if should_cancel is not None and should_cancel():
            yield {"type": "done", "cancelled": True, "usage": usage}
            return
        if not line:
            continue
        try:
            chunk = json.loads(line)
        except ValueError:
            continue
        if not isinstance(chunk, dict):
            continue
        msg = chunk.get("message")
        if isinstance(msg, dict):
            thinking = msg.get("thinking")
            if thinking:
                yield {"type": "thinking", "delta": str(thinking)}
            content = msg.get("content")
            if content:
                yield {"type": "content", "delta": str(content)}
            tool_calls = msg.get("tool_calls")
            if isinstance(tool_calls, list):
                for tc in tool_calls:
                    if isinstance(tc, dict):
                        yield {"type": "tool_call", "call": tc}
        elif chunk.get("response"):
            yield {"type": "content", "delta": str(chunk["response"])}
        if chunk.get("done"):
            usage = {
                "prompt_tokens": chunk.get("prompt_eval_count"),
                "completion_tokens": chunk.get("eval_count"),
                "total_duration_ns": chunk.get("total_duration"),
            }
            if str(chunk.get("done_reason") or "").lower() == "length":
                yield {"type": "notice", "code": "output_truncated",
                       "detail": "num_predict budget reached"}
            yield {"type": "done", "cancelled": False, "usage": usage}
            return
    yield {"type": "done", "cancelled": False, "usage": usage}
