"""Stitch per-clip renders into one placement-compliant video.

The Wan sampler can produce about 2.5 seconds per call on this box, so a 15 s
TikTok is six clips, not one impossible call. `video_formats.plan()` already
says how many; this module turns those clips into the deliverable the placement
contract describes:

    clips -> normalise to the preset canvas/fps/codec -> concat -> trim to the
    requested frame count -> H.264 MP4 -> ffprobe the result and CHECK it

The check is the point. A file that "encoded" is not a file that ships: the
duration can drift by a frame, the canvas can be the wrong shape, the codec can
be VP9 in a WEBM, and the size can exceed the platform cap. Every one of those
is measured with ffprobe and recorded; a failure is a refusal with the measured
value, never a silent pass.

Local only: ffmpeg/ffprobe on PATH (or FFMPEG_BIN/FFPROBE_BIN). No network, no
provider call, no cost.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple, Union

import video_formats


def _tool(env_name: str, default: str) -> str:
    return (os.environ.get(env_name) or shutil.which(default) or default)


FFMPEG = _tool("FFMPEG_BIN", "ffmpeg")
FFPROBE = _tool("FFPROBE_BIN", "ffprobe")


class StitchError(RuntimeError):
    """A measured refusal, always carrying the value that failed."""


def _run(argv: Sequence[str], *, timeout: float = 1200.0) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(list(argv), capture_output=True, text=True,
                              timeout=timeout, check=False)
    except FileNotFoundError as exc:
        raise StitchError(f"video_tool_missing: {argv[0]} ({exc})") from exc


def tools_available() -> Dict[str, Any]:
    return {"ffmpeg": bool(shutil.which(FFMPEG) or Path(FFMPEG).is_file()),
            "ffprobe": bool(shutil.which(FFPROBE) or Path(FFPROBE).is_file())}


def probe(path: Union[str, Path]) -> Dict[str, Any]:
    """ffprobe the file and return the facts the contract checks."""
    result = _run([FFPROBE, "-v", "error", "-print_format", "json",
                   "-show_streams", "-show_format", str(path)], timeout=120)
    if result.returncode != 0:
        raise StitchError(f"ffprobe_failed: {result.stderr.strip()[:300]}")
    data = json.loads(result.stdout or "{}")
    video = next((s for s in data.get("streams") or []
                  if s.get("codec_type") == "video"), None)
    if video is None:
        raise StitchError("video_stream_missing: the file has no video stream")
    audio = next((s for s in data.get("streams") or []
                  if s.get("codec_type") == "audio"), None)
    fmt = data.get("format") or {}

    def _fraction(value: str) -> float:
        try:
            num, den = str(value).split("/")
            return float(num) / float(den or 1)
        except Exception:  # noqa: BLE001 - an unreadable rate is reported as 0
            return 0.0

    duration = float(fmt.get("duration") or video.get("duration") or 0.0)
    fps = _fraction(video.get("avg_frame_rate") or video.get("r_frame_rate") or "0/1")
    declared = int(video.get("nb_frames") or 0)
    nb_frames = declared or int(round(duration * fps))
    return {
        "path": str(path),
        "bytes": int(fmt.get("size") or Path(path).stat().st_size),
        "duration": round(duration, 4),
        "width": int(video.get("width") or 0),
        "height": int(video.get("height") or 0),
        "fps": round(fps, 4),
        "nb_frames": nb_frames,
        "nb_frames_source": "container" if declared else "derived",
        "codec": video.get("codec_name"),
        "pix_fmt": video.get("pix_fmt"),
        "container": fmt.get("format_name"),
        "has_audio": audio is not None,
        "audio_codec": audio.get("codec_name") if audio else None,
    }


def _normalise(clip: Path, out: Path, plan: Dict[str, Any]) -> None:
    w, h, fps = plan["width"], plan["height"], plan["fps"]
    vf = (f"fps={fps},"
          f"scale={w}:{h}:force_original_aspect_ratio=decrease:flags=lanczos,"
          f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1,format=yuv420p")
    result = _run([FFMPEG, "-y", "-i", str(clip), "-vf", vf,
                   "-c:v", "libx264", "-preset", "veryfast", "-crf", "16",
                   "-an", "-r", str(fps), str(out)])
    if result.returncode != 0:
        raise StitchError(f"clip_normalise_failed: {clip.name}: "
                          f"{result.stderr.strip().splitlines()[-1][:300]}")


def _concat_line(path: Path) -> str:
    # concat demuxer quoting: a literal ' is written as '\''
    return "file '" + str(path).replace("'", "'\\''") + "'"


def _encode(concat_file: Path, out_path: Path, plan: Dict[str, Any], *,
            frames: int, audio: Optional[Path], video_args: List[str],
            timeout: float) -> subprocess.CompletedProcess:
    argv = [FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", str(concat_file)]
    if audio is not None:
        argv += ["-i", str(audio)]
    argv += ["-frames:v", str(int(frames)), "-r", str(plan["fps"]),
             "-c:v", "libx264", "-preset", "medium", "-pix_fmt", "yuv420p",
             *video_args, "-movflags", "+faststart"]
    if audio is not None:
        argv += ["-c:a", "aac", "-b:a", "128k", "-shortest"]
    else:
        argv += ["-an"]
    argv.append(str(out_path))
    return _run(argv, timeout=timeout)


def stitch_clips(clips: Sequence[Union[str, Path]], out_path: Union[str, Path], *,
                 platform: str, seconds: Optional[float] = None,
                 audio: Optional[Union[str, Path]] = None,
                 crf: int = 20, timeout: float = 1800.0) -> Dict[str, Any]:
    """Normalise, concatenate and trim clips to the platform contract.

    Returns a manifest with the per-clip normalisation, the final ffprobe and a
    list of checks. Raises `StitchError` when a measured fact fails (wrong
    canvas/codec/duration, missing audio, size over cap after a retry).
    """
    plan = video_formats.plan(platform, seconds)
    target_frames = int(plan.get("target_frames")
                        or round(plan["seconds"] * plan["fps"]))
    if not clips:
        raise StitchError("no_clips: stitching needs at least one rendered clip")
    if not tools_available()["ffmpeg"] or not tools_available()["ffprobe"]:
        raise StitchError("video_tool_missing: ffmpeg and ffprobe are required")

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    audio_path = Path(audio) if audio else None
    if audio_path is not None and not audio_path.is_file():
        raise StitchError(f"audio_missing: {audio_path}")

    with tempfile.TemporaryDirectory(prefix="ns-stitch-") as tmp:
        tmp_dir = Path(tmp)
        normalised: List[Path] = []
        clip_records: List[Dict[str, Any]] = []
        for i, clip in enumerate(clips):
            src = Path(clip)
            if not src.is_file():
                raise StitchError(f"clip_missing: {src}")
            dst = tmp_dir / f"clip_{i:03d}.mp4"
            _normalise(src, dst, plan)
            rec = probe(dst)
            clip_records.append({"source": src.name, "normalised": rec})
            normalised.append(dst)
        concat_file = tmp_dir / "concat.txt"
        concat_file.write_text("\n".join(_concat_line(p) for p in normalised) + "\n",
                               encoding="utf-8")

        budget_bps = int(plan["max_bytes"] * 8 * 0.92 / max(0.1, plan["seconds"]))
        video_args = ["-crf", str(int(crf)), "-maxrate", "16M", "-bufsize", "32M"]
        result = _encode(concat_file, out_path, plan, frames=target_frames,
                         audio=audio_path, video_args=video_args, timeout=timeout)
        if result.returncode != 0:
            raise StitchError(
                "video_encode_failed: " + (result.stderr.strip().splitlines() or [""])[-1][:400])

        final = probe(out_path)
        retried = False
        if final["bytes"] > plan["max_bytes"]:
            # One bounded retry at the cap's own bitrate, then refuse. Never
            # ship a file over the platform limit and call it done.
            retried = True
            kbps = max(200, min(16000, int(budget_bps / 1000)))
            over_args = ["-b:v", f"{kbps}k", "-maxrate", f"{kbps}k",
                         "-bufsize", f"{kbps * 2}k"]
            result = _encode(concat_file, out_path, plan, frames=target_frames,
                             audio=audio_path, video_args=over_args, timeout=timeout)
            if result.returncode != 0:
                raise StitchError("video_encode_failed_on_retry: "
                                  + (result.stderr.strip().splitlines() or [""])[-1][:400])
            final = probe(out_path)

    tolerance = 1.0 / plan["fps"] + 1e-3
    checks = {
        "duration_within_one_frame": abs(final["duration"] - plan["seconds"]) <= tolerance,
        "frame_count_exact": final["nb_frames"] == target_frames,
        "canvas_exact": (final["width"], final["height"]) == (plan["width"], plan["height"]),
        "fps_exact": abs(final["fps"] - plan["fps"]) < 0.01,
        "codec_h264": final["codec"] == "h264",
        "container_mp4": "mp4" in str(final["container"] or ""),
        "size_under_cap": final["bytes"] <= plan["max_bytes"],
        "audio_present": (final["has_audio"] if audio_path else True),
    }
    failed = [name for name, ok in checks.items() if not ok]
    if failed:
        raise StitchError(
            "video_contract_failed: " + ", ".join(failed)
            + f" | measured duration={final['duration']}s frames={final['nb_frames']} "
              f"canvas={final['width']}x{final['height']} codec={final['codec']} "
              f"bytes={final['bytes']} cap={plan['max_bytes']}")

    return {
        "ok": True,
        "platform": plan["platform"],
        "seconds": plan["seconds"],
        "target_frames": target_frames,
        "clips": len(clips),
        "clip_records": clip_records,
        "final": final,
        "checks": checks,
        "size_retry": retried,
        "compliance": plan["compliance"],
        "manifest": {
            "schema": "northstar.video_stitch.v1",
            "platform": plan["platform"], "aspect": plan["aspect"],
            "canvas": [plan["width"], plan["height"]], "fps": plan["fps"],
            "duration_s": plan["seconds"], "frames": target_frames,
            "clips": len(clips), "safe_zones": plan["safe_zones"],
            "compliance": plan["compliance"],
        },
    }


def render_and_stitch(
    render_clip: Callable[[int, int], bytes], out_path: Union[str, Path], *,
    platform: str, seconds: Optional[float] = None,
    audio: Optional[Union[str, Path]] = None,
    timeout: float = 1800.0,
) -> Dict[str, Any]:
    """Plan the clip count, render each clip, stitch and verify.

    `render_clip(index, frames) -> video bytes` is the engine boundary. Keeping
    it injectable is what lets the stitch contract be tested without spending
    minutes on the sampler, and what makes a failed clip a named refusal rather
    than a short video labelled as a full one.
    """
    plan = video_formats.plan(platform, seconds)
    frames_per_clip = int(plan["frames_per_clip"])
    with tempfile.TemporaryDirectory(prefix="ns-clips-") as tmp:
        clip_paths: List[Path] = []
        for i in range(int(plan["clips"])):
            payload = render_clip(i, frames_per_clip)
            if not payload:
                raise StitchError(f"clip_render_empty: clip {i} returned no bytes")
            path = Path(tmp) / f"render_{i:03d}.webm"
            path.write_bytes(payload)
            clip_paths.append(path)
        return stitch_clips(clip_paths, out_path, platform=platform,
                            seconds=seconds, audio=audio, timeout=timeout)


__all__ = ["stitch_clips", "render_and_stitch", "probe", "tools_available",
           "StitchError", "FFMPEG", "FFPROBE"]
