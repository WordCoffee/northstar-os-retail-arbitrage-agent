"""Local narration lane tests — offline, deterministic, no speech engine needed.

The lane exists so the creative pipeline can produce narrated video with no
provider key. These tests pin the honesty contract: when nothing can speak, the
lane raises (or reports an error on the clip) rather than returning silence.
"""

from __future__ import annotations

import os
import re
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import local_voice as lv  # noqa: E402

FAKE_VOICES = "Microsoft David Desktop|en-US|Male\nMicrosoft Zira Desktop|en-US|Female\n"


def _runner_that_writes(payload: bytes = b"RIFF" + b"\x00" * 4000):
    """A stand-in for PowerShell that actually produces the WAV the code expects."""
    def run(script: str, timeout: int = 120) -> str:
        if "GetInstalledVoices" in script:
            return FAKE_VOICES
        match = re.search(r"SetOutputToWaveFile\('([^']+)'\)", script)
        if match:
            with open(match.group(1), "wb") as fh:
                fh.write(payload)
        return ""
    return run


def _runner_that_fails(msg: str = "no speech subsystem"):
    def run(script: str, timeout: int = 120) -> str:
        raise RuntimeError(msg)
    return run


# --- engine discovery -------------------------------------------------------

def test_engines_reports_sapi_when_voices_exist(monkeypatch):
    monkeypatch.delenv("PIPER_EXE", raising=False)
    monkeypatch.delenv("PIPER_MODEL", raising=False)
    info = lv.engines(_runner_that_writes())
    assert info["sapi"]["available"] is True
    assert info["sapi"]["voices"] == 2
    assert info["preferred"] == "sapi"


def test_engines_reports_the_real_reason_when_speech_is_broken(monkeypatch):
    monkeypatch.delenv("PIPER_EXE", raising=False)
    monkeypatch.delenv("PIPER_MODEL", raising=False)
    info = lv.engines(_runner_that_fails("SAPI missing"))
    assert info["sapi"]["available"] is False
    assert "SAPI missing" in (info["sapi"]["error"] or "")
    assert info["preferred"] is None


# --- synthesis --------------------------------------------------------------

def test_synthesize_returns_audio_and_names_the_engine(monkeypatch, tmp_path):
    monkeypatch.delenv("PIPER_EXE", raising=False)
    monkeypatch.delenv("PIPER_MODEL", raising=False)
    out = lv.synthesize("Northstar narration test.", runner=_runner_that_writes(),
                        out_dir=str(tmp_path))
    assert out["engine"] == "sapi"
    assert out["bytes"].startswith(b"RIFF")
    assert out["voice"].startswith("microsoft-david")


def test_synthesize_rejects_empty_text():
    with pytest.raises(ValueError):
        lv.synthesize("   ", runner=_runner_that_writes())


def test_synthesize_rejects_overlong_text():
    with pytest.raises(ValueError):
        lv.synthesize("x" * (lv.MAX_TEXT + 1), runner=_runner_that_writes())


def test_synthesize_refuses_when_no_engine_can_speak(monkeypatch, tmp_path):
    monkeypatch.delenv("PIPER_EXE", raising=False)
    monkeypatch.delenv("PIPER_MODEL", raising=False)
    with pytest.raises(RuntimeError) as exc:
        lv.synthesize("hello", runner=_runner_that_fails(), out_dir=str(tmp_path))
    assert "no local speech engine" in str(exc.value)


def test_synthesize_rejects_an_unknown_voice(monkeypatch, tmp_path):
    monkeypatch.delenv("PIPER_EXE", raising=False)
    monkeypatch.delenv("PIPER_MODEL", raising=False)
    with pytest.raises(ValueError):
        lv.synthesize("hello", voice="not-a-voice", runner=_runner_that_writes(),
                      out_dir=str(tmp_path))


def test_synthesize_reports_when_the_engine_produces_nothing(monkeypatch, tmp_path):
    monkeypatch.delenv("PIPER_EXE", raising=False)
    monkeypatch.delenv("PIPER_MODEL", raising=False)
    with pytest.raises(RuntimeError) as exc:
        lv.synthesize("hello", runner=_runner_that_writes(b""), out_dir=str(tmp_path))
    assert "produced no audio" in str(exc.value)


# --- muxing -----------------------------------------------------------------

def test_mux_audio_requires_ffmpeg(monkeypatch):
    monkeypatch.setattr(lv.shutil, "which", lambda name: None)
    monkeypatch.delenv("FFMPEG", raising=False)
    with pytest.raises(RuntimeError) as exc:
        lv.mux_audio(b"vid", b"wav")
    assert "ffmpeg not found" in str(exc.value)


# --- video lane integration -------------------------------------------------

def _video_stubs(monkeypatch, calls):
    import studio_generation as sg

    monkeypatch.setattr(sg, "media_live_armed", lambda: True)
    monkeypatch.setattr(sg, "unload_brain", lambda wait_s=45.0: True)
    monkeypatch.setattr(sg, "release_models", lambda: None)
    monkeypatch.setattr(sg, "_run_graph_guarded",
                        lambda graph, timeout_s, **kw: [{"filename": "clip.mp4"}])
    monkeypatch.setattr(sg, "_fetch_output", lambda item: b"SILENT-MP4")

    class FakeVoice:
        @staticmethod
        def synthesize(text, voice=None):
            calls.append(("synthesize", text))
            return {"bytes": b"RIFF-WAV", "engine": "sapi", "voice": "david"}

        @staticmethod
        def mux_audio(video, audio):
            calls.append(("mux", len(video), len(audio)))
            return b"NARRATED-MP4"

    monkeypatch.setitem(sys.modules, "local_voice", FakeVoice)
    return sg


def test_video_without_narration_stays_silent_and_says_so(monkeypatch):
    calls = []
    sg = _video_stubs(monkeypatch, calls)
    out = sg.generate_video("a pouch on a bone backdrop", seed=1)
    assert out["bytes"] == b"SILENT-MP4"
    assert out["audio"] is None
    assert calls == [], "no speech engine should be touched without a narration"


def test_video_with_narration_is_muxed(monkeypatch):
    calls = []
    sg = _video_stubs(monkeypatch, calls)
    out = sg.generate_video("a pouch on a bone backdrop", seed=1,
                            narration="Organic Lions Mane powder.")
    assert out["bytes"] == b"NARRATED-MP4"
    assert out["audio"]["ok"] is True and out["audio"]["engine"] == "sapi"
    assert ("synthesize", "Organic Lions Mane powder.") in calls
    assert any(c[0] == "mux" for c in calls)


def test_video_survives_a_dead_speech_engine(monkeypatch):
    calls = []
    sg = _video_stubs(monkeypatch, calls)

    class DeadVoice:
        @staticmethod
        def synthesize(text, voice=None):
            raise RuntimeError("no local speech engine available")

        @staticmethod
        def mux_audio(video, audio):  # pragma: no cover - never reached
            raise AssertionError("must not mux without audio")

    monkeypatch.setitem(sys.modules, "local_voice", DeadVoice)
    out = sg.generate_video("clip", seed=2, narration="hello")
    assert out["bytes"] == b"SILENT-MP4", "the render must still be delivered"
    assert out["audio"]["ok"] is False
    assert "no local speech engine" in out["audio"]["error"]
