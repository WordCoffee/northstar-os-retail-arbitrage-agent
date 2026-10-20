"""Bojo speaks — the TTS route of the duplex voice loop.

The route reuses the existing voice-studio adapter. The contract that matters:
an unreachable engine is a 503 with the REAL reason, and a reply without an
``audio_url`` is a 502 — never a silent success that leaves the client waiting for
sound that will not come.
"""
from __future__ import annotations

import asyncio

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

import chat_voice
import voicestudio_adapter


def _speak(**kwargs):
    return asyncio.run(chat_voice.speak(chat_voice.SpeakIn(**kwargs), "acct-1"))


class _FakeAdapter:
    def __init__(self, result):
        self.result = result
        self.calls = []

    async def tts(self, text, voice_id, lang="en", **opts):
        self.calls.append((text, voice_id, lang))
        return self.result


# ── schema ─────────────────────────────────────────────────────────────────

def test_speak_input_is_validated():
    with pytest.raises(ValidationError):
        chat_voice.SpeakIn(text="", voice_id="v1")
    with pytest.raises(ValidationError):
        chat_voice.SpeakIn(text="hi", voice_id="")
    assert chat_voice.SpeakIn(text="hi", voice_id="v1").lang == "en"


# ── behaviour ──────────────────────────────────────────────────────────────

def test_speak_returns_the_audio_url(monkeypatch):
    fake = _FakeAdapter({"ok": True, "elapsed_ms": 420,
                         "data": {"audio_url": "http://127.0.0.1:8321/a.mp3"}})
    monkeypatch.setattr(voicestudio_adapter, "get_adapter", lambda: fake)
    out = _speak(text="Draft ready.", voice_id="bojo-narrator")
    assert out["ok"] is True
    assert out["audio_url"].endswith("a.mp3")
    assert out["elapsed_ms"] == 420
    assert fake.calls == [("Draft ready.", "bojo-narrator", "en")]


def test_an_unreachable_engine_is_a_503_with_the_real_reason(monkeypatch):
    fake = _FakeAdapter({"ok": False, "error": "VoiceStudio unreachable: connection refused"})
    monkeypatch.setattr(voicestudio_adapter, "get_adapter", lambda: fake)
    with pytest.raises(HTTPException) as exc:
        _speak(text="hi", voice_id="v1")
    assert exc.value.status_code == 503
    assert "unreachable" in str(exc.value.detail).lower()


def test_no_audio_url_is_not_reported_as_success(monkeypatch):
    fake = _FakeAdapter({"ok": True, "data": {}})
    monkeypatch.setattr(voicestudio_adapter, "get_adapter", lambda: fake)
    with pytest.raises(HTTPException) as exc:
        _speak(text="hi", voice_id="v1")
    assert exc.value.status_code == 502
    assert "no audio_url" in str(exc.value.detail)


def test_the_route_is_registered():
    paths = [r.path for r in chat_voice.router.routes]
    assert "/api/chat/voice/speak" in paths
    assert "/api/chat/voice/transcribe" in paths
