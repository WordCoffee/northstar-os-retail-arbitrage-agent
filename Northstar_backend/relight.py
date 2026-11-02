"""Studio relighting via the installed IC-Light SD1.5 unets.

The brief asks for "studio-grade directional lighting with soft drop shadows and
realistic reflections". This lane relights a product cut-out with the IC-Light
weights already on disk (iclight_sd15_fc / fbc + the SD1.5 CLIP and VAE), inside
ComfyUI, and returns the lit PNG. Nothing leaves the machine.

The graph is deliberately small: prep the reference, encode it, apply the
IC-Light unet, sample, decode. The SD1.5 base checkpoint is NOT required — the
IC-Light unet is the model — but the CLIP and VAE are, and both are present.
"""
from __future__ import annotations

import time
from typing import Any, Dict, List

IC_MODEL = "iclight_sd15_fc_unet_ldm.safetensors"
CLIP_FILE = "clip_l.safetensors"
VAE_FILE = "vae-ft-mse-840000-ema-pruned.safetensors"

NEGATIVE = ("low quality, blurry, distorted product, extra objects, text, "
            "watermark, cut off, deformed")

#: A lighting brief, not a scene brief: IC-Light reads the prompt as illumination.
DEFAULT_PROMPT = ("soft directional studio light from the upper left, gentle falloff, "
                  "neutral background, subtle contact shadow, product photography")


def build_graph(image_name: str, *, prompt: str = DEFAULT_PROMPT,
                negative: str = NEGATIVE, width: int = 1024, height: int = 1024,
                steps: int = 24, cfg: float = 2.0, seed: int = 1,
                border: int = 64) -> Dict[str, Any]:
    """The ComfyUI graph. Pure data, so it can be asserted in tests."""
    return {
        "1": {"class_type": "LoadImage", "inputs": {"image": image_name}},
        "2": {"class_type": "ImagePrepForICLora",
              "inputs": {"reference_image": ["1", 0], "output_width": int(width),
                         "output_height": int(height), "border_width": int(border)}},
        "3": {"class_type": "VAEEncode",
              "inputs": {"pixels": ["2", 0], "vae": ["10", 0]}},
        "4": {"class_type": "UNETLoader",
              "inputs": {"unet_name": IC_MODEL, "weight_dtype": "default"}},
        "5": {"class_type": "CLIPLoader",
              "inputs": {"clip_name": CLIP_FILE, "type": "stable_diffusion"}},
        "6": {"class_type": "CLIPTextEncode",
              "inputs": {"text": str(prompt), "clip": ["5", 0]}},
        "7": {"class_type": "CLIPTextEncode",
              "inputs": {"text": str(negative), "clip": ["5", 0]}},
        "8": {"class_type": "ICLightAppply",
              "inputs": {"model": ["4", 0], "ic_model": ["4", 0], "c_concat": ["3", 0]}},
        "9": {"class_type": "KSampler",
              "inputs": {"model": ["8", 0], "positive": ["6", 0], "negative": ["7", 0],
                         # IC-Light FC samples the reference latent itself: the concat
                         # prepped by node 2 carries the subject and the light map.
                         "latent_image": ["3", 0], "seed": int(seed),
                         "steps": int(steps), "cfg": float(cfg),
                         "sampler_name": "dpmpp_2m", "scheduler": "karras",
                         "denoise": 1.0}},
        "10": {"class_type": "VAELoader", "inputs": {"vae_name": VAE_FILE}},
        "11": {"class_type": "VAEDecode",
               "inputs": {"samples": ["9", 0], "vae": ["10", 0]}},
        "12": {"class_type": "SaveImage",
               "inputs": {"images": ["11", 0],
                          "filename_prefix": f"ns_relight_{int(time.time())}"}},
        "13": {"class_type": "EmptyLatentImage",
               "inputs": {"width": int(width), "height": int(height), "batch_size": 1}},
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


#: Above this the output is noise, not a render (measured 3.6 vs 58.98).
NOISE_LIMIT = 25.0


class RelightUnavailable(RuntimeError):
    """The lane produced something that cannot be shipped."""


def assert_usable(png: bytes) -> float:
    metric = noise_metric(png)
    if metric > NOISE_LIMIT:
        raise RelightUnavailable(
            f"relight_output_is_noise: high-frequency energy {metric} exceeds "
            f"{NOISE_LIMIT}; the installed IC-Light graph does not decode to an "
            "image yet (see reports/ for the probe evidence)")
    return metric


def relight(png: bytes, *, prompt: str = DEFAULT_PROMPT,
            width: int = 1024, height: int = 1024, steps: int = 24,
            cfg: float = 2.0, seed: int = 1, timeout_s: float = 1200.0) -> Dict[str, Any]:
    """Relight one product image. Refuses when the output is not an image."""
    import studio_generation as sg

    if not sg.media_live_armed():
        raise RuntimeError("media_generation_disarmed (MEDIA_GEN_LIVE is not 1)")
    name = sg.upload_image(png, filename=f"ns_relight_src_{int(time.time())}.png")
    graph = build_graph(name, prompt=prompt, width=width, height=height,
                        steps=steps, cfg=cfg, seed=seed)
    started = time.time()
    files = sg._run_graph(graph, timeout_s)
    if not files:
        raise RuntimeError("the relight lane returned no file")
    out = sg._fetch_output(files[0])
    metric = assert_usable(out)
    return {"png": out, "model": IC_MODEL, "prompt": str(prompt)[:300],
            "size": [int(width), int(height)], "steps": int(steps), "cfg": float(cfg),
            "seed": int(seed), "seconds": round(time.time() - started, 1),
            "noise_metric": metric}


__all__ = ["IC_MODEL", "CLIP_FILE", "VAE_FILE", "DEFAULT_PROMPT", "NOISE_LIMIT",
           "build_graph", "relight", "noise_metric", "assert_usable", "RelightUnavailable"]
