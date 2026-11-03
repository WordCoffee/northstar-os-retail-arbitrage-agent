"""Audio for a video: voiceover, a local music bed, ducking, loudness.

The video lanes were silent. A product clip with no voice and no bed is a
slideshow, and a voice buried under music is worse than either. This module:

  * speaks the script locally with Piper (or SAPI) through `local_voice`,
  * supplies a deterministic, royalty-free ambient bed generated here (a real
    licensed track can be passed with `music=`), so nothing is downloaded,
  * ducks the bed under the voice with ffmpeg's sidechain compressor,
  * normalises to the platform's loudness target with a two-pass `loudnorm`,
  * muxes the track onto the video without re-encoding the picture,
  * measures the result: audio stream present, not silent, loudness within
    tolerance, duration matching the picture.

"Not silent" and "normalised" are measurements (volumedetect, loudnorm), not
claims. Local only; no network, no provider call, no cost.
"""
from __future__ import annotations

import json
import math
import re
import struct
import subprocess
import tempfile
import wave
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Union

import video_stitch

TARGET_LUFS = -16.0
TARGET_TP = -1.5
TARGET_LRA = 11.0
#: A track quieter than this at its peak is treated as silence, not a mix.
MIN_PEAK_DB = -30.0
LOUDNESS_TOLERANCE_LU = 2.0


class AudioError(RuntimeError):
    """A measured audio refusal, carrying the value that failed."""


# ── procedural bed ──────────────────────────────────────────────────────────

def ambient_bed(seconds: float, *, sample_rate: int = 44100,
                root_hz: float = 110.0, gain: float = 0.18) -> bytes:
    """A soft, deterministic pad: root + fifth + octave + a slow tremolo.

    This is a bed, not a song. It exists so a video can have a music layer with
    no licence question and no download; `mix()` accepts a real track instead.
    """
    import numpy as np

    n = max(1, int(round(float(seconds) * sample_rate)))
    t = np.arange(n, dtype=np.float64) / float(sample_rate)
    partials = [(1.0, 0.50), (1.5, 0.28), (2.0, 0.16), (3.0, 0.06)]
    left = np.zeros(n, dtype=np.float64)
    right = np.zeros(n, dtype=np.float64)
    for mult, amp in partials:
        freq = root_hz * mult
        left += amp * np.sin(2 * math.pi * freq * t)
        # a few cents of detune on the right channel makes it stereo, not mono
        right += amp * np.sin(2 * math.pi * (freq * 1.002) * t + 0.4)
    trem = 1.0 + 0.06 * np.sin(2 * math.pi * 0.17 * t)
    fade = np.minimum(1.0, np.minimum(t / 0.8, (seconds - t) / 1.2)).clip(0.0, 1.0)
    env = trem * fade
    left *= env
    right *= env
    peak = max(float(np.max(np.abs(left))), float(np.max(np.abs(right))), 1e-9)
    scale = (gain / peak) * 32767.0
    stereo = np.stack([left * scale, right * scale], axis=1).astype("<i2")
    import io
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(stereo.tobytes())
    return buf.getvalue()


# ── measurement ─────────────────────────────────────────────────────────────

def _run(argv: Sequence[str], *, timeout: float = 900.0) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(list(argv), capture_output=True, text=True,
                              timeout=timeout, check=False)
    except FileNotFoundError as exc:
        raise AudioError(f"video_tool_missing: ffmpeg ({exc})") from exc


def loudness(path: Union[str, Path]) -> Dict[str, float]:
    """Integrated loudness / true peak of a file, from loudnorm's analysis."""
    result = _run([video_stitch.FFMPEG, "-hide_banner", "-nostats",
                   "-i", str(path), "-af",
                   f"loudnorm=I={TARGET_LUFS}:TP={TARGET_TP}:LRA={TARGET_LRA}:print_format=json",
                   "-f", "null", "-"])
    text = result.stderr or ""
    start = text.rfind("{")
    end = text.rfind("}")
    if result.returncode != 0 or start < 0 or end <= start:
        raise AudioError("loudness_measure_failed: " + text.strip()[-300:])
    try:
        data = json.loads(text[start:end + 1])
    except json.JSONDecodeError as exc:
        raise AudioError(f"loudness_measure_failed: {exc}") from exc
    return {k: float(v) for k, v in data.items()
            if isinstance(v, str) and re.fullmatch(r"-?\d+(\.\d+)?", v)}


def volume(path: Union[str, Path]) -> Dict[str, float]:
    """mean/max volume in dBFS via volumedetect."""
    result = _run([video_stitch.FFMPEG, "-hide_banner", "-nostats",
                   "-i", str(path), "-af", "volumedetect", "-f", "null", "-"])
    text = (result.stderr or "")
    out: Dict[str, float] = {}
    for key in ("mean_volume", "max_volume"):
        m = re.search(rf"{key}:\s*(-?\d+(?:\.\d+)?) dB", text)
        if m:
            out[key] = float(m.group(1))
    if "max_volume" not in out:
        raise AudioError("volume_measure_failed: " + text.strip()[-300:])
    return out


# ── mix ─────────────────────────────────────────────────────────────────────

def mix(voice_wav: Union[str, Path], music_wav: Optional[Union[str, Path]],
        out_wav: Union[str, Path], *, music_gain: float = 0.32,
        duck_threshold: float = 0.03, duck_ratio: float = 6.0,
        sample_rate: int = 44100) -> Dict[str, Any]:
    """Mix voice over a ducked bed, then two-pass loudness-normalise."""
    voice = Path(voice_wav)
    if not voice.is_file():
        raise AudioError(f"voice_missing: {voice}")
    out = Path(out_wav)
    out.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="ns-mix-") as tmp:
        tmp_dir = Path(tmp)
        raw = tmp_dir / "mixed.wav"
        if music_wav:
            music = Path(music_wav)
            if not music.is_file():
                raise AudioError(f"music_missing: {music}")
            graph = (
                f"[1:a]volume={float(music_gain):.3f},"
                f"aformat=sample_rates={sample_rate}:channel_layouts=stereo[bed];"
                f"[bed][0:a]sidechaincompress=threshold={float(duck_threshold):.3f}:"
                f"ratio={float(duck_ratio):.1f}:attack=5:release=280:makeup=1[ducked];"
                f"[0:a]aformat=sample_rates={sample_rate}:channel_layouts=stereo[voice];"
                f"[voice][ducked]amix=inputs=2:duration=longest:dropout_transition=0:"
                f"normalize=0[mix]"
            )
            argv = [video_stitch.FFMPEG, "-y", "-i", str(voice), "-i", str(music),
                    "-filter_complex", graph, "-map", "[mix]", "-ac", "2",
                    "-ar", str(sample_rate), str(raw)]
        else:
            argv = [video_stitch.FFMPEG, "-y", "-i", str(voice), "-ac", "2",
                    "-ar", str(sample_rate), str(raw)]
        result = _run(argv)
        if result.returncode != 0:
            raise AudioError("audio_mix_failed: "
                             + (result.stderr.strip().splitlines() or [""])[-1][:400])

        measured = loudness(raw)
        # Two-pass: feed the measured values back so the gain is linear, not a
        # dynamic guess. A single pass overshoots on short clips.
        graph = (
            f"loudnorm=I={TARGET_LUFS}:TP={TARGET_TP}:LRA={TARGET_LRA}"
            f":measured_I={measured.get('input_i', TARGET_LUFS)}"
            f":measured_TP={measured.get('input_tp', TARGET_TP)}"
            f":measured_LRA={measured.get('input_lra', TARGET_LRA)}"
            f":measured_thresh={measured.get('input_thresh', -30.0)}"
            f":offset={measured.get('target_offset', 0.0)}:linear=true"
        )
        result = _run([video_stitch.FFMPEG, "-y", "-i", str(raw), "-af", graph,
                       "-ac", "2", "-ar", str(sample_rate), str(out)])
        if result.returncode != 0:
            raise AudioError("loudness_normalise_failed: "
                             + (result.stderr.strip().splitlines() or [""])[-1][:400])

    final = loudness(out)
    vol = volume(out)
    return {
        "ok": True, "file": str(out), "music": bool(music_wav),
        "ducked": bool(music_wav), "measured_input": measured,
        "measured_final": final, "volume": vol,
        "target_lufs": TARGET_LUFS,
    }


# ── mux + verify ────────────────────────────────────────────────────────────

def mux(video: Union[str, Path], audio: Union[str, Path],
        out_path: Union[str, Path]) -> Dict[str, Any]:
    """Put the track on the picture without re-encoding the picture."""
    video_path, audio_path = Path(video), Path(audio)
    if not video_path.is_file():
        raise AudioError(f"video_missing: {video_path}")
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    result = _run([video_stitch.FFMPEG, "-y", "-i", str(video_path),
                   "-i", str(audio_path), "-map", "0:v:0", "-map", "1:a:0",
                   "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                   "-shortest", "-movflags", "+faststart", str(out)])
    if result.returncode != 0:
        raise AudioError("audio_mux_failed: "
                         + (result.stderr.strip().splitlines() or [""])[-1][:400])
    return verify(out)


def verify(path: Union[str, Path], *, target_lufs: float = TARGET_LUFS,
           tolerance_lu: float = LOUDNESS_TOLERANCE_LU) -> Dict[str, Any]:
    """Probe the muxed file and check the audio the same way video is checked."""
    p = video_stitch.probe(path)
    checks: Dict[str, bool] = {
        "has_audio": bool(p.get("has_audio")),
        "audio_aac": p.get("audio_codec") == "aac",
        "picture_kept": bool(p.get("width") and p.get("height")),
    }
    loud: Dict[str, float] = {}
    vol: Dict[str, float] = {}
    if checks["has_audio"]:
        loud = loudness(path)
        vol = volume(path)
        checks["not_silent"] = float(vol.get("max_volume", -99.0)) > MIN_PEAK_DB
        integrated = float(loud.get("input_i", -99.0))
        checks["loudness_within_tolerance"] = abs(integrated - target_lufs) <= tolerance_lu
    else:
        integrated = None
    failed = [k for k, ok in checks.items() if not ok]
    return {
        "ok": not failed,
        "file": str(path),
        "probe": p,
        "checks": checks,
        "loudness": loud,
        "volume": vol,
        "integrated_lufs": integrated,
        "target_lufs": target_lufs,
        "reason": "" if not failed else "audio_contract_failed: " + ", ".join(failed),
    }


def voiceover(text: str, *, voice: Optional[str] = None,
              out_wav: Optional[Union[str, Path]] = None) -> Dict[str, Any]:
    """Speak the script locally and return the WAV bytes (and path if asked)."""
    import local_voice

    spoken = local_voice.synthesize(str(text), voice=voice)
    payload = spoken.get("bytes") or b""
    if not payload:
        raise AudioError("voiceover_empty: the local TTS returned no audio")
    if out_wav:
        path = Path(out_wav)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
    return {"bytes": payload, "engine": spoken.get("engine"),
            "voice": spoken.get("voice"), "format": spoken.get("format"),
            "path": str(out_wav) if out_wav else None}


def add_audio(video: Union[str, Path], out_path: Union[str, Path], *,
              script: Optional[str] = None,
              voice: Optional[str] = None,
              music: Optional[Union[str, Path]] = None,
              bed_seconds: Optional[float] = None,
              music_gain: float = 0.32) -> Dict[str, Any]:
    """Voice + optional bed + ducking + loudness + mux + verification.

    A music bed is generated when `music` is not supplied; pass a licensed file
    to use it. At least one of `script`/`music` is required - a silent result is
    refused rather than returned.
    """
    if not script and not music:
        raise AudioError("audio_source_missing: give a script, a music file, or both")
    video_path = Path(video)
    if not video_path.is_file():
        raise AudioError(f"video_missing: {video_path}")
    with tempfile.TemporaryDirectory(prefix="ns-audio-") as tmp:
        tmp_dir = Path(tmp)
        voice_wav = None
        if script:
            voice_wav = tmp_dir / "voice.wav"
            voiceover(script, voice=voice, out_wav=voice_wav)
        if music:
            music_wav = Path(music)
        else:
            seconds = float(bed_seconds or video_stitch.probe(video_path).get("duration") or 15.0)
            music_wav = tmp_dir / "bed.wav"
            music_wav.write_bytes(ambient_bed(seconds))
        mixed = tmp_dir / "mix.wav"
        mix_result = mix(voice_wav or music_wav, music_wav if voice_wav else None,
                         mixed, music_gain=music_gain)
        verified = mux(video_path, mixed, out_path)
    verified["mix"] = mix_result
    verified["script"] = script
    verified["voice"] = voice
    verified["music_source"] = str(music) if music else "procedural-ambient-bed"
    if not verified.get("ok"):
        Path(out_path).unlink(missing_ok=True)
    return verified


__all__ = ["voiceover", "ambient_bed", "mix", "mux", "verify", "add_audio",
           "loudness", "volume", "AudioError", "TARGET_LUFS"]
