"""VoiceStudio adapter tests (V3) — async client + chat tool hooks.

Offline: the transport is mocked; no VoiceStudio, no network. Covers the
happy paths (health/list/tts/dub), the honest-unreachable path, and the
Create-focus tool handlers returning ok:false when the service is down.
"""

from __future__ import annotations

import os
import sys
from unittest import mock

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
_REPO = os.path.dirname(_HERE)
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

import chat_tools  # noqa: E402
import voicestudio_adapter  # noqa: E402
from voicestudio_adapter import VoiceStudioAdapter  # noqa: E402


class _Resp:
    def __init__(self, status=200, payload=None, text=""):
        self.status_code = status
        self._payload = payload or {}
        self.text = text

    def json(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


def _adapter():
    return VoiceStudioAdapter(base_url="http://127.0.0.1:9", timeout=2.0)


def _run(coro):
    import asyncio
    return asyncio.run(coro)


def test_health_ok():
    with mock.patch.object(voicestudio_adapter.requests, "request",
                           return_value=_Resp(200, {"status": "ok", "version": "1.2.3"})):
        out = _run(_adapter().health())
    assert out["ok"] is True
    assert out["data"]["version"] == "1.2.3"
    assert "elapsed_ms" in out


def test_health_unreachable_is_honest():
    import requests as _req
    with mock.patch.object(voicestudio_adapter.requests, "request",
                           side_effect=_req.exceptions.ConnectionError("refused")):
        out = _run(_adapter().health())
    assert out["ok"] is False
    assert "unreachable" in out["error"]


def test_list_voices_and_dub():
    with mock.patch.object(voicestudio_adapter.requests, "request",
                           return_value=_Resp(200, {"voices": [{"id": "v1", "name": "Creator"}]})):
        out = _run(_adapter().list_voices())
    assert out["ok"] is True and out["data"]["voices"][0]["id"] == "v1"
    with mock.patch.object(voicestudio_adapter.requests, "request",
                           return_value=_Resp(200, {"audio_url": "http://x/a.mp3"})):
        dub = _run(_adapter().dub("Hello", "es", voice_id="v1"))
    assert dub["ok"] is True and dub["data"]["audio_url"] == "http://x/a.mp3"


def test_http_error_is_honest():
    with mock.patch.object(voicestudio_adapter.requests, "request",
                           return_value=_Resp(503, {"detail": "busy"})):
        out = _run(_adapter().tts("Hi", "v1"))
    assert out["ok"] is False
    assert "503" in out["error"]


# ── Tool handlers (Create focus) ────────────────────────────────────────────

def _run(coro):
    import asyncio
    return asyncio.run(coro)


def test_voice_list_tool_unarmed_is_honest():
    with mock.patch.object(voicestudio_adapter.requests, "request",
                           side_effect=Exception("no service")):
        out = chat_tools.run_tool("voice_list", {}, {})
    assert out["ok"] is False
    assert "not reachable" in out["summary"]


def test_voice_list_tool_renders_card():
    with mock.patch.object(voicestudio_adapter.requests, "request",
                           return_value=_Resp(200, {"voices": [{"id": "v1", "name": "Creator"}]})):
        out = chat_tools.run_tool("voice_list", {}, {})
    assert out["ok"] is True
    card = out["data"]["card"]
    assert card["title"] == "Voice profiles"
    assert card["rows"][0]["value"] == "v1"
    assert card["action"]["label"] == "Clone a voice"


def test_voice_tts_requires_voice_id():
    out = chat_tools.run_tool("voice_tts", {"text": "Hello"}, {})
    assert out["ok"] is False
    assert "voice_id" in out["error"]


def test_voice_dub_requires_target_lang():
    out = chat_tools.run_tool("voice_dub", {"text": "Hello"}, {})
    assert out["ok"] is False
    assert "target_lang" in out["error"]


def test_voice_tools_are_registered_and_in_create_focus():
    import shell_focus
    assert "voice_list" in chat_tools.TOOLS
    assert "voice_tts" in chat_tools.TOOLS
    assert "voice_dub" in chat_tools.TOOLS
    create_tools = shell_focus.tools_for_focus("create")
    assert "voice_list" in create_tools
    assert "voice_tts" in create_tools
    assert "voice_dub" in create_tools
