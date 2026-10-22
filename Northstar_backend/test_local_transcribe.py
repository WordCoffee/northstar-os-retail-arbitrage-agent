"""Local transcription lane tests — offline, no model download, no GPU.

The lane exists so a reference clip can be torn down on this machine. These
tests pin the two things that matter: it runs on the CPU (no VRAM) and it never
invents a transcript.
"""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import local_transcribe as lt  # noqa: E402


class _Seg:
    def __init__(self, start, end, text):
        self.start, self.end, self.text = start, end, text


class _Info:
    language = "en"
    duration = 4.2


class _FakeEngine:
    def __init__(self, segments):
        self._segments = segments

    def transcribe(self, path, **kwargs):
        return iter(self._segments), _Info()


def test_engines_reports_what_is_installed():
    info = lt.engines()
    assert info["device"] == "cpu", "the lane must default to the CPU"
    assert info["compute_type"] == "int8"
    assert info["faster_whisper"], "faster-whisper should be importable"
    assert info["available"] is True


def test_transcribe_rejects_empty_audio():
    with pytest.raises(ValueError):
        lt.transcribe(b"")


def test_transcribe_maps_segments_and_reports_no_vram(monkeypatch):
    monkeypatch.setattr(lt, "_load",
                        lambda *a, **k: _FakeEngine([_Seg(0.0, 1.5, " hello "),
                                                     _Seg(1.5, 3.0, "world")]))
    out = lt.transcribe(b"RIFF....")
    assert out["ok"] is True
    assert out["text"] == "hello world"
    assert out["segments"][0] == {"start": 0.0, "end": 1.5, "text": "hello"}
    assert out["vram_used"] is False
    assert out["device"] == "cpu"


def test_transcribe_flags_truncation_instead_of_hiding_it(monkeypatch):
    segments = [_Seg(float(i), float(i + 1), f"w{i}") for i in range(50)]
    monkeypatch.setattr(lt, "_load", lambda *a, **k: _FakeEngine(segments))
    monkeypatch.setattr(lt.time, "time", iter([0, 0, 0, 100, 100, 100, 100, 100]).__next__)
    out = lt.transcribe(b"RIFF....", timeout_s=1)
    assert out["truncated"] is True
    assert len(out["segments"]) < len(segments)


def test_transcribe_surfaces_a_missing_engine(monkeypatch):
    def boom(*a, **k):
        raise ImportError("No module named 'faster_whisper'")

    monkeypatch.setattr(lt, "_load", boom)
    with pytest.raises(ImportError):
        lt.transcribe(b"RIFF....")
