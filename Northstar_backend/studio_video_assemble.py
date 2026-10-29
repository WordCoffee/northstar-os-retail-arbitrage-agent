"""Short-form ad assembly, deterministic and local (REA 1.3 candidate V1).

The whole ad except the footage is arithmetic: shots, moves, captions,
narration, loudness and vertical framing are FFmpeg + PIL + Piper. That was
proved by tools/rea_video_probe.py; this module is that probe turned into a
service other code can call.

Nothing here generates footage and nothing contacts a provider.

    from studio_video_assemble import assemble
    meta = assemble(
        ["plate.png", "panel.png"],
        captions=["The label nobody reads", "Printed on the bag"],
        narration="The label nobody reads. Now printed on the bag.",
        out_path="ad.mp4",
    )

CLI:
    python studio_video_assemble.py --image plate.png --image panel.png \
        --caption "The label nobody reads" --caption "Printed on the bag" \
        --narration-text "The label nobody reads." --out ad.mp4
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from PIL import Image, ImageDraw, ImageFont

DEFAULT_SIZE: Tuple[int, int] = (1080, 1920)
DEFAULT_FPS = 30
DEFAULT_SECONDS = 4.0
CAPTION_Y_FRAC = 0.55        # below the product, above the platform's bottom band
CAPTION_SAFE_BOTTOM = 0.30   # keep-out: naive, but it is the platform's own rule
FONT_CANDIDATES = ("C:/Windows/Fonts/arialbd.ttf", "C:/Windows/Fonts/segoeuib.ttf")


def _ffmpeg() -> Optional[str]:
    return shutil.which("ffmpeg")


def _font(size: int):
    for path in FONT_CANDIDATES:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def probe(path: Path) -> Dict[str, Any]:
    """ffprobe the result so every claim about the clip comes from the file."""
    exe = shutil.which("ffprobe")
    if not exe:
        return {"error": "ffprobe not found"}
    r = subprocess.run([exe, "-v", "error", "-print_format", "json",
                        "-show_format", "-show_streams", str(path)],
                       capture_output=True, text=True)
    if r.returncode != 0:
        return {"error": r.stderr.strip()[:300]}
    data = json.loads(r.stdout)
    streams = [{"type": s.get("codec_type"), "codec": s.get("codec_name"),
                "width": s.get("width"), "height": s.get("height"),
                "fps": s.get("r_frame_rate"), "sample_rate": s.get("sample_rate"),
                "duration_s": s.get("duration")} for s in data.get("streams", [])]
    fmt = data.get("format", {})
    return {"streams": streams,
            "duration_s": float(fmt.get("duration", 0) or 0),
            "size_bytes": int(fmt.get("size", 0) or 0),
            "bit_rate": int(fmt.get("bit_rate", 0) or 0)}


def _caption_png(text: str, size: Tuple[int, int], path: Path) -> None:
    w, h = size
    img = Image.new("RGBA", (w, 220), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    font = _font(max(28, int(w * 0.054)))
    box = d.textbbox((0, 0), text, font=font)
    tw = box[2] - box[0]
    x = max(24, (w - tw) // 2)
    d.rounded_rectangle([x - 28, 24, x + tw + 28, 180], radius=18, fill=(20, 24, 20, 190))
    d.text((x, 52), text, font=font, fill=(246, 244, 238, 255))
    img.save(path)


def _shot(src: Path, out: Path, seconds: float, size: Tuple[int, int],
          fps: int, zoom_in: bool) -> str:
    w, h = size
    z = "min(zoom+0.0008,1.18)" if zoom_in else "if(lte(zoom,1.0),1.18,max(1.001,zoom-0.0008))"
    vf = (f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},"
          f"zoompan=z='{z}':d={max(1, int(seconds * fps))}:s={w}x{h}:fps={fps},"
          f"format=yuv420p")
    r = subprocess.run(["ffmpeg", "-y", "-loop", "1", "-i", str(src), "-t", f"{seconds}",
                        "-vf", vf, "-r", str(fps), "-c:v", "libx264", "-preset", "veryfast",
                        "-pix_fmt", "yuv420p", str(out)],
                       capture_output=True, text=True)
    return "ok" if r.returncode == 0 else r.stderr[-400:]


def _narration(text: str, path: Path) -> tuple[Optional[Path], str]:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    try:
        import local_voice  # type: ignore
    except Exception as exc:  # noqa: BLE001 - the reason is the report
        return None, f"local_voice import failed: {type(exc).__name__}"
    try:
        result = local_voice.synthesize(text) or {}
    except Exception as exc:  # noqa: BLE001
        return None, f"synthesize raised {type(exc).__name__}: {exc}"[:200]
    data = result.get("bytes") or b""
    if len(data) < 1000:
        return None, "no audio produced"
    path.write_bytes(data)
    return path, f"engine={result.get('engine')} voice={result.get('voice') or result.get('voice_name')}"


def assemble(images: Sequence[Any],
             captions: Optional[Sequence[str]] = None,
             narration: Optional[str] = None,
             out_path: Any = None,
             seconds_per_shot: float = DEFAULT_SECONDS,
             size: Tuple[int, int] = DEFAULT_SIZE,
             fps: int = DEFAULT_FPS,
             crf: int = 21,
             loudness_lufs: float = -14.0) -> Dict[str, Any]:
    """Assemble a vertical clip from stills. Returns metadata + the honest reasons."""
    if not _ffmpeg():
        raise RuntimeError("ffmpeg is not on PATH; the assembly lane cannot run")
    images = [Path(p) for p in images if p]
    if not images:
        raise ValueError("at least one image is required")
    missing = [str(p) for p in images if not p.is_file()]
    if missing:
        raise FileNotFoundError(f"missing source image(s): {missing}")

    out_path = Path(out_path) if out_path else Path(tempfile.gettempdir()) / f"ad-{uuid.uuid4().hex[:8]}.mp4"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="ns-ad-"))
    try:
        clips: List[Path] = []
        for i, src in enumerate(images):
            clip = work / f"shot{i}.mp4"
            status = _shot(src, clip, seconds_per_shot, size, fps, zoom_in=(i % 2 == 0))
            if status != "ok":
                raise RuntimeError(f"shot {i} failed: {status}")
            clips.append(clip)

        listing = work / "concat.txt"
        listing.write_text("".join(f"file '{c.as_posix()}'\n" for c in clips), encoding="utf-8")
        base = work / "base.mp4"
        r = subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(listing),
                            "-c", "copy", str(base)], capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError(f"concat failed: {r.stderr[-300:]}")

        inputs = ["-i", str(base)]
        filters: List[str] = []
        captions = [c for c in (captions or []) if c]
        label = "0:v"
        for idx, text in enumerate(captions):
            cap = work / f"cap{idx}.png"
            _caption_png(text, size, cap)
            inputs += ["-i", str(cap)]
            start = idx * seconds_per_shot
            end = (idx + 1) * seconds_per_shot - 0.1
            nxt = f"v{idx + 1}"
            filters.append(f"[{label}][{idx + 1}:v]overlay=0:{int(size[1] * CAPTION_Y_FRAC)}:"
                           f"enable='between(t,{start:.2f},{end:.2f})'[{nxt}]")
            label = nxt

        audio_note = "no narration requested"
        wav = None
        if narration:
            wav, audio_note = _narration(narration, work / "narration.wav")
        maps = ["-map", f"[{label}]"] if filters else ["-map", "0:v"]
        if wav:
            inputs += ["-i", str(wav)]
            audio_idx = len(inputs) // 2 - 1
            filters.append(f"[{audio_idx}:a]loudnorm=I={loudness_lufs}:TP=-1.5:LRA=11,apad[aout]")
            maps += ["-map", "[aout]", "-c:a", "aac", "-b:a", "128k", "-shortest"]

        cmd = ["ffmpeg", "-y"] + inputs
        if filters:
            cmd += ["-filter_complex", ";".join(filters)]
        cmd += maps + ["-c:v", "libx264", "-preset", "veryfast", "-crf", str(crf),
                       "-pix_fmt", "yuv420p", "-r", str(fps), str(out_path)]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError(f"final mux failed: {r.stderr[-500:]}")

        meta = probe(out_path)
        return {
            "ok": True,
            "out_path": str(out_path),
            "shots": len(images),
            "seconds_per_shot": seconds_per_shot,
            "captions": len(captions),
            "caption_y_pct": round(CAPTION_Y_FRAC * 100, 1),
            "audio": audio_note,
            "audio_present": bool(wav),
            "size": list(size),
            "fps": fps,
            "probe": meta,
        }
    finally:
        shutil.rmtree(work, ignore_errors=True)


def main(argv: Optional[List[str]] = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="Assemble a vertical ad from stills (local, deterministic).")
    ap.add_argument("--image", action="append", required=True)
    ap.add_argument("--caption", action="append", default=[])
    ap.add_argument("--narration-text", default=None)
    ap.add_argument("--out", required=True)
    ap.add_argument("--seconds", type=float, default=DEFAULT_SECONDS)
    ap.add_argument("--width", type=int, default=DEFAULT_SIZE[0])
    ap.add_argument("--height", type=int, default=DEFAULT_SIZE[1])
    args = ap.parse_args(argv)
    meta = assemble(args.image, captions=args.caption, narration=args.narration_text,
                    out_path=args.out, seconds_per_shot=args.seconds,
                    size=(args.width, args.height))
    print(json.dumps(meta, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
