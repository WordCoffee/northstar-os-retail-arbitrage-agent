"""Scene rendering for the composite path: the product is real, only the scene is generated.

Every render here goes through ``tools/comfy_lane.py``: a fresh ComfyUI process is
started for the job, stopped afterwards, and the stop is *verified* (the lane's
own check waits for port 8188 to close). A lane that cannot start, or whose stop
cannot be proved, raises instead of returning a picture — a replayed image dressed
as a composite is exactly the failure this path exists to prevent.

GPU work takes the ``tools/gpu_budget.py`` lock first, so two heavy jobs never run
at once. No network, no download, no spend: the FLUX 3 weights are already on disk
and the model's licence is recorded in ``provenance.csv``.

``synthetic_scene`` exists for tests and for the honest offline fallback: it is a
deterministic PIL backdrop, it never claims to be generated, and a brief produced
that way is ``cannot_verify``.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

ROOT = Path(__file__).resolve().parents[2]
for _extra in (str(ROOT), str(ROOT / "tools"), str(ROOT / "Northstar_backend")):
    if _extra not in sys.path:
        sys.path.insert(0, _extra)

SCENE_NEGATIVE = ("product, packaging, bottle, pouch, jar, box, text, letters, "
                  "wordmark, logo, watermark, person, hands")
SITUATION_SCENES = {
    "white_background_main": ("a seamless pure white studio sweep, one soft shadow area, "
                              "even light, empty, no objects, no text, product photography"),
    "lifestyle": ("an empty sunlit kitchen counter by a window, pale linen surface, soft "
                  "morning light from the left, blurred greenery outside, no objects, no text"),
    "infographic": ("an empty matte slate-coloured studio panel with soft even light, "
                    "no objects, no text, generous empty space"),
    "scale_reference": ("an empty pale concrete surface with a soft neutral backdrop and "
                        "even light, no objects, no text"),
    "bundle_multipack": ("an empty warm oak table top against a plain plaster wall, soft "
                         "daylight, no objects, no text"),
    "packaging_mockup": ("an empty dusk forest clearing with soft mist and low warm light, "
                         "photographic, no objects, no text"),
    "background_swap": ("an empty soft beige studio background with a gentle gradient floor, "
                        "no objects, no text"),
    "series_consistency": ("an empty studio table with a plain neutral backdrop, even light, "
                           "no objects, no text"),
}


def scene_prompt(brief: Dict[str, Any]) -> str:
    """The prompt for an empty scene: the product is composited in afterwards."""
    explicit = str(brief.get("scene_prompt") or "").strip()
    if explicit:
        return explicit
    situation = str(brief.get("situation") or "")
    return SITUATION_SCENES.get(situation, SITUATION_SCENES["lifestyle"])


def full_prompt(brief: Dict[str, Any]) -> str:
    """The prompt for a full generation, used only where exact fidelity is not required."""
    explicit = str(brief.get("prompt") or "").strip()
    if explicit:
        return explicit
    subject = str((brief.get("reference") or {}).get("descriptor", {}).get("subject")
                  or brief.get("category") or "a product").strip()
    return (f"professional product photograph of {subject}, "
            f"{SITUATION_SCENES.get(str(brief.get('situation') or ''), '')}, "
            "realistic materials, studio lighting, no text overlay")


def lane_ready() -> Tuple[bool, str]:
    """Can this box start its own ComfyUI? A stated reason when it cannot."""
    try:
        import comfy_lane  # noqa: PLC0415

        home = Path(comfy_lane.COMFY_HOME)
        python = home / "venv" / "Scripts" / "python.exe"
        main = home / "main.py"
        if not python.is_file() or not main.is_file():
            return False, f"ComfyUI runtime not found under {home}"
        if comfy_lane.reachable():
            return False, ("ComfyUI is already running; a lane starts its own instance so it "
                           "can prove it stopped the one it used")
        return True, f"lane can start from {home}"
    except Exception as exc:  # noqa: BLE001 - reported, never guessed
        return False, f"lane probe failed: {type(exc).__name__}: {exc}"


def _free_ram_gb() -> Optional[float]:
    try:
        import gpu_budget  # noqa: PLC0415

        memory = gpu_budget.ram()
        return float(memory.get("free_gb") or 0.0) if memory.get("ok") else None
    except Exception:  # noqa: BLE001
        return None


SDXL_CKPT = "sd_xl_base_1.0.safetensors"
REALISTIC_CKPT = "Realistic_Vision_V6.0_NV_B1_fp16.safetensors"

CHECKPOINTS = {
    "sdxl": {"ckpt": SDXL_CKPT, "width": 1536, "height": 1536, "steps": 24, "cfg": 7.0},
    "realistic": {"ckpt": REALISTIC_CKPT, "width": 640, "height": 640, "steps": 25,
                  "cfg": 7.0},
}

#: VRAM a model needs at 1024^2, and the extra it needs per additional megapixel.
#: This is the model's *need*, not the machine's headroom: the headroom is measured
#: from nvidia-smi by the lane on every run and the two are subtracted there.
MODEL_VRAM_GB = {
    "sdxl": (5.2, 3.0),
    "realistic": (3.2, 1.2),
    "flux3": (11.0, 1.4),
}


def needed_vram_gb(model: str, width: int, height: int) -> Optional[float]:
    spec = MODEL_VRAM_GB.get(model)
    if spec is None:
        return None
    base, per_mp = spec
    megapixels = max(1.0, (int(width) * int(height)) / float(1024 * 1024))
    return round(base + per_mp * megapixels, 2)


def checkpoint_graph(ckpt: str, prompt: str, *, negative: str = SCENE_NEGATIVE,
                     width: int = 768, height: int = 768, steps: int = 20,
                     cfg: float = 7.0, seed: int = 0) -> Dict[str, Any]:
    """The classic checkpoint text-to-image graph.

    Kept alongside FLUX 3 because the nvfp4/aimdo loader failed here
    (`Fault failed: 2`, `hostbuf_file_reader_read failed`) while another model held
    ~7 GB of VRAM and RAM. The ordinary checkpoint path is the fallback that still
    fits the headroom, and a 2 GB checkpoint (SD 1.5) fits where a 7 GB one did not.
    """
    return {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": ckpt}},
        "2": {"class_type": "CLIPTextEncode",
              "inputs": {"text": prompt, "clip": ["1", 1]}},
        "3": {"class_type": "CLIPTextEncode",
              "inputs": {"text": negative, "clip": ["1", 1]}},
        "4": {"class_type": "EmptyLatentImage",
              "inputs": {"width": int(width), "height": int(height), "batch_size": 1}},
        "5": {"class_type": "KSampler",
              "inputs": {"model": ["1", 0], "seed": int(seed), "steps": int(steps),
                         "cfg": float(cfg), "sampler_name": "euler",
                         "scheduler": "normal", "denoise": 1.0,
                         "positive": ["2", 0], "negative": ["3", 0],
                         "latent_image": ["4", 0]}},
        "6": {"class_type": "VAEDecode",
              "inputs": {"samples": ["5", 0], "vae": ["1", 2]}},
        "7": {"class_type": "SaveImage",
              "inputs": {"images": ["6", 0], "filename_prefix": "ns-scene"}},
    }


def sdxl_graph(prompt: str, *, negative: str = SCENE_NEGATIVE, width: int = 768,
               height: int = 768, steps: int = 20, seed: int = 0) -> Dict[str, Any]:
    """SDXL at its named defaults (kept for callers and tests)."""
    return checkpoint_graph(SDXL_CKPT, prompt, negative=negative, width=width,
                            height=height, steps=steps, seed=seed)


def _run_graph(graph: Dict[str, Any], *, url: str = "http://127.0.0.1:8188",
               timeout: float = 900.0) -> Dict[str, Any]:
    """Queue one graph on a ComfyUI that is already running and wait for its image."""
    import json
    import time
    import urllib.request
    import uuid

    client_id = uuid.uuid4().hex
    payload = json.dumps({"prompt": graph, "client_id": client_id}).encode("utf-8")
    request = urllib.request.Request(url.rstrip("/") + "/prompt", data=payload,
                                     headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=30) as response:
        queued = json.loads(response.read().decode("utf-8", "replace") or "{}")
    prompt_id = queued.get("prompt_id")
    if not prompt_id:
        raise RuntimeError(f"ComfyUI rejected the graph: {queued}")
    deadline = time.time() + timeout
    while time.time() < deadline:
        with urllib.request.urlopen(url.rstrip("/") + "/history/" + prompt_id,
                                    timeout=15) as log:
            history = json.loads(log.read().decode("utf-8", "replace") or "{}")
        entry = history.get(prompt_id) or {}
        status = entry.get("status") or {}
        if status.get("status_str") == "error":
            raise RuntimeError(f"render failed: {status.get('messages')}")
        images = [image for node in (entry.get("outputs") or {}).values()
                  for image in (node.get("images") or []) if image.get("type") == "output"]
        if images:
            return {"images": [str((Path(r"C:\Users\T2Hol\ComfyUI\output")
                                    / (i.get("subfolder") or "") / i["filename"]).resolve())
                               for i in images],
                    "prompt_id": prompt_id}
        time.sleep(1.0)
    raise RuntimeError("timed out waiting for the render")


def render_scene(prompt: str, *, width: int = 768, height: int = 768,
                 steps: int = 8, seed: Optional[int] = None,
                 timeout: float = 900.0,
                 inside_lane: Optional[Any] = None,
                 model: str = "sdxl",
                 watchlist: Optional[list] = None) -> Dict[str, Any]:
    """One generated scene through a lane this call owns. Raises when it cannot.

    ``inside_lane`` is an optional callable run *inside* the lane, before the
    render. The composite path uses it to matte the product with BiRefNet on the
    same fresh instance, so one lane serves cutout and scene and the stop is still
    proved once.

    ``model`` is ``sdxl`` / ``realistic`` (classic checkpoint graph) or ``flux3``
    (the FLUX 3 graph). All are already on disk; the choice is a runtime fact
    about headroom, not a capability claim.
    """
    from .generators import GeneratorUnavailable

    try:
        import comfy_lane  # noqa: PLC0415
        import gpu_budget  # noqa: PLC0415
    except Exception as exc:  # noqa: BLE001
        raise GeneratorUnavailable(f"render lane unavailable: {type(exc).__name__}: {exc}")

    ram_free = _free_ram_gb()
    if ram_free is not None and ram_free < 3.0:
        raise GeneratorUnavailable(
            f"render refused: {ram_free:.1f} GB free RAM is below the 3 GB floor")
    ready, reason = lane_ready()
    if not ready:
        raise GeneratorUnavailable(f"render lane unavailable: {reason}")

    lock = gpu_budget.lock("seller_composite", ttl_s=1800)
    if not lock.get("ok"):
        raise GeneratorUnavailable(
            f"gpu locked by {lock.get('held_by')}; no render was attempted")
    try:
        def _work() -> Dict[str, Any]:
            side: Dict[str, Any] = {}
            if inside_lane is not None:
                side["inside_lane"] = inside_lane()
            if model == "flux3":
                from flux3_gateway import generate  # noqa: PLC0415

                side["render"] = generate(prompt, width=int(width), height=int(height),
                                          steps=int(steps), seed=seed,
                                          negative=SCENE_NEGATIVE, timeout=timeout)
            elif model in CHECKPOINTS:
                spec = CHECKPOINTS[model]
                chosen = int(seed) if seed is not None else int.from_bytes(
                    os.urandom(4), "big")
                rendered = _run_graph(
                    checkpoint_graph(spec["ckpt"], prompt, width=int(width),
                                     height=int(height), steps=int(steps),
                                     cfg=float(spec["cfg"]), seed=chosen),
                    timeout=timeout)
                side["render"] = {**rendered, "seed": chosen, "steps": int(steps),
                                  "width": int(width), "height": int(height)}
            else:
                raise RuntimeError(f"unknown scene model {model!r}")
            return side

        outcome = comfy_lane.lane(
            _work, needed_gb=needed_vram_gb(model, width, height),
            role=f"scene:{model}",
            watchlist=list(watchlist) if watchlist is not None else None)
    finally:
        gpu_budget.unlock("seller_composite")

    if not outcome.get("ok"):
        raise GeneratorUnavailable(f"render lane failed: {outcome.get('reason')}")
    lane_row = outcome.get("lane") or {}
    stopped = lane_row.get("stopped") or {}
    if not stopped.get("ok") or not stopped.get("stopped"):
        raise GeneratorUnavailable(
            f"render lane did not prove it released the process: {stopped.get('reason')}")
    combined = outcome.get("result") or {}
    result = combined.get("render") or {}
    images = result.get("images") or []
    if not images:
        raise GeneratorUnavailable("render lane returned no image path")
    data = Path(images[0]).read_bytes()
    return {"bytes": data, "source": "generated", "prompt": prompt,
            "model": model,
            "width": int(result.get("width") or width),
            "height": int(result.get("height") or height),
            "seed": result.get("seed"), "steps": int(result.get("steps") or steps),
            "image_path": str(images[0]), "lane": lane_row,
            "inside_lane": combined.get("inside_lane")}


class ComfySceneRenderer:
    """Default renderer: a fresh ComfyUI lane per brief, stop verified.

    SDXL at **1536** is the default because it was measured rendering at that size
    on this box with the lane empty (see reports/ty/sel01d_white_canvas_gpu.md).
    That makes the scene the brief's own size instead of a 768 render resampled up.

    FLUX 3's nvfp4 loader (comfy-aimdo ``vbar``) failed on this box (`Fault failed:
    2`) while another model held 7 GB of VRAM; the classic checkpoint path does not
    share that failure mode. FLUX 3 remains selectable with ``model="flux3"`` and a
    failure there is raised with the gateway's own error, never replayed.

    The lane refuses before it starts when the measured free VRAM cannot hold
    ``needed_vram_gb(model, width, height)`` plus the 1 GB reserve.
    """

    def __init__(self, *, width: int = 1536, height: int = 1536, steps: int = 24,
                 seed: Optional[int] = None, model: str = "sdxl") -> None:
        self.width, self.height, self.steps, self.seed = width, height, steps, seed
        self.model = model

    def __call__(self, brief: Dict[str, Any], mode: str = "scene",
                 inside_lane: Optional[Any] = None) -> Dict[str, Any]:
        prompt = full_prompt(brief) if mode == "full" else scene_prompt(brief)
        return render_scene(prompt, width=self.width, height=self.height,
                            steps=self.steps, seed=self.seed,
                            inside_lane=inside_lane, model=self.model)


def synthetic_scene(*, width: int = 1024, height: int = 1024, kind: str = "linen",
                    seed: int = 7) -> Dict[str, Any]:
    """A deterministic, honestly-labelled backdrop. Never called a generated scene."""
    import numpy as np
    from PIL import Image

    rng = np.random.default_rng(seed)
    top = np.array({"linen": (232, 224, 210), "slate": (74, 78, 84),
                    "dusk": (58, 62, 48)}.get(kind, (232, 224, 210)), dtype=np.float32)
    bottom = np.clip(top * 0.86, 0, 255)
    ramp = np.linspace(0.0, 1.0, height, dtype=np.float32)[:, None, None]
    canvas = top.reshape(1, 1, 3) * (1.0 - ramp) + bottom.reshape(1, 1, 3) * ramp
    canvas = np.repeat(canvas, width, axis=1)
    canvas += rng.normal(0.0, 2.2, canvas.shape).astype(np.float32)
    canvas = np.clip(canvas, 0, 255).astype(np.uint8)
    from io import BytesIO

    buffer = BytesIO()
    Image.fromarray(canvas, mode="RGB").save(buffer, format="PNG")
    return {"bytes": buffer.getvalue(), "source": "synthetic",
            "prompt": f"synthetic {kind} backdrop (no render lane)",
            "width": width, "height": height, "seed": seed, "steps": 0,
            "image_path": None, "lane": None,
            "note": "not generated: a synthetic backdrop used only for the offline proof"}


def renderer_from_name(name: str) -> Any:
    """'comfy' (default) or 'synthetic' — an explicit choice, never a silent fallback."""
    if name == "comfy":
        return ComfySceneRenderer()
    if name == "synthetic":
        def _synthetic(brief: Dict[str, Any], mode: str = "scene",
                       inside_lane: Optional[Any] = None) -> Dict[str, Any]:
            if inside_lane is not None:
                raise RuntimeError(
                    "a synthetic backdrop has no lane to run an in-lane cutout on")
            return synthetic_scene(
                width=1024, height=1024,
                kind={"packaging_mockup": "dusk", "infographic": "slate"}.get(
                    str(brief.get("situation") or ""), "linen"))

        return _synthetic
    raise ValueError(f"unknown renderer {name!r}; use 'comfy' or 'synthetic'")


__all__ = [
    "CHECKPOINTS",
    "ComfySceneRenderer",
    "MODEL_VRAM_GB",
    "SCENE_NEGATIVE",
    "SDXL_CKPT",
    "SITUATION_SCENES",
    "full_prompt",
    "lane_ready",
    "needed_vram_gb",
    "render_scene",
    "renderer_from_name",
    "scene_prompt",
    "sdxl_graph",
    "synthetic_scene",
]
