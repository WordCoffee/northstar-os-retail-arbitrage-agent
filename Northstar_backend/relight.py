"""Studio relighting via IC-Light, wired the way the node pack specifies.

The first attempt failed for a reason worth recording: `ICLightApply` does not
load the IC-Light unet as the model. It **patches a base SD1.5 checkpoint** with
the IC-Light weights (`ic_light_nodes.py`: `work_model = model.clone()` then
`add_patches` with the ic_model state dict), and it expects `c_concat` to be the
foreground with its masked area painted grey. Passing the IC-Light unet as the
base model produced colour noise at every sampler setting - the graph was valid,
the semantics were not.

This module follows `examples/fg.json` from the pack:

    LoadImage -> BiRefNet mask -> ICLightApplyMaskGrey -> VAEEncodeArgMax (c_concat)
    CheckpointLoaderSimple (SD1.5) + UNETLoader (iclight) -> ICLightApply
    EmptyLatentImage -> KSampler(denoise 0.9, dpmpp_2m_sde/karras) -> VAEDecode

Output is measured before it is returned: a noise decode raises rather than
shipping (see `noise_metric`).
"""
from __future__ import annotations

import shutil
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

#: A base SD1.5 checkpoint is required; the IC-Light unet is a patch, not a model.
BASE_CHECKPOINT = "Realistic_Vision_V6.0_NV_B1_fp16.safetensors"
IC_MODEL = "iclight_sd15_fc_unet_ldm.safetensors"
BG_MODEL = "birefnet.safetensors"

NEGATIVE = ("low quality, blurry, distorted product, extra objects, text, "
            "watermark, cut off, deformed, flat lighting")

#: The prompt describes light and surface, not a scene: IC-Light reads it as illumination.
DEFAULT_PROMPT = ("product photography, soft directional studio light from the upper left, "
                  "gentle falloff, neutral grey background, subtle contact shadow")

#: Above this the output is noise, not a render (measured 3.6 vs 58.98 on 2026-11-02).
NOISE_LIMIT = 25.0

#: A file below its floor is a partial download, not a model. A truncated
#: checkpoint loads as garbage or aborts the engine; checking size is cheaper.
MIN_BYTES = {
    "checkpoints": 1_500_000_000,
    "unet": 500_000_000,
    "background_removal": 200_000_000,
}


class RelightUnavailable(RuntimeError):
    """The lane cannot run, or produced something that cannot be shipped."""


def _models_dir() -> Path:
    import studio_generation as sg
    root = Path(getattr(sg, "COMFYUI_ROOT", r"C:\Users\T2Hol\ComfyUI"))
    return root / "models"


def availability() -> Dict[str, Any]:
    """Which files this lane needs, and whether they are complete on disk."""
    wanted = {
        "checkpoints": BASE_CHECKPOINT,
        "unet": IC_MODEL,
        "background_removal": BG_MODEL,
    }
    missing: List[str] = []
    partial: List[str] = []
    for folder, name in wanted.items():
        path = _models_dir() / folder / name
        if not path.is_file():
            missing.append(name)
        elif path.stat().st_size < MIN_BYTES[folder]:
            partial.append(f"{name} ({path.stat().st_size / 1e9:.2f} GB)")
    problems = ([f"missing {missing}"] if missing else []) + \
               ([f"partial {partial}"] if partial else [])
    return {"available": not problems, "missing": missing, "partial": partial,
            "base_checkpoint": BASE_CHECKPOINT, "ic_model": IC_MODEL,
            "reason": (None if not problems else
                       "relight_checkpoint_missing: " + "; ".join(problems))}


def build_graph(image_name: str, *, prompt: str = DEFAULT_PROMPT,
                negative: str = NEGATIVE, width: int = 1024, height: int = 1024,
                steps: int = 25, cfg: float = 2.0, seed: int = 1,
                denoise: float = 0.9) -> Dict[str, Any]:
    """The ComfyUI graph, as data, following the pack's own fg example."""
    return {
        "1": {"class_type": "LoadImage", "inputs": {"image": image_name}},
        # Every latent in the graph must share one size: the source is rescaled to
        # the requested canvas before the mask, or c_concat and the empty latent
        # disagree (measured: "Expected size 96 but got size 128").
        "2": {"class_type": "ImageScale",
              "inputs": {"image": ["1", 0], "upscale_method": "lanczos",
                         "width": int(width), "height": int(height),
                         "crop": "disabled"}},
        "3": {"class_type": "LoadBackgroundRemovalModel",
              "inputs": {"bg_removal_name": BG_MODEL}},
        "4": {"class_type": "RemoveBackground",
              "inputs": {"bg_removal_model": ["3", 0], "image": ["2", 0]}},
        # IC-Light FC requires the masked area to be GREY before the VAE, or the
        # background bleeds into the relight (pack README, verbatim).
        "5": {"class_type": "ICLightApplyMaskGrey",
              "inputs": {"image": ["2", 0], "alpha": ["4", 0]}},
        "6": {"class_type": "VAEEncodeArgMax",
              "inputs": {"pixels": ["5", 0], "vae": ["7", 2]}},
        "7": {"class_type": "CheckpointLoaderSimple",
              "inputs": {"ckpt_name": BASE_CHECKPOINT}},
        "8": {"class_type": "CLIPTextEncode",
              "inputs": {"text": str(prompt), "clip": ["7", 1]}},
        "9": {"class_type": "CLIPTextEncode",
              "inputs": {"text": str(negative), "clip": ["7", 1]}},
        "10": {"class_type": "UNETLoader",
               "inputs": {"unet_name": IC_MODEL, "weight_dtype": "default"}},
        "11": {"class_type": "ICLightAppply",
               "inputs": {"model": ["7", 0], "ic_model": ["10", 0],
                          "c_concat": ["6", 0]}},
        "12": {"class_type": "EmptyLatentImage",
               "inputs": {"width": int(width), "height": int(height), "batch_size": 1}},
        "13": {"class_type": "KSampler",
               "inputs": {"model": ["11", 0], "positive": ["8", 0], "negative": ["9", 0],
                          "latent_image": ["12", 0], "seed": int(seed),
                          "steps": int(steps), "cfg": float(cfg),
                          "sampler_name": "dpmpp_2m_sde", "scheduler": "karras",
                          "denoise": float(denoise)}},
        "14": {"class_type": "VAEDecode",
               "inputs": {"samples": ["13", 0], "vae": ["7", 2]}},
        "15": {"class_type": "SaveImage",
               "inputs": {"images": ["14", 0],
                          "filename_prefix": f"ns_relight_{int(time.time())}"}},
    }


def noise_metric(png: bytes) -> float:
    """High-frequency energy of a 128px greyscale thumbnail.

    Measured on this box: a real product render scores 3.6, a failed relight that
    decoded to colour noise scored 58.98. The metric exists so a lane can refuse
    to hand back garbage it cannot otherwise detect.
    """
    import io
    from PIL import Image, ImageChops, ImageStat

    with Image.open(io.BytesIO(png)) as im:
        small = im.convert("L").resize((128, 128))
    dx = ImageChops.difference(small, ImageChops.offset(small, 1, 0))
    dy = ImageChops.difference(small, ImageChops.offset(small, 0, 1))
    return round((ImageStat.Stat(dx).mean[0] + ImageStat.Stat(dy).mean[0]) / 2, 2)


def assert_usable(png: bytes) -> float:
    metric = noise_metric(png)
    if metric > NOISE_LIMIT:
        raise RelightUnavailable(
            f"relight_output_is_noise: high-frequency energy {metric} exceeds "
            f"{NOISE_LIMIT}; the graph decoded to noise instead of an image")
    return metric


def relight(png: bytes, *, prompt: str = DEFAULT_PROMPT,
            width: int = 1024, height: int = 1024, steps: int = 25,
            cfg: float = 2.0, seed: int = 1, denoise: float = 0.9,
            timeout_s: float = 1200.0) -> Dict[str, Any]:
    """Relight one product image. Refuses when the lane cannot run or the output is noise."""
    import studio_generation as sg

    state = availability()
    if not state["available"]:
        raise RelightUnavailable(state["reason"])
    if not sg.media_live_armed():
        raise RuntimeError("media_generation_disarmed (MEDIA_GEN_LIVE is not 1)")
    name = sg.upload_image(png, filename=f"ns_relight_src_{int(time.time())}.png")
    graph = build_graph(name, prompt=prompt, width=width, height=height,
                        steps=steps, cfg=cfg, seed=seed, denoise=denoise)
    started = time.time()
    files = sg._run_graph(graph, timeout_s)
    if not files:
        raise RuntimeError("the relight lane returned no file")
    out = sg._fetch_output(files[0])
    metric = assert_usable(out)
    return {"png": out, "base_checkpoint": BASE_CHECKPOINT, "ic_model": IC_MODEL,
            "prompt": str(prompt)[:300], "size": [int(width), int(height)],
            "steps": int(steps), "cfg": float(cfg), "seed": int(seed),
            "denoise": float(denoise), "seconds": round(time.time() - started, 1),
            "noise_metric": metric}


def package(result: Dict[str, Any], *, source_asset_id: Optional[str] = None,
            brief: str = "", out_root: Optional[Any] = None,
            run_id: Optional[str] = None) -> Dict[str, Any]:
    """Gate the relit image and package it, or write nothing.

    Typography is deliberately out of scope here: copy is composited later by the
    deterministic lanes, so an inherited label is not "unwanted text". The axes
    this lane can actually speak to are alignment, layout and material.
    """
    import json
    import re
    from pathlib import Path

    import quality_gate as qg

    scored = qg.score(result["png"], brief=brief or "relit product photograph",
                      requested_form="", text_requested=False)
    axes = {
        "form": {"status": "not_applicable", "reason": "relight_of_existing_product"},
        "design_alignment": scored["axes"]["design_alignment"],
        "layout": scored["axes"]["layout"],
        "typography": {"status": "not_applicable", "reason": "copy_composited_later"},
        "material": scored["axes"]["material"],
    }
    verdict = qg.verdict({"axes": axes, "available": scored.get("available"),
                          "model": scored.get("model")})
    root = Path(out_root) if out_root else Path(__file__).resolve().parents[1] / "state" / "deliverables"
    rid = re.sub(r"[^A-Za-z0-9._-]+", "_", str(run_id or f"relight_{int(time.time())}"))
    folder = root / rid
    if not verdict["ok"]:
        return {"folder": None, "verdict": verdict,
                "quality": qg.manifest_block(scored, verdict),
                "reason": "quality gate refused the relight; nothing was written"}
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "relit.png").write_bytes(result["png"])
    manifest = {
        "run_id": rid,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "kind": "relight",
        "base_checkpoint": result.get("base_checkpoint"),
        "ic_model": result.get("ic_model"),
        "prompt": result.get("prompt"),
        "size": result.get("size"),
        "steps": result.get("steps"),
        "cfg": result.get("cfg"),
        "denoise": result.get("denoise"),
        "seed": result.get("seed"),
        "render_seconds": result.get("seconds"),
        "noise_metric": result.get("noise_metric"),
        "quality": qg.manifest_block(scored, verdict),
        "dieline": {"built": False, "reason": "relit mockup; no print dieline applies"},
        "color_profile": {"working": "RGB", "target": "sRGB", "converted": False},
        "files": ["relit.png", "manifest.json"],
    }
    if source_asset_id:
        manifest["source_asset_id"] = source_asset_id
    (folder / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return {"folder": str(folder), "manifest": manifest, "verdict": verdict}


__all__ = ["BASE_CHECKPOINT", "IC_MODEL", "BG_MODEL", "DEFAULT_PROMPT", "NOISE_LIMIT",
           "RelightUnavailable", "availability", "build_graph", "relight", "package",
           "noise_metric", "assert_usable"]
