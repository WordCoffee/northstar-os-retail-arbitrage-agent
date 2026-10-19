"""Research Wave 2 — whisper pass for videos without usable captions.

Downloads audio with yt-dlp and transcribes locally with faster-whisper.
Resumable: a video with an existing transcript is skipped. Tries CUDA first,
falls back to CPU with an honest record of which device ran (no silent
downgrade of the reported result).

Outputs (research/research_wave2_20261019/):
  transcripts/<video_id>.whisper.txt   plain text
  transcripts/<video_id>.whisper.json  segments + model + device + timing
  whisper_state.json                   done/failed lists

Usage:
  python transcribe_missing.py --max 25 [--model small] [--all] [--device cpu]
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

OUT = Path(__file__).resolve().parent
VIDEOS = OUT / "videos.jsonl"
TRANSCRIPTS = OUT / "transcripts"
STATE = OUT / "whisper_state.json"
AUDIO_TMP = OUT / "_audio_tmp"


def load_state() -> dict:
    if STATE.is_file():
        try:
            return json.loads(STATE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"done": [], "failed": [], "started_at": datetime.now(timezone.utc).isoformat()}


def save_state(s: dict) -> None:
    STATE.write_text(json.dumps(s, indent=2), encoding="utf-8")


def load_videos() -> list[dict]:
    out = []
    if VIDEOS.is_file():
        for line in VIDEOS.read_text(encoding="utf-8").splitlines():
            try:
                out.append(json.loads(line))
            except Exception:
                pass
    return out


def has_caption(vid: str) -> bool:
    return any(TRANSCRIPTS.glob(f"{vid}*.vtt"))


def has_whisper(vid: str) -> bool:
    return (TRANSCRIPTS / f"{vid}.whisper.txt").is_file()


def pick_model(device: str, name: str):
    from faster_whisper import WhisperModel
    ct = "int8_float16" if device == "cuda" else "int8"
    try:
        return WhisperModel(name, device=device, compute_type=ct), device, ct
    except Exception as exc:  # noqa: BLE001
        if device == "cpu":
            raise
        print(f"[whisper] cuda unavailable ({str(exc)[:120]}); falling back to cpu",
              flush=True)
        return WhisperModel(name, device="cpu", compute_type="int8"), "cpu", "int8"


def download_audio(url: str, dest_stem: Path) -> Path | None:
    cmd = [sys.executable, "-m", "yt_dlp", "-x", "--audio-format", "m4a",
           "--no-playlist", "--no-warnings", "--quiet", "--ignore-errors",
           "-o", str(dest_stem) + ".%(ext)s", url]
    try:
        subprocess.run(cmd, capture_output=True, text=True, timeout=900)
    except subprocess.TimeoutExpired:
        return None
    for p in dest_stem.parent.glob(dest_stem.name + ".*"):
        if p.suffix.lower() in (".m4a", ".mp3", ".webm", ".opus", ".wav"):
            return p
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="small")
    ap.add_argument("--device", default="auto", choices=["auto", "cuda", "cpu"])
    ap.add_argument("--max", type=int, default=25)
    ap.add_argument("--all", action="store_true",
                    help="include videos that already have captions")
    ap.add_argument("--min-views", type=int, default=0)
    args = ap.parse_args()

    TRANSCRIPTS.mkdir(exist_ok=True)
    AUDIO_TMP.mkdir(exist_ok=True)
    state = load_state()
    done = set(state["done"])
    failed = {f["id"] for f in state["failed"]}

    videos = [v for v in load_videos() if v.get("url")]
    if not args.all:
        videos = [v for v in videos if not has_caption(v["id"])]
    videos = [v for v in videos if (v.get("view_count") or 0) >= args.min_views]
    videos = [v for v in videos if v["id"] not in done and v["id"] not in failed]
    videos.sort(key=lambda v: -(v.get("view_count") or 0))
    videos = videos[: args.max]
    if not videos:
        print(json.dumps({"ok": True, "note": "nothing to transcribe", "done": len(done)}))
        return 0

    device = args.device
    if device == "auto":
        device = "cuda"
    model, device, ct = pick_model(device, args.model)
    print(json.dumps({"model": args.model, "device": device, "compute_type": ct,
                      "queued": len(videos)}), flush=True)

    added = 0
    for i, v in enumerate(videos, 1):
        t0 = time.time()
        stem = AUDIO_TMP / v["id"]
        audio = download_audio(v["url"], stem)
        if audio is None:
            state["failed"].append({"id": v["id"], "reason": "audio download failed"})
            save_state(state)
            print(f"[{i}/{len(videos)}] {v['id']} download FAILED", flush=True)
            continue
        try:
            segs, info = model.transcribe(str(audio), vad_filter=True,
                                          beam_size=1, language=None)
            parts, seg_list = [], []
            for s in segs:
                parts.append(s.text.strip())
                seg_list.append({"start": round(s.start, 2), "end": round(s.end, 2),
                                 "text": s.text.strip()})
            text = "\n".join(p for p in parts if p).strip()
            (TRANSCRIPTS / f"{v['id']}.whisper.txt").write_text(text, encoding="utf-8")
            (TRANSCRIPTS / f"{v['id']}.whisper.json").write_text(json.dumps({
                "id": v["id"], "title": v.get("title"), "channel": v.get("channel"),
                "url": v.get("url"), "query": v.get("query"),
                "model": args.model, "device": device, "compute_type": ct,
                "detected_language": getattr(info, "language", None),
                "language_probability": round(getattr(info, "language_probability", 0.0) or 0.0, 3),
                "duration_s": round(getattr(info, "duration", 0.0) or 0.0, 1),
                "chars": len(text), "segments": seg_list,
                "transcribed_at": datetime.now(timezone.utc).isoformat(),
                "seconds": round(time.time() - t0, 1),
            }, ensure_ascii=False, indent=1), encoding="utf-8")
            state["done"].append(v["id"])
            added += 1
            print(f"[{i}/{len(videos)}] {v['id']} ok {len(text)} chars "
                  f"{round(time.time() - t0, 1)}s", flush=True)
        except Exception as exc:  # noqa: BLE001
            state["failed"].append({"id": v["id"], "reason": str(exc)[:160]})
            print(f"[{i}/{len(videos)}] {v['id']} FAILED {str(exc)[:100]}", flush=True)
        finally:
            if audio and audio.exists():
                try:
                    audio.unlink()
                except OSError:
                    pass
            save_state(state)

    print(json.dumps({"ok": True, "transcribed": added,
                      "total_done": len(state["done"]),
                      "failed": len(state["failed"])}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
