"""Audio contracts: bed, voice, ducking, loudness and the mux.

These use real Piper and real ffmpeg; the point is the measurement, not a stub.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

import video_audio as va
import video_stitch as vs


def _clip(path: Path, seconds: float = 2.0) -> Path:
    result = subprocess.run([
        vs.FFMPEG, "-y", "-f", "lavfi",
        "-i", f"testsrc2=size=1080x1920:rate=30:duration={seconds}",
        "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
        str(path)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr[-400:]
    return path


def test_the_generated_bed_is_audible(tmp_path):
    wav = tmp_path / "bed.wav"
    wav.write_bytes(va.ambient_bed(2.0))
    vol = va.volume(wav)
    assert vol["max_volume"] > -30.0
    assert vol["mean_volume"] > -45.0


def test_the_local_voice_returns_real_audio():
    spoken = va.voiceover("Lion mane, six ounces.")
    assert spoken["bytes"][:4] == b"RIFF"
    assert spoken["engine"] in ("piper", "sapi")
    assert len(spoken["bytes"]) > 10_000


def test_voice_and_bed_are_normalised_and_the_picture_is_kept(tmp_path):
    source = _clip(tmp_path / "src.mp4")
    out = tmp_path / "out.mp4"
    result = va.add_audio(source, out, script="Lion mane. Six ounces.")
    assert result["ok"] is True, result
    assert result["checks"]["audio_aac"] and result["checks"]["has_audio"]
    assert abs(result["integrated_lufs"] + 16.0) <= 2.0
    assert result["probe"]["width"] == 1080
    assert result["probe"]["duration"] == pytest.approx(2.0, abs=1 / 30 + 1e-3)
    assert result["mix"]["ducked"] is True


def test_a_silent_request_is_refused(tmp_path):
    source = _clip(tmp_path / "src.mp4")
    with pytest.raises(va.AudioError, match="audio_source_missing"):
        va.add_audio(source, tmp_path / "x.mp4")


def test_a_missing_voice_file_is_refused(tmp_path):
    with pytest.raises(va.AudioError, match="voice_missing"):
        va.mix(tmp_path / "nope.wav", None, tmp_path / "x.wav")
