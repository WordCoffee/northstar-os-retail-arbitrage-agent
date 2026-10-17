"""Voice intake tests (S3) — parser, unavailable path, mocked pipeline, live smoke.

The live smoke (skipped when the binaries/model are absent) synthesizes a two
second tone with ffmpeg and runs the REAL whisper.cpp pipeline end-to-end. A
tone contains no speech: the honest expectation is an empty transcript.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import chat_voice  # noqa: E402


def test_parse_whisper_output_filters_noise():
    raw = (
        "system_info: n_threads = 8 / 16 | AVX = 1\n"
        "main: processing 'in.wav' (32000 samples, 2.0 sec), 4 threads\n"
        "whisper_print_timings: load time =  210.11 ms\n"
        "Hello and welcome to the studio.\n"
        "[00:00:00.000 --> 00:00:01.900]  Hello and welcome to the studio.\n"
        "ggml_backend_cpu_init: backend CPU\n"
    )
    assert chat_voice._parse_whisper_output(raw) == "Hello and welcome to the studio."


def test_transcribe_unavailable_raises(monkeypatch, tmp_path):
    src = tmp_path / "x.webm"
    src.write_bytes(b"fake")
    monkeypatch.setattr(chat_voice, "_whisper_cli", lambda: None)
    monkeypatch.setattr(chat_voice, "_model_path", lambda: None)
    with pytest.raises(chat_voice.VoiceUnavailable):
        chat_voice.transcribe_file(src)


def test_transcribe_mocked_pipeline(monkeypatch, tmp_path):
    src = tmp_path / "x.webm"
    src.write_bytes(b"fake-opus")
    monkeypatch.setattr(chat_voice, "_whisper_cli", lambda: "whisper-cli.exe")
    monkeypatch.setattr(chat_voice, "_model_path", lambda: tmp_path / "ggml-base.en.bin")

    calls = {"n": 0}

    def fake_run(cmd, **kw):
        calls["n"] += 1
        if cmd[0] == "ffmpeg":
            Path(cmd[-1]).write_bytes(b"RIFFfake")
            return SimpleNamespace(returncode=0, stdout=b"", stderr=b"")
        return SimpleNamespace(
            returncode=0,
            stdout=b"system_info: noise\nmain: noise\nDraft a pouch concept\n",
            stderr=b"")

    monkeypatch.setattr(chat_voice, "_run", fake_run)
    out = chat_voice.transcribe_file(src)
    assert out["ok"] is True
    assert out["text"] == "Draft a pouch concept"
    assert out["model"] == "ggml-base.en.bin"
    assert isinstance(out["elapsed_ms"], int)
    assert calls["n"] == 2


def _live_available() -> bool:
    return bool(chat_voice._whisper_cli() and chat_voice._model_path())


@pytest.mark.skipif(not _live_available(), reason="whisper.cpp toolchain not installed")
def test_live_smoke_tone_transcribes_empty(tmp_path):
    """REAL pipeline: genesis tone → real whisper-cli. No speech → empty text."""
    tone = tmp_path / "tone.wav"
    conv = subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
         "-ar", "16000", "-ac", "1", str(tone)],
        capture_output=True, timeout=60)
    assert conv.returncode == 0 and tone.is_file()
    out = chat_voice.transcribe_file(tone)
    assert out["ok"] is True
    assert isinstance(out["text"], str)
    # A pure tone has no words. whisper.cpp may hallucinate an annotation
    # ("(eerie music)") — the parser must reduce annotation-only output to an
    # honestly empty transcript, and never leak special tokens.
    assert "<|" not in out["text"]
    assert out["text"].strip() == ""
    assert out["elapsed_ms"] >= 0
