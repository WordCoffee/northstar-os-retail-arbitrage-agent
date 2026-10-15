"""Clip tools for the NorthstarOS Design Studio — split long videos into
5–15 s clips and stitch clips back together. ffmpeg-powered, fully local.

Usage:
  python tools/clip_split.py split  INPUT.mp4 --out-dir OUT [--min 5] [--max 15]
                                     [--mode fixed|scene] [--target 10]
  python tools/clip_split.py concat CLIP1 CLIP2 [...] --out FINAL.mp4

- fixed mode (default): cuts at ~target s, every clip clamped to [min, max].
- scene mode: detects scene changes (ffmpeg scene score > 0.3) and splits at
  scene boundaries, then merges short scenes until each clip is >= min.
- Prints a JSON summary (segments + ffmpeg path) on stdout for the app.
- ffmpeg discovery: $FFMPEG env var, PATH, WinGet Links, imageio-ffmpeg.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


def find_ffmpeg() -> str:
    env = os.environ.get("FFMPEG")
    if env and Path(env).exists():
        return env
    which = shutil.which("ffmpeg")
    if which:
        return which
    cand = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Links" / "ffmpeg.exe"
    if cand.exists():
        return str(cand)
    local = Path.home() / "tools" / "ffmpeg" / "bin" / "ffmpeg.exe"
    if local.exists():
        return str(local)
    try:  # bundled binary fallback (pip install imageio-ffmpeg)
        import imageio_ffmpeg  # type: ignore

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        pass
    raise SystemExit("ffmpeg not found — install ffmpeg or `pip install imageio-ffmpeg`")


def probe_duration(ffmpeg: str, path: str) -> float:
    # ffmpeg prints duration to stderr
    out = subprocess.run(
        [ffmpeg, "-i", path], capture_output=True, text=True, errors="ignore"
    ).stderr
    for line in out.splitlines():
        line = line.strip()
        if line.startswith("Duration:"):
            ts = line.split("Duration:")[1].split(",")[0].strip()
            h, m, s = ts.split(":")
            return int(h) * 3600 + int(m) * 60 + float(s)
    raise SystemExit(f"could not read duration of {path}")


def scene_cuts(ffmpeg: str, path: str, threshold: float = 0.3) -> list[float]:
    cmd = [
        ffmpeg, "-i", path, "-filter:v", f"select='gt(scene,{threshold})',showinfo",
        "-f", "null", "-",
    ]
    out = subprocess.run(cmd, capture_output=True, text=True, errors="ignore").stderr
    cuts: list[float] = []
    for line in out.splitlines():
        if "pts_time:" in line and "showinfo" in line:
            try:
                ts = line.split("pts_time:")[1].split()[0]
                cuts.append(float(ts))
            except (ValueError, IndexError):
                continue
    return cuts


def build_fixed(duration: float, target: float, mn: float, mx: float) -> list[tuple[float, float]]:
    segs: list[tuple[float, float]] = []
    t = 0.0
    while t < duration - 0.5:
        end = min(t + target, duration)
        seg = end - t
        if seg < mn and segs:
            segs[-1] = (segs[-1][0], duration)  # merge tail into last clip
            break
        if seg > mx:
            seg = mx
            end = t + seg
        segs.append((t, end))
        t = end
    return [(round(a, 3), round(b, 3)) for a, b in segs]


def build_scene(duration: float, cuts: list[float], mn: float, mx: float) -> list[tuple[float, float]]:
    bounds = [0.0] + [c for c in cuts if 0.5 < c < duration - 0.5] + [duration]
    segs: list[tuple[float, float]] = []
    start = bounds[0]
    for b in bounds[1:]:
        if b - start >= mn:
            segs.append((start, b))
            start = b
    if start < duration:
        if segs and duration - start < mn:
            segs[-1] = (segs[-1][0], duration)
        else:
            segs.append((start, duration))
    # enforce max by splitting
    final: list[tuple[float, float]] = []
    for a, b in segs:
        while b - a > mx:
            final.append((a, a + mx))
            a += mx
        final.append((a, b))
    return [(round(a, 3), round(b, 3)) for a, b in final]


def cut_clip(ffmpeg: str, src: str, start: float, end: float, out: str) -> None:
    cmd = [
        ffmpeg, "-y", "-ss", f"{start}", "-to", f"{end}", "-i", src,
        "-c:v", "libx264", "-preset", "fast", "-crf", "18",
        "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", out,
    ]
    subprocess.run(cmd, check=True, capture_output=True)


def do_split(args: argparse.Namespace) -> None:
    ffmpeg = find_ffmpeg()
    src = args.input
    duration = probe_duration(ffmpeg, src)
    if args.mode == "scene":
        segs = build_scene(duration, scene_cuts(ffmpeg, src), args.min, args.max)
    else:
        segs = build_fixed(duration, args.target, args.min, args.max)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = Path(src).stem
    made = []
    for i, (a, b) in enumerate(segs, 1):
        out = out_dir / f"{stem}_clip{i:02d}_{int(round(a))}-{int(round(b))}s.mp4"
        cut_clip(ffmpeg, src, a, b, str(out))
        made.append({"file": str(out), "start": a, "end": b, "seconds": round(b - a, 2)})
    print(json.dumps({"ffmpeg": ffmpeg, "input": src, "duration": round(duration, 2),
                      "mode": args.mode, "clips": made}, indent=2))


def do_concat(args: argparse.Namespace) -> None:
    ffmpeg = find_ffmpeg()
    listing = Path(args.out).with_suffix(".concat.txt")
    with listing.open("w", encoding="utf-8") as fh:
        for clip in args.clips:
            fh.write(f"file '{Path(clip).resolve().as_posix()}'\n")
    # stream-copy first; fall back to re-encode when formats differ
    try:
        subprocess.run(
            [ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", str(listing), "-c", "copy", args.out],
            check=True, capture_output=True,
        )
        mode = "copy"
    except subprocess.CalledProcessError:
        subprocess.run(
            [ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", str(listing),
             "-c:v", "libx264", "-preset", "fast", "-crf", "18", "-c:a", "aac", "-b:a", "192k", args.out],
            check=True, capture_output=True,
        )
        mode = "reencode"
    print(json.dumps({"ffmpeg": ffmpeg, "mode": mode, "out": args.out,
                      "clips": args.clips}, indent=2))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sp = sub.add_parser("split")
    sp.add_argument("input")
    sp.add_argument("--out-dir", required=True)
    sp.add_argument("--min", type=float, default=5.0)
    sp.add_argument("--max", type=float, default=15.0)
    sp.add_argument("--target", type=float, default=10.0)
    sp.add_argument("--mode", choices=["fixed", "scene"], default="fixed")
    sp.set_defaults(func=do_split)
    cp = sub.add_parser("concat")
    cp.add_argument("clips", nargs="+")
    cp.add_argument("--out", required=True)
    cp.set_defaults(func=do_concat)
    args = ap.parse_args()
    args.func(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
