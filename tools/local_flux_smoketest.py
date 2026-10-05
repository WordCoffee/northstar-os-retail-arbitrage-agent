"""Local FLUX smoke test — submits ONE txt2img job to the localhost ComfyUI.

Localhost-only, image-only, one job. This is the "first real generation" step and
is owner-gated: by default it only prints the workflow (dry-run); it submits to
ComfyUI only with --yes.

Usage:
    python tools/local_flux_smoketest.py --prompt "a red ceramic coffee mug on a pine table"      # dry-run
    python tools/local_flux_smoketest.py --prompt "..." --yes                                     # submit ONE job

It never contacts a cloud provider, never reads secrets, and never publishes.
Output lands in <COMFYUI_HOME>/output/ (localhost ComfyUI only).
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.request
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from Northstar_backend import local_image_engine as lie  # noqa: E402

COMFY_URL = "http://127.0.0.1:8188"
UNET = "flux1-dev-fp8.safetensors"
VAE = "flux-vae-bf16.safetensors"
CLIP_L = "clip_l.safetensors"
T5 = "t5xxl_fp8_e4m3fn.safetensors"


def build_workflow(prompt: str, width: int, height: int, steps: int, seed: int) -> dict:
    """A minimal FLUX txt2img graph for the split-file install."""
    return {
        "1": {"class_type": "UNETLoader", "inputs": {"unet_name": UNET, "weight_dtype": "default"}},
        "2": {"class_type": "DualCLIPLoader", "inputs": {"clip_name1": CLIP_L, "clip_name2": T5, "type": "flux"}},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": VAE}},
        "4": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["2", 0]}},
        "5": {"class_type": "CLIPTextEncode", "inputs": {"text": "", "clip": ["2", 0]}},
        "6": {"class_type": "EmptyLatentImage", "inputs": {"width": width, "height": height, "batch_size": 1}},
        "7": {"class_type": "KSampler", "inputs": {
            "seed": seed, "steps": steps, "cfg": 1.0, "sampler_name": "euler", "scheduler": "simple",
            "denoise": 1.0, "model": ["1", 0], "positive": ["4", 0], "negative": ["5", 0], "latent_image": ["6", 0]}},
        "8": {"class_type": "VAEDecode", "inputs": {"samples": ["7", 0], "vae": ["3", 0]}},
        "9": {"class_type": "SaveImage", "inputs": {"filename_prefix": "northstar_smoke", "images": ["8", 0]}},
    }


def _get(path: str, timeout: float = 10.0):
    with urllib.request.urlopen(f"{COMFY_URL}{path}", timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def _post(path: str, body: dict, timeout: float = 30.0):
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(f"{COMFY_URL}{path}", data=data,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Local FLUX smoke test (localhost, one image).")
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--width", type=int, default=1024)
    ap.add_argument("--height", type=int, default=1024)
    ap.add_argument("--steps", type=int, default=20)
    ap.add_argument("--seed", type=int, default=int(time.time()) % 1_000_000)
    ap.add_argument("--yes", action="store_true", help="actually submit ONE job (owner-gated)")
    ap.add_argument("--timeout", type=int, default=600, help="seconds to wait for completion")
    args = ap.parse_args(argv)

    lie.apply_env_file_media_flag()
    status = lie.build_status()
    print(f"engine_reachable: {status['items'][2]['state']}  media_gate: {'on' if lie.media_gate_on() else 'off'}")
    if not args.yes:
        print("\nDRY RUN — workflow that would be submitted (nothing is generated):")
        print(json.dumps(build_workflow(args.prompt, args.width, args.height, args.steps, args.seed), indent=2))
        print("\nRe-run with --yes to submit ONE job to the localhost ComfyUI.")
        return 0

    if status["items"][2]["state"] != "reachable":
        print("Refusing: local engine not reachable. Start ComfyUI first.", file=sys.stderr)
        return 2
    if not lie.media_gate_on():
        print("Refusing: MEDIA_GEN_LIVE is not set to 1 (gate off).", file=sys.stderr)
        return 2

    wf = build_workflow(args.prompt, args.width, args.height, args.steps, args.seed)
    t0 = time.time()
    res = _post("/prompt", {"prompt": wf})
    pid = res.get("prompt_id")
    print(f"queued prompt_id={pid} — waiting (localhost, one job)…")

    deadline = t0 + args.timeout
    outputs = []
    while time.time() < deadline:
        hist = _get(f"/history/{pid}")
        entry = hist.get(pid) if isinstance(hist, dict) else None
        if entry and entry.get("outputs"):
            for node in entry["outputs"].values():
                for img in node.get("images", []) or []:
                    outputs.append(img.get("filename"))
            break
        time.sleep(2)

    dt = time.time() - t0
    if not outputs:
        print(f"timed out after {dt:.0f}s — no output produced.", file=sys.stderr)
        return 1
    home = lie.resolve_comfyui_home()
    print(f"done in {dt:.1f}s — {len(outputs)} image(s):")
    for f in outputs:
        p = (home / "output" / f) if home else None
        print(f"  {f}  ({p})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
