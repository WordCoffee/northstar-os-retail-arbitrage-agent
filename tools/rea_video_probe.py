"""
REA 1.3 probe — deterministic short-form ad assembly with FFmpeg only.

No generative model, no provider, no spend. Proves which parts of a short-form
ad can be assembled from stills + narration + captions by FFmpeg alone, and
produces one real clip with ffprobe evidence.

Inputs are files already on this machine:
  - a real Northstar studio render (Northstar_backend/data/studio_generated)
  - the synthetic label panel produced by tools/rea_warp_probe.py
  - Piper narration through Northstar_backend/local_voice.py (falls back to
    silence and says so)

Output: reports/rea_probe/video/  (clips + probe.json)

Run: python tools/rea_video_probe.py
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports" / "rea_probe" / "video"
OUT.mkdir(parents=True, exist_ok=True)

W, H, FPS = 1080, 1920, 30
FONT = "C:/Windows/Fonts/arialbd.ttf"

PANEL = ROOT / "reports" / "rea_probe" / "panel_flat.png"
RENDERS = sorted(
    (ROOT / "Northstar_backend" / "data" / "studio_generated").glob("*.png"),
    key=lambda p: p.stat().st_size, reverse=True)

CAPTIONS = [
    (0.0, 4.0, "The label nobody reads"),
    (4.0, 8.0, "Printed on the bag, not stuck on it"),
    (8.0, 12.0, "Northstar OS"),
]


def run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, shell=False)


def ffprobe(path: Path) -> dict:
    r = run(["ffprobe", "-v", "error", "-print_format", "json",
             "-show_format", "-show_streams", str(path)])
    if r.returncode != 0:
        return {"error": r.stderr.strip()[:400]}
    data = json.loads(r.stdout)
    streams = [{
        "type": s.get("codec_type"),
        "codec": s.get("codec_name"),
        "width": s.get("width"),
        "height": s.get("height"),
        "fps": s.get("r_frame_rate"),
        "sample_rate": s.get("sample_rate"),
        "duration_s": s.get("duration"),
        "bit_rate": s.get("bit_rate"),
    } for s in data.get("streams", [])]
    fmt = data.get("format", {})
    return {
        "streams": streams,
        "duration_s": float(fmt.get("duration", 0) or 0),
        "size_bytes": int(fmt.get("size", 0) or 0),
        "bit_rate": int(fmt.get("bit_rate", 0) or 0),
    }


def caption_png(text: str, path: Path) -> None:
    img = Image.new("RGBA", (W, 220), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    font = ImageFont.truetype(FONT, 58)
    # measure and centre
    box = d.textbbox((0, 0), text, font=font)
    tw = box[2] - box[0]
    x = max(24, (W - tw) // 2)
    d.rounded_rectangle([x - 28, 24, x + tw + 28, 180], radius=18,
                        fill=(20, 24, 20, 190))
    d.text((x, 52), text, font=font, fill=(246, 244, 238, 255))
    img.save(path)


def shot(src: Path, out: Path, seconds: float, zoom_in: bool) -> str:
    """One Ken-Burns shot fitted to 1080x1920, no letterboxing."""
    z = "min(zoom+0.0008,1.18)" if zoom_in else "if(lte(zoom,1.0),1.18,max(1.001,zoom-0.0008))"
    vf = (
        f"scale={W}:{H}:force_original_aspect_ratio=increase,"
        f"crop={W}:{H},"
        f"zoompan=z='{z}':d={int(seconds * FPS)}:s={W}x{H}:fps={FPS},"
        f"format=yuv420p"
    )
    r = run(["ffmpeg", "-y", "-loop", "1", "-i", str(src), "-t", f"{seconds}",
             "-vf", vf, "-r", str(FPS), "-c:v", "libx264", "-preset", "veryfast",
             "-pix_fmt", "yuv420p", str(out)])
    return r.stderr[-500:] if r.returncode != 0 else "ok"


def narration(text: str) -> tuple[Path | None, str]:
    """Try the local Piper/SAPI lane; report honestly if it is unavailable."""
    sys.path.insert(0, str(ROOT / "Northstar_backend"))
    try:
        import local_voice  # type: ignore
    except Exception as exc:
        return None, f"local_voice import failed: {type(exc).__name__}"
    try:
        result = local_voice.synthesize(text)
    except Exception as exc:
        return None, f"synthesize raised {type(exc).__name__}: {exc}"[:300]
    data = (result or {}).get("bytes") or b""
    if len(data) < 1000:
        return None, f"no audio produced ({result})"
    wav = OUT / "narration.wav"
    wav.write_bytes(data)
    return wav, f"engine={result.get('engine')} voice={result.get('voice') or result.get('voice_name')}"


def main() -> None:
    if not PANEL.exists():
        raise SystemExit("run tools/rea_warp_probe.py first (panel_flat.png missing)")
    if not RENDERS:
        raise SystemExit("no studio render found to use as footage")

    render = RENDERS[0]
    shots = [
        (render, 4.0, True, "hook: product on the surface"),
        (PANEL, 4.0, False, "middle: the flat artwork"),
        (render, 4.0, True, "close: brand lockup"),
    ]
    clips = []
    for i, (src, secs, zin, _label) in enumerate(shots):
        clip = OUT / f"shot{i}.mp4"
        status = shot(src, clip, secs, zin)
        if status != "ok":
            raise SystemExit(f"shot {i} failed: {status}")
        clips.append(clip)

    listing = OUT / "concat.txt"
    listing.write_text("".join(f"file '{c.as_posix()}'\n" for c in clips), encoding="utf-8")
    base = OUT / "base.mp4"
    r = run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(listing),
             "-c", "copy", str(base)])
    if r.returncode != 0:
        raise SystemExit(f"concat failed: {r.stderr[-400:]}")

    caps = []
    for i, (_, _, text) in enumerate(CAPTIONS):
        p = OUT / f"cap{i}.png"
        caption_png(text, p)
        caps.append(p)

    script = ("The label nobody reads. Now printed on the bag, not stuck on it. "
              "Northstar OS.")
    wav, audio_note = narration(script)

    inputs = ["-i", str(base)]
    for p in caps:
        inputs += ["-i", str(p)]
    if wav:
        inputs += ["-i", str(wav)]

    # captions sit at 55-65% of the height: below the product, above the bottom
    # 30% UI keep-out that every short-form platform overlays.
    y = int(H * 0.55)
    fc = [f"[0:v][1:v]overlay=0:{y}:enable='between(t,0,3.9)'[v1]",
          f"[v1][2:v]overlay=0:{y}:enable='between(t,4,7.9)'[v2]",
          f"[v2][3:v]overlay=0:{y}:enable='between(t,8,11.9)'[v3]"]
    maps = ["-map", "[v3]"]
    if wav:
        fc.append("[4:a]loudnorm=I=-14:TP=-1.5:LRA=11,apad[aout]")
        maps += ["-map", "[aout]", "-c:a", "aac", "-b:a", "128k", "-shortest"]

    final = OUT / "ad_15s_1080x1920.mp4"
    cmd = (["ffmpeg", "-y"] + inputs +
           ["-filter_complex", ";".join(fc)] + maps +
           ["-c:v", "libx264", "-preset", "veryfast", "-crf", "21",
            "-pix_fmt", "yuv420p", "-r", str(FPS), str(final)])
    r = run(cmd)
    if r.returncode != 0:
        raise SystemExit(f"final mux failed: {r.stderr[-800:]}")

    probe = {
        "probe": "rea_video_probe",
        "date": "2026-10-28",
        "ffmpeg": run(["ffmpeg", "-version"]).stdout.splitlines()[0],
        "source_plate": str(render.relative_to(ROOT)),
        "source_panel": str(PANEL.relative_to(ROOT)),
        "audio": audio_note,
        "audio_present": bool(wav),
        "captions": [{"start": a, "end": b, "text": t} for a, b, t in CAPTIONS],
        "caption_y_px": y,
        "caption_y_pct": round(y / H * 100, 1),
        "output": ffprobe(final),
        "shots": [{"src": str(src.name), "seconds": secs, "zoom_in": zin, "job": label}
                  for src, secs, zin, label in shots],
    }
    (OUT / "video_probe.json").write_text(json.dumps(probe, indent=2), encoding="utf-8")
    print(json.dumps(probe, indent=2))
    for p in clips + [base]:
        pass
    shutil.rmtree(OUT / "_none", ignore_errors=True)


if __name__ == "__main__":
    main()
