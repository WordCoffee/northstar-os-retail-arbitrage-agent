"""Local image generation core — the ARMED half of the creative lane.

This module is the single place that actually renders an image. It is the
counterpart to ``local_image_engine`` (which is read-only status): this one
submits a job, waits, and returns bytes.

Boundaries (all enforced here, not just in the caller):
  * **Localhost only.** The engine URL is ``COMFYUI_URL`` (default
    ``http://127.0.0.1:8188``) and the host is pinned to loopback; a
    non-loopback host is refused. No cloud provider is ever contacted.
  * **Armed only.** ``MEDIA_GEN_LIVE=1`` (honouring the repo ``.env``) is
    required. Without it every call raises ``GenerationError("media_gate_off")``
    before any work happens.
  * **Bounded.** Every network call has a timeout and the poll loop has a
    wall-clock deadline; the response size is capped.
  * **No secrets.** Nothing here reads, logs, or returns a credential. The
    ComfyUI graph references only public model filenames.

The workflow is the same split-file FLUX graph proven by
``tools/local_flux_smoketest.py`` on this machine (UNETLoader +
DualCLIPLoader + VAELoader). It is not invented here.
"""
from __future__ import annotations

import base64
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Dict, Optional
from urllib.parse import urlparse

DEFAULT_COMFY_URL = "http://127.0.0.1:8188"

# Proven split-file FLUX install (see tools/local_flux_smoketest.py). Overridable
# by env for a different install; defaults match what is on this machine.
DEFAULT_UNET = "flux1-dev-fp8.safetensors"
DEFAULT_VAE = "flux-vae-bf16.safetensors"
DEFAULT_CLIP_L = "clip_l.safetensors"
DEFAULT_T5 = "t5xxl_fp8_e4m3fn.safetensors"

DEFAULT_STEPS = 28
MAX_STEPS = 60
MIN_DIM = 256
MAX_DIM = 2048
MAX_IMAGE_BYTES = 32 * 1024 * 1024  # 32 MiB hard cap on a single render
POLL_INTERVAL_S = 2.0
DEFAULT_TIMEOUT_S = 600.0

# Fixed negative prompt — FLUX is guidance-distilled (cfg 1.0); an empty
# negative is correct and avoids inventing failure modes.
NEGATIVE_PROMPT = ""


class GenerationError(RuntimeError):
    """A generation refusal or failure with a stable, honest ``code``."""

    def __init__(self, code: str, message: str, *, status: int = 400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


# --------------------------------------------------------------------------- #
# gate + endpoint helpers
# --------------------------------------------------------------------------- #

def _local_image_engine():
    try:
        import local_image_engine as lie  # Northstar_backend on sys.path
    except ImportError:  # pragma: no cover - repo-root sys.path variant
        from Northstar_backend import local_image_engine as lie
    return lie


def media_gate_on() -> bool:
    """True when MEDIA_GEN_LIVE=1 is in effect (repo .env honoured)."""
    try:
        lie = _local_image_engine()
        lie.apply_env_file_media_flag()
        return bool(lie.media_gate_on())
    except Exception:  # noqa: BLE001 - a gate read failure means "not armed"
        return False


def engine_url() -> str:
    return (os.getenv("COMFYUI_URL", "") or "").strip() or DEFAULT_COMFY_URL


def _assert_loopback(url: str) -> None:
    """Refuse any non-loopback engine host — this lane is localhost-only."""
    try:
        host = (urlparse(url).hostname or "").strip().lower()
    except (ValueError, TypeError):
        host = ""
    if host not in ("127.0.0.1", "localhost", "::1", "0.0.0.0"):
        raise GenerationError(
            "engine_not_localhost",
            f"refused: COMFYUI_URL host {host!r} is not loopback (localhost-only lane)",
            status=400,
        )


def engine_reachable(timeout: float = 1.0) -> bool:
    try:
        _assert_loopback(engine_url())
    except GenerationError:
        return False
    try:
        req = urllib.request.Request(f"{engine_url()}/system_stats",
                                     headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status == 200
    except Exception:  # noqa: BLE001
        return False


# --------------------------------------------------------------------------- #
# workflow
# --------------------------------------------------------------------------- #

def build_flux_workflow(prompt: str, width: int, height: int, steps: int,
                        seed: int, *, prefix: str = "northstar_creative") -> Dict[str, object]:
    """The proven split-file FLUX txt2img graph. Pure — no I/O, easy to test."""
    return {
        "1": {"class_type": "UNETLoader",
              "inputs": {"unet_name": os.getenv("FLUX_UNET", DEFAULT_UNET), "weight_dtype": "default"}},
        "2": {"class_type": "DualCLIPLoader",
              "inputs": {"clip_name1": os.getenv("FLUX_CLIP_L", DEFAULT_CLIP_L),
                         "clip_name2": os.getenv("FLUX_T5", DEFAULT_T5), "type": "flux"}},
        "3": {"class_type": "VAELoader",
              "inputs": {"vae_name": os.getenv("FLUX_VAE", DEFAULT_VAE)}},
        "4": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["2", 0]}},
        "5": {"class_type": "CLIPTextEncode", "inputs": {"text": NEGATIVE_PROMPT, "clip": ["2", 0]}},
        "6": {"class_type": "EmptyLatentImage",
              "inputs": {"width": width, "height": height, "batch_size": 1}},
        "7": {"class_type": "KSampler", "inputs": {
            "seed": seed, "steps": steps, "cfg": 1.0, "sampler_name": "euler",
            "scheduler": "simple", "denoise": 1.0, "model": ["1", 0],
            "positive": ["4", 0], "negative": ["5", 0], "latent_image": ["6", 0]}},
        "8": {"class_type": "VAEDecode", "inputs": {"samples": ["7", 0], "vae": ["3", 0]}},
        "9": {"class_type": "SaveImage",
              "inputs": {"filename_prefix": prefix, "images": ["8", 0]}},
    }


def _validate(prompt: str, width: int, height: int, steps: int) -> None:
    if not (prompt or "").strip():
        raise GenerationError("empty_prompt", "a prompt is required", status=400)
    if len(prompt) > 4000:
        raise GenerationError("prompt_too_long", "prompt exceeds 4000 characters", status=400)
    for name, v in (("width", width), ("height", height)):
        if not isinstance(v, int) or not (MIN_DIM <= v <= MAX_DIM):
            raise GenerationError("bad_dimension",
                                  f"{name} must be an integer in [{MIN_DIM}, {MAX_DIM}]", status=400)
    if not isinstance(steps, int) or not (1 <= steps <= MAX_STEPS):
        raise GenerationError("bad_steps", f"steps must be an integer in [1, {MAX_STEPS}]", status=400)


# --------------------------------------------------------------------------- #
# transport
# --------------------------------------------------------------------------- #

def _post(path: str, body: dict, timeout: float):
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(f"{engine_url()}{path}", data=data,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:  # ComfyUI reports bad graphs as 400 + JSON
        detail = ""
        try:
            detail = e.read().decode("utf-8", errors="replace")[:400]
        except Exception:  # noqa: BLE001
            pass
        raise GenerationError("engine_rejected",
                              f"engine rejected the job (HTTP {e.code}): {detail}", status=502) from e


def _get(path: str, timeout: float = 10.0):
    with urllib.request.urlopen(f"{engine_url()}{path}", timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def _fetch_image(info: dict) -> bytes:
    q = (f"/view?filename={urllib.parse.quote(info.get('filename', ''))}"
         f"&subfolder={urllib.parse.quote(info.get('subfolder', '') or '')}"
         f"&type={urllib.parse.quote(info.get('type', 'output') or 'output')}")
    with urllib.request.urlopen(f"{engine_url()}{q}", timeout=60) as r:
        data = r.read(MAX_IMAGE_BYTES + 1)
    if len(data) > MAX_IMAGE_BYTES:
        raise GenerationError("image_too_large", "rendered image exceeded the size cap", status=502)
    return data


# --------------------------------------------------------------------------- #
# public entrypoint
# --------------------------------------------------------------------------- #

def generate_image(prompt: str, width: int = 1024, height: int = 1024,
                   steps: int = DEFAULT_STEPS, seed: Optional[int] = None,
                   timeout: float = DEFAULT_TIMEOUT_S, *, save_dir: Optional[Path] = None,
                   prefix: str = "northstar_creative") -> Dict[str, object]:
    """Render ONE image locally and return it.

    Returns a dict with ``image_bytes`` (PNG) plus provenance metadata. Raises
    ``GenerationError`` with a stable ``code`` for every refusal/failure.
    """
    _validate(prompt, width, height, steps)

    if not media_gate_on():
        raise GenerationError("media_gate_off",
                              "generation is not armed: set MEDIA_GEN_LIVE=1", status=409)

    _assert_loopback(engine_url())
    if not engine_reachable():
        raise GenerationError("engine_unreachable",
                              f"local engine not reachable at {engine_url()}", status=503)

    if seed is None:
        seed = int(time.time() * 1000) % 2_147_483_647

    wf = build_flux_workflow(prompt, width, height, steps, seed, prefix=prefix)
    t0 = time.time()
    res = _post("/prompt", {"prompt": wf}, timeout=30)
    pid = res.get("prompt_id")
    if not pid:
        raise GenerationError("engine_no_job_id", "engine did not return a prompt_id", status=502)

    deadline = t0 + max(1.0, timeout)
    info = None
    while time.time() < deadline:
        try:
            hist = _get(f"/history/{pid}")
        except Exception:  # noqa: BLE001 - transient; keep polling until deadline
            time.sleep(POLL_INTERVAL_S)
            continue
        entry = hist.get(pid) if isinstance(hist, dict) else None
        if entry and entry.get("outputs"):
            for node in entry["outputs"].values():
                imgs = node.get("images") or []
                if imgs:
                    info = imgs[0]
                    break
            break
        time.sleep(POLL_INTERVAL_S)

    if not info:
        raise GenerationError("timeout",
                              f"no output within {timeout:.0f}s (prompt_id={pid})", status=504)

    data = _fetch_image(info)
    elapsed = round(time.time() - t0, 1)

    saved = None
    if save_dir is not None:
        try:
            save_dir = Path(save_dir)
            save_dir.mkdir(parents=True, exist_ok=True)
            name = f"{prefix}_{pid[:8]}.png"
            (save_dir / name).write_bytes(data)
            saved = str(save_dir / name)
        except OSError:  # a disk problem must not lose a successful render
            saved = None

    return {
        "ok": True,
        "prompt_id": pid,
        "seconds": elapsed,
        "width": width,
        "height": height,
        "steps": steps,
        "seed": seed,
        "engine": engine_url(),
        "filename": info.get("filename"),
        "saved_path": saved,
        "bytes": len(data),
        "mime": "image/png",
        "image_bytes": data,
    }


def to_data_url(result: Dict[str, object]) -> str:
    b64 = base64.b64encode(result["image_bytes"]).decode("ascii")  # type: ignore[arg-type]
    return f"data:{result.get('mime', 'image/png')};base64,{b64}"
