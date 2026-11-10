"""Separate the product body from its label, and put the label on by warp.

A text-to-image model asked for "a pouch printed ORGANIC LION'S MANE" draws *plausible letters* —
which no OCR can read and which the brief's text rule then fails. Splitting the job is the fix the
owner asked for:

* the model draws the **body** — shape, colour, material, zipper — with no lettering at all;
* the **label** is composed deterministically (Pillow: brand, product, weight) and warped onto the
  body's front face with a measured quad, exactly like the packaging stage warps artwork.

That makes the copy readable by construction, and it keeps the model doing the thing it is good at.

This module holds the label composer and the warp; the generator calls them for a brief that asks for
`label_mode: "warp"`.
"""
from __future__ import annotations

from io import BytesIO
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

LABEL_W, LABEL_H = 900, 1200
INK = (26, 42, 34)
ACCENT = (33, 92, 66)
PAPER = (250, 249, 245)
RULE = (206, 210, 204)


def _font(size: int, *, bold: bool = False):
    from PIL import ImageFont  # noqa: PLC0415

    for name in (("georgiab.ttf", "segoeuib.ttf") if bold else ("georgia.ttf", "segoeui.ttf")):
        path = f"C:/Windows/Fonts/{name}"
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def compose_label(brief: Dict[str, Any]) -> bytes:
    """The label artwork, as a flat panel. Deterministic: same brief, same bytes."""
    from PIL import Image, ImageDraw  # noqa: PLC0415

    panel = Image.new("RGB", (LABEL_W, LABEL_H), PAPER)
    draw = ImageDraw.Draw(panel)
    label = brief.get("label") or {}
    brand = str(label.get("brand") or (brief.get("product_line") or "northstar")).upper()
    product = str(label.get("product") or brief.get("category") or "").upper()
    weight = str(label.get("weight") or "")
    lines: List[str] = [str(item).upper() for item in (label.get("lines") or []) if str(item).strip()]

    draw.rounded_rectangle((24, 24, LABEL_W - 24, LABEL_H - 24), radius=48,
                           fill=PAPER, outline=RULE, width=6)
    draw.text((72, 90), brand, font=_font(76, bold=True), fill=INK)
    draw.line((72, 190, LABEL_W - 72, 190), fill=ACCENT, width=6)
    y = 240
    for index, line in enumerate(([product] if product else []) + lines):
        font = _font(64 if index == 0 else 44, bold=index == 0)
        draw.text((72, y), line[:28], font=font, fill=INK)
        y += 92 if index == 0 else 64
        if y > LABEL_H - 260:
            break
    if weight:
        draw.text((72, LABEL_H - 200), weight, font=_font(48), fill=ACCENT)
    draw.line((72, LABEL_H - 150, LABEL_W - 72, LABEL_H - 150), fill=RULE, width=4)
    draw.text((72, LABEL_H - 128), "northstar · label artwork", font=_font(32), fill=RULE)

    buffer = BytesIO()
    panel.save(buffer, format="PNG")
    return buffer.getvalue()


def _quad_for(box: Sequence[int], *, inset: float = 0.18, top: float = 0.16,
              height: float = 0.52) -> List[List[int]]:
    """Where the label sits on the body: a quad on the upper front, slightly trapezoid."""
    # height used to be both the box height and the label-height fraction: the unpacking shadowed
    # the parameter and the quad ran off the canvas. Two names, no shadowing.
    x, y, box_w, box_h = (int(v) for v in box)
    left = x + int(box_w * inset)
    right = x + box_w - int(box_w * inset)
    upper = y + int(box_h * top)
    lower = y + int(box_h * (top + height))
    pinch = int((right - left) * 0.04)
    return [[left + pinch, upper], [right - pinch, upper], [right, lower], [left, lower]]


def warp_label(canvas_bytes: bytes, box: Sequence[int], label_png: bytes, *,
               quad: Optional[Sequence[Sequence[int]]] = None,
               strength: float = 1.0) -> Dict[str, Any]:
    """Warp the label into a quad on the body and blend it with the body's own shading."""
    import cv2  # noqa: PLC0415
    from PIL import Image  # noqa: PLC0415

    target = list(quad) if quad else _quad_for(box)
    # np.asarray on a PIL image returns a read-only view; the blend writes into it.
    canvas = np.array(Image.open(BytesIO(canvas_bytes)).convert("RGB"))
    label = np.asarray(Image.open(BytesIO(label_png)).convert("RGB"))
    xs = [int(point[0]) for point in target]
    ys = [int(point[1]) for point in target]
    left, top = min(xs), min(ys)
    right, bottom = max(xs), max(ys)
    width, height = right - left + 1, bottom - top + 1
    if width <= 2 or height <= 2:
        raise ValueError("the label quad has no area")

    source = np.float32([[0, 0], [label.shape[1] - 1, 0],
                         [label.shape[1] - 1, label.shape[0] - 1], [0, label.shape[0] - 1]])
    dest = np.float32([[point[0] - left, point[1] - top] for point in target])
    matrix = cv2.getPerspectiveTransform(source, dest)
    warped = cv2.warpPerspective(label, matrix, (width, height), flags=cv2.INTER_AREA,
                                 borderMode=cv2.BORDER_REPLICATE)

    # Multiply by the body's own luminance so the label sits *on* the material rather than floating
    # over it. A flat paste is the thing that reads as a sticker.
    region = canvas[top:top + height, left:left + width].astype(np.float32)
    shade = region.mean(axis=2, keepdims=True) / max(1.0, float(region.mean()))
    shade = np.clip(shade, 0.55, 1.25)
    blended = np.clip(warped.astype(np.float32) * (1.0 + (shade - 1.0) * float(strength)), 0, 255)
    # Only the quad itself is written. The bounding box is a rectangle around a trapezoid, and
    # pasting the box would put label pixels in the corners the label does not cover.
    footprint = cv2.warpPerspective(np.full((label.shape[0], label.shape[1]), 255, np.uint8),
                                    matrix, (width, height), flags=cv2.INTER_NEAREST,
                                    borderMode=cv2.BORDER_CONSTANT, borderValue=0) > 0
    target_region = canvas[top:top + height, left:left + width]
    target_region[footprint] = blended.astype(np.uint8)[footprint]
    canvas[top:top + height, left:left + width] = target_region

    buffer = BytesIO()
    Image.fromarray(canvas).save(buffer, format="PNG")
    return {"bytes": buffer.getvalue(), "quad": target,
            "meta": {"layout": "label_warp", "quad": target, "strength": round(float(strength), 3)}}
