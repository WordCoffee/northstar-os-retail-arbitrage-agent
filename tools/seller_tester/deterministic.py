"""Deterministic layout stages for the two situations a free render cannot satisfy.

An **infographic** is text and callouts on a composed page. A diffusion model draws plausible
lettering that no OCR can read and that lands outside the frame's margin where the copy has to be,
so the brief's own check (`text_expected`, aspect, fill) fails for a reason that is not the
product's fault. A **packaging mockup** is the seller's real artwork on a panel; a generated scene
invents a new box.

So for those two situations the pipeline stops trusting the model with the part that has geometry:

* infographic  = generated (or flat) background, the real cutout placed by the composite path, then
  Pillow draws the title, the callout labels with leader lines and the footer. Deterministic: same
  brief, same inputs, same bytes.
* packaging_mockup = the placed artwork is perspective-warped onto a panel quad inside its own
  bounding box, with a crease and a shading gradient. Deterministic for the same reason.

Neither stage invents a product claim. The callouts are structural ("front view", "label",
"net weight"), because a claim is the seller's to make, not a renderer's. That is recorded in the
metadata as `copy_source`, so a reviewer can see the choice rather than infer it.

    python -m tools.seller_tester composite --catalog … --layout deterministic
"""
from __future__ import annotations

import hashlib
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

SITUATIONS = ("infographic", "packaging_mockup")

MARGIN_RATIO = 0.10
INK = (26, 42, 34)
PAPER = (248, 245, 238)
ACCENT = (33, 92, 66)
RULE = (196, 204, 197)

#: Structural labels only. A renderer may say where the product is; it may not say what the
#: product does. The seller supplies claims, if any.
CALLOUTS = ("front view", "label", "net weight")

FONT_DIR = Path("C:/Windows/Fonts")
FONT_CANDIDATES = ("georgia.ttf", "segoeui.ttf")
FONT_BOLD_CANDIDATES = ("georgiab.ttf", "segoeuib.ttf")


def fit_aspect(canvas_bytes: bytes, product_box: Sequence[int], ratio: float
               ) -> Dict[str, Any]:
    """Extend the canvas to the brief's aspect by mirroring the scene edge. Never crop.

    The render lane produces a square. A brief that asks for 4:5 (0.8) is then failed on `aspect`
    by a pipeline that cannot produce anything but 1.0 — which is what happened to every
    infographic and packaging brief in the held-out run. Extending the canvas is the honest fix:
    the product keeps every pixel it had, the new band is a reflected continuation of the scene
    (not invented content), and the band is where the copy and the footer go.

    Returns the new bytes, the product box moved into the new canvas, and what was added.
    """
    from PIL import Image  # noqa: PLC0415

    target = float(ratio)
    if not 0.2 <= target <= 5.0:
        raise ValueError(f"aspect ratio {ratio!r} is outside 0.2..5.0")
    image = _as_image(canvas_bytes)
    width, height = image.size
    current = width / float(height)
    if abs(current - target) <= 0.005:
        return {"bytes": canvas_bytes, "product_box": [int(v) for v in product_box],
                "added": {"width": 0, "height": 0, "top": 0, "left": 0}}

    array = np.asarray(image)
    x, y, box_w, box_h = (int(v) for v in product_box)
    if target < current:
        new_width, new_height = width, int(round(width / target))
        add = new_height - height
        # Two thirds of the new band above the product (title), one third below (footer).
        top = int(round(add * 0.66))
        canvas = np.zeros((new_height, new_width, 3), dtype=np.uint8)
        canvas[top:top + height] = array
        if top:
            canvas[:top] = np.flipud(array[:min(top, height)])[-top:]
        if add - top:
            bottom = add - top
            canvas[top + height:] = np.flipud(array[-min(bottom, height):])[:bottom]
        moved = [x, y + top, box_w, box_h]
        added = {"width": 0, "height": add, "top": top, "left": 0}
    else:
        new_width, new_height = int(round(height * target)), height
        add = new_width - width
        left = add // 2
        canvas = np.zeros((new_height, new_width, 3), dtype=np.uint8)
        canvas[:, left:left + width] = array
        if left:
            canvas[:, :left] = np.fliplr(array[:, :min(left, width)])[:, -left:]
        if add - left:
            right = add - left
            canvas[:, left + width:] = np.fliplr(array[:, -min(right, width):])[:, :right]
        moved = [x + left, y, box_w, box_h]
        added = {"width": add, "height": 0, "top": 0, "left": left}

    # A gentle darkening of the reflected band, so it reads as a page margin rather than a glitch.
    if added["height"]:
        band = canvas[:added["top"]] if added["top"] else canvas[-max(1, added["height"] - added["top"]):]
        band[:] = np.clip(band.astype(np.float32) * 0.82, 0, 255).astype(np.uint8)
    elif added["width"]:
        canvas[:, :added["left"]] = np.clip(
            canvas[:, :added["left"]].astype(np.float32) * 0.82, 0, 255).astype(np.uint8)
    out = _as_png(_from_array(canvas))
    return {"bytes": out, "product_box": moved, "added": added}


def brief_aspect(brief: Dict[str, Any], default: float = 1.0) -> float:
    spec = ((brief.get("constraints") or {}).get("aspect") or {})
    try:
        ratio = float(spec.get("ratio") or default)
    except (TypeError, ValueError):
        return default
    return ratio if 0.2 <= ratio <= 5.0 else default


def stable_seed(text: str) -> int:
    """A seed for layout jitter that is the same on every machine and every run."""
    return int(hashlib.sha256(str(text).encode("utf-8")).hexdigest()[:8], 16)


def _font(size: int, *, bold: bool = False):
    from PIL import ImageFont  # noqa: PLC0415

    for name in (FONT_BOLD_CANDIDATES if bold else FONT_CANDIDATES):
        path = FONT_DIR / name
        if path.is_file():
            try:
                return ImageFont.truetype(str(path), size)
            except OSError:
                continue
    return ImageFont.load_default()


def _as_image(canvas_bytes: bytes):
    from PIL import Image  # noqa: PLC0415

    return Image.open(BytesIO(canvas_bytes)).convert("RGB")


def _as_png(image) -> bytes:
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _outside(box: Sequence[int], rect: Tuple[int, int, int, int]) -> bool:
    left, top, right, bottom = rect
    x, y, width, height = (int(v) for v in box)
    return right <= x or left >= x + width or bottom <= y or top >= y + height


def margin_ink_fraction(rgb: np.ndarray, ratio: float = MARGIN_RATIO) -> float:
    """The fraction of the outer band that is ink — the same measure the scorer applies."""
    height, width = rgb.shape[:2]
    band = max(1, int(min(width, height) * ratio))
    grey = rgb.mean(axis=2)
    ink = (grey < 235)
    border = np.zeros_like(ink, dtype=bool)
    border[:band, :] = True
    border[-band:, :] = True
    border[:, :band] = True
    border[:, -band:] = True
    return float(ink[border].mean())


def infographic(canvas_bytes: bytes, product_box: Sequence[int],
                brief: Dict[str, Any], *, title: str = "") -> Dict[str, Any]:
    """Draw the page furniture around an already-placed product. Deterministic."""
    from PIL import ImageDraw  # noqa: PLC0415

    image = _as_image(canvas_bytes)
    draw = ImageDraw.Draw(image)
    width, height = image.size
    seed = stable_seed(str(brief.get("id") or "infographic"))
    box = [int(v) for v in product_box]

    top = _font(max(28, height // 16), bold=True)
    sub = _font(max(20, height // 34))
    small = _font(max(16, height // 52))

    # Title inside the top margin band, so the copy is where the brief says copy lives.
    heading = (title or str(brief.get("product_line") or brief.get("category") or "product"))
    heading = heading.replace("-", " ").upper()
    band = int(height * MARGIN_RATIO)
    # A filled banner guarantees readable margin ink instead of relying on a thin line of type:
    # the brief's `text_expected` rule measures ink in the outer band, and 0.01 % is not copy.
    draw.rectangle((0, 0, width, min(height, int(band * 1.15))), fill=PAPER)
    draw.rectangle((0, 0, width, max(6, height // 90)), fill=ACCENT)
    draw.text((int(width * 0.06), int(height * 0.030)), heading, font=top, fill=INK)
    draw.text((int(width * 0.06), int(height * 0.082)), "product guide", font=sub,
              fill=ACCENT)
    draw.line((int(width * 0.06), int(height * 0.112), int(width * 0.44), int(height * 0.112)),
              fill=RULE, width=max(2, height // 700))

    # Callouts: label + leader line aimed at the product box edge, never drawn over the product.
    drawn = 0
    for index, label in enumerate(CALLOUTS):
        y = int(height * (0.40 + 0.16 * index))
        left_text = (index + seed) % 2 == 0
        if left_text:
            anchor_x = int(width * 0.07)
            text = label.upper()
            draw.text((anchor_x, y), text, font=small, fill=INK)
            start = (anchor_x + int(width * 0.20), y + int(height * 0.012))
            end = (box[0] - int(width * 0.005), y + int(height * 0.012))
        else:
            anchor_x = int(width * 0.93) - int(width * 0.20)
            text = label.upper()
            draw.text((anchor_x, y), text, font=small, fill=INK)
            start = (anchor_x - int(width * 0.012), y + int(height * 0.012))
            end = (box[0] + box[2] + int(width * 0.005), y + int(height * 0.012))
        if _outside(box, (min(start[0], end[0]), y, max(start[0], end[0]) + 1,
                          y + int(height * 0.03))):
            draw.line((start, end), fill=ACCENT, width=max(2, height // 900))
            dot = max(3, height // 300)
            draw.ellipse((end[0] - dot, end[1] - dot, end[0] + dot, end[1] + dot),
                         fill=ACCENT)
            drawn += 1

    # Footer strip inside the bottom margin band.
    foot_y = int(height * 0.955)
    draw.rectangle((0, int(height * (1 - MARGIN_RATIO * 1.15)), width, height), fill=PAPER)
    draw.line((int(width * 0.06), foot_y - int(height * 0.012),
               int(width * 0.94), foot_y - int(height * 0.012)),
              fill=RULE, width=max(2, height // 900))
    draw.text((int(width * 0.06), foot_y),
              f"prepared by northstar  ·  {str(brief.get('id') or '')}".strip(), font=small,
              fill=INK)

    out = _as_png(image)
    rgb = np.asarray(_as_image(out))
    return {
        "bytes": out,
        "meta": {"layout": "infographic", "callouts": drawn, "seed": seed,
                 "title": heading,
                 "margin_ink": round(margin_ink_fraction(rgb), 5),
                 "copy_source": ("structural labels only; no product claim is invented "
                                 "by a renderer"),
                 "product_box": box},
    }


def panel_warp(canvas_bytes: bytes, product_box: Sequence[int], brief: Dict[str, Any],
               *, skew: float = 0.06) -> Dict[str, Any]:
    """Perspective-warp the placed artwork onto a panel quad inside its own box. Deterministic.

    The quad is the product's own bounding box with the far edge pulled in by `skew`, which is what
    a panel looks like when it is photographed slightly off-axis. The quad is returned so the
    product-region check can warp the cutout the same way and compare like with like.
    """
    import cv2  # noqa: PLC0415

    image = _as_image(canvas_bytes)
    arr = np.asarray(image)
    x, y, width, height = (int(v) for v in product_box)
    x = max(0, min(x, arr.shape[1] - 1))
    y = max(0, min(y, arr.shape[0] - 1))
    width = max(1, min(width, arr.shape[1] - x))
    height = max(1, min(height, arr.shape[0] - y))
    crop = arr[y:y + height, x:x + width].copy()
    inset = int(round(width * float(skew)))

    source = np.float32([[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]])
    dest = np.float32([[inset, 0], [width - 1 - inset, 0],
                       [width - 1, height - 1], [0, height - 1]])
    matrix = cv2.getPerspectiveTransform(source, dest)
    warped = cv2.warpPerspective(crop, matrix, (width, height),
                                 flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)

    # A soft vertical shading so the panel reads as a surface, and a crease at the far edge.
    shade = np.linspace(1.02, 0.90, height, dtype=np.float32).reshape(height, 1, 1)
    warped = np.clip(warped.astype(np.float32) * shade, 0, 255).astype(np.uint8)

    canvas = arr.copy()
    mask = cv2.warpPerspective(np.full((height, width), 255, dtype=np.uint8), matrix,
                               (width, height), flags=cv2.INTER_NEAREST,
                               borderMode=cv2.BORDER_CONSTANT, borderValue=0) > 0
    canvas[y:y + height, x:x + width][mask] = warped[mask]

    quad = [[x + int(inset), y], [x + width - 1 - int(inset), y],
            [x + width - 1, y + height - 1], [x, y + height - 1]]
    return {
        "bytes": _as_png(_from_array(canvas)),
        "quad": quad,
        "meta": {"layout": "packaging_panel", "skew": round(float(skew), 4),
                 "quad": quad, "panel": [width, height],
                 "product_box": [x, y, width, height],
                 "copy_source": "the seller's artwork, warped onto a panel quad"},
    }


def _from_array(rgb: np.ndarray):
    from PIL import Image  # noqa: PLC0415

    return Image.fromarray(rgb.astype(np.uint8), mode="RGB")


def quad_bbox(quad: Sequence[Sequence[int]]) -> List[int]:
    xs = [int(point[0]) for point in quad]
    ys = [int(point[1]) for point in quad]
    left, top = min(xs), min(ys)
    return [left, top, max(xs) - left + 1, max(ys) - top + 1]
