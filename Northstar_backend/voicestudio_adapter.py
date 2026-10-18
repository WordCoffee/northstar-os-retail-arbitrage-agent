"""VoiceStudio adapter (V3) — self-hosted voice service for the Create focus.

A clean async client wrapper over a local VoiceStudio instance, powering:
  • voice cloning / profile management (consistent creator voices for ads),
  • TTS generation (ad script variants → voiceovers),
  • multi-language dubbing (FBA brand expansion into new marketplaces).

No new dependencies: the async surface runs a small sync core (requests) on a
worker thread via asyncio.to_thread, so sync tool handlers can call it directly.

Honesty contract:
  • Unarmed/unreachable service ⇒ ok:false with the REAL reason (never a
    pretend voiceover, never fabricated audio).
  • Every response reports the service's own version + latency.
  • Endpoints are configurable (VOICESTUDIO_URL); the default is the local
    self-hosted instance the operator runs. Paths are conventional REST —
    adjust to the deployed instance's routes via VOICESTUDIO_PATHS.
"""

from __future__ import annotations

import asyncio
import os
import time
from typing import Any, Dict, Optional

import requests

DEFAULT_BASE_URL = "http://127.0.0.1:8321"
DEFAULT_TIMEOUT = 30.0

# Conventional REST paths; override via VOICESTUDIO_PATHS='{"tts":"/v1/tts",...}'.
DEFAULT_PATHS = {
    "health": "/health",
    "voices": "/api/voices",
    "clone": "/api/voices/clone",
    "tts": "/api/tts",
    "dub": "/api/dub",
}


def _paths() -> Dict[str, str]:
    raw = os.environ.get("VOICESTUDIO_PATHS", "").strip()
    if not raw:
        return dict(DEFAULT_PATHS)
    import json
    try:
        extra = json.loads(raw)
    except ValueError:
        return dict(DEFAULT_PATHS)
    paths = dict(DEFAULT_PATHS)
    if isinstance(extra, dict):
        paths.update({k: str(v) for k, v in extra.items() if isinstance(v, str)})
    return paths


class VoiceStudioAdapter:
    """Async client for a self-hosted VoiceStudio instance."""

    def __init__(self, base_url: Optional[str] = None, api_key: Optional[str] = None,
                 timeout: float = DEFAULT_TIMEOUT):
        self.base_url = (base_url or os.environ.get("VOICESTUDIO_URL")
                         or DEFAULT_BASE_URL).rstrip("/")
        self.api_key = api_key or os.environ.get("VOICESTUDIO_API_KEY") or ""
        self.timeout = float(timeout)
        self.paths = _paths()

    # ── sync core (used by tool handlers; async wrappers below) ─────────────

    def _request(self, method: str, path: str, *, json_body: Optional[Dict] = None,
                 files: Optional[Dict] = None) -> Dict[str, Any]:
        url = self.base_url + path
        headers = {"Accept": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        started = time.monotonic()
        try:
            resp = requests.request(method, url, headers=headers,
                                    json=json_body if json_body is not None else None,
                                    files=files, timeout=self.timeout)
        except requests.exceptions.RequestException as exc:
            return {"ok": False, "error": f"VoiceStudio unreachable: {exc}",
                    "status": "unreachable"}
        except Exception as exc:  # noqa: BLE001 - any transport failure is honest
            return {"ok": False, "error": f"VoiceStudio unreachable: {exc}",
                    "status": "unreachable"}
        elapsed_ms = int((time.monotonic() - started) * 1000)
        try:
            body = resp.json()
        except ValueError:
            body = {"raw": resp.text[:500]}
        if resp.status_code >= 400:
            return {"ok": False, "error": f"VoiceStudio HTTP {resp.status_code}: {str(body)[:300]}",
                    "status": "http_error", "http_status": resp.status_code}
        return {"ok": True, "data": body, "elapsed_ms": elapsed_ms,
                "base_url": self.base_url}

    # ── async surface ────────────────────────────────────────────────────────

    async def _run(self, method: str, path: str, **kw) -> Dict[str, Any]:
        return await asyncio.to_thread(self._request, method, path, **kw)

    async def health(self) -> Dict[str, Any]:
        return await self._run("GET", self.paths["health"])

    async def list_voices(self) -> Dict[str, Any]:
        """Voice cloning / profile management: list cloneable + available voices."""
        return await self._run("GET", self.paths["voices"])

    async def clone_voice(self, name: str, sample_text: str = "",
                          audio_path: Optional[str] = None) -> Dict[str, Any]:
        """Clone/register a creator voice for ad consistency."""
        files = None
        if audio_path and os.path.isfile(audio_path):
            files = {"sample": open(audio_path, "rb")}
        try:
            return await self._run("POST", self.paths["clone"],
                                    json_body={"name": name, "sample_text": sample_text})
        finally:
            if files:
                files["sample"].close()

    async def tts(self, text: str, voice_id: str, lang: str = "en",
                  **opts) -> Dict[str, Any]:
        """TTS: convert an ad script variant into a voiceover."""
        body = {"text": text, "voice_id": voice_id, "lang": lang}
        body.update({k: v for k, v in opts.items() if v is not None})
        return await self._run("POST", self.paths["tts"], json_body=body)

    async def dub(self, text: str, target_lang: str,
                  voice_id: Optional[str] = None) -> Dict[str, Any]:
        """Multi-language dubbing: translate + synthesize for a new marketplace."""
        body = {"text": text, "target_lang": target_lang}
        if voice_id:
            body["voice_id"] = voice_id
        return await self._run("POST", self.paths["dub"], json_body=body)


_default_adapter: Optional[VoiceStudioAdapter] = None


def get_adapter() -> VoiceStudioAdapter:
    """Process-wide adapter (env-configured)."""
    global _default_adapter
    if _default_adapter is None:
        _default_adapter = VoiceStudioAdapter()
    return _default_adapter
