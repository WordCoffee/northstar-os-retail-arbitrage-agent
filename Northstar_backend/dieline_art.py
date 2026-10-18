"""Dieline panel art — real logo + real fonts + real icons ON the true-scale dieline.

The honest architecture this lands (2026-10-16 evening, after the model kept
producing garbled/ghosted sheets): a diffusion model is the wrong tool for
"print-ready packaging sheets". This lane assembles the sheet deterministically
instead:

  build_doypack geometry (mm, layered)  ->  panel art ops (this module)
  ->  300-dpi PNG preview  +  true PDF (reportlab, real embedded fonts)

Front panel: cream roundel with the operator's REAL logo, Playfair product name,
tracked subtitle, four drawn cert icons, weight footer. Back panel: description
lines, reserved Supplement-Facts / QR / UPC zones (outlined, labelled), storage /
origin / distributed-by lines, zipper note. Everything in millimetres at 100%.

No model, no OCR, no cleanup - spelling is exact by construction.
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFont

import design_studio_print as dp
from mockup_compositor import draw_cert_icon, prepare_logo

FONTS_DIR = Path(__file__).resolve().parent / "assets" / "fonts"
CREAM = (245, 238, 226)
GOLD_A = (196, 160, 74)
GOLD_B = (214, 158, 62)
INK = (23, 23, 23)
MM_PER_IN = 25.4


def _font(name: str, size_px: int, axes=None):
    f = ImageFont.truetype(str(FONTS_DIR / name), size_px)
    if axes is not None:
        try:
            f.set_variation_by_axes(list(axes))
        except Exception:
            pass
    return f


def _clear_text(d: ImageDraw.ImageDraw, cx: float, y: float, text: str, f, fill, tracking=0.0):
    widths = [d.textlength(ch, font=f) for ch in text]
    total = sum(widths) + tracking * max(0, len(text) - 1)
    x = cx - total / 2
    for ch, w_ in zip(text, widths):
        d.text((x, y), ch, font=f, fill=fill, anchor="lm")
        x += w_ + tracking


def extract_ink_motif(image: Any, box: Sequence[int], *, tint: Optional[Tuple[int, int, int]] = None,
                      min_alpha: int = 18) -> Image.Image:
    """Pull engraved line art off a rendered pouch into a reusable RGBA motif.

    Ground luminance comes from the crop's border ring; ink alpha rises as
    pixels darken away from it. Optional tint recolours the ink (e.g. gold);
    without a tint the original ink colour is kept, so a light-ground motif can
    also be placed on a light sheet.
    """
    if isinstance(image, (bytes, bytearray)):
        im = Image.open(io.BytesIO(image))
    elif isinstance(image, (str, Path)):
        im = Image.open(image)
    else:
        im = image
    crop = im.convert("RGB").crop(tuple(int(v) for v in box))
    a = np.array(crop).astype(np.float32)
    lum = a.mean(axis=2)
    # local ground estimate: median filter (ignores ink strokes) then blur.
    # A noise-floor margin keeps lighting/highlight variation from fogging the
    # whole crop - only genuinely darker ink survives.
    from PIL import ImageFilter as IF  # noqa: PLC0415
    size = 31 if min(crop.size) > 40 else 9
    med = crop.convert("L").filter(IF.MedianFilter(size)).filter(IF.GaussianBlur(12))
    bref = np.array(med).astype(np.float32)
    delta = bref - lum
    alpha = np.clip((delta - 16.0) / (bref * 0.32 + 22.0), 0.0, 1.0)
    alpha = np.power(alpha, 1.3)
    h, w = alpha.shape
    fade = 14
    ramp = np.linspace(0.0, 1.0, fade)
    alpha[:fade, :] *= ramp[:, None]
    alpha[-fade:, :] *= ramp[::-1, None]
    alpha[:, :fade] *= ramp[None, :]
    alpha[:, -fade:] *= ramp[::-1][None, :]
    alpha[alpha < (min_alpha / 255.0)] = 0.0
    out = np.array(crop.convert("RGBA"))
    if tint is not None:
        out[..., 0], out[..., 1], out[..., 2] = tint
    out[..., 3] = (alpha * 255).astype(np.uint8)
    return Image.fromarray(out, "RGBA")


def build_ops(build: Dict[str, Any], sku: Dict[str, Any], logo: Image.Image,
              field_color: Tuple[int, int, int]) -> List[Dict[str, Any]]:
    """All drawing operations in MM space for one SKU sheet."""
    meta = build["meta"]
    fx, fy, fw, fh = meta["panels"]["front"]
    bx, by, bw, bh = meta["panels"]["back"]
    gx, gy, gw, gh = meta["panels"]["gusset"]
    gold = tuple(sku.get("gold", GOLD_A))
    ground = tuple(sku.get("ground", (255, 255, 255)))
    ops: List[Dict[str, Any]] = []

    # panel grounds first (full-coverage print, both sides + gusset)
    ops.append({"kind": "panel_fill", "x0": fx, "y0": fy, "x1": fx + fw, "y1": fy + fh,
                "color": ground})
    ops.append({"kind": "panel_fill", "x0": gx, "y0": gy, "x1": gx + gw, "y1": gy + gh,
                "color": ground})
    ops.append({"kind": "panel_fill", "x0": bx, "y0": by, "x1": bx + bw, "y1": by + bh,
                "color": ground})

    # ── FRONT ──────────────────────────────────────────────────────────────
    r_mm = min(fw * 0.34, fh * 0.17)
    cx, cy = fx + fw / 2, fy + fh * 0.20
    ops.append({"kind": "image", "img": "logo_badge", "cx": cx, "cy": cy,
                "r": r_mm, "field": field_color, "gold": gold})
    ops.append({"kind": "text_centered", "cx": cx, "y": fy + fh * 0.40,
                "text": sku["title"], "font": "PlayfairDisplay.ttf", "axes": [700],
                "size_mm": 8.2, "max_w_mm": fw * 0.86, "color": tuple(sku["title_color"])})
    ops.append({"kind": "text_centered", "cx": cx, "y": fy + fh * 0.455,
                "text": sku.get("subtitle", "MUSHROOM POWDER"), "font": "Inter.ttf",
                "axes": [14, 640], "size_mm": 3.4, "tracking_mm": 1.1,
                "color": tuple(sku["subtitle_color"])})
    if sku.get("motif") is not None:
        ops.append({"kind": "motif", "img_pil": sku["motif"], "cx": cx,
                    "y": fy + fh * 0.585, "w_mm": fw * (sku.get("motif_width_frac", 0.40))})
    ops.append({"kind": "icons", "cx": cx, "y": fy + fh * 0.770,
                "r_mm": 3.4, "gap_mm": 9.5, "ink": gold})
    ops.append({"kind": "text_centered", "cx": cx, "y": fy + fh * 0.92,
                "text": sku["weight"], "font": "Inter.ttf", "axes": [14, 560],
                "size_mm": 3.2, "color": tuple(sku["subtitle_color"])})
    ops.append({"kind": "rule", "y": fy + fh * 0.92, "x0": cx - 26, "x1": cx - 13,
                "color": gold})
    ops.append({"kind": "rule", "y": fy + fh * 0.92, "x0": cx + 13, "x1": cx + 26,
                "color": gold})

    # ── BACK ───────────────────────────────────────────────────────────────
    tx = bx + bw * 0.08
    tw = bw * 0.84
    ops.append({"kind": "text_left", "x": tx, "y": by + bh * 0.05,
                "text": sku.get("back_title", sku["title"]), "font": "PlayfairDisplay.ttf",
                "axes": [700], "size_mm": 6.0, "color": INK})
    for i, line in enumerate(sku.get("description_lines", [])):
        ops.append({"kind": "text_left", "x": tx, "y": by + bh * 0.11 + i * 4.6,
                    "text": line, "font": "Inter.ttf", "axes": [14, 400],
                    "size_mm": 2.7, "color": INK})
    # reserved: Supplement Facts 65x110mm (actual size per the brief) - white
    # block with black rules, clear of the QR/UPC row below it.
    sf_w, sf_h = 65.0, 110.0
    sf_x = bx + bw - sf_w - bw * 0.08
    sf_y = by + bh * 0.21
    ops.append({"kind": "panel_fill", "x0": sf_x, "y0": sf_y, "x1": sf_x + sf_w,
                "y1": sf_y + sf_h, "color": (255, 255, 255)})
    ops.append({"kind": "box", "x0": sf_x, "y0": sf_y, "x1": sf_x + sf_w, "y1": sf_y + sf_h,
                "color": (0, 0, 0), "width_mm": 0.4})
    ops.append({"kind": "text_left", "x": sf_x + 2, "y": sf_y + 5,
                "text": "SUPPLEMENT FACTS", "font": "Inter.ttf", "axes": [14, 700],
                "size_mm": 3.0, "color": (0, 0, 0)})
    ops.append({"kind": "text_left", "x": sf_x + 2, "y": sf_y + 10,
                "text": "(final panel supplied by brand)", "font": "Inter.ttf",
                "axes": [14, 400], "size_mm": 2.2, "color": (90, 90, 90)})
    # reserved: QR + UPC row BELOW the facts block
    qr_x = bx + bw * 0.08
    qr_y = by + bh * 0.80
    ops.append({"kind": "box", "x0": qr_x, "y0": qr_y, "x1": qr_x + 22, "y1": qr_y + 22,
                "color": (0, 0, 0), "width_mm": 0.4})
    ops.append({"kind": "text_left", "x": qr_x + 1, "y": qr_y + 24.5, "text": "QR (reserved)",
                "font": "Inter.ttf", "axes": [14, 400], "size_mm": 2.0, "color": (60, 60, 60)})
    ops.append({"kind": "box", "x0": qr_x + 28, "y0": qr_y + 1, "x1": qr_x + 78, "y1": qr_y + 20,
                "color": (0, 0, 0), "width_mm": 0.4})
    ops.append({"kind": "text_left", "x": qr_x + 28, "y": qr_y + 24.5, "text": "UPC (reserved)",
                "font": "Inter.ttf", "axes": [14, 400], "size_mm": 2.0, "color": (60, 60, 60)})
    back_lines = sku.get("back_lines", [
        "Suggested use: mix one scoop into water or your favourite drink.",
        "Store in a cool, dry place. Keep out of direct sunlight.",
        "Packed in the USA. Distributed by T2 Holdings LLC.",
    ])
    for i, line in enumerate(back_lines):
        ops.append({"kind": "text_left", "x": tx, "y": by + bh * 0.925 + i * 4.2,
                    "text": line, "font": "Inter.ttf", "axes": [14, 400],
                    "size_mm": 2.4, "color": tuple(sku.get("back_ink", INK))})

    # ── GUSSET ─────────────────────────────────────────────────────────────
    ops.append({"kind": "text_centered", "cx": gx + gw / 2, "y": gy + gh / 2,
                "text": sku.get("gusset_text", "MOGRA ORGANICS - HEALTHY & ORGANIC"),
                "font": "Inter.ttf", "axes": [14, 500], "size_mm": 3.0,
                "tracking_mm": 1.2, "color": tuple(sku["subtitle_color"])})
    return ops


# ── renderers ───────────────────────────────────────────────────────────────

def render_png(build: Dict[str, Any], ops: List[Dict[str, Any]], logo: Image.Image,
               field_color, dpi: int = 300) -> Image.Image:
    scale = dpi / MM_PER_IN
    W = int(round(build["width_mm"] * scale))
    H = int(round(build["height_mm"] * scale))
    px = lambda mm: int(round(mm * scale))  # noqa: E731
    img = Image.new("RGB", (W, H), (255, 255, 255))
    d = ImageDraw.Draw(img)

    def font_for(spec, size_mm):
        return _font(spec["font"], max(8, px(size_mm)), spec.get("axes"))

    for op in ops:
        k = op["kind"]
        if k == "image" and op["img"] == "logo_badge":
            r_px = px(op["r"])
            x0, y0 = px(op["cx"]) - r_px - px(1), px(op["cy"]) - r_px - px(1)
            badge = Image.new("RGBA", (2 * r_px + px(2), 2 * r_px + px(2)), (0, 0, 0, 0))
            bd = ImageDraw.Draw(badge)
            bd.ellipse([px(1), px(1), badge.width - px(1), badge.height - px(1)],
                       fill=tuple(op["field"]) + (255,))
            lock_w = int(r_px * 2 * 0.72)
            lock = logo.resize((lock_w, int(lock_w * logo.height / logo.width)), Image.LANCZOS)
            badge.paste(lock, ((badge.width - lock.width) // 2,
                               (badge.height - lock.height) // 2), lock)
            mask = Image.new("L", badge.size, 0)
            ImageDraw.Draw(mask).ellipse([px(1), px(1), badge.width - px(1), badge.height - px(1)],
                                         fill=255)
            badge.putalpha(ImageChops.multiply(badge.split()[3], mask))
            img.paste(badge, (x0, y0), badge)
            d.ellipse([px(op["cx"] - op["r"]), px(op["cy"] - op["r"]),
                       px(op["cx"] + op["r"]), px(op["cy"] + op["r"])],
                      outline=tuple(op["gold"]), width=max(2, px(0.6)))
        elif k == "text_centered":
            f = font_for(op, op["size_mm"])
            _clear_text(d, px(op["cx"]), px(op["y"]), op["text"], f, op["color"],
                        tracking=px(op.get("tracking_mm", 0)))
        elif k == "text_left":
            f = font_for(op, op["size_mm"])
            d.text((px(op["x"]), px(op["y"])), op["text"], font=f, fill=op["color"], anchor="lm")
        elif k == "icons":
            kinds = ("organic_sprout", "non_gmo", "gluten_free", "fruiting_body")
            n = len(kinds)
            for i, kind in enumerate(kinds):
                x = op["cx"] + (i - (n - 1) / 2) * op["gap_mm"]
                draw_cert_icon(d, kind, px(x), px(op["y"]), px(op["r_mm"]),
                               ink=op["ink"], ring=op["ink"], disc=CREAM, width=max(2, px(0.5)))
        elif k == "motif":
            m = op["img_pil"].resize((px(op["w_mm"]), int(px(op["w_mm"]) * op["img_pil"].height / op["img_pil"].width)),
                                     Image.LANCZOS)
            img.paste(m, (int(px(op["cx"]) - m.width / 2), int(px(op["y"]) - m.height / 2)), m)
        elif k == "panel_fill":
            d.rectangle([px(op["x0"]), px(op["y0"]), px(op["x1"]), px(op["y1"])],
                        fill=tuple(op["color"]))
        elif k == "rule":
            d.line([(px(op["x0"]), px(op["y"])), (px(op["x1"]), px(op["y"]))],
                   fill=tuple(op["color"]), width=max(2, px(0.5)))
        elif k == "box":
            d.rectangle([px(op["x0"]), px(op["y0"]), px(op["x1"]), px(op["y1"])],
                        outline=op["color"], width=max(2, px(op.get("width_mm", 0.4))))

    # dieline marks ON TOP (trim/fold/bleed deliberately visible on the art sheet)
    for it in build["layers"]:
        if it["kind"] == "rect":
            d.rectangle([px(it["x"]), px(it["y"]), px(it["x"] + it["w"]), px(it["y"] + it["h"])],
                        outline=(120, 120, 120), width=max(1, px(0.2)))
        elif it["kind"] == "line":
            col = (60, 110, 220) if it["layer"] == "fold" else (120, 120, 120)
            d.line([(px(it["x1"]), px(it["y1"])), (px(it["x2"]), px(it["y2"]))],
                   fill=col, width=max(1, px(0.25)))
    return img


def render_pdf(build: Dict[str, Any], ops: List[Dict[str, Any]], logo: Image.Image,
               logo_badge_r_mm: float, field_color) -> bytes:
    """True PDF with embedded fonts (not outlined - noted as next step)."""
    from reportlab.pdfgen import canvas as _canvas
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    W = build["width_mm"] * dp.MM_PT
    H = build["height_mm"] * dp.MM_PT
    buf = io.BytesIO()
    c = _canvas.Canvas(buf, pagesize=(W, H))
    c.setTitle(build.get("title", "dieline"))
    yp = lambda mm: H - mm * dp.MM_PT  # noqa: E731
    M = dp.MM_PT

    # register fonts once
    for reg, path in (("Playfair", FONTS_DIR / "PlayfairDisplay.ttf"),
                      ("Inter", FONTS_DIR / "Inter.ttf")):
        try:
            pdfmetrics.registerFont(TTFont(reg, str(path)))
        except Exception:
            pass

    for op in ops:
        k = op["kind"]
        if k == "motif":
            m = op["img_pil"]
            w_mm = op["w_mm"]
            h_mm = w_mm * m.height / m.width
            c.drawImage(ImageReader(m), (op["cx"] - w_mm / 2) * M, yp(op["y"] + h_mm / 2),
                        width=w_mm * M, height=h_mm * M, mask="auto")
        elif k == "panel_fill":
            c.setFillColorRGB(*(v / 255 for v in op["color"]))
            c.rect(op["x0"] * M, yp(op["y1"]), (op["x1"] - op["x0"]) * M,
                   (op["y1"] - op["y0"]) * M, stroke=0, fill=1)
        elif k == "image" and op["img"] == "logo_badge":
            rr = op["r"]
            c.setFillColorRGB(*(v / 255 for v in op["field"]))
            c.circle(op["cx"] * M, yp(op["cy"]), rr * M, stroke=0, fill=1)
            lock_w_mm = rr * 2 * 0.72
            lock_h_mm = lock_w_mm * logo.height / logo.width
            c.drawImage(ImageReader(logo), (op["cx"] - lock_w_mm / 2) * M,
                        yp(op["cy"] + lock_h_mm / 2),
                        width=lock_w_mm * M, height=lock_h_mm * M, mask="auto")
            c.setStrokeColorRGB(*(v / 255 for v in op["gold"]))
            c.setLineWidth(0.6 * M)
            c.circle(op["cx"] * M, yp(op["cy"]), rr * M, stroke=1, fill=0)
        elif k == "text_centered":
            fname = "Playfair" if op["font"].startswith("Playfair") else "Inter"
            c.setFont(fname, op["size_mm"] * M)
            c.setFillColorRGB(*(v / 255 for v in op["color"]))
            width = c.stringWidth(op["text"], fname, op["size_mm"] * M)
            c.drawString(op["cx"] * M - width / 2, yp(op["y"]), op["text"])
        elif k == "text_left":
            fname = "Playfair" if op["font"].startswith("Playfair") else "Inter"
            c.setFont(fname, op["size_mm"] * M)
            c.setFillColorRGB(*(v / 255 for v in op["color"]))
            c.drawString(op["x"] * M, yp(op["y"]), op["text"])
        elif k == "box":
            c.setStrokeColorRGB(*(v / 255 for v in op["color"]))
            c.setLineWidth(op.get("width_mm", 0.4) * M)
            c.rect(op["x0"] * M, yp(op["y1"]), (op["x1"] - op["x0"]) * M,
                   (op["y1"] - op["y0"]) * M, stroke=1, fill=0)
        elif k == "rule":
            c.setStrokeColorRGB(*(v / 255 for v in op["color"]))
            c.setLineWidth(0.5 * M)
            c.line(op["x0"] * M, yp(op["y"]), op["x1"] * M, yp(op["y"]))
    # dieline marks on top
    for it in build["layers"]:
        if it["kind"] == "line":
            col = (0.24, 0.43, 0.86) if it["layer"] == "fold" else (0.5, 0.5, 0.5)
            c.setStrokeColorRGB(*col)
            c.setLineWidth(0.25 * M)
            c.line(it["x1"] * M, yp(it["y1"]), it["x2"] * M, yp(it["y2"]))
    c.showPage()
    c.save()
    return buf.getvalue()
