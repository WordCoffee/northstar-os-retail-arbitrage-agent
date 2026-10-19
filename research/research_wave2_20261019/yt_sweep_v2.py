"""Research Wave 2 — YouTube transcript sweep.

Two phases, resumable, append-only:
  Phase 1 (enumerate): yt-dlp `ytsearch` per query -> videos.jsonl
                       (id, title, channel, duration, views, upload_date)
  Phase 2 (captions):  yt-dlp subtitle download (signed-out, no login)
                       for every enumerated video -> transcripts/<id>.vtt
                       Videos without captions are recorded as such and are
                       eligible for the later local faster-whisper pass
                       (transcribe_missing.py) — no audio download here.

Compliance: public, signed-out only. No logins, no cookies, no credential
entry. robots/ToS posture is the operator's standing research policy; only
`ytsearch` + public caption endpoints are used.

Outputs (research/research_wave2_20261019/):
  videos.jsonl            one JSON object per enumerated video
  videos_index.csv        flat index
  transcripts/<id>.vtt    downloaded captions
  yt_state.json           per-query completion + running counts

Usage:
  python yt_sweep_v2.py --phase enumerate [--per-query 15]
  python yt_sweep_v2.py --phase captions  [--max 400]
  python yt_sweep_v2.py --phase all
"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

OUT = Path(__file__).resolve().parent
VIDEOS = OUT / "videos.jsonl"
INDEX = OUT / "videos_index.csv"
TRANSCRIPTS = OUT / "transcripts"
STATE = OUT / "yt_state.json"

QUERIES = [
    # packaging design craft
    "packaging design tutorial", "dieline design illustrator",
    "stand up pouch design", "label design tutorial",
    "print ready file packaging", "flexographic printing design",
    "CMYK print file setup", "spot UV packaging", "foil stamping packaging design",
    "fold carton design", "packaging structure design", "pouch film printing",
    "packaging artwork bleed", "supplement facts label design",
    "food packaging design process", "cosmetic packaging design",
    "beverage label design", "packaging brand identity",
    "retail packaging design tips", "amazon packaging design",
    # 3D / mockups
    "blender packaging mockup", "blender product render",
    "product mockup photoshop", "packaging 3D render",
    "box packaging blender tutorial", "product render lighting",
    "blender cycles product shot", "mockup design accuracy",
    "product photography mockup", "3d mockup blender",
    # AI product imagery
    "AI product images ecommerce", "comfyui product photography",
    "comfyui flux tutorial", "flux image editing tutorial",
    "qwen image edit", "comfyui workflow tutorial",
    "ai product photography workflow", "stable diffusion product shots",
    "image harmonization photoshop", "photoshop composite shadows",
    "product photo composite tutorial", "ai mockup generator",
    "comfyui upscale product", "comfyui relight",
    # retail/listing craft
    "amazon listing images design", "amazon a+ content design",
    "product listing photography", "ecommerce image optimization",
    # printing / prepress
    "prepress tutorial", "packaging print production",
    "packaging dieline tutorial", "packaging design portfolio",
    "graphic design packaging branding", "packaging design workflow",
    # generative design
    "ai packaging design", "packify ai", "pacdora tutorial",
    "canva packaging design", "illustrator packaging workflow",
    "adobe dimension packaging", "ai mockup tool review",
    # realism / compositing fundamentals
    "realistic product composite", "shadow painting photoshop product",
    "reflection photoshop product", "displacement map mockup",
    "mockup displacement tutorial", "smart object mockup photoshop",
]


def run(cmd: list[str], timeout: int = 120) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                          encoding="utf-8", errors="replace")


def load_state() -> dict:
    if STATE.is_file():
        try:
            return json.loads(STATE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"enumerated": {}, "captions_done": [], "captions_missing": [],
            "started_at": datetime.now(timezone.utc).isoformat()}


def save_state(state: dict) -> None:
    STATE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def load_seen() -> set[str]:
    seen: set[str] = set()
    if VIDEOS.is_file():
        for line in VIDEOS.read_text(encoding="utf-8").splitlines():
            try:
                seen.add(json.loads(line)["id"])
            except Exception:
                pass
    return seen


def enumerate_videos(state: dict, per_query: int) -> int:
    seen = load_seen()
    new_count = 0
    fields = ["id", "title", "channel", "duration", "view_count",
              "upload_date", "query", "url"]
    csv_exists = INDEX.is_file()
    with INDEX.open("a", newline="", encoding="utf-8") as cf, \
            VIDEOS.open("a", encoding="utf-8") as vf:
        w = csv.DictWriter(cf, fieldnames=fields)
        if not csv_exists:
            w.writeheader()
        for q in QUERIES:
            if q in state["enumerated"] and not state["enumerated"][q].get("retry"):
                continue
            cmd = [sys.executable, "-m", "yt_dlp",
                   f"ytsearch{per_query}:{q}",
                   "--flat-playlist", "--dump-json", "--skip-download",
                   "--no-warnings", "--quiet", "--ignore-errors"]
            try:
                res = run(cmd, timeout=180)
            except subprocess.TimeoutExpired:
                state["enumerated"][q] = {"count": 0, "error": "timeout",
                                          "retry": True}
                save_state(state)
                continue
            got = 0
            for line in (res.stdout or "").splitlines():
                line = line.strip()
                if not line.startswith("{"):
                    continue
                try:
                    it = json.loads(line)
                except Exception:
                    continue
                vid = it.get("id")
                if not vid or vid in seen:
                    continue
                seen.add(vid)
                row = {
                    "id": vid, "title": (it.get("title") or "")[:200],
                    "channel": (it.get("channel") or it.get("uploader") or "")[:120],
                    "duration": it.get("duration"),
                    "view_count": it.get("view_count"),
                    "upload_date": it.get("upload_date"),
                    "query": q,
                    "url": f"https://www.youtube.com/watch?v={vid}",
                }
                w.writerow(row)
                vf.write(json.dumps(row, ensure_ascii=False) + "\n")
                got += 1
            cf.flush()
            vf.flush()
            state["enumerated"][q] = {"count": got, "at": datetime.now(timezone.utc).isoformat()}
            new_count += got
            save_state(state)
            print(f"[yt:enum] {q!r}: +{got} (total {len(seen)})", flush=True)
            time.sleep(1.2)
    return new_count


def download_captions(state: dict, max_n: int) -> tuple[int, int]:
    TRANSCRIPTS.mkdir(exist_ok=True)
    have: set[str] = set(state.get("captions_done") or [])
    missing: set[str] = set(state.get("captions_missing") or [])
    done_n = miss_n = 0
    videos: list[dict] = []
    if VIDEOS.is_file():
        for line in VIDEOS.read_text(encoding="utf-8").splitlines():
            try:
                videos.append(json.loads(line))
            except Exception:
                pass

    attempts = 0
    for v in videos:
        if attempts >= max_n:
            break
        vid = v["id"]
        if vid in have or vid in missing:
            continue
        attempts += 1
        out_tpl = str(TRANSCRIPTS / "%(id)s.%(ext)s")
        cmd = [sys.executable, "-m", "yt_dlp",
               "--skip-download", "--write-auto-sub", "--write-sub",
               "--sub-langs", "en.*", "--sub-format", "vtt",
               "--no-warnings", "--quiet", "--ignore-errors",
               "-o", out_tpl, v["url"]]
        try:
            run(cmd, timeout=90)
        except subprocess.TimeoutExpired:
            pass
        got = list(TRANSCRIPTS.glob(f"{vid}*.vtt"))
        if got:
            have.add(vid)
            done_n += 1
        else:
            missing.add(vid)
            miss_n += 1
        if attempts % 25 == 0:
            state["captions_done"] = sorted(have)
            state["captions_missing"] = sorted(missing)
            save_state(state)
            print(f"[yt:cap] attempted={attempts} captions={done_n} "
                  f"missing={miss_n}", flush=True)
        time.sleep(0.6)

    state["captions_done"] = sorted(have)
    state["captions_missing"] = sorted(missing)
    save_state(state)
    return done_n, miss_n


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase", choices=["enumerate", "captions", "all"],
                    default="all")
    ap.add_argument("--per-query", type=int, default=15)
    ap.add_argument("--max", type=int, default=400)
    args = ap.parse_args()

    state = load_state()
    if args.phase in ("enumerate", "all"):
        n = enumerate_videos(state, args.per_query)
        print(f"[yt] enumerated +{n}", flush=True)
    if args.phase in ("captions", "all"):
        d, m = download_captions(state, args.max)
        print(f"[yt] captions done={d} missing={m}", flush=True)
    save_state(state)
    print("DONE yt sweep", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
