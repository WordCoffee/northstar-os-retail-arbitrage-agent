"""ComfyUI client + Qwen image workflow builders.

This is the *scene generation lane* of the Northstar image/text workflow. It
talks to a local ComfyUI server over HTTP and builds API-format workflow graphs
for:

* **Qwen-Image-2512** (text-to-image) — base product scenes, jars, pouches,
  label zones. Loaded from GGUF via ``UnetLoaderGGUF``.
* **Qwen-Image-Edit-2511** (image edit) — edit an existing render while
  preserving composition (shape, lighting, fill, label area).
* **FLUX.1 dev fp8** fallback — always available on this box.

The graphs mirror ComfyUI's own Qwen blueprints (verified node-for-node), only
swapping ``UNETLoader`` for ``UnetLoaderGGUF`` so the quantized GGUF weights
load. The AI lane never produces final text — that is
``creative.exact_text``'s job.

Nothing here is imported by the FastAPI app unless a route is actually called,
so ``create_app`` stays fast and offline-safe.
"""

from __future__ import annotations

import json
import mimetypes
import os
import random
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Defaults / disk locations
# ---------------------------------------------------------------------------

QWEN_CLIP_DEFAULT = "qwen_2.5_vl_7b_nvfp4.safetensors"
QWEN_VAE_DEFAULT = "qwen_image_vae.safetensors"
QWEN_T2I_UNET_DEFAULT = "qwen-image-2512-Q4_K_M.gguf"
QWEN_EDIT_UNET_DEFAULT = "qwen-image-edit-2511-Q4_K_M.gguf"
FLUX_UNET_DEFAULT = "flux1-dev-fp8.safetensors"


def comfy_base_url() -> str:
    return (os.environ.get("COMFYUI_URL") or "http://127.0.0.1:8188").rstrip("/")


def comfy_dir() -> Path:
    env = os.environ.get("COMFYUI_DIR")
    if env:
        return Path(env)
    for cand in (Path.home() / "ComfyUI", Path("C:/ComfyUI"),
                 Path.home() / "Desktop" / "ComfyUI"):
        if cand.exists():
            return cand
    return Path.home() / "ComfyUI"


def expected_model_paths() -> Dict[str, Path]:
    d = comfy_dir() / "models"
    return {
        "clip": d / "text_encoders" / QWEN_CLIP_DEFAULT,
        "vae": d / "vae" / QWEN_VAE_DEFAULT,
        "t2i_unet": d / "unet" / QWEN_T2I_UNET_DEFAULT,
        "edit_unet": d / "unet" / QWEN_EDIT_UNET_DEFAULT,
        "flux_unet": d / "unet" / FLUX_UNET_DEFAULT,
    }


class ComfyUIError(RuntimeError):
    pass


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

class ComfyClient:
    """Minimal ComfyUI HTTP client (stdlib only — no third-party deps)."""

    def __init__(self, base_url: Optional[str] = None, *, timeout: float = 30.0):
        self.base_url = (base_url or comfy_base_url()).rstrip("/")
        self.timeout = timeout

    # -- low level ---------------------------------------------------------
    def _request(self, method: str, path: str, *, data: Optional[bytes] = None,
                 headers: Optional[Dict[str, str]] = None,
                 timeout: Optional[float] = None) -> bytes:
        url = f"{self.base_url}{path}"
        req = urllib.request.Request(url, data=data, method=method,
                                     headers=headers or {})
        with urllib.request.urlopen(req, timeout=timeout or self.timeout) as resp:
            return resp.read()

    def _json(self, method: str, path: str, payload: Optional[dict] = None) -> Any:
        data = None
        headers: Dict[str, str] = {}
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        raw = self._request(method, path, data=data, headers=headers)
        return json.loads(raw.decode("utf-8")) if raw else None

    # -- status ------------------------------------------------------------
    def is_up(self) -> bool:
        try:
            self._json("GET", "/system_stats")
            return True
        except Exception:
            return False

    def system_stats(self) -> Dict[str, Any]:
        return self._json("GET", "/system_stats") or {}

    def object_info(self, node: Optional[str] = None) -> Dict[str, Any]:
        path = "/object_info" if not node else f"/object_info/{node}"
        return self._json("GET", path) or {}

    def has_node(self, class_type: str) -> bool:
        try:
            return bool(self.object_info(class_type))
        except Exception:
            return False

    # -- upload / queue / fetch -------------------------------------------
    def upload_image(self, path: str | os.PathLike, *, subfolder: str = "",
                     overwrite: bool = True,
                     name: Optional[str] = None) -> str:
        """Upload an image to ComfyUI's input dir. Returns the stored name."""
        p = Path(path)
        if not p.exists():
            raise ComfyUIError(f"upload source not found: {p}")
        name = name or p.name
        boundary = "----northstar" + uuid.uuid4().hex
        ctype = mimetypes.guess_type(str(p))[0] or "application/octet-stream"
        body = bytearray()

        def field(k: str, v: str) -> None:
            body.extend(f"--{boundary}\r\n".encode())
            body.extend(f'Content-Disposition: form-data; name="{k}"\r\n\r\n'.encode())
            body.extend(f"{v}\r\n".encode())

        field("overwrite", "true" if overwrite else "false")
        if subfolder:
            field("subfolder", subfolder)
        body.extend(f"--{boundary}\r\n".encode())
        body.extend(
            f'Content-Disposition: form-data; name="image"; filename="{name}"\r\n'.encode())
        body.extend(f"Content-Type: {ctype}\r\n\r\n".encode())
        body.extend(p.read_bytes())
        body.extend(f"\r\n--{boundary}--\r\n".encode())

        raw = self._request(
            "POST", "/upload/image", data=bytes(body),
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
            timeout=max(self.timeout, 120.0),
        )
        info = json.loads(raw.decode("utf-8")) or {}
        stored = info.get("name") or name
        if info.get("subfolder"):
            stored = f"{info['subfolder']}/{stored}"
        return stored

    def queue_prompt(self, workflow: Dict[str, Any],
                     client_id: Optional[str] = None) -> str:
        payload = {"prompt": workflow, "client_id": client_id or uuid.uuid4().hex}
        result = self._json("POST", "/prompt", payload)
        prompt_id = (result or {}).get("prompt_id")
        if not prompt_id:
            raise ComfyUIError(f"ComfyUI rejected the workflow: {result}")
        return prompt_id

    def history(self, prompt_id: str) -> Dict[str, Any]:
        return self._json("GET", f"/history/{prompt_id}") or {}

    def wait_for(self, prompt_id: str, *, timeout: float = 900.0,
                 poll: float = 1.5) -> Dict[str, Any]:
        deadline = time.time() + timeout
        while time.time() < deadline:
            entry = self.history(prompt_id)
            rec = entry.get(prompt_id)
            if rec and rec.get("outputs"):
                status = (rec.get("status") or {}).get("status_str")
                if status == "error":
                    raise ComfyUIError(f"ComfyUI execution error: {rec.get('status')}")
                return rec
            time.sleep(poll)
        raise ComfyUIError(f"timed out after {timeout:.0f}s waiting for {prompt_id}")

    def fetch_image(self, image_ref: Dict[str, Any]) -> bytes:
        qs = urllib.parse.urlencode({
            "filename": image_ref["filename"],
            "subfolder": image_ref.get("subfolder", ""),
            "type": image_ref.get("type", "output"),
        })
        return self._request("GET", f"/view?{qs}", timeout=max(self.timeout, 120.0))

    def run(self, workflow: Dict[str, Any], *, timeout: float = 900.0) -> bytes:
        """Queue a workflow, wait, and return the first output image's bytes."""
        if not self.is_up():
            raise ComfyUIError(f"ComfyUI not reachable at {self.base_url}")
        prompt_id = self.queue_prompt(workflow)
        rec = self.wait_for(prompt_id, timeout=timeout)
        for _node_id, node_out in (rec.get("outputs") or {}).items():
            images = node_out.get("images")
            if images:
                return self.fetch_image(images[0])
        raise ComfyUIError("workflow completed but produced no image")

    def intercept(self, workflow: Dict[str, Any], *, timeout: float = 60.0) -> Dict[str, Any]:
        """Validation helper: does ComfyUI accept the graph? (no execution)"""
        return self._json("POST", "/prompt", {"prompt": workflow}) or {}


# ---------------------------------------------------------------------------
# Model resolution / validation
# ---------------------------------------------------------------------------

def _choices(obj_info: Dict[str, Any], node: str, input_name: str) -> List[str]:
    try:
        spec = obj_info[node]["input"]["required"][input_name]
        if isinstance(spec, list) and spec and isinstance(spec[0], list):
            return list(spec[0])
    except Exception:
        pass
    return []


def resolve_models(client: Optional[ComfyClient] = None) -> Dict[str, Any]:
    """Report which of the required local models are present and usable.

    Uses ComfyUI's ``/object_info`` when the server is up (authoritative), and
    falls back to checking the expected files on disk when it is not.
    """
    exp = expected_model_paths()
    result: Dict[str, Any] = {
        "comfyui_url": comfy_base_url(),
        "comfyui_dir": str(comfy_dir()),
        "comfy_up": False,
        "gguf_node": False,
        "clip": None, "vae": None, "t2i_unet": None, "edit_unet": None,
        "flux_unet": None,
        "expected": {k: str(v) for k, v in exp.items()},
        "on_disk": {k: v.exists() for k, v in exp.items()},
        "source": "disk",
    }

    clips = unets = vaes = None
    c = client or ComfyClient()
    if c.is_up():
        result["comfy_up"] = True
        result["source"] = "object_info"
        try:
            gguf_info = c.object_info("UnetLoaderGGUF")
            result["gguf_node"] = bool(gguf_info)
            unets = _choices(gguf_info, "UnetLoaderGGUF", "unet_name")
        except Exception:
            unets = None
        try:
            clips = _choices(c.object_info("CLIPLoader"), "CLIPLoader", "clip_name")
        except Exception:
            clips = None
        try:
            vaes = _choices(c.object_info("VAELoader"), "VAELoader", "vae_name")
        except Exception:
            vaes = None

    def pick(preferred: str, available: Optional[List[str]], disk_ok: bool) -> Optional[str]:
        if available is not None:
            if preferred in available:
                return preferred
            named = [a for a in available if a.lower() == preferred.lower()]
            if named:
                return named[0]
            return None
        return preferred if disk_ok else None

    result["clip"] = pick(QWEN_CLIP_DEFAULT, clips, exp["clip"].exists())
    result["vae"] = pick(QWEN_VAE_DEFAULT, vaes, exp["vae"].exists())
    result["t2i_unet"] = pick(QWEN_T2I_UNET_DEFAULT, unets, exp["t2i_unet"].exists())
    result["edit_unet"] = pick(QWEN_EDIT_UNET_DEFAULT, unets, exp["edit_unet"].exists())
    result["flux_unet"] = pick(FLUX_UNET_DEFAULT, unets, exp["flux_unet"].exists())
    result["qwen_ready"] = bool(result["clip"] and result["vae"] and result["t2i_unet"])
    result["qwen_edit_ready"] = bool(result["clip"] and result["vae"] and result["edit_unet"])
    return result


# ---------------------------------------------------------------------------
# Workflow builders (API format)
# ---------------------------------------------------------------------------

def _seed(seed: Optional[int]) -> int:
    return int(seed) if seed is not None else random.randint(0, 2 ** 31 - 1)


def qwen_t2i_workflow(
    prompt: str,
    *,
    negative: str = "",
    width: int = 1024,
    height: int = 1024,
    steps: int = 20,
    cfg: float = 4.0,
    seed: Optional[int] = None,
    sampler: str = "euler",
    scheduler: str = "simple",
    shift: float = 3.1,
    unet_name: str = QWEN_T2I_UNET_DEFAULT,
    clip_name: str = QWEN_CLIP_DEFAULT,
    vae_name: str = QWEN_VAE_DEFAULT,
    filename_prefix: str = "northstar_qwen_t2i",
) -> Dict[str, Any]:
    """Qwen-Image-2512 text-to-image (GGUF UNet)."""
    return {
        "1": {"class_type": "CLIPLoader",
              "inputs": {"clip_name": clip_name, "type": "qwen_image", "device": "default"}},
        "2": {"class_type": "VAELoader", "inputs": {"vae_name": vae_name}},
        "3": {"class_type": "UnetLoaderGGUF", "inputs": {"unet_name": unet_name}},
        "4": {"class_type": "ModelSamplingAuraFlow",
              "inputs": {"model": ["3", 0], "shift": shift}},
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
                         "sampler_name": sampler, "scheduler": scheduler, "denoise": 1.0}},
        "9": {"class_type": "VAEDecode",
              "inputs": {"samples": ["8", 0], "vae": ["2", 0]}},
        "10": {"class_type": "SaveImage",
               "inputs": {"filename_prefix": filename_prefix, "images": ["9", 0]}},
    }


def qwen_edit_workflow(
    prompt: str,
    image_name: str,
    *,
    negative: str = " ",
    steps: int = 20,
    cfg: float = 4.0,
    seed: Optional[int] = None,
    sampler: str = "euler",
    scheduler: str = "simple",
    shift: float = 3.1,
    unet_name: str = QWEN_EDIT_UNET_DEFAULT,
    clip_name: str = QWEN_CLIP_DEFAULT,
    vae_name: str = QWEN_VAE_DEFAULT,
    filename_prefix: str = "northstar_qwen_edit",
) -> Dict[str, Any]:
    """Qwen-Image-Edit-2511 (GGUF UNet), mirroring ComfyUI's 2511 blueprint."""
    return {
        "1": {"class_type": "CLIPLoader",
              "inputs": {"clip_name": clip_name, "type": "qwen_image", "device": "default"}},
        "2": {"class_type": "VAELoader", "inputs": {"vae_name": vae_name}},
        "3": {"class_type": "UnetLoaderGGUF", "inputs": {"unet_name": unet_name}},
        "4": {"class_type": "ModelSamplingAuraFlow",
              "inputs": {"model": ["3", 0], "shift": shift}},
        "5": {"class_type": "CFGNorm", "inputs": {"model": ["4", 0], "strength": 1.0}},
        "6": {"class_type": "LoadImage", "inputs": {"image": image_name}},
        "7": {"class_type": "FluxKontextImageScale", "inputs": {"image": ["6", 0]}},
        "8": {"class_type": "TextEncodeQwenImageEditPlus",
              "inputs": {"clip": ["1", 0], "vae": ["2", 0], "image1": ["7", 0],
                         "image2": None, "image3": None, "prompt": prompt}},
        "9": {"class_type": "TextEncodeQwenImageEditPlus",
              "inputs": {"clip": ["1", 0], "vae": ["2", 0], "image1": ["7", 0],
                         "image2": None, "image3": None, "prompt": negative}},
        "10": {"class_type": "VAEEncode", "inputs": {"pixels": ["7", 0], "vae": ["2", 0]}},
        "11": {"class_type": "KSampler",
               "inputs": {"model": ["5", 0], "positive": ["8", 0], "negative": ["9", 0],
                          "latent_image": ["10", 0], "seed": _seed(seed),
                          "steps": int(steps), "cfg": float(cfg),
                          "sampler_name": sampler, "scheduler": scheduler, "denoise": 1.0}},
        "12": {"class_type": "VAEDecode",
               "inputs": {"samples": ["11", 0], "vae": ["2", 0]}},
        "13": {"class_type": "SaveImage",
               "inputs": {"filename_prefix": filename_prefix, "images": ["12", 0]}},
    }


def flux_t2i_workflow(
    prompt: str,
    *,
    negative: str = "",
    width: int = 1024,
    height: int = 1024,
    steps: int = 20,
    cfg: float = 1.0,
    seed: Optional[int] = None,
    unet_name: str = FLUX_UNET_DEFAULT,
    clip_l: str = "clip_l.safetensors",
    t5xxl: str = "t5xxl_fp8_e4m3fn.safetensors",
    vae_name: str = "ae.safetensors",
    filename_prefix: str = "northstar_flux",
) -> Dict[str, Any]:
    """FLUX.1 dev fallback (standalone UNet + DualCLIPLoader)."""
    return {
        "1": {"class_type": "DualCLIPLoader",
              "inputs": {"clip_name1": clip_l, "clip_name2": t5xxl, "type": "flux"}},
        "2": {"class_type": "VAELoader", "inputs": {"vae_name": vae_name}},
        "3": {"class_type": "UNETLoader",
              "inputs": {"unet_name": unet_name, "weight_dtype": "default"}},
        "4": {"class_type": "CLIPTextEncode",
              "inputs": {"clip": ["1", 0], "text": prompt}},
        "5": {"class_type": "CLIPTextEncode",
              "inputs": {"clip": ["1", 0], "text": negative or " "}},
        "6": {"class_type": "EmptyLatentImage",
              "inputs": {"width": int(width), "height": int(height), "batch_size": 1}},
        "7": {"class_type": "KSampler",
              "inputs": {"model": ["3", 0], "positive": ["4", 0], "negative": ["5", 0],
                         "latent_image": ["6", 0], "seed": _seed(seed),
                         "steps": int(steps), "cfg": float(cfg),
                         "sampler_name": "euler", "scheduler": "simple", "denoise": 1.0}},
        "8": {"class_type": "VAEDecode",
              "inputs": {"samples": ["7", 0], "vae": ["2", 0]}},
        "9": {"class_type": "SaveImage",
              "inputs": {"filename_prefix": filename_prefix, "images": ["8", 0]}},
    }


# ---------------------------------------------------------------------------
# Scene prompt helper
# ---------------------------------------------------------------------------

_NO_TEXT = "no text, no words, no logos, no labels, no icons, no watermarks"


def build_scene_prompt(*, container: Optional[Dict[str, Any]] = None,
                       product: Optional[Dict[str, Any]] = None,
                       extra: str = "",
                       brand: str = "Mogra Organics") -> str:
    """Compose a scene-only prompt: clean product, blank label zone, no text."""
    parts: List[str] = []
    if container and container.get("scene_prompt"):
        parts.append(container["scene_prompt"])
    if product and product.get("scene_words"):
        parts.append(f"containing {product['scene_words']}")
    parts.append(f"premium packaging for the {brand} brand, label area clean and "
                 f"blank, studio product photography, photorealistic")
    if extra:
        parts.append(extra)
    parts.append(_NO_TEXT)
    return ", ".join(parts)


# ---------------------------------------------------------------------------
# High level generate / edit
# ---------------------------------------------------------------------------

def generate_scene(prompt: str, out_path: str | os.PathLike, *,
                   width: int = 1024, height: int = 1024, steps: int = 20,
                   cfg: float = 4.0, seed: Optional[int] = None,
                   negative: str = "", client: Optional[ComfyClient] = None,
                   allow_flux_fallback: bool = True) -> Dict[str, Any]:
    """Generate a base scene PNG with the best available local lane."""
    c = client or ComfyClient()
    models = resolve_models(c)
    if not models["comfy_up"]:
        raise ComfyUIError(
            f"ComfyUI is not running at {comfy_base_url()}. Start it, or upload "
            f"your own base image instead."
        )
    if models["qwen_ready"] and models["gguf_node"]:
        wf = qwen_t2i_workflow(prompt, negative=negative, width=width, height=height,
                               steps=steps, cfg=cfg, seed=seed,
                               unet_name=models["t2i_unet"],
                               clip_name=models["clip"], vae_name=models["vae"])
        lane = "qwen-image-2512"
    elif allow_flux_fallback and models["flux_unet"]:
        wf = flux_t2i_workflow(prompt, negative=negative, width=width, height=height,
                               steps=steps, seed=seed)
        lane = "flux1-dev"
    else:
        raise ComfyUIError(
            "No usable local scene generator: Qwen-Image-2512 GGUF + encoder + VAE "
            "or FLUX fallback must be present. See docs/NORTHSTAR_IMAGE_TEXT_WORKFLOW.md."
        )
    data = c.run(wf)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(data)
    return {"lane": lane, "output": str(out_path), "size": [width, height],
            "seed": seed, "prompt": prompt}


def edit_scene(prompt: str, source_path: str | os.PathLike,
               out_path: str | os.PathLike, *, steps: int = 20, cfg: float = 4.0,
               seed: Optional[int] = None, client: Optional[ComfyClient] = None,
               unet_name: Optional[str] = None, clip_name: Optional[str] = None,
               vae_name: Optional[str] = None) -> Dict[str, Any]:
    """Edit an existing render with Qwen-Image-Edit-2511 (GGUF)."""
    c = client or ComfyClient()
    models = resolve_models(c)
    if not models["qwen_edit_ready"] or not models["gguf_node"]:
        raise ComfyUIError(
            "Qwen-Image-Edit-2511 GGUF + Qwen encoder + VAE not all present. "
            f"Expected: {expected_model_paths()['edit_unet']}"
        )
    if not c.is_up():
        raise ComfyUIError(f"ComfyUI is not running at {comfy_base_url()}.")
    name = c.upload_image(source_path)
    wf = qwen_edit_workflow(prompt, name, steps=steps, cfg=cfg, seed=seed,
                            unet_name=unet_name or models["edit_unet"],
                            clip_name=clip_name or models["clip"],
                            vae_name=vae_name or models["vae"])
    data = c.run(wf)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(data)
    return {"lane": "qwen-image-edit-2511", "output": str(out_path),
            "source": str(source_path), "prompt": prompt, "seed": seed}
