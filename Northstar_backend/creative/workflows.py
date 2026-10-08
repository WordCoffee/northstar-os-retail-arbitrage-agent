"""Workflow builders for the additional approved model families (SDXL, Z-Image).

Kept separate from ``comfy_client`` (which owns the Qwen/FLUX lane) so model
families stay explicit: *SDXL adapters are never assumed to work with Z-Image*,
and vice-versa.

Each builder returns a ComfyUI API-format graph. The node names are validated
against ``/object_info`` at run time by ``comfy_client.ComfyClient.run``; if a
required node is missing, the lane fails honestly rather than silently.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from . import comfy_client


def _seed(seed: Optional[int]) -> int:
    return comfy_client._seed(seed)  # type: ignore[attr-defined]


def sdxl_t2i(
    prompt: str,
    *,
    negative: str = "",
    width: int = 1024,
    height: int = 1024,
    steps: int = 25,
    cfg: float = 7.0,
    seed: Optional[int] = None,
    sampler: str = "dpmpp_2m",
    scheduler: str = "karras",
    checkpoint: str = "sd_xl_base_1.0.safetensors",
    filename_prefix: str = "northstar_sdxl",
    controlnet: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """SDXL Base 1.0 text-to-image (optional ControlNet preprocessor output)."""
    g: Dict[str, Any] = {
        "1": {"class_type": "CheckpointLoaderSimple",
              "inputs": {"ckpt_name": checkpoint}},
        "2": {"class_type": "CLIPTextEncode",
              "inputs": {"clip": ["1", 1], "text": prompt}},
        "3": {"class_type": "CLIPTextEncode",
              "inputs": {"clip": ["1", 1], "text": negative or " "}},
        "4": {"class_type": "EmptyLatentImage",
              "inputs": {"width": int(width), "height": int(height), "batch_size": 1}},
        "7": {"class_type": "VAEDecode",
              "inputs": {"samples": ["6", 0], "vae": ["1", 2]}},
        "8": {"class_type": "SaveImage",
              "inputs": {"filename_prefix": filename_prefix, "images": ["7", 0]}},
    }
    model_ref: Any = ["1", 0]
    pos_ref: Any = ["2", 0]
    neg_ref: Any = ["3", 0]
    if controlnet:
        # controlnet = {"image": <uploaded name>, "type": "canny", "strength": 0.6,
        #               "control_model": "xinsir-canny-sdxl.safetensors"}
        g["10"] = {"class_type": "LoadImage",
                   "inputs": {"image": controlnet["image"]}}
        g["11"] = {"class_type": "ControlNetLoader",
                   "inputs": {"control_net_name": controlnet.get(
                       "control_model", "xinsir-canny-sdxl.safetensors")}}
        pre = controlnet.get("type", "canny")
        prep_node = {"canny": "Canny",
                     "depth": "DepthAnythingV2Preprocessor",
                     "openpose": "OpenposePreprocessor"}.get(pre)
        ctrl_image_ref: Any = ["10", 0]
        if prep_node:
            prep_inputs: Dict[str, Any] = {"image": ["10", 0]}
            if prep_node == "Canny":
                prep_inputs["low_threshold"] = float(controlnet.get("low_threshold", 0.4))
                prep_inputs["high_threshold"] = float(controlnet.get("high_threshold", 0.8))
            g["12"] = {"class_type": prep_node, "inputs": prep_inputs}
            ctrl_image_ref = ["12", 0]
        g["13"] = {"class_type": "ControlNetApplyAdvanced",
                   "inputs": {"positive": ["2", 0], "negative": ["3", 0],
                              "control_net": ["11", 0], "image": ctrl_image_ref,
                              "strength": float(controlnet.get("strength", 0.6)),
                              "start_percent": 0.0, "end_percent": 1.0}}
        pos_ref = ["13", 0]
        neg_ref = ["13", 1]
    g["6"] = {"class_type": "KSampler",
              "inputs": {"model": model_ref, "positive": pos_ref, "negative": neg_ref,
                         "latent_image": ["4", 0], "seed": _seed(seed),
                         "steps": int(steps), "cfg": float(cfg),
                         "sampler_name": sampler, "scheduler": scheduler,
                         "denoise": 1.0}}
    return g


def z_image_t2i(
    prompt: str,
    *,
    negative: str = "",
    width: int = 1024,
    height: int = 1024,
    steps: int = 8,
    cfg: float = 1.0,
    seed: Optional[int] = None,
    sampler: str = "euler",
    scheduler: str = "simple",
    shift: float = 3.0,
    unet_name: str = "z_image_turbo_nvfp4.safetensors",
    clip_name: str = "qwen_3_4b_fp8_mixed.safetensors",
    vae_name: str = "ae.safetensors",
    filename_prefix: str = "northstar_zimage",
) -> Dict[str, Any]:
    """Z-Image-Turbo (8 NFEs, CFG 1), matching the official ComfyUI graph:
    UNETLoader + CLIPLoader(type=lumina2) + VAELoader(ae) + ModelSamplingAuraFlow.
    """
    return {
        "1": {"class_type": "CLIPLoader",
              "inputs": {"clip_name": clip_name, "type": "lumina2",
                         "device": "default"}},
        "2": {"class_type": "VAELoader", "inputs": {"vae_name": vae_name}},
        "3": comfy_client._unet_loader(unet_name),  # type: ignore[attr-defined]
        "4": {"class_type": "ModelSamplingAuraFlow",
              "inputs": {"model": ["3", 0], "shift": float(shift)}},
        "5": {"class_type": "CLIPTextEncode",
              "inputs": {"clip": ["1", 0], "text": prompt}},
        "6": {"class_type": "CLIPTextEncode",
              "inputs": {"clip": ["1", 0], "text": negative or " "}},
        "7": {"class_type": "EmptySD3LatentImage",
              "inputs": {"width": int(width), "height": int(height), "batch_size": 1}},
        "8": {"class_type": "KSampler",
              "inputs": {"model": ["4", 0], "positive": ["5", 0], "negative": ["6", 0],
                         "latent_image": ["7", 0], "seed": _seed(seed),
                         "steps": int(steps), "cfg": float(cfg),
                         "sampler_name": sampler, "scheduler": scheduler,
                         "denoise": 1.0}},
        "9": {"class_type": "VAEDecode",
              "inputs": {"samples": ["8", 0], "vae": ["2", 0]}},
        "10": {"class_type": "SaveImage",
               "inputs": {"filename_prefix": filename_prefix, "images": ["9", 0]}},
    }


def sdxl_ipadapter_t2i(
    prompt: str,
    *,
    reference_image: str,
    negative: str = "",
    width: int = 1024,
    height: int = 1024,
    steps: int = 25,
    cfg: float = 7.0,
    seed: Optional[int] = None,
    sampler: str = "dpmpp_2m",
    scheduler: str = "karras",
    checkpoint: str = "sd_xl_base_1.0.safetensors",
    preset: str = "PLUS (high strength)",
    weight: float = 0.8,
    filename_prefix: str = "northstar_sdxl_ip",
) -> Dict[str, Any]:
    """SDXL text-to-image conditioned on a reference image via IP-Adapter Plus."""
    return {
        "1": {"class_type": "CheckpointLoaderSimple",
              "inputs": {"ckpt_name": checkpoint}},
        "2": {"class_type": "IPAdapterUnifiedLoader",
              "inputs": {"model": ["1", 0], "preset": preset}},
        "3": {"class_type": "LoadImage", "inputs": {"image": reference_image}},
        "4": {"class_type": "IPAdapter",
              "inputs": {"model": ["2", 0], "ipadapter": ["2", 1], "image": ["3", 0],
                         "weight": float(weight), "start_at": 0.0, "end_at": 1.0,
                         "weight_type": "standard"}},
        "5": {"class_type": "CLIPTextEncode",
              "inputs": {"clip": ["1", 1], "text": prompt}},
        "6": {"class_type": "CLIPTextEncode",
              "inputs": {"clip": ["1", 1], "text": negative or " "}},
        "7": {"class_type": "EmptyLatentImage",
              "inputs": {"width": int(width), "height": int(height), "batch_size": 1}},
        "8": {"class_type": "KSampler",
              "inputs": {"model": ["4", 0], "positive": ["5", 0], "negative": ["6", 0],
                         "latent_image": ["7", 0], "seed": _seed(seed),
                         "steps": int(steps), "cfg": float(cfg),
                         "sampler_name": sampler, "scheduler": scheduler,
                         "denoise": 1.0}},
        "9": {"class_type": "VAEDecode",
              "inputs": {"samples": ["8", 0], "vae": ["1", 2]}},
        "10": {"class_type": "SaveImage",
               "inputs": {"filename_prefix": filename_prefix, "images": ["9", 0]}},
    }


def upscale_image(
    image_name: str,
    *,
    model_name: str = "RealESRGAN_x4plus.pth",
    filename_prefix: str = "northstar_upscale",
) -> Dict[str, Any]:
    """Real-ESRGAN (or any ComfyUI upscale model) via built-in nodes."""
    return {
        "1": {"class_type": "LoadImage", "inputs": {"image": image_name}},
        "2": {"class_type": "UpscaleModelLoader", "inputs": {"model_name": model_name}},
        "3": {"class_type": "ImageUpscaleWithModel",
              "inputs": {"upscale_model": ["2", 0], "image": ["1", 0]}},
        "4": {"class_type": "SaveImage",
              "inputs": {"filename_prefix": filename_prefix, "images": ["3", 0]}},
    }


def remove_background(
    image_name: str,
    *,
    model_name: str = "birefnet.safetensors",
    filename_prefix: str = "northstar_mask",
    cutout: bool = True,
) -> Dict[str, Any]:
    """BiRefNet foreground mask (and optional RGBA cutout) via built-in nodes."""
    g: Dict[str, Any] = {
        "1": {"class_type": "LoadImage", "inputs": {"image": image_name}},
        "2": {"class_type": "LoadBackgroundRemovalModel",
              "inputs": {"bg_removal_name": model_name}},
        "3": {"class_type": "RemoveBackground",
              "inputs": {"bg_removal_model": ["2", 0], "image": ["1", 0]}},
        "4": {"class_type": "MaskToImage", "inputs": {"mask": ["3", 0]}},
        "5": {"class_type": "SaveImage",
              "inputs": {"filename_prefix": filename_prefix + "_mask", "images": ["4", 0]}},
    }
    if cutout:
        # JoinImageWithAlpha computes alpha = 1 - mask, so invert the foreground
        # mask first to get an opaque foreground / transparent background PNG.
        g["6"] = {"class_type": "InvertMask", "inputs": {"mask": ["3", 0]}}
        g["7"] = {"class_type": "JoinImageWithAlpha",
                  "inputs": {"image": ["1", 0], "alpha": ["6", 0]}}
        g["8"] = {"class_type": "SaveImage",
                  "inputs": {"filename_prefix": filename_prefix + "_cutout",
                             "images": ["7", 0]}}
    return g


def build(workflow: str, prompt: str, **kwargs) -> Dict[str, Any]:
    if workflow == "sdxl_t2i":
        return sdxl_t2i(prompt, **kwargs)
    if workflow == "z_image_t2i":
        return z_image_t2i(prompt, **kwargs)
    if workflow == "qwen_t2i":
        return comfy_client.qwen_t2i_workflow(prompt, **kwargs)
    if workflow == "qwen_edit":
        image_name = kwargs.pop("image_name")
        return comfy_client.qwen_edit_workflow(prompt, image_name, **kwargs)
    raise ValueError(f"unknown workflow: {workflow}")
