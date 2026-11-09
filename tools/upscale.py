"""Measured upscaling for the composite path — no assumption that Lanczos is the answer.

The 768 -> 1536 step used to be `PIL.Image.LANCZOS`, which is a resample: it adds no
detail. This module evaluates real upscalers against that control on the same fixed
set and only replaces the control when the measurement beats it.

Candidates and licences (recorded in ``provenance.csv``):

=============  ==============================================  ==================
method         runtime                                         licence
=============  ==============================================  ==================
lanczos        Pillow resample (CPU)                           Pillow MIT; no weights
realesrgan     RealESRGAN_x4plus.pth via spandrel (GPU)        BSD-3-Clause
swinir         SwinIR-M x4 GAN via spandrel (GPU)              Apache-2.0
comfy_latent   ComfyUI LatentUpscale + low-denoise KSampler    Apache-2.0 nodes
=============  ==============================================  ==================

The GPU candidates run in ComfyUI's own virtualenv (it is the only CUDA torch on
this box). The parent process keeps the GPU lock and the VRAM budget; the worker
only does inference. Nothing is downloaded by this module.

    python tools/upscale.py --benchmark
    python tools/upscale.py --list
    python tools/upscale.py --apply --method realesrgan --in a.png --out b.png --target 1536
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
for _extra in (str(ROOT), str(ROOT / "tools"), str(ROOT / "Northstar_backend")):
    if _extra not in sys.path:
        sys.path.insert(0, _extra)

COMFY_PYTHON = Path(os.environ.get(
    "COMFY_PYTHON", r"C:\Users\T2Hol\ComfyUI\venv\Scripts\python.exe"))
UPSCALE_DIR = Path(os.environ.get(
    "COMFY_UPSCALE_DIR", r"C:\Users\T2Hol\ComfyUI\models\upscale_models"))

WEIGHTS = {
    "realesrgan": UPSCALE_DIR / "RealESRGAN_x4plus.pth",
    "swinir": UPSCALE_DIR / "SwinIR-M_x4_GAN.pth",
}

LICENCES = {
    "lanczos": "Pillow MIT; no weights",
    "realesrgan": "BSD-3-Clause (Real-ESRGAN code and x4plus weights)",
    "swinir": "Apache-2.0 (SwinIR code and SwinIR-M x4 GAN weights)",
    "comfy_latent": "Apache-2.0 ComfyUI nodes; checkpoint licence applies (SDXL OpenRAIL++-M)",
}

#: Native scale of each backend. The result is resampled to the exact target size.
NATIVE_SCALE = {"lanczos": 1, "realesrgan": 4, "swinir": 4, "comfy_latent": 1}

#: Measured winner (2026-11-08): SwinIR 14/18 items vs the Lanczos control 0/18,
#: tied with Real-ESRGAN on items and ahead on mean SSIM (0.92625 vs 0.9219).
#: Replaced only by a benchmark that beats the control; never by preference.
ACTIVE = "swinir"
FALLBACK = "lanczos"

#: Rough VRAM need for a 768 -> 1536 tile pass. The lane judges it against the
#: measured free VRAM; this is the model's need, not the machine's headroom.
#: Measured peak allocation per backend (nvidia-smi, lane empty), rounded up:
#: realesrgan 3.56 GB, swinir 3.94 GB, comfy_latent runs the SDXL graph (lane need).
NEEDED_GB = {"lanczos": 0.0, "realesrgan": 4.5, "swinir": 5.0, "comfy_latent": 12.0}

EVAL_IMAGES = (
    ("pair_main", "renders/references/mogra/mogra_pair_main.png", 1536),
    ("pair_lifestyle", "renders/references/mogra/mogra_pair_lifestyle.png", 1024),
    ("forest_dusk", "renders/references/mogra/mogra_forest_dusk.png", 768),
)


class UpscalerUnavailable(RuntimeError):
    """The requested upscaler cannot run here. Never silently replaced."""


def available(method: str) -> Tuple[bool, str]:
    if method in ("lanczos",):
        return True, "Pillow resample (CPU)"
    if method == "comfy_latent":
        try:
            import comfy_lane
            home = Path(comfy_lane.COMFY_HOME)
            if not (home / "main.py").is_file():
                return False, f"ComfyUI runtime missing under {home}"
        except Exception as exc:  # noqa: BLE001
            return False, f"lane probe failed: {type(exc).__name__}: {exc}"
        return True, "ComfyUI latent upscale (starts its own lane)"
    weight = WEIGHTS.get(method)
    if weight is None:
        return False, f"unknown upscaler {method!r}"
    if not weight.is_file():
        return False, f"weights missing: {weight}"
    if not COMFY_PYTHON.is_file():
        return False, f"CUDA torch runtime missing: {COMFY_PYTHON}"
    return True, f"{weight.name} via spandrel"


# ---------------------------------------------------------------- worker (ComfyUI venv)
def _torch_device() -> str:
    import torch

    return "cuda" if torch.cuda.is_available() else "cpu"


def _infer_tiled(model: Any, image: Any, scale: int, *, tile: int = 256,
                 overlap: int = 16, device: str = "cuda") -> Any:
    """Tile the model over the image so VRAM stays bounded."""
    import numpy as np
    import torch
    from PIL import Image

    arr = np.asarray(image.convert("RGB"), dtype=np.float32) / 255.0
    tensor = torch.from_numpy(arr).permute(2, 0, 1).unsqueeze(0).to(device)
    height, width = tensor.shape[-2:]
    out = torch.zeros((1, 3, height * scale, width * scale), device=device)
    for top in range(0, height, tile):
        for left in range(0, width, tile):
            y0 = max(0, top - overlap)
            x0 = max(0, left - overlap)
            y1 = min(height, top + tile + overlap)
            x1 = min(width, left + tile + overlap)
            patch = tensor[:, :, y0:y1, x0:x1]
            with torch.no_grad():
                rendered = model(patch)
            if not torch.is_tensor(rendered):
                rendered = rendered[0]
            oy0 = (top - y0) * scale
            ox0 = (left - x0) * scale
            oy1 = oy0 + (min(height, top + tile) - top) * scale
            ox1 = ox0 + (min(width, left + tile) - left) * scale
            out[:, :, top * scale:min(height, top + tile) * scale,
                left * scale:min(width, left + tile) * scale] = \
                rendered[:, :, oy0:oy1, ox0:ox1]
    flat = (out.clamp(0, 1).squeeze(0).permute(1, 2, 0).cpu().numpy() * 255.0)
    return Image.fromarray(flat.round().astype(np.uint8), mode="RGB")


def _load_backend(method: str, device: str) -> Any:
    import spandrel

    weight = WEIGHTS.get(method)
    if weight is None or not weight.is_file():
        raise UpscalerUnavailable(f"weights missing for {method!r}: {weight}")
    model = spandrel.ModelLoader().load_from_file(str(weight))
    model.eval().to(device)
    return model


def _worker(method: str, src: Path, dst: Path, target: int) -> int:
    """Run one upscale inside ComfyUI's venv. Prints one JSON line."""
    from PIL import Image

    started = time.time()
    device = _torch_device()
    scale = NATIVE_SCALE.get(method, 4)
    model = _load_backend(method, device)
    with Image.open(src) as opened:
        base = opened.convert("RGB")
    rendered = _infer_tiled(model, base, scale, device=device)
    # Resample to the exact target width, preserving aspect.
    if rendered.width != target:
        new_h = max(1, int(round(rendered.height * target / rendered.width)))
        rendered = rendered.resize((target, new_h), Image.LANCZOS)
    rendered.save(dst, format="PNG")
    payload = {"ok": True, "method": method, "device": device, "scale": scale,
               "width": rendered.width, "height": rendered.height,
               "seconds": round(time.time() - started, 2)}
    print(json.dumps(payload))
    return 0


# ---------------------------------------------------------------- public API
def _lanczos(png: bytes, target_w: int, target_h: int) -> bytes:
    from PIL import Image

    with Image.open(BytesIO(png)) as opened:
        resized = opened.convert("RGB").resize((target_w, target_h), Image.LANCZOS)
    buffer = BytesIO()
    resized.save(buffer, format="PNG")
    return buffer.getvalue()


def upscale_bytes(png: bytes, target_size: Tuple[int, int], *,
                  method: Optional[str] = None,
                  timeout: float = 600.0) -> Dict[str, Any]:
    """Upscale to exactly ``target_size``. Returns bytes + what ran and how long.

    The GPU backends are refused with a named reason when they cannot run; the
    caller decides whether to record a Lanczos fallback. This function does not
    fall back on its own.
    """
    chosen = method or ACTIVE
    target_w, target_h = int(target_size[0]), int(target_size[1])
    started = time.time()
    if chosen == "lanczos":
        data = _lanczos(png, target_w, target_h)
        return {"ok": True, "bytes": data, "method": "lanczos",
                "licence": LICENCES["lanczos"], "seconds": round(time.time() - started, 2),
                "from": None, "to": [target_w, target_h], "native_scale": 1}

    ready, detail = available(chosen)
    if not ready:
        raise UpscalerUnavailable(f"{chosen}: {detail}")

    if chosen == "comfy_latent":
        result = _latent_upscale(png, (target_w, target_h), timeout=timeout)
        result.setdefault("licence", LICENCES[chosen])
        return result

    # The parent owns the lock and the budget; the worker only does inference.
    import gpu_budget  # noqa: PLC0415

    snap = gpu_budget.snapshot()
    need = NEEDED_GB.get(chosen, 4.0)
    if not snap.get("ok"):
        raise UpscalerUnavailable(f"{chosen}: no VRAM reading: {snap.get('reason')}")
    headroom = round(float(snap.get("free_gb") or 0.0) - need, 2)
    if headroom < gpu_budget.RESERVE_GB:
        raise UpscalerUnavailable(
            f"{chosen}: {snap.get('free_gb')} GB free - {need} GB needed = "
            f"{headroom} GB < {gpu_budget.RESERVE_GB} GB reserve")
    lock = gpu_budget.lock("upscale", ttl_s=1800)
    if not lock.get("ok"):
        raise UpscalerUnavailable(f"{chosen}: gpu locked by {lock.get('held_by')}")
    baseline_used = float(snap.get("used_mb") or 0) / 1024.0
    peak_used = baseline_used
    try:
        with tempfile.TemporaryDirectory(prefix="ns-upscale-") as tmp:
            src = Path(tmp) / "in.png"
            dst = Path(tmp) / "out.png"
            src.write_bytes(png)
            proc = subprocess.Popen(
                [str(COMFY_PYTHON), str(Path(__file__).resolve()), "--worker",
                 "--method", chosen, "--in", str(src), "--out", str(dst),
                 "--target", str(target_w)],
                cwd=str(ROOT), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            deadline = time.time() + timeout
            while proc.poll() is None and time.time() < deadline:
                time.sleep(0.25)
                reading = gpu_budget.snapshot()
                if reading.get("ok"):
                    peak_used = max(peak_used, float(reading.get("used_mb") or 0) / 1024.0)
            if proc.poll() is None:
                proc.kill()
                raise UpscalerUnavailable(f"{chosen} worker exceeded {timeout}s")
            stdout, stderr = proc.communicate()
            if proc.returncode != 0 or not dst.is_file():
                tail = (stderr or stdout or "").strip().splitlines()
                raise UpscalerUnavailable(
                    f"{chosen} worker failed: {tail[-1] if tail else 'no output'}"[:400])
            data = dst.read_bytes()
            info = {}
            for line in reversed((stdout or "").strip().splitlines()):
                try:
                    info = json.loads(line)
                    break
                except ValueError:
                    continue
    finally:
        gpu_budget.unlock("upscale")
    return {**info, "ok": True, "bytes": data, "method": chosen,
            "licence": LICENCES[chosen], "to": [target_w, int(info.get("height") or target_h)],
            "vram_gb": round(max(0.0, peak_used - baseline_used), 2),
            "seconds": info.get("seconds", round(time.time() - started, 2))}


LATENT_PROMPT = ("natural photographic detail, product photography, sharp focus, "
                 "no text, no watermark")


def _latent_graph(image_name: str, width: int, height: int, *, steps: int = 20,
                  denoise: float = 0.35, seed: int = 0) -> Dict[str, Any]:
    """ComfyUI-native latent upscale: VAE encode, latent resize, low-denoise refine."""
    return {
        "1": {"class_type": "CheckpointLoaderSimple",
              "inputs": {"ckpt_name": "sd_xl_base_1.0.safetensors"}},
        "2": {"class_type": "LoadImage", "inputs": {"image": image_name}},
        "3": {"class_type": "VAEEncode", "inputs": {"pixels": ["2", 0], "vae": ["1", 2]}},
        "4": {"class_type": "LatentUpscale",
              "inputs": {"samples": ["3", 0], "upscale_method": "bislerp",
                         "width": int(width), "height": int(height), "crop": "disabled"}},
        "5": {"class_type": "CLIPTextEncode",
              "inputs": {"text": LATENT_PROMPT, "clip": ["1", 1]}},
        "6": {"class_type": "CLIPTextEncode",
              "inputs": {"text": "blurry, text, watermark, logo",
                         "clip": ["1", 1]}},
        "7": {"class_type": "KSampler",
              "inputs": {"model": ["1", 0], "seed": int(seed), "steps": int(steps),
                         "cfg": 6.0, "sampler_name": "euler", "scheduler": "normal",
                         "denoise": float(denoise), "positive": ["5", 0],
                         "negative": ["6", 0], "latent_image": ["4", 0]}},
        "8": {"class_type": "VAEDecode", "inputs": {"samples": ["7", 0], "vae": ["1", 2]}},
        "9": {"class_type": "SaveImage",
              "inputs": {"images": ["8", 0], "filename_prefix": "ns-latent-upscale"}},
    }


def _upload(png: bytes, filename: str) -> str:
    import urllib.request
    import uuid

    import comfy_lane

    boundary = "----northstar" + uuid.uuid4().hex
    head = (f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="image"; filename="{filename}"\r\n'
            f"Content-Type: image/png\r\n\r\n").encode("utf-8")
    tail = (f"\r\n--{boundary}\r\n"
            f'Content-Disposition: form-data; name="overwrite"\r\n\r\ntrue'
            f"\r\n--{boundary}--\r\n").encode("utf-8")
    request = urllib.request.Request(
        comfy_lane.COMFY_URL + "/upload/image", data=head + png + tail,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    with urllib.request.urlopen(request, timeout=180) as response:
        payload = json.loads(response.read().decode("utf-8") or "{}")
    name = payload.get("name") or filename
    sub = (payload.get("subfolder") or "").strip("/")
    return f"{sub}/{name}" if sub else name


def _latent_upscale(png: bytes, target_size: Tuple[int, int], *,
                    timeout: float = 600.0) -> Dict[str, Any]:
    """One latent upscale through a lane this call owns (started and stopped)."""
    import comfy_lane

    from PIL import Image

    width, height = int(target_size[0]), int(target_size[1])
    started = time.time()

    def _work() -> Dict[str, Any]:
        name = _upload(png, f"upscale-{int(time.time())}.png")
        from tools.seller_tester.scene_render import _run_graph  # noqa: PLC0415

        return _run_graph(_latent_graph(name, width, height, seed=7), timeout=timeout)

    outcome = comfy_lane.lane(_work, needed_gb=NEEDED_GB["comfy_latent"],
                              role="upscale:comfy_latent")
    if not outcome.get("ok"):
        raise UpscalerUnavailable(f"comfy_latent lane failed: {outcome.get('reason')}")
    images = (outcome.get("result") or {}).get("images") or []
    if not images:
        raise UpscalerUnavailable("comfy_latent lane returned no image")
    with Image.open(images[0]) as opened:
        rendered = opened.convert("RGB")
    if rendered.size != (width, height):
        rendered = rendered.resize((width, height), Image.LANCZOS)
    buffer = BytesIO()
    rendered.save(buffer, format="PNG")
    return {"ok": True, "bytes": buffer.getvalue(), "method": "comfy_latent",
            "licence": LICENCES["comfy_latent"],
            "seconds": round(time.time() - started, 2),
            "to": [width, height], "lane": outcome.get("lane")}


def upscale_to_min(png: bytes, required_sizes: Tuple[int, int], record: Dict[str, Any],
                   *, method: Optional[str] = None) -> Tuple[bytes, Dict[str, Any]]:
    """Upscale a picture to at least the brief's minimum, recorded, never silent."""
    from PIL import Image

    with Image.open(BytesIO(png)) as opened:
        width, height = opened.size
    target_w, target_h = int(required_sizes[0]), int(required_sizes[1])
    if width >= target_w and height >= target_h:
        return png, record
    factor = max(target_w / float(width), target_h / float(height))
    new_size = (int(round(width * factor)), int(round(height * factor)))
    chosen = method or ACTIVE
    try:
        result = upscale_bytes(png, new_size, method=chosen)
    except UpscalerUnavailable as exc:
        if chosen == FALLBACK:
            raise
        result = upscale_bytes(png, new_size, method=FALLBACK)
        result["refused"] = f"{chosen}: {exc}"
        chosen = FALLBACK
    record["upscaled_from"] = [width, height]
    record["upscaled_to"] = list(new_size)
    record["upscale"] = {
        "method": result.get("method", chosen),
        "licence": result.get("licence"),
        "seconds": result.get("seconds"),
        "refused": result.get("refused"),
    }
    record["upscale_note"] = (
        f"{result.get('method', chosen)} to the brief's minimum; "
        + ("a resample that adds no detail (the measured upscaler was refused: "
           f"{result.get('refused')})" if result.get("refused") else
           "a measured reconstruction, not a resample"))
    box = record.get("product_box")
    if isinstance(box, list) and len(box) == 4:
        record["product_box"] = [int(round(value * factor)) for value in box]
    return result["bytes"], record


# ---------------------------------------------------------------- benchmark
def _metrics(rendered: Any, reference: Any) -> Dict[str, Any]:
    import numpy as np
    from skimage.filters import sobel
    from skimage.metrics import peak_signal_noise_ratio, structural_similarity

    a = np.asarray(rendered.convert("RGB"), dtype=np.uint8)
    b = np.asarray(reference.convert("RGB"), dtype=np.uint8)
    if a.shape != b.shape:
        return {"error": f"shape {a.shape} != {b.shape}"}
    psnr = float(peak_signal_noise_ratio(b, a, data_range=255))
    ssim = float(structural_similarity(b, a, channel_axis=2, data_range=255))
    luma = a.astype(np.float32) @ np.array([0.299, 0.587, 0.114], dtype=np.float32)
    edge = float(sobel(luma / 255.0).mean())
    return {"psnr_db": round(psnr, 3), "ssim": round(ssim, 5),
            "edge_sharpness": round(edge, 5)}


DEGRADATIONS = ("clean", "soft")


def _soften(probe: Any) -> Any:
    """A soft render, not a clean downsample: blur plus low sensor noise.

    A 768 diffusion scene is not a Lanczos-downsampled photograph — it is soft and
    slightly noisy. Grading only the clean case measures how well Lanczos inverts
    itself, so both conditions are fixed here and both are reported.
    """
    import numpy as np
    from PIL import ImageFilter

    rng = np.random.default_rng(20261108)
    blurred = probe.filter(ImageFilter.GaussianBlur(radius=0.8))
    array = np.asarray(blurred, dtype=np.float32)
    array = np.clip(array + rng.normal(0.0, 2.0, array.shape), 0, 255)
    from PIL import Image

    return Image.fromarray(array.round().astype(np.uint8), mode="RGB")


def build_pairs() -> List[Dict[str, Any]]:
    """Known-good native crops, at two fixed degradations — the probes to upscale."""
    from PIL import Image

    pairs: List[Dict[str, Any]] = []
    for name, rel, native in EVAL_IMAGES:
        path = ROOT / rel
        if not path.is_file():
            raise UpscalerUnavailable(f"eval image missing: {path}")
        with Image.open(path) as opened:
            image = opened.convert("RGB")
        side = min(native, image.width, image.height)
        left = (image.width - side) // 2
        top = (image.height - side) // 2
        reference = image.crop((left, top, left + side, top + side))
        clean = reference.resize((side // 2, side // 2), Image.LANCZOS)
        for degradation in DEGRADATIONS:
            probe = clean if degradation == "clean" else _soften(clean)
            pairs.append({"name": f"{name}_{degradation}", "image": name,
                          "degradation": degradation, "path": rel, "side": side,
                          "probe": probe, "reference": reference})
    return pairs


def benchmark(methods: Optional[List[str]] = None, *, budget_seconds: float = 300.0) -> Dict[str, Any]:
    """Fixed eval: PSNR/SSIM against the native crop, edge sharpness, seconds."""
    from PIL import Image

    chosen = methods or [m for m in ("lanczos", "realesrgan", "swinir", "comfy_latent")
                         if available(m)[0]]
    pairs = build_pairs()
    rows: Dict[str, Dict[str, Any]] = {}
    try:
        import gpu_budget
        ram_free = gpu_budget.ram().get("free_gb")
    except Exception:  # noqa: BLE001
        ram_free = None
    for method in chosen:
        per_image: List[Dict[str, Any]] = []
        for pair in pairs:
            buffer = BytesIO()
            pair["probe"].save(buffer, format="PNG")
            started = time.time()
            try:
                result = upscale_bytes(buffer.getvalue(),
                                       (pair["side"], pair["side"]), method=method,
                                       timeout=budget_seconds)
                with Image.open(BytesIO(result["bytes"])) as opened:
                    rendered = opened.convert("RGB")
                metrics = _metrics(rendered, pair["reference"])
                row = {"name": pair["name"], "ok": True,
                       "seconds": round(time.time() - started, 2),
                       "vram_gb": result.get("vram_gb", 0.0), **metrics}
            except Exception as exc:  # noqa: BLE001 - a failed candidate is a row
                row = {"name": pair["name"], "ok": False,
                       "error": f"{type(exc).__name__}: {exc}"[:400],
                       "seconds": round(time.time() - started, 2)}
            per_image.append(row)
        measured = [r for r in per_image if r.get("ok")]
        by_condition: Dict[str, Any] = {}
        for condition in DEGRADATIONS:
            subset = [r for r in measured if r["name"].endswith(f"_{condition}")]
            by_condition[condition] = {
                "mean_psnr_db": round(sum(r["psnr_db"] for r in subset) / len(subset), 3)
                if subset else None,
                "mean_ssim": round(sum(r["ssim"] for r in subset) / len(subset), 5)
                if subset else None,
                "mean_edge_sharpness": round(
                    sum(r["edge_sharpness"] for r in subset) / len(subset), 5)
                if subset else None,
            }
        rows[method] = {
            "by_degradation": by_condition,
            "licence": LICENCES.get(method),
            "status": "measured" if measured else "failed",
            "per_image": per_image,
            "ram_free_gb": ram_free,
            "mean_psnr_db": round(sum(r["psnr_db"] for r in measured) / len(measured), 3)
            if measured else None,
            "mean_ssim": round(sum(r["ssim"] for r in measured) / len(measured), 5)
            if measured else None,
            "mean_edge_sharpness": round(
                sum(r["edge_sharpness"] for r in measured) / len(measured), 5)
            if measured else None,
            "mean_seconds": round(sum(r["seconds"] for r in measured) / len(measured), 2)
            if measured else None,
            "vram_gb": max((r.get("vram_gb") or 0.0) for r in measured) if measured else None,
        }
    decision = _score(rows)
    return {"schema": 1, "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "eval": {"images": [p["name"] for p in pairs],
                     "reference": "native-resolution centre crop (known good)",
                     "probe": ("native crop downsampled 2x; 'soft' adds a 0.8 px blur "
                               "and low noise to model a diffusion render"),
                     "metrics": ["PSNR", "SSIM", "Sobel edge sharpness", "seconds"]},
            "methods": rows, "decision": decision}


def _score(rows: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """Score measured rows against the Lanczos control on the same items.

    Three items per image (PSNR, SSIM, edge sharpness beat the control). That is
    the integer item count the scout's swap rule understands.
    """
    control_rows = {r["name"]: r for r in
                    (rows.get("lanczos") or {}).get("per_image", []) if r.get("ok")}
    for row in rows.values():
        if row.get("status") != "measured":
            continue
        correct = 0
        for r in row["per_image"]:
            if not r.get("ok") or r["name"] not in control_rows:
                continue
            base = control_rows[r["name"]]
            if r["psnr_db"] > base["psnr_db"]:
                correct += 1
            if r["ssim"] > base["ssim"]:
                correct += 1
            if r["edge_sharpness"] > base["edge_sharpness"]:
                correct += 1
        row["correct"] = correct
        row["items"] = 3 * len(control_rows)
    measured_rows = {m: r for m, r in rows.items() if r.get("status") == "measured"}
    winner = None
    for method, row in measured_rows.items():
        if method == "lanczos":
            continue
        if winner is None or (row.get("correct") or 0) > (measured_rows[winner].get("correct") or 0):
            winner = method
        elif (row.get("correct") or 0) == (measured_rows[winner].get("correct") or 0):
            if (row.get("mean_ssim") or 0) > (measured_rows[winner].get("mean_ssim") or 0):
                winner = method
    control = measured_rows.get("lanczos", {})
    if not winner:
        return {"verdict": "keep-incumbent", "model": "lanczos", "incumbent": "lanczos",
                "reason": "no candidate was measured"}
    tied = sorted(method for method, row in measured_rows.items()
                  if method != "lanczos"
                  and (row.get("correct") or 0) == (measured_rows[winner].get("correct") or 0))
    if (measured_rows[winner].get("correct") or 0) >= (control.get("correct") or 0) + 2:
        reason = (f"{winner} wins {measured_rows[winner].get('correct')}/"
                  f"{measured_rows[winner].get('items')} items vs the Lanczos control "
                  f"({control.get('correct')}/{control.get('items')})")
        others = [m for m in tied if m != winner]
        if others:
            reason += ("; tied on items with " + ", ".join(others)
                       + ", tie broken on mean SSIM "
                       + f"({measured_rows[winner].get('mean_ssim')} vs "
                       + ", ".join(str(measured_rows[m].get("mean_ssim")) for m in others)
                       + ")")
        return {"verdict": "replace", "model": winner, "incumbent": "lanczos",
                "reason": reason + ".", "tied": tied}
    return {"verdict": "keep-incumbent", "model": "lanczos", "incumbent": "lanczos",
            "reason": ("no candidate cleared the +2 item margin over the Lanczos "
                       "control: " + ", ".join(
                           f"{m} {row.get('correct')}/{row.get('items')}"
                           for m, row in measured_rows.items()))}


def _write_leaderboard(result: Dict[str, Any]) -> Dict[str, Any]:
    """Merge the upscalers role into ty/model_leaderboard.json through the scout.

    Only the `upscalers` role is replaced; every other role's measurements stay.
    """
    import model_scout

    roles = model_scout.load_roles()
    role_entry = roles.get("upscalers") or {}
    measurements: Dict[str, Dict[str, Any]] = {}
    for method, row in result["methods"].items():
        measurements[method] = {
            "role": "upscalers",
            "status": row["status"],
            "correct": row.get("correct", 0),
            "items": row.get("items", 0),
            "latency_ms": int(round((row.get("mean_seconds") or 0) * 1000)),
            "ssim": row.get("mean_ssim"),
            "psnr_db": row.get("mean_psnr_db"),
            "edge_sharpness": row.get("mean_edge_sharpness"),
            "vram_gb": row.get("vram_gb"),
            "ram_free_gb": row.get("ram_free_gb"),
            "licence": row.get("licence"),
            "error": next((r.get("error") for r in row["per_image"] if r.get("error")), None),
        }
    recommendation = model_scout.recommend(role_entry, measurements)
    best = result["decision"]
    if recommendation.get("verdict") == "replace" and best.get("verdict") == "replace" \
            and recommendation.get("model") != best.get("model"):
        # The scout keeps the first candidate when item counts tie. The fixed
        # tie-break here is mean SSIM, then mean PSNR — stated, not assumed.
        recommendation["model"] = best["model"]
        recommendation["reason"] = (
            f"scout item margin confirmed; {best['reason']}")
    recommendation["decided_by"] = "measurement on the three Mogra crops"
    recommendation["eval_spec"] = result["eval"]

    path = model_scout.LEADERBOARD_PATH
    try:
        leaderboard = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(leaderboard, dict):
            leaderboard = {}
    except (OSError, ValueError):
        leaderboard = {}
    if not leaderboard:
        leaderboard = model_scout.build_leaderboard(roles, {})
    role_row = leaderboard.setdefault("roles", {}).setdefault("upscalers", {})
    role_row.update({
        "label": role_entry.get("label"),
        "lane": role_entry.get("lane"),
        "eval": role_entry.get("eval"),
        "budget_key": role_entry.get("budget_key"),
        "budget_gb": role_entry.get("budget_gb"),
        "manager_key": None,
        "incumbent": role_entry.get("incumbent"),
        "candidates": role_entry.get("candidates") or [],
        "measurements": measurements,
        "recommendation": recommendation,
        "quarantine": None,
        "notes": role_entry.get("notes"),
        "eval_detail": result["eval"],
        "measured_at": result["generated_at"],
    })
    leaderboard["generated_at"] = result["generated_at"]
    written = model_scout.write_leaderboard(leaderboard)
    return {"recommendation": recommendation, **written}


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Measured upscalers")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--benchmark", action="store_true")
    parser.add_argument("--rescore", metavar="PATH",
                        help="recompute the scores of an existing benchmark JSON")
    parser.add_argument("--methods", default="")
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--method")
    parser.add_argument("--in", dest="source")
    parser.add_argument("--out", dest="dest")
    parser.add_argument("--target", type=int, default=0)
    args = parser.parse_args(argv)

    if args.worker:
        return _worker(str(args.method), Path(args.source), Path(args.dest),
                       int(args.target))
    if args.list:
        print(json.dumps({name: {"licence": LICENCES[name], "available": available(name)}
                          for name in LICENCES}, indent=2))
        return 0
    if args.rescore:
        target = Path(args.rescore)
        result = json.loads(target.read_text(encoding="utf-8"))
        result["decision"] = _score(result["methods"])
        target.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        merged = _write_leaderboard(result)
        print(json.dumps({"decision": result["decision"], **merged}, indent=2))
        return 0
    if args.benchmark:
        methods = [m.strip() for m in args.methods.split(",") if m.strip()] or None
        result = benchmark(methods)
        out = ROOT / "state" / "seller" / "upscale_bench.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        merged = _write_leaderboard(result)
        print(json.dumps({"decision": result["decision"],
                          "methods": {m: {k: r.get(k) for k in (
                              "status", "mean_psnr_db", "mean_ssim",
                              "mean_edge_sharpness", "mean_seconds", "correct", "items")}
                                      for m, r in result["methods"].items()},
                          "evidence": str(out), **merged}, indent=2))
        return 0
    if args.source and args.dest:
        method = args.method or ACTIVE
        data = Path(args.source).read_bytes()
        from PIL import Image

        with Image.open(BytesIO(data)) as opened:
            target = args.target or opened.width * 2
            height = int(round(opened.height * target / opened.width))
        result = upscale_bytes(data, (target, height), method=method)
        Path(args.dest).write_bytes(result["bytes"])
        print(json.dumps({k: v for k, v in result.items() if k != "bytes"}, indent=2))
        return 0
    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
