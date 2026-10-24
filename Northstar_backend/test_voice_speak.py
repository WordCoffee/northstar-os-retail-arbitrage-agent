"""Bojo speaks — the TTS route of the duplex voice loop.

The route reuses the existing voice-studio adapter. The contract that matters:
an unreachable engine is a 503 with the REAL reason, a reply without an
``audio_url`` is a 502, and audio is served SAME-ORIGIN from this app (the engine's
own ``http://127.0.0.1:8321/...`` URL is blocked as mixed content by a browser on
the https tunnel, which is why Bojo could not speak in the hosted UI).
"""
from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

import chat_voice
import voicestudio_adapter


def _speak(**kwargs):
    return asyncio.run(chat_voice.speak(chat_voice.SpeakIn(**kwargs), "acct-1"))


class _FakeAdapter:
    def __init__(self, result, voices=None):
        self.result = result
        self.voices = voices if voices is not None else {
            "ok": True, "data": {"voices": [{"id": "microsoft-zira-desktop"}]}}
        self.calls = []

    async def tts(self, text, voice_id, lang="en", **opts):
        self.calls.append((text, voice_id, lang))
        return self.result

    async def list_voices(self):
        return self.voices


def _use(monkeypatch, adapter, tmp_path=None):
    monkeypatch.setattr(voicestudio_adapter, "get_adapter", lambda: adapter)
    if tmp_path is not None:
        monkeypatch.setattr(chat_voice, "_AUDIO_DIR", tmp_path)
    # The bytes are fetched over the wire in production; the transport itself is
    # covered by _store_audio's own test below.
    monkeypatch.setattr(chat_voice, "_store_audio",
                        lambda url, lang="en": tmp_path / "clip.wav" if tmp_path else None)
    return adapter


# ── schema ─────────────────────────────────────────────────────────────────

def test_speak_input_is_validated():
    with pytest.raises(ValidationError):
        chat_voice.SpeakIn(text="", voice_id="v1")
    assert chat_voice.SpeakIn(text="hi", voice_id="v1").lang == "en"
    # A blank voice is legal: the route resolves one from the engine's real list.
    assert chat_voice.SpeakIn(text="hi").voice_id == ""


# ── behaviour ──────────────────────────────────────────────────────────────

def test_speak_returns_a_same_origin_audio_url(monkeypatch, tmp_path):
    fake = _use(monkeypatch, _FakeAdapter(
        {"ok": True, "elapsed_ms": 420, "data": {"audio_url": "http://127.0.0.1:8321/a.wav"}}),
        tmp_path)
    out = _speak(text="Draft ready.", voice_id="microsoft-zira-desktop")
    assert out["ok"] is True
    assert out["audio_url"] == "/api/chat/voice/audio/clip.wav"
    assert out["elapsed_ms"] == 420
    assert out["voice_fell_back"] is False
    assert fake.calls == [("Draft ready.", "microsoft-zira-desktop", "en")]


def test_an_unknown_voice_is_resolved_instead_of_failing(monkeypatch, tmp_path):
    """The exact production failure: the client held 'bojo-narrator', a voice the
    engine has never had, so every spoken turn died on a 422."""
    fake = _use(monkeypatch, _FakeAdapter(
        {"ok": True, "data": {"audio_url": "http://127.0.0.1:8321/a.wav"}}), tmp_path)
    out = _speak(text="hi", voice_id="bojo-narrator")
    assert out["voice_id"] == "microsoft-zira-desktop"
    assert out["voice_fell_back"] is True
    assert fake.calls[0][1] == "microsoft-zira-desktop"


def test_a_blank_voice_uses_the_first_real_voice(monkeypatch, tmp_path):
    fake = _use(monkeypatch, _FakeAdapter(
        {"ok": True, "data": {"audio_url": "http://127.0.0.1:8321/a.wav"}}), tmp_path)
    out = _speak(text="hi", voice_id="")
    assert out["voice_id"] == "microsoft-zira-desktop"
    assert fake.calls[0][1] == "microsoft-zira-desktop"


def test_an_unreachable_engine_is_a_503_with_the_real_reason(monkeypatch, tmp_path):
    _use(monkeypatch, _FakeAdapter(
        {"ok": False, "error": "VoiceStudio unreachable: connection refused"}), tmp_path)
    with pytest.raises(HTTPException) as exc:
        _speak(text="hi", voice_id="v1")
    assert exc.value.status_code == 503
    assert "unreachable" in str(exc.value.detail).lower()


def test_no_audio_url_is_not_reported_as_success(monkeypatch, tmp_path):
    _use(monkeypatch, _FakeAdapter({"ok": True, "data": {}}), tmp_path)
    with pytest.raises(HTTPException) as exc:
        _speak(text="hi", voice_id="v1")
    assert exc.value.status_code == 502
    assert "no audio_url" in str(exc.value.detail)


def test_audio_that_cannot_be_fetched_is_a_502(monkeypatch):
    monkeypatch.setattr(voicestudio_adapter, "get_adapter", lambda: _FakeAdapter(
        {"ok": True, "data": {"audio_url": "http://127.0.0.1:8321/a.wav"}}))

    def boom(url, lang="en"):
        raise RuntimeError("connection refused")

    monkeypatch.setattr(chat_voice, "_store_audio", boom)
    with pytest.raises(HTTPException) as exc:
        _speak(text="hi", voice_id="v1")
    assert exc.value.status_code == 502
    assert "could not be fetched" in str(exc.value.detail)


# ── the routes ─────────────────────────────────────────────────────────────

def test_the_routes_are_registered():
    paths = [r.path for r in chat_voice.router.routes]
    assert "/api/chat/voice/speak" in paths
    assert "/api/chat/voice/transcribe" in paths
    assert "/api/chat/voice/voices" in paths
    assert "/api/chat/voice/audio/{name}" in paths


def test_audio_is_served_from_the_app(monkeypatch, tmp_path):
    monkeypatch.setattr(chat_voice, "_AUDIO_DIR", tmp_path)
    (tmp_path / "abc.wav").write_bytes(b"RIFF0000WAVE")
    resp = chat_voice.voice_audio("abc.wav", "acct-1")
    assert Path(str(resp.path)) == tmp_path / "abc.wav"


def test_audio_never_traverses_out_of_the_audio_dir(monkeypatch, tmp_path):
    monkeypatch.setattr(chat_voice, "_AUDIO_DIR", tmp_path)
    with pytest.raises(HTTPException) as exc:
        chat_voice.voice_audio("..%2Fsecrets.txt", "acct-1")
    assert exc.value.status_code == 404


# ── the voice picker ───────────────────────────────────────────────────────

class _FakeVoices:
    def __init__(self, result):
        self.result = result

    async def list_voices(self):
        return self.result


def _voices():
    return asyncio.run(chat_voice.voices("acct-1"))


def test_voices_returns_the_engine_list(monkeypatch):
    monkeypatch.setattr(voicestudio_adapter, "get_adapter", lambda: _FakeVoices(
        {"ok": True, "data": {"voices": [{"id": "microsoft-zira-desktop", "name": "Zira"}]}}))
    out = _voices()
    assert out["ok"] is True
    assert out["voices"][0]["id"] == "microsoft-zira-desktop"


def test_an_empty_engine_list_is_an_empty_list_not_an_error(monkeypatch):
    monkeypatch.setattr(voicestudio_adapter, "get_adapter",
                        lambda: _FakeVoices({"ok": True, "data": {}}))
    assert _voices()["voices"] == []


def test_voices_unreachable_is_a_503_with_the_reason(monkeypatch):
    monkeypatch.setattr(voicestudio_adapter, "get_adapter", lambda: _FakeVoices(
        {"ok": False, "error": "VoiceStudio unreachable: connection refused"}))
    with pytest.raises(HTTPException) as exc:
        _voices()
    assert exc.value.status_code == 503
    assert "unreachable" in str(exc.value.detail).lower()
