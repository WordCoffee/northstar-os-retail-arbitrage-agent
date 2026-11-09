"""Cut the real product out of an upload, and measure how well each method did.

The composite path (owner instruction, 2026-11-08) only preserves the product if
the cutout is honest: the pixels inside the alpha must be the seller's pixels and
the alpha must stop at the product, not at a rectangle. So this module does two
things and refuses to conflate them:

* ``cutout(rgb, method)`` returns an RGBA-ready alpha for a named method;
* ``alpha_metrics(alpha, reference_coverage=...)`` measures coverage, edge
  gradient width and the bounding box, so a choice between methods is a
  measurement rather than a preference.

Candidates, all local, no network:
  * ``background_distance`` — corner-sampled background + threshold + morphology;
  * ``otsu_lab`` — Otsu threshold on the LAB distance from the corner background;
  * ``grabcut`` — OpenCV GrabCut from an inset rectangle;
  * ``birefnet`` — the BiRefNet background-removal node already on disk, run by a
    ComfyUI instance the caller owns (it needs the media lane).

``rembg`` is named in ``CANDIDATES`` but is not installed here; ``cutout`` raises
``CutoutUnavailable`` for it instead of silently substituting another method.
"""
from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Tuple

import numpy as np

METHODS = ("background_distance", "otsu_lab", "grabcut", "birefnet")
CANDIDATES = METHODS + ("rembg",)

#: Longest side used for the estimation pass. A 2000px upload is downscaled,
#: segmented, and the mask is resized back up; the returned alpha is full size.
WORKING_MAX_SIDE = 1024

#: A pixel is "product" above this alpha value.
SOLID = 128


class CutoutUnavailable(RuntimeError):
    """The requested method cannot run here. Never swapped for another method."""


@dataclass
class Cutout:
    method: str
    alpha: np.ndarray          # HxW uint8, 0 = background, 255 = product
    rgb: np.ndarray            # HxWx3 uint8, same size as `alpha`
    seconds: float
    working_side: int
    notes: Dict[str, Any] = field(default_factory=dict)

    @property
    def coverage(self) -> float:
        return float((self.alpha >= SOLID).mean())

    def bbox(self) -> Tuple[int, int, int, int]:
        rows, columns = np.where(self.alpha >= SOLID)
        if rows.size == 0:
            return (0, 0, 0, 0)
        return (int(columns.min()), int(rows.min()),
                int(columns.max() + 1), int(rows.max() + 1))


def load_rgb(source: str | Path | bytes) -> np.ndarray:
    """RGB uint8 array from a path or bytes. RGBA is flattened onto its own alpha."""
    from PIL import Image
    from io import BytesIO

    raw = Path(source).read_bytes() if isinstance(source, (str, Path)) else source
    with Image.open(BytesIO(raw)) as opened:
        rgba = opened.convert("RGBA")
        background = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
        background.alpha_composite(rgba)
        return np.asarray(background.convert("RGB"), dtype=np.uint8)


def _corner_background(rgb: np.ndarray, patch: int = 24) -> np.ndarray:
    height, width = rgb.shape[:2]
    size = max(4, min(patch, height // 8, width // 8))
    patches = (rgb[:size, :size], rgb[:size, width - size:],
               rgb[height - size:, :size], rgb[height - size:, width - size:])
    return np.median(np.array([np.median(p.reshape(-1, 3), axis=0) for p in patches]),
                     axis=0)


def _working(rgb: np.ndarray, max_side: int = WORKING_MAX_SIDE
             ) -> Tuple[np.ndarray, Tuple[int, int]]:
    import cv2

    height, width = rgb.shape[:2]
    scale = min(1.0, float(max_side) / float(max(height, width)))
    if scale >= 1.0:
        return rgb, (width, height)
    small = cv2.resize(rgb, (max(1, int(width * scale)), max(1, int(height * scale))),
                       interpolation=cv2.INTER_AREA)
    return small, (width, height)


def _feather_and_clean(mask: np.ndarray, *, kernel_ratio: float = 0.006,
                       sigma_ratio: float = 0.0012) -> np.ndarray:
    """Morphology to drop speckle, a small blur so the alpha edge is not a staircase."""
    import cv2

    height, width = mask.shape[:2]
    k = max(3, int(round(min(height, width) * kernel_ratio)) | 1)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))
    cleaned = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    cleaned = cv2.morphologyEx(cleaned, cv2.MORPH_CLOSE, kernel)
    sigma = max(0.8, min(height, width) * sigma_ratio)
    return cv2.GaussianBlur(cleaned, (0, 0), sigmaX=sigma)


def _upscale(mask: np.ndarray, size: Tuple[int, int]) -> np.ndarray:
    import cv2

    if (mask.shape[1], mask.shape[0]) == size:
        return mask
    return cv2.resize(mask, size, interpolation=cv2.INTER_LINEAR)


def background_distance_alpha(rgb: np.ndarray, *, threshold: int = 28) -> np.ndarray:
    """Pixels that differ from the corner-sampled background, cleaned and feathered."""
    small, (full_w, full_h) = _working(rgb)
    background = _corner_background(small)
    difference = np.abs(small.astype(np.int16) - background.astype(np.int16)).max(axis=2)
    mask = ((difference > int(threshold)).astype(np.uint8)) * 255
    coverage = float((mask > 0).mean())
    if coverage > 0.92:
        # No separable background: everything differs from the corners.
        mask = np.full_like(mask, 255)
    else:
        mask = _feather_and_clean(mask)
    return _upscale(mask, (full_w, full_h))


def otsu_lab_alpha(rgb: np.ndarray) -> np.ndarray:
    """Otsu threshold on the LAB distance from the corner background."""
    import cv2

    small, (full_w, full_h) = _working(rgb)
    lab = cv2.cvtColor(small, cv2.COLOR_RGB2LAB).astype(np.int32)
    background = _corner_background(small)
    background_lab = cv2.cvtColor(background.astype(np.uint8).reshape(1, 1, 3),
                                  cv2.COLOR_RGB2LAB).reshape(3).astype(np.int32)
    distance = np.sqrt(((lab - background_lab) ** 2).sum(axis=2))
    scaled = np.clip(distance, 0, 255).astype(np.uint8)
    _, mask = cv2.threshold(scaled, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    if float((mask > 0).mean()) > 0.92:
        mask = np.full_like(mask, 255)
    else:
        mask = _feather_and_clean(mask, kernel_ratio=0.012)
    return _upscale(mask, (full_w, full_h))


def grabcut_alpha(rgb: np.ndarray, *, iterations: int = 5) -> np.ndarray:
    """OpenCV GrabCut from an inset rectangle; the border is certainly background."""
    import cv2

    small, (full_w, full_h) = _working(rgb)
    height, width = small.shape[:2]
    inset_x, inset_y = max(1, int(width * 0.06)), max(1, int(height * 0.06))
    mask = np.full((height, width), cv2.GC_BGD, dtype=np.uint8)
    mask[inset_y:height - inset_y, inset_x:width - inset_x] = cv2.GC_PR_BGD
    core_x, core_y = max(2, int(width * 0.22)), max(2, int(height * 0.18))
    mask[core_y:height - core_y, core_x:width - core_x] = cv2.GC_PR_FGD
    background_model = np.zeros((1, 65), np.float64)
    foreground_model = np.zeros((1, 65), np.float64)
    cv2.grabCut(small, mask, None, background_model, foreground_model,
                int(iterations), cv2.GC_INIT_WITH_MASK)
    binary = np.where((mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD), 255, 0).astype(np.uint8)
    binary = _feather_and_clean(binary, kernel_ratio=0.004)
    return _upscale(binary, (full_w, full_h))


def _comfy_post(url: str, path: str, payload: Dict[str, Any], timeout: float) -> Dict[str, Any]:
    request = urllib.request.Request(
        url.rstrip("/") + path, data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8", "replace") or "{}")


def _comfy_upload(url: str, data: bytes, filename: str, timeout: float = 180.0) -> str:
    boundary = "----northstar" + uuid.uuid4().hex
    head = (f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="image"; filename="{filename}"\r\n'
            f"Content-Type: image/png\r\n\r\n").encode("utf-8")
    tail = (f"\r\n--{boundary}\r\n"
            f'Content-Disposition: form-data; name="overwrite"\r\n\r\ntrue'
            f"\r\n--{boundary}--\r\n").encode("utf-8")
    request = urllib.request.Request(
        url.rstrip("/") + "/upload/image", data=head + data + tail,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        info = json.loads(response.read().decode("utf-8") or "{}")
    name = info.get("name") or filename
    subfolder = (info.get("subfolder") or "").strip("/")
    return f"{subfolder}/{name}" if subfolder else name


def birefnet_graph(image_name: str, model: str = "birefnet.safetensors") -> Dict[str, Any]:
    """The graph already recorded as live in studio_generation: mask -> inverted alpha."""
    return {
        "1": {"class_type": "LoadBackgroundRemovalModel",
              "inputs": {"bg_removal_name": model}},
        "2": {"class_type": "LoadImage", "inputs": {"image": image_name}},
        "3": {"class_type": "RemoveBackground",
              "inputs": {"bg_removal_model": ["1", 0], "image": ["2", 0]}},
        "4": {"class_type": "InvertMask", "inputs": {"mask": ["3", 0]}},
        "5": {"class_type": "JoinImageWithAlpha",
              "inputs": {"image": ["2", 0], "alpha": ["4", 0]}},
        "6": {"class_type": "SaveImage",
              "inputs": {"images": ["5", 0], "filename_prefix": "ns-sel01b-cutout"}},
    }


def birefnet_alpha(rgb: np.ndarray, *, url: str = "http://127.0.0.1:8188",
                   timeout: float = 600.0) -> np.ndarray:
    """BiRefNet matting through a ComfyUI instance the caller owns. Needs the media lane."""
    from io import BytesIO
    from PIL import Image

    png = _png_bytes(rgb)
    name = _comfy_upload(url, png, f"sel01b-{uuid.uuid4().hex[:8]}.png")
    queued = _comfy_post(url, "/prompt", {"prompt": birefnet_graph(name),
                                          "client_id": "ns-sel01b-cutout"}, 30)
    prompt_id = queued.get("prompt_id")
    if not prompt_id:
        raise CutoutUnavailable(f"ComfyUI rejected the BiRefNet graph: {queued}")
    deadline = time.time() + timeout
    while time.time() < deadline:
        with urllib.request.urlopen(url.rstrip("/") + "/history/" + prompt_id, timeout=15) as log:
            history = json.loads(log.read().decode("utf-8", "replace") or "{}")
        entry = history.get(prompt_id) or {}
        status = entry.get("status") or {}
        if status.get("status_str") == "error":
            raise CutoutUnavailable(f"BiRefNet run failed: {status}")
        images = [image for node in (entry.get("outputs") or {}).values()
                  for image in (node.get("images") or []) if image.get("type") == "output"]
        if images:
            image = images[0]
            query = urllib.parse.urlencode({"filename": image["filename"],
                                            "subfolder": image.get("subfolder", ""),
                                            "type": "output"})
            with urllib.request.urlopen(url.rstrip("/") + "/view?" + query, timeout=60) as resp:
                data = resp.read()
            with Image.open(BytesIO(data)) as opened:
                rgba = opened.convert("RGBA")
                return np.asarray(rgba)[:, :, 3].copy()
        time.sleep(1.0)
    raise CutoutUnavailable("timed out waiting for the BiRefNet cutout")


def _png_bytes(rgb: np.ndarray) -> bytes:
    from io import BytesIO
    from PIL import Image

    buffer = BytesIO()
    Image.fromarray(rgb, mode="RGB").save(buffer, format="PNG")
    return buffer.getvalue()


def cutout(source: str | Path | bytes | np.ndarray, method: str,
           **kwargs: Any) -> Cutout:
    """Run one named method. Unknown or unavailable methods are refused, never swapped."""
    rgb = source if isinstance(source, np.ndarray) else load_rgb(source)
    started = time.perf_counter()
    if method == "background_distance":
        alpha = background_distance_alpha(rgb, **kwargs)
    elif method == "otsu_lab":
        alpha = otsu_lab_alpha(rgb)
    elif method == "grabcut":
        alpha = grabcut_alpha(rgb, **kwargs)
    elif method == "birefnet":
        alpha = birefnet_alpha(rgb, **kwargs)
    elif method == "rembg":
        raise CutoutUnavailable("rembg is not installed in this environment")
    else:
        raise CutoutUnavailable(f"unknown cutout method {method!r}; known: {CANDIDATES}")
    seconds = time.perf_counter() - started
    small, _ = _working(rgb)
    return Cutout(method=method, alpha=alpha, rgb=rgb, seconds=seconds,
                  working_side=int(max(small.shape[:2])),
                  notes={"kwargs": {k: v for k, v in kwargs.items() if k != "url"}})


def alpha_metrics(alpha: np.ndarray, *, reference_coverage: Optional[float] = None,
                  solid: int = SOLID) -> Dict[str, Any]:
    """Coverage, edge gradient width and bbox for one alpha plane.

    ``edge_gradient_px`` is the transition band measured in pixels: the count of
    partially transparent pixels divided by the boundary perimeter. A hard mask
    is ~1-2 px; a heavily feathered one is 5+ px. It measures the delivered edge,
    not the method's intent.
    """
    binary = alpha >= solid
    coverage = float(binary.mean())
    rows, columns = np.where(binary)
    bbox = ([int(columns.min()), int(rows.min()), int(columns.max() + 1),
             int(rows.max() + 1)] if rows.size else [0, 0, 0, 0])
    if rows.size:
        boundary = (binary[:, 1:] != binary[:, :-1]).sum() + \
                   (binary[1:, :] != binary[:-1, :]).sum()
    else:
        boundary = 0
    transition = int(((alpha > 12) & (alpha < 243)).sum())
    width = float(transition) / float(max(1, int(boundary)))
    area = int(binary.sum())
    roughness = (float(boundary) / (2.0 * float(np.sqrt(np.pi * max(1, area))))
                 if area else 0.0)
    border = np.concatenate([binary[0, :], binary[-1, :], binary[:, 0], binary[:, -1]])
    metrics: Dict[str, Any] = {
        "coverage": round(coverage, 4),
        "edge_gradient_px": round(width, 3),
        "boundary_roughness": round(roughness, 3),
        "border_contact": round(float(border.mean()), 4),
        "transition_px": transition,
        "perimeter_px": int(boundary),
        "bbox": bbox,
        "subject_px": int(rows.size),
    }
    if reference_coverage is not None:
        metrics["reference_coverage"] = round(float(reference_coverage), 4)
        metrics["coverage_delta"] = round(abs(coverage - float(reference_coverage)), 4)
    return metrics


def coverage_plausible(metrics: Dict[str, Any], *, max_delta: float = 0.20) -> Optional[bool]:
    """Is the coverage consistent with the reference's own subject mask?

    None means "not measurable": on a full-bleed picture the corner mask is the
    scene, not a silhouette. The cut-off is 0.80 because the Mogra forest mockup's
    corner mask marks 85% of the frame, i.e. it describes foliage and sky; using it
    as ground truth penalised the methods that correctly cut out only the pack.
    """
    reference = metrics.get("reference_coverage")
    coverage = metrics.get("coverage")
    if reference is None or coverage is None:
        return None
    if float(reference) > 0.80:
        return None
    if float(coverage) < 0.03:
        return False
    return abs(float(coverage) - float(reference)) <= max_delta


def border_ok(metrics: Dict[str, Any], *, max_contact: float = 0.05) -> bool:
    """A product cutout does not own the frame border; a scene pasted whole does."""
    return float(metrics.get("border_contact") or 0.0) <= float(max_contact)


def compose_on(rgb: np.ndarray, alpha: np.ndarray,
               background: Tuple[int, int, int] = (255, 255, 255)) -> np.ndarray:
    """The product over a flat background, for measuring what survived the cut."""
    a = (alpha.astype(np.float32) / 255.0)[:, :, None]
    bg = np.array(background, dtype=np.float32).reshape(1, 1, 3)
    return np.clip(rgb.astype(np.float32) * a + bg * (1.0 - a), 0, 255).astype(np.uint8)


def rgba_png_bytes(rgb: np.ndarray, alpha: np.ndarray) -> bytes:
    from io import BytesIO
    from PIL import Image

    buffer = BytesIO()
    Image.fromarray(np.dstack([rgb, alpha]), mode="RGBA").save(buffer, format="PNG")
    return buffer.getvalue()


__all__ = [
    "CANDIDATES",
    "Cutout",
    "CutoutUnavailable",
    "METHODS",
    "SOLID",
    "WORKING_MAX_SIDE",
    "alpha_metrics",
    "background_distance_alpha",
    "birefnet_alpha",
    "birefnet_graph",
    "border_ok",
    "compose_on",
    "coverage_plausible",
    "cutout",
    "grabcut_alpha",
    "load_rgb",
    "otsu_lab_alpha",
    "rgba_png_bytes",
]
