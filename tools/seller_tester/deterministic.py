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

**Every box in this module is `(x, y, width, height)`.** The generator records `product_box` as
`(left, top, right, bottom)` and converts once at the boundary; mixing the two conventions has
produced two false geometry failures on this project, so the conversion lives in one place.

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


def _text_width(draw, text: str, font) -> int:
    try:
        bounds = draw.textbbox((0, 0), text, font=font)
        return bounds[2] - bounds[0]
    except (AttributeError, ValueError):
        return int(len(text) * getattr(font, "size", 12) * 0.55)


def _wrap_text(text: str, font, max_width: int, draw) -> List[str]:
    """Wrap one declared line to the column width, on word boundaries only."""
    words = str(text or "").split()
    if not words:
        return [""]
    out: List[str] = []
    current = words[0]
    for word in words[1:]:
        trial = f"{current} {word}"
        if _text_width(draw, trial, font) <= max_width:
            current = trial
        else:
            out.append(current)
            current = word
    out.append(current)
    return out


def _typeset_copy(page, lines: Sequence[str], box: Sequence[int], *,
                  size: int, align: str = "left", rules: bool = False) -> int:
    """Draw each declared line inside a pixel box, wrapping to its width.

    Deterministic: same font, same box, same lines, same pixels. The box is in the module's
    margin, never over the product panel.
    """
    from PIL import ImageDraw  # noqa: PLC0415

    left, top, width, height = (int(v) for v in box)
    if width <= 0 or height <= 0:
        return 0
    draw = ImageDraw.Draw(page)
    font = _font(max(12, int(size)))
    gap = max(4, int(size * 0.42))
    y = top
    drawn = 0
    for raw in lines:
        for line in _wrap_text(str(raw), font, width, draw):
            if y + size > top + height:
                return drawn
            x = left
            if align == "center":
                x = left + max(0, (width - _text_width(draw, line, font)) // 2)
            elif align == "right":
                x = left + max(0, width - _text_width(draw, line, font))
            draw.text((x, y), line, font=font, fill=INK)
            y += size + gap
            drawn += 1
        if rules and drawn:
            draw.line((left, y - gap // 2, left + width, y - gap // 2),
                      fill=RULE, width=max(1, size // 24))
    return drawn


def infographic(canvas_bytes: bytes, product_box: Sequence[int],
                brief: Dict[str, Any], *, title: str = "",
                copy_lines: Sequence[str] = (), variant: str = "page",
                copy_box: Optional[Sequence[float]] = None, copy_align: str = "left",
                background: Optional[int] = None) -> Dict[str, Any]:
    """Compose a page: the scene as a framed photo panel, copy in the margins. Deterministic.

    A full-bleed collage is 100 % "subject" by the brief's own fill measure, so a page has to leave
    real margin. The scene (with the product already placed in it) becomes a panel inset on paper;
    the title, callouts and footer live in the margin. The product's box is mapped through the
    panel transform and returned, so the product-region check still compares the real pixels.

    `variant` is the one layout parameter the A+ producer needs:

    * ``page``  - the original page: a centred 70 % x 50 % photo panel, copy and callouts in the
      margins;
    * ``band``  - a wide module: the photo panel sits on the product's own side (left when the
      product is anchored left) and the declared copy is typeset in the opposite column;
    * ``copy``  - a text-only module: no panel, the declared copy fills its own box.
    """
    from PIL import Image, ImageDraw  # noqa: PLC0415

    if variant not in ("page", "band", "copy"):
        raise ValueError(f"variant must be 'page', 'band' or 'copy', got {variant!r}")
    source = _as_image(canvas_bytes)
    width, height = source.size
    seed = stable_seed(str(brief.get("id") or "infographic"))
    box = [int(v) for v in product_box]
    # The page meets the brief's background level, so `subject_fill` measures the panel and the
    # copy rather than counting a slightly-off-white page as 100 % subject. An A+ module carries
    # its own background; the caller passes it explicitly so the module and its page agree.
    if background is not None:
        page_level = background
    else:
        page_background = ((brief.get("page") or {}).get("background") or {})
        background = ((brief.get("constraints") or {}).get("background") or {})
        page_level = background.get("value", page_background.get("value", 255))
    try:
        page_level = int(page_level)
    except (TypeError, ValueError):
        page_level = 255
    page_level = max(0, min(255, page_level))
    lines = [str(line) for line in copy_lines if str(line).strip()]

    page = _from_array(np.full((height, width, 3), page_level, dtype=np.uint8))
    draw = ImageDraw.Draw(page)
    top = _font(max(28, height // 16), bold=True)
    sub = _font(max(20, height // 34))
    small = _font(max(16, height // 52))
    heading = (title or str(brief.get("product_line") or brief.get("category") or "product"))
    heading = heading.replace("-", " ").upper()

    def footer() -> None:
        foot_y = int(height * 0.94)
        draw.line((int(width * 0.07), foot_y - int(height * 0.014),
                   int(width * 0.93), foot_y - int(height * 0.014)),
                  fill=RULE, width=max(2, height // 900))
        draw.text((int(width * 0.07), foot_y),
                  f"prepared by northstar  ·  {str(brief.get('id') or '')}".strip(), font=small,
                  fill=INK)

    def accent_rule() -> None:
        # Inset so all four corners stay at the page level: the fill measure samples the corners,
        # and a full-bleed bar at a corner makes a white page read as 99 % subject.
        draw.rectangle((int(width * 0.07), int(height * 0.018),
                        int(width * 0.93), int(height * 0.026)), fill=ACCENT)

    if variant == "copy":
        accent_rule()
        drawn = 0
        if title:
            draw.text((int(width * 0.07), int(height * 0.045)), heading, font=top, fill=INK)
        fractions = copy_box or (0.06, 0.22, 0.88, 0.62)
        pixel_box = (int(width * float(fractions[0])), int(height * float(fractions[1])),
                     int(width * float(fractions[2])), int(height * float(fractions[3])))
        drawn = _typeset_copy(page, lines or [heading], pixel_box,
                              size=max(18, int(height * 0.065)),
                              align=copy_align or "left", rules=False)
        footer()
        out = _as_png(page)
        rgb = np.asarray(page)
        return {
            "bytes": out,
            "meta": {"layout": "module_copy", "variant": variant, "callouts": 0,
                     "seed": seed, "title": heading, "copy_lines": drawn,
                     "margin_ink": round(margin_ink_fraction(rgb), 5),
                     "product_box": list(box),
                     "copy_source": "the brief's declared copy, typeset deterministically"},
            "product_box": list(box),
        }

    # The photo panel. A page centres it; a wide band puts it on the product's own side and
    # leaves the opposite column for the declared copy.
    if variant == "page":
        panel_w = int(width * 0.70)
        panel_h = int(height * 0.50)
        panel_x = (width - panel_w) // 2
        panel_y = int(height * 0.27)
        copy_left = int(width * 0.07)
        copy_width = int(width * 0.86)
        copy_top = int(height * 0.135)
        copy_height = int(height * 0.125)
        body_size = max(18, height // 34)
    else:
        panel_w = int(width * 0.46)
        panel_h = int(height * 0.68)
        panel_y = int(height * 0.16)
        centre = box[0] + box[2] / 2.0
        panel_right = centre >= width / 2.0
        panel_x = int(width * 0.50) if panel_right else int(width * 0.06)
        copy_left = int(width * 0.05) if panel_right else int(width * 0.55)
        copy_width = int(width * 0.40)
        copy_top = int(height * 0.24)
        copy_height = int(height * 0.58)
        body_size = max(18, int(height * 0.055))

    # Crop around the product with a small margin, keeping the product's own aspect, then fit that
    # crop into the panel rectangle. The panel is sized to the crop, so the mapping is one uniform
    # scale: the product is never stretched, and the panel edge never crops it. (The old panel
    # aspect was imposed on the crop; a wide subject and a taller panel then clamped one dimension,
    # which distorted the mapped box and made a correct composite score as a mismatched region.)
    max_x, max_y, max_w, max_h = panel_x, panel_y, panel_w, panel_h
    margin = min(1.18, width / float(max(1, box[2])), height / float(max(1, box[3])))
    crop_w = max(float(box[2]) * margin, 1.0)
    crop_h = max(float(box[3]) * margin, 1.0)
    crop_aspect = crop_w / crop_h
    cx, cy = box[0] + box[2] / 2.0, box[1] + box[3] / 2.0
    if max_w / float(max_h) > crop_aspect:
        panel_h = max_h
        panel_w = max(1, int(round(panel_h * crop_aspect)))
    else:
        panel_w = max_w
        panel_h = max(1, int(round(panel_w / crop_aspect)))
    panel_x = max_x + (max_w - panel_w) // 2
    panel_y = max_y + (max_h - panel_h) // 2
    left = int(round(max(0.0, min(width - crop_w, cx - crop_w / 2.0))))
    upper = int(round(max(0.0, min(height - crop_h, cy - crop_h / 2.0))))
    crop_w = max(1, min(int(round(crop_w)), width - left))
    crop_h = max(1, min(int(round(crop_h)), height - upper))
    crop = source.crop((left, upper, left + crop_w, upper + crop_h))
    panel = crop.resize((panel_w, panel_h), Image.LANCZOS)
    page.paste(panel, (panel_x, panel_y))
    draw.rectangle((panel_x, panel_y, panel_x + panel_w, panel_y + panel_h),
                   outline=RULE, width=max(2, height // 500))

    scale = min(panel_w / float(max(1, crop_w)), panel_h / float(max(1, crop_h)))
    mapped = [int(round(panel_x + (box[0] - left) * scale)),
              int(round(panel_y + (box[1] - upper) * scale)),
              max(1, int(round(box[2] * scale))),
              max(1, int(round(box[3] * scale)))]

    # Title above the panel.
    accent_rule()
    draw.text((int(width * 0.07), int(height * 0.030)), heading, font=top, fill=INK)
    draw.text((int(width * 0.07), int(height * 0.085)), "product guide", font=sub, fill=ACCENT)
    draw.line((int(width * 0.07), int(height * 0.118), int(width * 0.45), int(height * 0.118)),
              fill=RULE, width=max(2, height // 700))

    drawn = 0
    if variant == "page":
        # Callouts live in the side margins and point *into* the panel. Nothing is drawn over the
        # product: a chip or a line across the label would destroy the very pixels being audited.
        chip_w = int(width * 0.125)
        for index, label in enumerate(CALLOUTS):
            left_side = (index + seed) % 2 == 0
            y = panel_y + int(panel_h * (0.14 + 0.32 * index))
            chip_x = int(width * 0.012) if left_side else (width - chip_w - int(width * 0.012))
            draw.rounded_rectangle((chip_x, y, chip_x + chip_w, y + int(height * 0.032)),
                                   radius=max(4, height // 320), fill=PAPER, outline=RULE,
                                   width=max(2, height // 900))
            draw.text((chip_x + int(width * 0.008), y + int(height * 0.006)), label.upper(),
                      font=small, fill=INK)
            start = (chip_x + chip_w, y + int(height * 0.016)) if left_side \
                else (chip_x, y + int(height * 0.016))
            end = ((panel_x + 8) if left_side else (panel_x + panel_w - 8),
                   min(max(y + int(height * 0.016), mapped[1]), mapped[1] + mapped[3]))
            draw.line((start, end), fill=ACCENT, width=max(2, height // 900))
            dot = max(3, height // 320)
            draw.ellipse((end[0] - dot, end[1] - dot, end[0] + dot, end[1] + dot), fill=ACCENT)
            drawn += 1

    # The brief's own copy. In a band it fills the column opposite the panel; in a page it sits in
    # the top margin above the panel. Nothing is ever drawn over the product pixels.
    copied = 0
    if lines:
        copied = _typeset_copy(page, lines, (copy_left, copy_top, copy_width, copy_height),
                               size=body_size, align=copy_align or "left",
                               rules=bool((brief.get("page") or {}).get("rules")))
    footer()

    out = _as_png(page)
    rgb = np.asarray(page)
    return {
        "bytes": out,
        "meta": {"layout": "infographic" if variant == "page" else "module_band",
                 "variant": variant, "callouts": drawn, "seed": seed,
                 "title": heading, "panel": [panel_x, panel_y, panel_w, panel_h],
                 "copy_lines": copied,
                 "margin_ink": round(margin_ink_fraction(rgb), 5),
                 "product_box": mapped,
                 "copy_source": ("the brief's declared copy, typeset deterministically; "
                                 "structural labels only, no product claim is invented "
                                 "by a renderer")},
        "product_box": mapped,
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
