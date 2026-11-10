"""Render one image-to-video clip through the local ComfyUI (Wan 2.2 TI2V-5B).

This is the acceptance harness for the video lane: it uploads a still, queues a
native Wan graph, waits, and reports the measured wall time, peak VRAM and the
output file. It never edits pricing or credits - it only produces evidence.

Usage:
  python tools/render_wan_clip.py --image path\to\still.png --prompt "..." \
      --out reports\video_scan\clip_01.webm [--length 121] [--width 960] \
      [--height 960] [--seed 42] [--steps 30] [--cfg 5.0]

Requires ComfyUI running on 127.0.0.1:8188 with ComfyUI-GGUF installed and the
Wan 2.2 TI2V-5B Q5_K_M model + wan2.2 VAE + umt5 encoder on disk.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import threading
import time
import urllib.request
import uuid
from pathlib import Path

COMFY = Path(r"C:\Users\T2Hol\ComfyUI")
HOST = "http://127.0.0.1:8188"
UNET = "Wan2.2-TI2V-5B-Q5_K_M.gguf"
CLIP = "umt5-xxl-encoder-Q5_K_M.gguf"
VAE = "wan2.2_vae" + ".safetensors"

DEFAULT_NEG = ("static, frozen, jitter, flicker, warping, distorted label text, "
               "melting packaging, low quality, watermark, extra objects")


def post_json(path: str, payload: dict) -> dict:
    req = urllib.request.Request(
        HOST + path, data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode())


def get_json(path: str) -> dict:
    with urllib.request.urlopen(HOST + path, timeout=60) as resp:
        return json.loads(resp.read().decode())


def vram_used_mb() -> int:
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=10)
        return int(out.stdout.strip().splitlines()[0])
    except Exception:  # noqa: BLE001 - telemetry must never kill a render
        return -1


def build_graph(image_name: str, prompt: str, negative: str, *,
                width: int, height: int, length: int, seed: int,
                steps: int, cfg: float, shift: float, fps: float) -> dict:
    return {
        "1": {"class_type": "UnetLoaderGGUF", "inputs": {"unet_name": UNET}},
        "2": {"class_type": "CLIPLoaderGGUF",
              "inputs": {"clip_name": CLIP, "type": "wan"}},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": VAE}},
        "4": {"class_type": "ModelSamplingSD3",
              "inputs": {"model": ["1", 0], "shift": shift}},
        "5": {"class_type": "CLIPTextEncode",
              "inputs": {"text": prompt, "clip": ["2", 0]}},
        "6": {"class_type": "CLIPTextEncode",
              "inputs": {"text": negative, "clip": ["2", 0]}},
        "7": {"class_type": "LoadImage", "inputs": {"image": image_name}},
        "8": {"class_type": "Wan22ImageToVideoLatent",
              "inputs": {"vae": ["3", 0], "width": width, "height": height,
                         "length": length, "batch_size": 1,
                         "start_image": ["7", 0]}},
        "9": {"class_type": "KSampler",
              "inputs": {"model": ["4", 0], "seed": seed, "steps": steps,
                         "cfg": cfg, "sampler_name": "uni_pc",
                         "scheduler": "simple", "positive": ["5", 0],
                         "negative": ["6", 0], "latent_image": ["8", 0],
                         "denoise": 1.0}},
        "10": {"class_type": "VAEDecode",
               "inputs": {"samples": ["9", 0], "vae": ["3", 0]}},
        "11": {"class_type": "SaveWEBM",
               "inputs": {"images": ["10", 0], "filename_prefix": "northstar/wan",
                          "codec": "vp9", "fps": fps, "crf": 20.0}},
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", required=True)
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--negative", default=DEFAULT_NEG)
    ap.add_argument("--out", required=True)
    ap.add_argument("--length", type=int, default=121)   # 5.04 s at 24 fps
    ap.add_argument("--width", type=int, default=960)
    ap.add_argument("--height", type=int, default=960)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--steps", type=int, default=30)
    ap.add_argument("--cfg", type=float, default=5.0)
    ap.add_argument("--shift", type=float, default=8.0)
    ap.add_argument("--fps", type=float, default=24.0)
    ap.add_argument("--timeout", type=int, default=1800)
    ap.add_argument("--summary", default="", help="append a JSON line per run here")
    args = ap.parse_args()

    src = Path(args.image).resolve()
    if not src.exists():
        raise SystemExit(f"input image not found: {src}")
    target = COMFY / "input" / "northstar_test_still.png"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, target)
    print(f"  still: {src.name} -> {target.name}")

    graph = build_graph("northstar_test_still.png", args.prompt, args.negative,
                        width=args.width, height=args.height, length=args.length,
                        seed=args.seed, steps=args.steps, cfg=args.cfg,
                        shift=args.shift, fps=args.fps)
    client_id = "northstar-" + uuid.uuid4().hex[:8]

    peak = {"mb": 0}
    stop = threading.Event()

    def watch() -> None:
        while not stop.is_set():
            used = vram_used_mb()
            if used > peak["mb"]:
                peak["mb"] = used
            time.sleep(1.5)

    watcher = threading.Thread(target=watch, daemon=True)
    watcher.start()

    t0 = time.time()
    queued = post_json("/prompt", {"prompt": graph, "client_id": client_id})
    prompt_id = queued.get("prompt_id")
    if not prompt_id:
        stop.set()
        raise SystemExit(f"queue rejected: {json.dumps(queued)[:600]}")
    print(f"  queued {prompt_id}")

    result = None
    while time.time() - t0 < args.timeout:
        time.sleep(3)
        hist = get_json(f"/history/{prompt_id}")
        if prompt_id in hist:
            result = hist[prompt_id]
            break
        status = result_status = get_json("/queue")
        running = len(status.get("queue_running") or [])
        pending = len(status.get("queue_pending") or [])
        print(f"    {time.time() - t0:6.1f}s  vram {vram_used_mb():5d} MB  "
              f"running={running} pending={pending}", flush=True)
    stop.set()
    wall = time.time() - t0

    if result is None:
        raise SystemExit(f"timeout after {args.timeout}s")

    status = result.get("status", {})
    if status.get("status_str") == "error":
        msgs = [m for m in status.get("messages", []) if m and m[0] == "execution_error"]
        raise SystemExit("render failed: " + json.dumps(msgs)[:1200])

    outputs = result.get("outputs", {})
    # Newer ComfyUI returns {filename, subfolder, type}; the prefix may contain a
    # directory ("northstar/wan"), so always honour subfolder before searching.
    candidates: list[Path] = []
    for node_out in outputs.values():
        for key in ("images", "gifs", "video"):
            for item in node_out.get(key, []) or []:
                if not isinstance(item, dict) or not item.get("filename"):
                    continue
                base = COMFY / "output"
                if item.get("subfolder"):
                    base = base / str(item["subfolder"])
                candidates.append(base / str(item["filename"]))
    produced = next((p for p in candidates if p.exists()), None)
    if produced is None:
        found = sorted((COMFY / "output").rglob("*.webm"), key=lambda p: p.stat().st_mtime,
                       reverse=True)
        produced = found[0] if found else None
    if produced is None:
        raise SystemExit(f"render finished but no output file found: {candidates}")
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(produced, out_path)

    summary = {
        "ok": True,
        "wall_s": round(wall, 1),
        "peak_vram_mb": peak["mb"],
        "frames": args.length,
        "fps": args.fps,
        "seconds_of_video": round(args.length / args.fps, 2),
        "resolution": f"{args.width}x{args.height}",
        "steps": args.steps,
        "seed": args.seed,
        "output": str(out_path),
        "bytes": out_path.stat().st_size,
    }
    if args.summary:
        sp = Path(args.summary)
        sp.parent.mkdir(parents=True, exist_ok=True)
        with sp.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({**summary, "finished": time.strftime("%Y-%m-%dT%H:%M:%S")},
                                ensure_ascii=False) + "\n")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
