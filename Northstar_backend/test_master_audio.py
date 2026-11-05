"""Tests for the master-audio finisher (`tools/master_audio.py`).

The point of these tests is the honesty of the measurements: an SRT built from
transcript segments must carry the real timings, loudness must be *measured*
rather than assumed, and a file with no audio track must be reported as such
instead of returning a number.

ffmpeg is used for real (it is a hard dependency of the media stack), so the
loudness tests generate their own tone with `lavfi`.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
sys.path.insert(0, os.path.join(_REPO, "tools"))

import master_audio as ma  # noqa: E402

FFMPEG = shutil.which("ffmpeg")
needs_ffmpeg = pytest.mark.skipif(FFMPEG is None, reason="ffmpeg not installed")


# ── SRT (pure) ──────────────────────────────────────────────────────────────

def test_srt_timestamps_use_the_srt_format():
    assert ma._srt_timestamp(0) == "00:00:00,000"
    assert ma._srt_timestamp(1.5) == "00:00:01,500"
    assert ma._srt_timestamp(61.25) == "00:01:01,250"
    assert ma._srt_timestamp(3661.001) == "01:01:01,001"


def test_srt_carries_measured_timings_and_skips_empty_segments():
    srt = ma.segments_to_srt([
        {"start": 0.0, "end": 2.4, "text": "Mogra Organics."},
        {"start": 2.4, "end": 3.0, "text": "   "},
        {"start": 3.0, "end": 5.75, "text": "Lion's Mane mushroom powder."},
    ])
    blocks = [b for b in srt.split("\n\n") if b.strip()]
    assert len(blocks) == 2, "an empty segment must not become a cue"
    assert blocks[0].startswith("1\n00:00:00,000 --> 00:00:02,400")
    assert blocks[1].startswith("2\n00:00:03,000 --> 00:00:05,750")
    assert "Lion's Mane" in blocks[1]


def test_srt_repairs_a_zero_length_segment():
    srt = ma.segments_to_srt([{"start": 4.0, "end": 4.0, "text": "hi"}])
    assert "00:00:04,000 --> 00:00:05,000" in srt


def test_no_segments_produces_an_empty_file_not_a_guess():
    assert ma.segments_to_srt([]) == ""


# ── Caption alignment ───────────────────────────────────────────────────────

def test_captions_use_the_script_when_the_counts_match():
    """ASR mangles a synthetic voice; the timings are good, the words are not."""
    segments = [{"start": 0.0, "end": 4.24, "text": "Magra Organics Lions main powder,"},
                {"start": 4.24, "end": 8.88, "text": "sir a spoonful into coffee."}]
    script = "Mogra Organics Lion's Mane powder. Stir a spoonful into coffee."
    aligned = ma.align_captions(segments, script)
    assert aligned["source"] == "script_aligned"
    assert [s["text"] for s in aligned["segments"]] == [
        "Mogra Organics Lion's Mane powder.", "Stir a spoonful into coffee."]
    assert [s["start"] for s in aligned["segments"]] == [0.0, 4.24]


def test_captions_keep_the_transcript_when_the_counts_disagree():
    segments = [{"start": 0.0, "end": 2.0, "text": "a"}, {"start": 2.0, "end": 3.0, "text": "b"}]
    aligned = ma.align_captions(segments, "one sentence only.")
    assert aligned["source"] == "asr_transcript"
    assert [s["text"] for s in aligned["segments"]] == ["a", "b"]
    assert "2 spoken" in aligned["note"] and "1 script" in aligned["note"]


# ── Loudness (real ffmpeg) ──────────────────────────────────────────────────

def _tone(path, *, seconds=3.0, freq=440, volume=0.12):
    result = subprocess.run([
        FFMPEG, "-y", "-v", "error", "-f", "lavfi",
        "-i", f"sine=frequency={freq}:duration={seconds}",
        "-af", f"volume={volume}", str(path)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr[-400:]
    return path


def _silent_video(path, *, seconds=2.0):
    result = subprocess.run([
        FFMPEG, "-y", "-v", "error", "-f", "lavfi",
        "-i", f"color=c=black:s=320x240:d={seconds}",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", str(path)],
        capture_output=True, text=True)
    assert result.returncode == 0, result.stderr[-400:]
    return path


@needs_ffmpeg
def test_loudness_is_measured_on_real_audio(tmp_path):
    tone = _tone(tmp_path / "tone.wav")
    report = ma.measure_loudness(tone)
    assert report["ok"] and report["audio"] is True
    assert isinstance(report["integrated_lufs"], float)
    assert report["integrated_lufs"] < 0


@needs_ffmpeg
def test_a_silent_video_reports_no_audio_rather_than_a_number(tmp_path):
    clip = _silent_video(tmp_path / "silent.mp4")
    report = ma.measure_loudness(clip)
    assert report["ok"] is True
    assert report["audio"] is False
    assert "no audio stream" in report["reason"]
    assert "integrated_lufs" not in report


@needs_ffmpeg
def test_normalise_hits_the_target_and_is_re_measured(tmp_path):
    tone = _tone(tmp_path / "quiet.wav")
    out = tmp_path / "loud.wav"
    result = ma.normalise(tone, out, target_lufs=-16.0, true_peak=-1.5)
    assert result["ok"], result
    verified = result["verified"]
    assert verified["ok"] and verified["audio"] is True
    # loudnorm is allowed 1 dB of slop on a 3 s tone; the point is that it moved
    # to the target and that the number comes from a fresh measurement.
    assert abs(verified["integrated_lufs"] - (-16.0)) <= 1.0, verified


@needs_ffmpeg
def test_narrate_reports_a_missing_engine_instead_of_silence(tmp_path, monkeypatch):
    import local_voice

    def _boom(*a, **k):
        raise RuntimeError("no_speech_engine")

    monkeypatch.setattr(local_voice, "synthesize", _boom)
    report = ma.narrate("hello", out_dir=tmp_path)
    assert report["ok"] is False
    assert "no_speech_engine" in report["reason"]


def test_narrate_writes_the_wav_bytes_the_engine_returns(tmp_path, monkeypatch):
    """local_voice returns bytes, not a path - the wrapper must not assume a file."""
    import local_voice

    payload = b"RIFF" + b"0" * 200
    monkeypatch.setattr(local_voice, "synthesize",
                        lambda *a, **k: {"bytes": payload, "engine": "piper",
                                         "voice": "piper"})
    report = ma.narrate("hello", out_dir=tmp_path)
    assert report["ok"] is True, report
    assert report["engine"] == "piper"
    assert report["bytes"] == len(payload)
    from pathlib import Path
    written = Path(report["file"])
    assert written.is_file() and written.read_bytes() == payload


def test_narrate_refuses_a_non_wav_payload(tmp_path, monkeypatch):
    import local_voice
    monkeypatch.setattr(local_voice, "synthesize",
                        lambda *a, **k: {"bytes": b"not-a-wav", "engine": "sapi"})
    report = ma.narrate("hello", out_dir=tmp_path)
    assert report["ok"] is False
    assert "non-WAV" in report["reason"]


# ── Probe ───────────────────────────────────────────────────────────────────

@needs_ffmpeg
def test_probe_reports_streams_and_no_audio_for_a_silent_clip(tmp_path):
    clip = _silent_video(tmp_path / "silent.mp4")
    report = ma.probe(clip)
    assert report["ok"] is True
    assert report["audio"] is None
    assert report["video"]["width"] == 320
    assert report["video"]["height"] == 240
    assert report["duration_s"] == pytest.approx(2.0, abs=0.35)


def test_evidence_is_json_serialisable(tmp_path):
    evidence = {"contract": "master_audio/v1",
                "verdict": {"audio_present": True},
                "final_loudness": {"ok": True, "audio": True,
                                   "integrated_lufs": -16.0}}
    (tmp_path / "e.json").write_text(json.dumps(evidence), encoding="utf-8")
    assert json.loads((tmp_path / "e.json").read_text(encoding="utf-8"))["contract"] == \
        "master_audio/v1"
