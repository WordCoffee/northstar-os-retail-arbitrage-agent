"""Finish a video master: narration, loudness, captions, and one manifest.

A video that renders is not a master that ships. The V3.2 acceptance in
`docs/V3_MASTER_PLAN.md` asks for an ffprobe contract, OCR-verified captions and
**-16 LUFS** integrated loudness. `shorts.py` produces a silent, picture-gated
clip; this tool does the audio half and measures it rather than assuming it:

  1. speak the script locally (piper via `local_voice`, SAPI fallback);
  2. mux it onto the clip;
  3. normalise to the target with ffmpeg `loudnorm`, then **re-measure** with
     EBU R128 and report the real number;
  4. transcribe the narration with `local_transcribe` (faster-whisper, CPU) and
     write an SRT from the *measured* timings - captions come from the audio
     that exists, not from the script that was typed;
  5. write a manifest with every measurement.

Nothing is invented: a missing speech engine, a missing audio track or an
unavailable transcriber is reported as such and never papered over.

Usage::

    python tools/master_audio.py --video <clip.mp4> --script copy.txt
    python tools/master_audio.py --video <clip.mp4> --script-copy "..." --target-lufs -16
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO = Path(__file__).resolve().parents[1]
BACKEND = REPO / "Northstar_backend"

DEFAULT_TARGET_LUFS = -16.0
DEFAULT_TRUE_PEAK = -1.5


def _run(cmd: List[str], timeout: float = 600.0,
         keep: Optional[int] = 4000) -> Dict[str, Any]:
    """Run a command. ``keep=None`` keeps the whole stdout (JSON parsers need it).

    The 4000-char tail is right for an ffmpeg log and wrong for ffprobe JSON:
    truncating it made a valid probe look unparseable.
    """
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"ok": False, "reason": f"{type(exc).__name__}: {exc}"}
    stdout = proc.stdout or ""
    stderr = proc.stderr or ""
    return {"ok": proc.returncode == 0, "exit_code": proc.returncode,
            "stdout": stdout if keep is None else stdout[-keep:],
            "stderr": stderr[-keep:] if keep else stderr}


def ffmpeg() -> Optional[str]:
    return shutil.which("ffmpeg")


def measure_loudness(path: Path) -> Dict[str, Any]:
    """Integrated loudness + true peak, or an honest reason there is none.

    Audio presence is taken from `probe()`, not from scraping ffmpeg's stderr:
    the ebur128 log is long enough that a truncated tail can lose the stream
    header, which made a file with audio look silent.
    """
    exe = ffmpeg()
    if not exe:
        return {"ok": False, "reason": "ffmpeg_not_installed"}
    stream = probe(path)
    if stream.get("ok") and stream.get("audio") is None:
        return {"ok": True, "audio": False,
                "reason": "no audio stream in the file"}
    out = _run([exe, "-hide_banner", "-nostats", "-i", str(path),
                "-af", "ebur128=peak=true", "-f", "null", "-"])
    text = (out.get("stderr") or "") + (out.get("stdout") or "")
    integrated = re.findall(r"I:\s*(-?[0-9.]+)\s*LUFS", text)
    peak = re.findall(r"Peak:\s*(-?[0-9.]+)\s*dBFS", text)
    if not integrated:
        return {"ok": False, "reason": "no EBU R128 measurement produced",
                "tail": text[-400:]}
    return {"ok": True, "audio": True,
            "integrated_lufs": float(integrated[-1]),
            "true_peak_dbfs": float(peak[-1]) if peak else None}


def probe(path: Path) -> Dict[str, Any]:
    exe = shutil.which("ffprobe")
    if not exe:
        return {"ok": False, "reason": "ffprobe_not_installed"}
    out = _run([exe, "-v", "error", "-show_format", "-show_streams", "-of", "json",
                str(path)], timeout=120, keep=None)
    if not out.get("ok"):
        return {"ok": False, "reason": out.get("stderr") or out.get("reason")}
    try:
        doc = json.loads(out["stdout"])
    except json.JSONDecodeError:
        return {"ok": False, "reason": "ffprobe_output_unparseable"}
    video = next((s for s in doc.get("streams", []) if s.get("codec_type") == "video"), {})
    audio = next((s for s in doc.get("streams", []) if s.get("codec_type") == "audio"), None)
    fps = str(video.get("avg_frame_rate") or "")
    num, _, den = fps.partition("/")
    try:
        fps_val = round(float(num) / float(den or 1), 3) if num else None
    except (ValueError, ZeroDivisionError):
        fps_val = None
    return {
        "ok": True,
        "duration_s": round(float(doc.get("format", {}).get("duration") or 0), 3),
        "bytes": int(doc.get("format", {}).get("size") or 0),
        "container": doc.get("format", {}).get("format_name"),
        "video": {"codec": video.get("codec_name"), "width": video.get("width"),
                  "height": video.get("height"), "fps": fps_val,
                  "frames": video.get("nb_frames")},
        "audio": None if audio is None else {
            "codec": audio.get("codec_name"), "channels": audio.get("channels"),
            "sample_rate": audio.get("sample_rate"),
            "bit_rate": audio.get("bit_rate")},
    }


def _srt_timestamp(seconds: float) -> str:
    total_ms = max(0, int(round(float(seconds) * 1000)))
    hours, rem = divmod(total_ms, 3_600_000)
    minutes, rem = divmod(rem, 60_000)
    secs, ms = divmod(rem, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{ms:03d}"


def align_captions(segments: List[Dict[str, Any]], script: str) -> Dict[str, Any]:
    """Cue text from the approved script, cue timings from the measured speech.

    ASR on a synthetic voice produced "Magra Organics Lions main" and "sir a
    spoonful" - usable timings, unusable copy. When the segment count matches
    the sentence count the script wins and the measured timings are kept;
    otherwise the transcript is left alone and the mismatch is stated, because
    guessing which segment maps to which sentence would be invention.
    """
    spoken = [s for s in segments if str(s.get("text") or "").strip()]
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", str(script or "").strip())
                 if s.strip()]
    if spoken and len(spoken) == len(sentences):
        aligned = [{"start": s.get("start"), "end": s.get("end"), "text": sentence}
                   for s, sentence in zip(spoken, sentences)]
        return {"ok": True, "segments": aligned, "source": "script_aligned",
                "note": "timings measured from the narration; words from the approved script"}
    return {"ok": True, "segments": spoken, "source": "asr_transcript",
            "note": (f"{len(spoken)} spoken segment(s) vs {len(sentences)} script "
                     f"sentence(s); text left as transcribed")}


def segments_to_srt(segments: List[Dict[str, Any]]) -> str:
    """SRT from measured segments, numbered by emitted cue.

    Empty segments are dropped *before* numbering: skipping one used to leave a
    gap in the cue numbers (1, 3), which strict players dislike.
    """
    blocks: List[str] = []
    for seg in segments:
        text = str(seg.get("text") or "").strip()
        if not text:
            continue
        start = float(seg.get("start") or 0.0)
        end = float(seg.get("end") or start + 1.0)
        if end <= start:
            end = start + 1.0
        number = len(blocks) + 1
        blocks.append(f"{number}\n{_srt_timestamp(start)} --> {_srt_timestamp(end)}\n{text}\n")
    return "\n".join(blocks)


def normalise(src: Path, dst: Path, *, target_lufs: float,
              true_peak: float, timeout: float = 900.0) -> Dict[str, Any]:
    """Two-pass loudnorm to the target, then a fresh measurement of the result."""
    exe = ffmpeg()
    if not exe:
        return {"ok": False, "reason": "ffmpeg_not_installed"}
    # Pass 1: measure with loudnorm's own analysis, parse its JSON.
    first = _run([exe, "-hide_banner", "-nostats", "-i", str(src),
                  "-af", f"loudnorm=I={target_lufs}:TP={true_peak}:LRA=11:print_format=json",
                  "-f", "null", "-"], timeout=timeout)
    text = (first.get("stderr") or "") + (first.get("stdout") or "")
    match = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", text, re.S)
    if not first.get("ok") or not match:
        return {"ok": False, "reason": "loudnorm_analysis_failed",
                "tail": text[-400:]}
    try:
        measured = json.loads(match.group(0))
    except json.JSONDecodeError:
        return {"ok": False, "reason": "loudnorm_analysis_unparseable"}
    filt = (f"loudnorm=I={target_lufs}:TP={true_peak}:LRA=11:"
            f"measured_I={measured['input_i']}:measured_TP={measured['input_tp']}:"
            f"measured_LRA={measured['input_lra']}:measured_thresh={measured['input_thresh']}:"
            f"offset={measured.get('target_offset', 0)}:linear=true:print_format=json")
    # Container-aware codec: AAC cannot live in a .wav, and asking for it there
    # produced a header-less file that still exited 0. Pick by extension.
    audio_codec = "pcm_s16le" if dst.suffix.lower() == ".wav" else "aac"
    codec_args = ["-c:a", audio_codec] + ([] if audio_codec == "pcm_s16le"
                                          else ["-b:a", "192k"])
    second = _run([exe, "-y", "-hide_banner", "-nostats", "-i", str(src),
                   "-af", filt, *codec_args, "-c:v", "copy", str(dst)],
                  timeout=timeout)
    if not second.get("ok"):
        return {"ok": False, "reason": "loudnorm_apply_failed",
                "tail": (second.get("stderr") or "")[-400:]}
    return {"ok": True, "analysis": measured, "applied": filt,
            "verified": measure_loudness(dst)}


def mux(video: Path, audio: Path, dst: Path, *, timeout: float = 600.0) -> Dict[str, Any]:
    """Video + narration. Narration shorter than the clip is padded, not truncating.

    A plain `-shortest` would cut a 15 s master down to the length of a 10 s
    voice-over; `apad` pads the audio and `-shortest` then ends at the video.
    """
    exe = ffmpeg()
    if not exe:
        return {"ok": False, "reason": "ffmpeg_not_installed"}
    out = _run([exe, "-y", "-hide_banner", "-nostats", "-i", str(video),
                "-i", str(audio),
                "-filter_complex", "[1:a]apad[a]",
                "-map", "0:v:0", "-map", "[a]",
                "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                "-shortest", "-movflags", "+faststart", str(dst)], timeout=timeout)
    return {"ok": bool(out.get("ok")), "reason": None if out.get("ok")
            else (out.get("stderr") or "")[-400:]}


def narrate(script: str, voice: Optional[str] = None,
            out_dir: Optional[Path] = None) -> Dict[str, Any]:
    """Speak the script locally.

    `local_voice.synthesize()` returns the WAV *bytes* (``{bytes, engine,
    voice}``) and raises when no engine can speak — it has no ``ok`` flag. The
    first version of this wrapper assumed one and reported every successful
    narration as ``speech_engine_failed``; this reads the real contract.
    """
    import local_voice  # type: ignore
    try:
        out = local_voice.synthesize(script, voice=voice)
    except Exception as exc:  # noqa: BLE001 - the reason is the report
        return {"ok": False, "reason": f"{type(exc).__name__}: {exc}", "engine": None}
    audio = (out or {}).get("bytes") or b""
    if not audio:
        return {"ok": False, "reason": (out or {}).get("reason") or "no audio produced",
                "engine": (out or {}).get("engine")}
    if not audio.startswith(b"RIFF"):
        return {"ok": False, "reason": "speech engine returned a non-WAV payload",
                "engine": (out or {}).get("engine")}
    target_dir = Path(out_dir) if out_dir else (BACKEND / "data" / "studio_generated")
    target_dir.mkdir(parents=True, exist_ok=True)
    path = target_dir / f"narration_{int(time.time())}.wav"
    path.write_bytes(audio)
    return {"ok": True, "file": str(path), "engine": (out or {}).get("engine"),
            "voice": (out or {}).get("voice"), "bytes": len(audio)}


def transcribe(audio: Path) -> Dict[str, Any]:
    try:
        import local_transcribe  # type: ignore
        report = local_transcribe.transcribe_file(str(audio))
    except Exception as exc:  # noqa: BLE001 - a missing transcriber is reported
        return {"ok": False, "reason": f"{type(exc).__name__}: {exc}"}
    if not report.get("ok"):
        return {"ok": False, "reason": report.get("reason") or report.get("error")}
    return {"ok": True, "text": report.get("text"),
            "segments": report.get("segments") or [],
            "model": report.get("model"), "seconds": report.get("seconds")}


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Narrate, normalise and caption a video master")
    parser.add_argument("--video", required=True)
    parser.add_argument("--script", default=None, help="file containing the narration copy")
    parser.add_argument("--script-copy", default=None, help="narration copy inline")
    parser.add_argument("--voice", default=None)
    parser.add_argument("--target-lufs", type=float, default=DEFAULT_TARGET_LUFS)
    parser.add_argument("--true-peak", type=float, default=DEFAULT_TRUE_PEAK)
    parser.add_argument("--out-dir", default=None)
    parser.add_argument("--json", default=None, help="evidence JSON path")
    args = parser.parse_args(argv)

    sys.path.insert(0, str(BACKEND))
    video = Path(args.video)
    if not video.is_file():
        raise SystemExit(f"video_not_found: {video}")
    script = (args.script_copy or "").strip()
    if args.script:
        script = Path(args.script).read_text(encoding="utf-8").strip()
    if not script:
        raise SystemExit("no_script: pass --script or --script-copy")

    out_dir = Path(args.out_dir) if args.out_dir else video.parent / f"{video.stem}_master"
    out_dir.mkdir(parents=True, exist_ok=True)

    evidence: Dict[str, Any] = {
        "contract": "master_audio/v1",
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "source_video": str(video),
        "script": script,
        "target_lufs": args.target_lufs,
        "source_probe": probe(video),
    }

    voice = narrate(script, args.voice)
    evidence["narration"] = voice
    if not voice.get("ok"):
        evidence["finished_at"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
        _write(args.json, out_dir, evidence)
        print(json.dumps(evidence, indent=2)[:1200])
        return 2

    spoken = Path(voice["file"])
    evidence["narration_probe"] = probe(spoken)

    narrated = out_dir / f"{video.stem}_narrated.mp4"
    muxed = mux(video, spoken, narrated)
    evidence["mux"] = {"ok": muxed.get("ok"), "file": str(narrated),
                       "reason": muxed.get("reason")}
    if not muxed.get("ok"):
        evidence["finished_at"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
        _write(args.json, out_dir, evidence)
        return 3

    normalised = out_dir / f"{video.stem}_master.mp4"
    norm = normalise(narrated, normalised, target_lufs=args.target_lufs,
                     true_peak=args.true_peak)
    evidence["loudness"] = norm
    final = normalised if norm.get("ok") else narrated

    captioning = transcribe(spoken)
    evidence["transcription"] = {k: captioning.get(k) for k in
                                 ("ok", "reason", "model", "seconds")} | {
        "text": (captioning.get("text") or "")[:600],
        "segments": len(captioning.get("segments") or [])}
    srt_path = out_dir / f"{video.stem}.srt"
    caption_source = None
    if captioning.get("ok") and captioning.get("segments"):
        aligned = align_captions(captioning["segments"], script)
        caption_source = aligned["source"]
        srt_path.write_text(segments_to_srt(aligned["segments"]), encoding="utf-8")
        evidence["captions"] = {"file": str(srt_path),
                                "cues": len([s for s in aligned["segments"]
                                             if str(s.get("text") or "").strip()]),
                                "source": aligned["source"],
                                "note": aligned.get("note")}
    else:
        evidence["captions"] = {"file": None, "reason": captioning.get("reason")
                                or "no segments returned"}

    evidence["final_probe"] = probe(final)
    measured = measure_loudness(final)
    evidence["final_loudness"] = measured
    evidence["verdict"] = {
        "audio_present": bool((evidence["final_probe"].get("audio"))),
        "loudness_within_1db": (abs(measured.get("integrated_lufs", 0) - args.target_lufs) <= 1.0
                                if measured.get("ok") and measured.get("audio") else None),
        "true_peak_ok": (measured.get("true_peak_dbfs") is not None
                         and measured["true_peak_dbfs"] <= args.true_peak + 0.5
                         if measured.get("audio") else None),
        "captions_written": bool(evidence["captions"].get("file")),
        "duration_preserved": (abs(float(evidence["final_probe"].get("duration_s") or 0)
                                  - float(evidence["source_probe"].get("duration_s") or 0)) <= 0.35),
    }
    evidence["verdict"]["all_ok"] = all(v is True for v in evidence["verdict"].values())
    evidence["finished_at"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    _write(args.json, out_dir, evidence)
    print(json.dumps({k: evidence[k] for k in
                      ("verdict", "final_probe", "final_loudness", "captions")}, indent=2))
    print(f"\nfinal: {final}\nsrt:   {srt_path}")
    return 0 if evidence["verdict"]["all_ok"] else 1


def _write(json_path: Optional[str], out_dir: Path, evidence: Dict[str, Any]) -> None:
    dst = Path(json_path) if json_path else out_dir / "master_audio.json"
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(json.dumps(evidence, indent=2), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
