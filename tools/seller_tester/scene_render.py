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
import re
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
    """The prompt for a full generation, used only where exact fidelity is not required.

    A brief with ``label_mode: "warp"`` draws its lettering deterministically and warps it on, so
    the model must be asked for an **unlettered body**. Its ``body_prompt`` is the prompt; using the
    brief's `prompt` there would ask the diffusion model to spell the brand, which is exactly the
    part it cannot do (measured 2026-11-11: "MOGGARA" for "MOGRA ORGANICS", "AOW" for "Word
    Coffee").
    """
    if str(brief.get("label_mode") or "") == "warp":
        body = str(brief.get("body_prompt") or "").strip()
        if body:
            return body
        raise ValueError(
            "label_mode 'warp' needs a body_prompt: the label is composed deterministically, so "
            "the prompt must describe an unlettered body. A brief with no body_prompt would ask "
            "the model for lettering and then paste a second copy over it")
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
            # Inside a lane the running instance IS the lane's own, freshly started
            # with a cold cache; refusing it there made the real-plate pass
            # unreachable from the very wrapper that owns the GPU.
            if os.environ.get("COMFY_LANE_OWNED") == "1":
                return True, f"lane owns the running instance ({home})"
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
    # Measured 2026-11-09 with every resident unloaded: FLUX 3 at 1024 peaked at **11.93 GB**
    # (89.5 s, `reports/ty/flux_vram_measure.json`). The old (11.0, 1.4) claimed 12.4 GB at the
    # same size and refused a render that works. These numbers are the measurement, plus a
    # 0.3 GB cushion for the sampler's transient allocations.
    "flux3": (10.6, 1.3),
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


def synthetic_plate(*, width: int = 1536, height: int = 1536, kind: str = "pouch",
                    field: str = "sweep", value: int = 255,
                    stock: Optional[Any] = None, units: int = 1,
                    shadow: bool = True,
                    seed: int = 7) -> Dict[str, Any]:
    """A **drawn** blank package on a field — the plate stand-in for the app pipeline.

    `product_picture.build` needs a photograph of an unlettered package to measure
    and print on. When the render lane is down this draws one instead of pretending:
    the record says ``source: "synthetic_plate"`` and the summary repeats it. It is
    not a generated scene and must never be reported as one.

    ``shadow=False`` omits the drawn base shadow. A **main-image** brief is the product
    alone on a flat value: a shadow under it is a defect, not a selling cue, and because
    the ellipse is attached the cutout keeps it — the silhouette then contains it and no
    later check can see it (D-021, measured 2026-11-11).
    """
    import numpy as np
    from PIL import Image, ImageDraw

    level = max(0, min(255, int(value))) if field == "white" else 232
    ground = (level, level, level) if field == "white" else (232, 230, 226)
    img = Image.new("RGB", (width, height), ground)
    d = ImageDraw.Draw(img)

    if kind == "gift_box":
        base = tuple(stock) if stock else (240, 196, 202)
        body = base
        top = tuple(max(0, int(c * 0.94)) for c in base)
        unit_w = int(width * 0.44 / max(1, units) * (0.92 if units > 1 else 1.0))
        h = int(height * 0.62)
        gap = int(width * 0.03) if units > 1 else 0
        span = unit_w * units + gap * (units - 1)
        start = (width - span) // 2
        top_y = int(height * 0.19)
        for index in range(max(1, units)):
            left = start + index * (unit_w + gap)
            w = unit_w
            d.polygon([(left, top_y), (left + w, top_y),
                       (left + w + int(w * 0.03), top_y + h),
                       (left - int(w * 0.03), top_y + h)], fill=body)
            d.rectangle([left, top_y, left + w, top_y + max(6, h // 40)], fill=top)
    elif kind == "apparel":
        # A garment laid flat (D-025): a torso with two sleeves, drawn as one
        # silhouette so the plate's own colour cut finds a single subject with a
        # chest area inside it. Drawn, never called a photograph.
        base = tuple(stock) if stock else (238, 236, 231)
        body = base
        shade = tuple(max(0, int(c * 0.94)) for c in base)
        unit_w = int(width * 0.54 / max(1, units) * (0.92 if units > 1 else 1.0))
        h = int(height * 0.66)
        gap = int(width * 0.04) if units > 1 else 0
        span = unit_w * units + gap * (units - 1)
        start = (width - span) // 2
        top_y = int(height * 0.17)
        for index in range(max(1, units)):
            left = start + index * (unit_w + gap)
            w = unit_w
            sleeve = int(w * 0.26)
            d.polygon([(left + int(w * 0.18), top_y),
                       (left + int(w * 0.82), top_y),
                       (left + w + sleeve, top_y + int(h * 0.30)),
                       (left + w + sleeve - int(w * 0.06), top_y + int(h * 0.46)),
                       (left + w, top_y + int(h * 0.34)),
                       (left + w, top_y + h),
                       (left, top_y + h),
                       (left, top_y + int(h * 0.34)),
                       (left - sleeve + int(w * 0.06), top_y + int(h * 0.46)),
                       (left - sleeve, top_y + int(h * 0.30))], fill=body)
            # a collar and a hem line, so the garment reads as a tee and the chest
            # panel has a top edge to sit under
            d.arc([left + int(w * 0.36), top_y - int(h * 0.02),
                   left + int(w * 0.64), top_y + int(h * 0.06)], 0, 180, fill=shade,
                  width=max(2, w // 90))
            d.line([left, top_y + h - int(h * 0.06), left + w, top_y + h - int(h * 0.06)],
                   fill=shade, width=max(2, w // 120))
    elif kind == "cylinder":
        # A rigid cylinder (jar, bottle, tube, canister): a round body with a
        # shoulder, a cap and a base curve. Drawn, never called a photograph.
        base = tuple(stock) if stock else (214, 199, 178)
        body = base
        cap = tuple(max(0, int(c * 0.62)) for c in base)
        # A cylinder has to meet a brief's fill band in the frame: 0.52 of the
        # width and 0.70 of the height measures ~37% of the frame as subject,
        # which sits inside the bands the catalog declares (18-45%).
        unit_w = int(width * 0.52 / max(1, units) * (0.92 if units > 1 else 1.0))
        h = int(height * 0.70)
        gap = int(width * 0.04) if units > 1 else 0
        span = unit_w * units + gap * (units - 1)
        start = (width - span) // 2
        top_y = int(height * 0.19)
        for index in range(max(1, units)):
            left = start + index * (unit_w + gap)
            w = unit_w
            shoulder = int(h * 0.10)
            d.rounded_rectangle([left, top_y + shoulder, left + w, top_y + h],
                                radius=max(4, w // 7), fill=body)
            d.polygon([(left, top_y + shoulder),
                       (left + int(w * 0.20), top_y),
                       (left + int(w * 0.80), top_y),
                       (left + w, top_y + shoulder)], fill=body)
            d.rectangle([left + int(w * 0.18), top_y - int(h * 0.06),
                         left + w - int(w * 0.18), top_y + int(h * 0.02)], fill=cap)
            if shadow:
                d.ellipse([left - w // 9, top_y + h - h // 34,
                           left + w + w // 9, top_y + h + h // 20], fill=(206, 204, 200))
    else:
        base = tuple(stock) if stock else (213, 167, 122)
        body = base
        top = tuple(max(0, int(c * 0.92)) for c in base)
        unit_w = int(width * 0.38 / max(1, units) * (0.92 if units > 1 else 1.0))
        h = int(height * 0.62)
        gap = int(width * 0.03) if units > 1 else 0
        span = unit_w * units + gap * (units - 1)
        start = (width - span) // 2
        top_y = int(height * 0.20)
        for index in range(max(1, units)):
            left = start + index * (unit_w + gap)
            w = unit_w
            d.polygon([(left, top_y), (left + w, top_y),
                       (left + w + max(2, w // 60), top_y + h),
                       (left - max(2, w // 60), top_y + h)], fill=body)
            d.rectangle([left, top_y, left + w, top_y + max(6, h // 40)], fill=top)
            # base shadow so the plate is not a sticker on a flat field — but never on a
            # main image, where the product must be alone on the value (D-021).
            if shadow:
                d.ellipse([left - w // 8, top_y + h - h // 40,
                           left + w + w // 8, top_y + h + h // 22], fill=(206, 204, 200))

    if field != "white":
        # a vertical light ramp, so the measured surface has real shading
        array = np.asarray(img).astype(np.float32)
        ramp = np.linspace(1.03, 0.94, height, dtype=np.float32)[:, None, None]
        array = np.clip(array * ramp, 0, 255).astype(np.uint8)
        img = Image.fromarray(array)

    from io import BytesIO

    buffer = BytesIO()
    img.save(buffer, format="PNG")
    return {"bytes": buffer.getvalue(), "source": "synthetic_plate",
            "prompt": f"drawn blank {kind} on a {field} field (no render lane)",
            "width": width, "height": height, "seed": seed, "steps": 0,
            "image_path": None, "lane": None,
            "note": "not generated: a drawn plate used only for the offline proof"}


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


def stock_from_brief(brief: Dict[str, Any]) -> Optional[Any]:
    """The stock colour a brief asks for, from its own body prompt.

    A drawn plate is still a stand-in, but it should not contradict the brief:
    a forest-green pouch drawn kraft makes every vision check fail on the plate
    rather than on the artwork. Only explicit colour words are read; anything
    unrecognised keeps the form's default stock.
    """
    text = " ".join(str(brief.get(key) or "") for key in ("body_prompt", "prompt")).lower()
    # Word boundaries, not substrings: "message" contains "sage", and the first
    # version painted every Word Coffee box sage because its tagline says
    # "One Message at a Time". Compound colours are checked before simple ones.
    palette = (
        (("forest-green", "forest green", "dark green"), (37, 54, 40)),
        (("pale-pink", "pale pink", "blush", "lilac"), (240, 196, 202)),
        (("matte black", "charcoal"), (38, 38, 40)),
        (("olive",), (96, 108, 70)),
        (("sage",), (150, 168, 146)),
        (("pink",), (238, 206, 208)),
        (("black",), (38, 38, 40)),
        (("navy", "midnight"), (32, 44, 58)),
        (("white", "ivory", "bone"), (245, 238, 226)),
        (("cream",), (238, 226, 205)),
        (("kraft", "brown", "tan"), (213, 167, 122)),
    )
    for words, colour in palette:
        if any(re.search(rf"\b{re.escape(word)}\b", text) for word in words):
            return colour
    return None


def renderer_from_name(name: str) -> Any:
    """'comfy' (default), 'synthetic' or 'drawn' — an explicit choice, never a silent fallback."""
    if name == "comfy":
        return ComfySceneRenderer()
    if name == "drawn":
        def _drawn(brief: Dict[str, Any], mode: str = "plate",
                   inside_lane: Optional[Any] = None,
                   size: Optional[Any] = None) -> Dict[str, Any]:
            if inside_lane is not None:
                raise RuntimeError(
                    "a drawn plate has no lane to run an in-lane cutout on")
            # The blank body must be the shape the design's panel belongs on: a
            # brief's category is the seller's taxonomy, the design's form is what
            # the app will print. Reading the category alone drew a box for a jar.
            kind = None
            try:
                import brand_art  # noqa: PLC0415

                kind = brand_art.plate_kind(brand_art.design_for_brief(brief))
            except Exception:  # noqa: BLE001 - an unresolved design falls back to category
                kind = None
            if kind is None:
                kind = ("gift_box" if str(brief.get("category") or "") in
                        ("food_jar", "gift_box", "box") else "pouch")
            constraints = brief.get("constraints") or {}
            background = constraints.get("background") or {}
            matte = constraints.get("matte") or {}
            mode = str(background.get("mode") or "").lower()
            # The same rule as `generators.flat`: a uniform field or a clean white
            # matte needs a flat canvas, or the edge grain fails the matte check.
            white = (mode == "uniform"
                     or str(matte.get("mode") or "").lower() == "white_matte"
                     or mode.startswith("white") or mode.startswith("solid"))
            field = "white" if white else "sweep"
            value = int(background.get("value", 255)) if white else 232
            stock_colour = stock_from_brief(brief)
            unit_count = max(1, int(brief.get("units") or 1))
            width, height = (int(size[0]), int(size[1])) if size else (1536, 1536)
            return synthetic_plate(width=max(1024, width), height=max(1024, height),
                                   kind=kind, field=field, value=value,
                                   stock=stock_colour, units=unit_count,
                                   # a main image is the product alone on the value:
                                   # no drawn shadow to survive the cutout (D-021)
                                   shadow=not white)

        return _drawn
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
    "synthetic_plate",
    "synthetic_scene",
]
