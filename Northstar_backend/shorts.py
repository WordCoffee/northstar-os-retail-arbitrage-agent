"""Shorts: 9:16 image-to-video on the installed Wan 2.2 TI2V 5B, frame-gated.

Social and YouTube Shorts need motion, and the weights for it are already on this
machine: `Wan2.2-TI2V-5B-Q5_K_M.gguf` (3.5 GB) with its `umt5` text encoder and
`wan2.2_vae`. Nothing is downloaded and nothing leaves the box.

The lane returns three things, because a video that "ran" is not a video that
shipped:

  * the WEBM the sampler produced,
  * a handful of decoded frames,
  * the same measurable evidence the still lanes use (size, frames, fps, steps).

Frames are written as PNG as well as muxed, so the caller can run the OCR and
quality gate on them exactly as it does on a still. A 5B model at 9:16 is slow;
the defaults here are deliberately small and the caller decides what to spend.
"""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

WAN_UNET = "Wan2.2-TI2V-5B-Q5_K_M.gguf"
WAN_CLIP = "umt5-xxl-encoder-Q5_K_M.gguf"
WAN_VAE = "wan2.2_vae.safetensors"

DEFAULT_PROMPT = "the product rotates slowly, soft studio lighting, premium packaging film"
DEFAULT_NEGATIVE = "static, blurry, distorted, text artefacts, watermark, flicker"

#: Wan counts frames as 4n+1; 33 frames at 16 fps is a two-second vertical clip.
FRAME_STEP = 4
DEFAULT_FRAMES = 33
DEFAULT_FPS = 16


def frame_count(length: int) -> int:
    """Round a requested frame count to the 4n+1 the Wan latent accepts."""
    n = max(9, int(length))
    return n - ((n - 1) % FRAME_STEP)


def build_graph(image_name: str, *, prompt: str = DEFAULT_PROMPT,
                negative: str = DEFAULT_NEGATIVE, width: int = 480, height: int = 832,
                length: int = DEFAULT_FRAMES, steps: int = 24, cfg: float = 5.0,
                shift: float = 8.0, seed: int = 1,
                fps: int = DEFAULT_FPS) -> Dict[str, Any]:
    """The ComfyUI graph, as data, so the wiring can be asserted offline."""
    frames = frame_count(length)
    stamp = int(time.time())
    return {
        "1": {"class_type": "UnetLoaderGGUF", "inputs": {"unet_name": WAN_UNET}},
        "2": {"class_type": "CLIPLoaderGGUF",
              "inputs": {"clip_name": WAN_CLIP, "type": "wan"}},
        "3": {"class_type": "CLIPTextEncode",
              "inputs": {"text": str(prompt), "clip": ["2", 0]}},
        "4": {"class_type": "CLIPTextEncode",
              "inputs": {"text": str(negative), "clip": ["2", 0]}},
        "5": {"class_type": "VAELoader", "inputs": {"vae_name": WAN_VAE}},
        "6": {"class_type": "LoadImage", "inputs": {"image": image_name}},
        "7": {"class_type": "Wan22ImageToVideoLatent",
              "inputs": {"vae": ["5", 0], "width": int(width), "height": int(height),
                         "length": frames, "batch_size": 1, "start_image": ["6", 0]}},
        "8": {"class_type": "ModelSamplingSD3",
              "inputs": {"model": ["1", 0], "shift": float(shift)}},
        "9": {"class_type": "KSampler",
              "inputs": {"model": ["8", 0], "positive": ["3", 0], "negative": ["4", 0],
                         "latent_image": ["7", 0], "seed": int(seed),
                         "steps": int(steps), "cfg": float(cfg),
                         "sampler_name": "euler", "scheduler": "simple",
                         "denoise": 1.0}},
        "10": {"class_type": "VAEDecode",
               "inputs": {"samples": ["9", 0], "vae": ["5", 0]}},
        "11": {"class_type": "SaveWEBM",
               "inputs": {"images": ["10", 0], "filename_prefix": f"ns_short_{stamp}",
                          "codec": "vp9", "fps": float(fps), "crf": 20.0}},
        "12": {"class_type": "SaveImage",
               "inputs": {"images": ["10", 0], "filename_prefix": f"ns_short_frame_{stamp}"}},
    }


def generate(png: bytes, *, prompt: str = DEFAULT_PROMPT,
             negative: str = DEFAULT_NEGATIVE, width: int = 480, height: int = 832,
             length: int = DEFAULT_FRAMES, steps: int = 24, cfg: float = 5.0,
             seed: int = 1, fps: int = DEFAULT_FPS,
             timeout_s: float = 2400.0,
             keep_frames: int = 3) -> Dict[str, Any]:
    """Render one vertical clip. Returns the video, sampled frames and metadata."""
    import studio_generation as sg

    if not sg.media_live_armed():
        raise RuntimeError("media_generation_disarmed (MEDIA_GEN_LIVE is not 1)")
    name = sg.upload_image(png, filename=f"ns_short_src_{int(time.time())}.png")
    graph = build_graph(name, prompt=prompt, negative=negative, width=width,
                        height=height, length=length, steps=steps, cfg=cfg,
                        seed=seed, fps=fps)
    started = time.time()
    files = sg._run_graph(graph, timeout_s)
    if not files:
        raise RuntimeError("the video lane returned no file")

    video: Optional[bytes] = None
    frames: List[bytes] = []
    for item in files:
        fname = str(item.get("filename") or "")
        data = None
        try:
            data = sg._fetch_output(item)
        except Exception:  # noqa: BLE001 - a missing side file must not lose the video
            continue
        if fname.lower().endswith((".webm", ".mp4")):
            video = data
        elif fname.lower().endswith((".png", ".jpg", ".jpeg")):
            frames.append(data)
    if video is None and not frames:
        raise RuntimeError("the video lane produced no video and no frames")

    # Keep the first, middle and last frame: enough to spot a collapsed clip
    # without shipping 33 PNGs to the gate.
    picked: List[bytes] = []
    if frames:
        idx = sorted({0, len(frames) // 2, len(frames) - 1})[:max(1, keep_frames)]
        picked = [frames[i] for i in idx]
    return {"video": video, "frames": picked, "frame_count": frame_count(length),
            "fps": int(fps), "size": [int(width), int(height)], "steps": int(steps),
            "cfg": float(cfg), "seed": int(seed), "model": WAN_UNET,
            "seconds": round(time.time() - started, 1),
            "video_bytes": len(video or b"")}


def package_render(result: Dict[str, Any], *, brief: str, text_requested: bool,
                   expected_terms: Optional[List[str]] = None,
                   run_id: Optional[str] = None, out_root: Optional[Any] = None) -> Dict[str, Any]:
    """Gate the clip on a decoded frame and package it, or write nothing.

    A video that ran is not a video that shipped: the middle frame goes through
    the same five-axis gate as a still, and a failing verdict leaves the
    filesystem untouched.
    """
    import json
    import re
    from pathlib import Path

    import quality_gate as qg

    root = Path(out_root) if out_root else Path(__file__).resolve().parents[1] / "state" / "deliverables"
    frames = result.get("frames") or []
    if not frames:
        raise RuntimeError("shorts_package_needs_a_frame: the lane returned no frames")
    probe = frames[len(frames) // 2]
    scored = qg.score(probe, brief=brief, requested_form="", text_requested=text_requested,
                      expected_terms=expected_terms or [])
    verdict = qg.verdict(scored)

    rid = re.sub(r"[^A-Za-z0-9._-]+", "_", str(run_id or f"short_{int(time.time())}"))
    folder = root / rid
    if not verdict["ok"]:
        return {"folder": None, "verdict": verdict, "quality": qg.manifest_block(scored, verdict),
                "reason": "quality gate refused the clip; nothing was written"}
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "short.webm").write_bytes(result.get("video") or b"")
    frame_names = []
    for i, frame in enumerate(frames):
        name = f"frame_{i:02d}.png"
        (folder / name).write_bytes(frame)
        frame_names.append(name)
    manifest = {
        "run_id": rid,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "kind": "shorts_clip",
        "model": result.get("model"),
        "size": result.get("size"),
        "frames": result.get("frame_count"),
        "fps": result.get("fps"),
        "duration_seconds": round(float(result.get("frame_count") or 0) / max(1, int(result.get("fps") or 16)), 2),
        "steps": result.get("steps"),
        "cfg": result.get("cfg"),
        "seed": result.get("seed"),
        "video_bytes": result.get("video_bytes"),
        "render_seconds": result.get("seconds"),
        "quality": qg.manifest_block(scored, verdict),
        "dieline": {"built": False, "reason": "motion clip; no print dieline applies"},
        "color_profile": {"working": "RGB", "target": "sRGB", "converted": False},
        "files": ["short.webm"] + frame_names + ["manifest.json"],
    }
    (folder / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return {"folder": str(folder), "manifest": manifest, "verdict": verdict}


__all__ = ["WAN_UNET", "WAN_CLIP", "WAN_VAE", "DEFAULT_FRAMES", "DEFAULT_FPS",
           "frame_count", "build_graph", "generate", "package_render"]
