"""Put the seller's *own* product into a generated scene, deterministically.

Why this module exists: every competitor that does product photography preserves
the product. Our conditioning path did not — measured on 2026-11-05, FLUX 3
reference renders scored subject-crop ssim 0.010-0.323 and pHash 26-28 against
the reference photo, i.e. a different pouch. The instruction-edit path that would
fix it (Qwen-Image-Edit-2511, Apache-2.0) is not on disk and cannot be
downloaded now (9.5 GB free, below the 10 GB floor).

So identity is preserved by construction instead: cut the product out of the
real photo (BiRefNet, already in the lane), scale it, place it on a generated
scene, and add a measured contact shadow. The product pixels in the output *are*
the seller's pixels. Nothing about the label, the wordmark or the material is
invented, which also removes the `KERT& SLATE` class of defect for free.

This module is PIL-only and deterministic. It does no GPU work, so it can be
tested and used even when the render lane is paused.

    from product_composite import place_product
    out = place_product(scene_png, cutout_png, scale=0.72, anchor=(0.5, 0.68))
"""
from __future__ import annotations

import io
from typing import Any, Dict, Optional, Tuple

PNG = "PNG"


def _open_rgba(data: bytes):
    from PIL import Image

    im = Image.open(io.BytesIO(data))
    return im.convert("RGBA")


def trim_to_alpha(im, *, threshold: int = 8):
    """Drop the transparent margin so the product's real size drives the scale."""
    alpha = im.getchannel("A")
    mask = alpha.point(lambda v: 255 if v > threshold else 0)
    box = mask.getbbox()
    return im.crop(box) if box else im


def _contact_shadow(product_w: int, product_h: int, *, opacity: int = 96,
                    spread: float = 0.06, factor: float = 1.0):
    """A soft ellipse that sits *under the product's base*.

    Sized relative to the product (1.15x wide, ~0.22x tall) so the blob reads as
    a contact shadow at any scale, and blurred by about 4 percent of its width.
    ``factor`` shrinks the whole footprint when the frame has less slack than the
    nominal shadow needs; it never grows it.
    """
    from PIL import Image, ImageDraw, ImageFilter

    k = max(0.30, min(1.0, float(factor)))
    pad = max(6, int(product_w * spread * k))
    w = max(6, int(product_w * 1.15 * k))
    h = max(6, int(product_h * 0.22 * k))
    canvas = Image.new("L", (w + 2 * pad, h + 2 * pad), 0)
    draw = ImageDraw.Draw(canvas)
    draw.ellipse([pad, pad, pad + w, pad + h], fill=opacity)
    return canvas.filter(ImageFilter.GaussianBlur(radius=max(2, int(w * 0.04))))


def place_product(scene_png: bytes, cutout_png: bytes, *,
                  scale: float = 0.72,
                  anchor: Tuple[float, float] = (0.5, 0.68),
                  shadow: bool = True,
                  shadow_strength: float = 1.0) -> Dict[str, Any]:
    """Composite the product onto the scene. Returns PNG bytes + what it did.

    ``scale`` is the product's height as a fraction of the scene height (clamped
    so a very tall product cannot overflow the width). ``anchor`` is the centre of
    the product's box as a fraction of the scene (0-1). Nothing is cropped: if the
    product would not fit, the scale is reduced and the reduction is reported.

    **The shadow is part of the subject.** It used to sit half its height below the
    product's base with no reservation, so at scale 0.62 with anchor 0.6 it ran past
    the frame edge and was cut off by it. That is a visible defect in every such
    picture (a hard straight edge under the product) and it is what failed the
    white-matte ring check on six held-out prompt-only briefs, measured 2026-11-11:
    border mean 252.1, std 7.19 against a limit of 6.0, all of it in the bottom
    twenty rows. The footprint is now reserved inside the frame margin, shrinking
    the *shadow* first and the product only when the frame genuinely cannot hold
    both.
    """
    from PIL import Image

    scene = _open_rgba(scene_png)
    product = trim_to_alpha(_open_rgba(cutout_png))
    alpha = product.getchannel("A")
    if alpha.getextrema()[1] == 0:
        raise ValueError("the cutout has no visible pixels")
    sw, sh = scene.size
    pw, ph = product.size
    if pw <= 0 or ph <= 0:
        raise ValueError("the cutout has no visible pixels")

    wanted = max(0.05, min(1.0, float(scale)))
    target_h = int(sh * wanted)
    target_w = max(1, int(pw * target_h / ph))
    if target_w > int(sw * 0.95):
        target_w = int(sw * 0.95)
        target_h = max(1, int(ph * target_w / pw))
    product = product.resize((target_w, target_h), Image.LANCZOS)

    ax = max(0.0, min(1.0, float(anchor[0])))
    ay = max(0.0, min(1.0, float(anchor[1])))
    margin = int(min(sw, sh) * 0.02)
    left = int(sw * ax - target_w / 2)
    top = int(sh * ay - target_h / 2)
    # Keep the whole product inside the frame with a small margin: a product
    # sliced by the bottom edge reads as a crop, not a product shot. Measured
    # 2026-11-06: anchor 0.72 put a 716px pouch flush to y=1024.
    left = max(margin, min(sw - target_w - margin, left))
    top = max(margin, min(sh - target_h - margin, top))

    opacity = max(0, min(255, int(96 * shadow_strength)))
    shadow_mask = None
    shadow_below = 0
    if shadow:
        avail_w = sw - 2 * margin
        slack_h = (sh - 2 * margin) - target_h
        factor = 1.0
        for _ in range(3):
            shadow_mask = _contact_shadow(target_w, target_h, opacity=opacity, factor=factor)
            shadow_below = shadow_mask.height - shadow_mask.height // 2
            too_tall = shadow_below > slack_h > 0
            too_wide = shadow_mask.width > avail_w
            if not (too_tall or too_wide):
                break
            if too_tall:
                factor = max(0.30, factor * (slack_h / float(shadow_below)))
            if too_wide:
                factor = max(0.30, factor * (avail_w / float(shadow_mask.width)))
        if target_h + shadow_below > (sh - 2 * margin):
            # Last resort: the frame cannot hold both, so the product gives way and the
            # reduction is reported. The shadow has already shrunk to its floor.
            ratio = max(0.05, ((sh - 2 * margin) - shadow_below) / float(target_h))
            target_h = max(1, int(target_h * ratio))
            target_w = max(1, int(target_w * ratio))
            product = product.resize((target_w, target_h), Image.LANCZOS)
            shadow_mask = _contact_shadow(target_w, target_h, opacity=opacity, factor=0.9)
            shadow_below = shadow_mask.height - shadow_mask.height // 2
        # Horizontal: the shadow is wider than the product, so the product's box is
        # clamped inwards by half that difference; otherwise the blob would be cut by
        # the left or right edge, which is the same defect as the clipped base.
        over = max(0, shadow_mask.width - target_w) // 2
        lo = margin + over
        hi = sw - margin - target_w - over
        left = lo if hi < lo else max(lo, min(hi, left))
        # The product now sits high enough that its shadow ends inside the margin.
        top = max(margin, min(sh - margin - target_h - shadow_below, top))

    out = scene.copy()
    if shadow and shadow_mask is not None:
        dark = Image.new("RGBA", shadow_mask.size, (18, 14, 10, 255))
        dark.putalpha(shadow_mask)
        sx = left + (target_w - shadow_mask.width) // 2
        # Centre the blob on the product's base, so it touches the product.
        sy = top + target_h - shadow_mask.height // 2
        # paste() with a mask clips at the frame edge; alpha_composite() raises
        # "images do not match" when the shadow would extend past it.
        out.paste(dark, (sx, sy), dark)
    out.alpha_composite(product, (left, top))

    buf = io.BytesIO()
    out.convert("RGB").save(buf, format=PNG)
    return {
        "bytes": buf.getvalue(),
        "width": sw, "height": sh,
        "product_box": [left, top, left + target_w, top + target_h],
        "product_scale": round(target_h / float(sh), 4),
        "scale_clamped": abs((target_h / float(sh)) - wanted) > 0.01,
        "shadow": bool(shadow),
        "shadow_below_px": shadow_below,
        "shadow_inside_frame": bool(
            not shadow or top + target_h + shadow_below <= sh - margin + 1),
    }


def identity_check(composite_png: bytes, cutout_png: bytes,
                   product_box: Tuple[int, int, int, int], *,
                   size: int = 256) -> Dict[str, Any]:
    """Prove the product in the composite is the product that went in.

    The composite's product region is compared with the (resized) cutout. A high
    SSIM means the pasted pixels really are the seller's; a low one means the
    composite moved, recoloured or rescaled the product.
    """
    import numpy as np

    out = _open_rgba(composite_png)
    product = trim_to_alpha(_open_rgba(cutout_png))
    region = out.crop(tuple(int(v) for v in product_box))
    # Compare only the pixels the product actually owns. The crop's corners are
    # scene, and including them made a correct composite score 0.93 ("drifted")
    # purely because the background differed.
    mask = product.resize(region.size, 1).getchannel("A")
    region_rgb = region.convert("RGB")
    product_rgb = product.convert("RGB").resize(region.size, 1)

    a = np.asarray(region_rgb, dtype=np.float64) / 255.0
    b = np.asarray(product_rgb, dtype=np.float64) / 255.0
    m = np.asarray(mask, dtype=np.float64) / 255.0 > 0.5
    if m.sum() < 64:
        return {"ssim": None, "region": list(region.size),
                "verdict": "unmeasurable", "note": "no opaque product pixels in the box"}
    a = a[m]
    b = b[m]

    mu_a, mu_b = a.mean(), b.mean()
    va, vb = a.var(), b.var()
    cov = ((a - mu_a) * (b - mu_b)).mean()
    c1, c2 = 0.01 ** 2, 0.03 ** 2
    ssim = ((2 * mu_a * mu_b + c1) * (2 * cov + c2)) / ((mu_a ** 2 + mu_b ** 2 + c1)
                                                       * (va + vb + c2))
    return {"ssim": round(float(ssim), 4),
            "region": list(region.size),
            "masked_pixels": int(m.sum()),
            "verdict": "identity_preserved" if ssim >= 0.95 else "identity_drifted"}
