"""Local media generation for the Design Studio — the operator's own ComfyUI.

Free and private by construction: every render happens on this machine through
COMFYUI_URL (default http://127.0.0.1:8199) and nothing else. Armed only when
MEDIA_GEN_LIVE=1 AND ComfyUI answers. Models are the weights this machine
already has staged:

  image : FLUX.2 klein 4B Q8 (Apache-2.0, commercial-ok)   -> PNG
  video : Wan 2.2 TI2V-5B Q5_K_M (short clips)             -> MP4

The workflow graphs are the same ones verified by tools/comfy_smoke.py.
No provider keys are read here; no credential value is ever touched.
"""

from __future__ import annotations

import json
import os
import random
import time
import urllib.parse
import urllib.request
import uuid

DEFAULT_COMFYUI_URL = "http://127.0.0.1:8199"  # this box's ComfyUI (8188 is upstream default)

IMAGE_MODEL_FILE = "flux-2-klein-4b-Q8_0.gguf"
VIDEO_MODEL_FILE = "Wan2.2-TI2V-5B-Q5_K_M.gguf"

_STYLE_SUFFIX = ", professional commercial product photography, clean composition, no text, no watermark, no logos"


def comfyui_url() -> str:
    return (os.environ.get("COMFYUI_URL") or DEFAULT_COMFYUI_URL).rstrip("/")


def media_live_armed() -> bool:
    return str(os.environ.get("MEDIA_GEN_LIVE", "") or "").strip() == "1"


def _reachable(url: str, timeout: float = 3.0) -> bool:
    try:
        with urllib.request.urlopen(url + "/system_stats", timeout=timeout) as r:
            return r.status == 200
    except Exception:
        return False


def engine_status() -> dict:
    """Honest engine state for the studio. Unknown is NOT armed."""
    url = comfyui_url()
    live = media_live_armed()
    up = _reachable(url)
    return {
        "engine": "comfyui",
        "url": url,
        "url_configured": bool(os.environ.get("COMFYUI_URL")),
        "gate": live,             # MEDIA_GEN_LIVE=1
        "reachable": up,
        "armed": bool(live and up),
        "models": {"image": IMAGE_MODEL_FILE, "video": VIDEO_MODEL_FILE},
        "note": (
            "The local engine is armed: renders run on this machine's GPU (ComfyUI)."
            if (live and up) else
            (f"Armed but unreachable at {url} - start ComfyUI." if live else
             "Unarmed: MEDIA_GEN_LIVE is not 1.")
        ),
    }


# ── ComfyUI client ─────────────────────────────────────────────────────────

def _api(path: str, payload=None, timeout: float = 60.0):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        comfyui_url() + path, data=data, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def _run_graph(graph: dict, timeout_s: float) -> list:
    res = _api("/prompt", {"prompt": graph, "client_id": f"ns-studio-{uuid.uuid4().hex[:10]}"}, timeout=30)
    if res.get("node_errors"):
        raise RuntimeError(f"graph rejected: {json.dumps(res['node_errors'])[:400]}")
    pid = res["prompt_id"]
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        time.sleep(3)
        try:
            hist = _api(f"/history/{pid}", timeout=30)
        except Exception:
            continue
        if pid in hist:
            status = hist[pid].get("status", {}) or {}
            if status.get("status_str") != "success":
                raise RuntimeError(f"generation failed: {json.dumps(status)[:400]}")
            files = []
            for node_out in (hist[pid].get("outputs") or {}).values():
                for key in ("images", "gifs", "videos"):
                    for item in node_out.get(key) or []:
                        if isinstance(item, dict) and item.get("filename"):
                            files.append(item)
            return files
    raise TimeoutError("timed out waiting for the ComfyUI render")


def _fetch_output(item: dict) -> bytes:
    q = urllib.parse.urlencode({
        "filename": item.get("filename"),
        "subfolder": item.get("subfolder", ""),
        "type": item.get("type", "output"),
    })
    with urllib.request.urlopen(comfyui_url() + "/view?" + q, timeout=300) as r:
        return r.read()


def _clamp(v, lo: int, hi: int, mult: int = 16) -> int:
    v = int(v)
    v = max(lo, min(hi, v))
    return max(mult, (v // mult) * mult)


# ── Workflow graphs (verified by tools/comfy_smoke.py) ─────────────────────

def _klein_graph(prompt: str, width: int, height: int, steps: int, seed: int) -> dict:
    return {
        "1": {"class_type": "UnetLoaderGGUF", "inputs": {"unet_name": IMAGE_MODEL_FILE}},
        "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": "qwen_3_4b_fp8_mixed.safetensors", "type": "flux2", "device": "default"}},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": "flux2-vae.safetensors"}},
        "4": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["2", 0], "text": prompt + _STYLE_SUFFIX}},
        "5": {"class_type": "ConditioningZeroOut", "inputs": {"conditioning": ["4", 0]}},
        "6": {"class_type": "EmptyFlux2LatentImage", "inputs": {"width": width, "height": height, "batch_size": 1}},
        "7": {"class_type": "CFGGuider", "inputs": {"model": ["1", 0], "positive": ["4", 0], "negative": ["5", 0], "cfg": 1}},
        "8": {"class_type": "KSamplerSelect", "inputs": {"sampler_name": "euler"}},
        "9": {"class_type": "Flux2Scheduler", "inputs": {"steps": steps, "width": width, "height": height}},
        "10": {"class_type": "RandomNoise", "inputs": {"noise_seed": seed}},
        "11": {"class_type": "SamplerCustomAdvanced", "inputs": {"noise": ["10", 0], "guider": ["7", 0], "sampler": ["8", 0], "sigmas": ["9", 0], "latent_image": ["6", 0]}},
        "12": {"class_type": "VAEDecode", "inputs": {"samples": ["11", 0], "vae": ["3", 0]}},
        "13": {"class_type": "SaveImage", "inputs": {"images": ["12", 0], "filename_prefix": "ns-studio"}},
    }


def _wan_graph(prompt: str, width: int, height: int, frames: int, steps: int, seed: int) -> dict:
    return {
        "1": {"class_type": "UnetLoaderGGUF", "inputs": {"unet_name": VIDEO_MODEL_FILE}},
        "2": {"class_type": "CLIPLoaderGGUF", "inputs": {"clip_name": "umt5-xxl-encoder-Q5_K_M.gguf", "type": "wan"}},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": "wan2.2_vae.safetensors"}},
        "4": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["2", 0], "text": prompt + _STYLE_SUFFIX}},
        "5": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["2", 0], "text": "blurry, low quality, static, watermark"}},
        "6": {"class_type": "ModelSamplingSD3", "inputs": {"model": ["1", 0], "shift": 8}},
        "7": {"class_type": "Wan22ImageToVideoLatent", "inputs": {"vae": ["3", 0], "width": width, "height": height, "length": frames, "batch_size": 1}},
        "8": {"class_type": "KSampler", "inputs": {"model": ["6", 0], "positive": ["4", 0], "negative": ["5", 0], "latent_image": ["7", 0], "seed": seed, "steps": steps, "cfg": 5, "sampler_name": "uni_pc", "scheduler": "simple", "denoise": 1}},
        "9": {"class_type": "VAEDecode", "inputs": {"samples": ["8", 0], "vae": ["3", 0]}},
        "10": {"class_type": "CreateVideo", "inputs": {"images": ["9", 0], "fps": 24}},
        "11": {"class_type": "SaveVideo", "inputs": {"video": ["10", 0], "filename_prefix": "ns-studio", "format": "auto", "codec": "auto"}},
    }


# ── Public generation entries ──────────────────────────────────────────────

def generate_image(prompt: str, width=None, height=None, tier: str = "draft", seed=None) -> dict:
    if not media_live_armed():
        raise RuntimeError("media_generation_disarmed (MEDIA_GEN_LIVE is not 1)")
    w = _clamp(width or 1024, 512, 1216)
    h = _clamp(height or 1024, 512, 1216)
    steps = 8 if str(tier).lower() == "final" else 4
    seed = int(seed) if seed is not None else random.randrange(1, 2 ** 31)
    files = _run_graph(_klein_graph(prompt, w, h, steps, seed), timeout_s=1800)
    img = next((f for f in files if str(f.get("filename", "")).lower().endswith((".png", ".jpg", ".webp"))), None)
    if not img:
        raise RuntimeError("the render finished but produced no image output")
    return {
        "bytes": _fetch_output(img), "ext": "png", "mime": "image/png",
        "model": "flux-2-klein-4b-q8", "provider": "comfyui",
        "seed": seed, "width": w, "height": h, "duration_seconds": None,
    }


def generate_video(prompt: str, width=None, height=None, tier: str = "draft", seed=None) -> dict:
    if not media_live_armed():
        raise RuntimeError("media_generation_disarmed (MEDIA_GEN_LIVE is not 1)")
    w = _clamp(width or 832, 512, 1280)
    h = _clamp(height or 480, 480, 736)
    frames = 97 if str(tier).lower() == "final" else 49   # 4n+1 for the Wan latent; ~2s / ~4s at 24fps
    steps = 20
    seed = int(seed) if seed is not None else random.randrange(1, 2 ** 31)
    files = _run_graph(_wan_graph(prompt, w, h, frames, steps, seed), timeout_s=5400)
    vid = next((f for f in files if str(f.get("filename", "")).lower().endswith((".mp4", ".webm"))), None)
    if not vid:
        raise RuntimeError("the render finished but produced no video output")
    return {
        "bytes": _fetch_output(vid), "ext": "mp4", "mime": "video/mp4",
        "model": "wan2.2-ti2v-5b-q5", "provider": "comfyui",
        "seed": seed, "width": w, "height": h, "duration_seconds": round(frames / 24.0, 1),
    }
