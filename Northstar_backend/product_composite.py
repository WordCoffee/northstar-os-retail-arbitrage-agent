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


def drop_thin_runs(im, *, floor_frac: float = 0.12, run_frac: float = 0.04,
                   stick_frac: float = 0.04) -> Tuple[Any, int]:
    """Erase thin leading/trailing runs of alpha — a stick, a wire, a layout rule.

    Measured 2026-11-11 on PO-001: the cutout carried a 20 px-wide vertical stick
    from y=520 to y=960, attached to a body 650 px wide, so it survived the
    detached-speck pass and stood in the picture as a line above the pouch. A run
    is erased only when it is **thin** (under ``floor_frac`` of the body's median
    row width) and **at an end** of the silhouette (a bottle's neck is thin but it
    is followed by a body of similar width, and a run shorter than ``run_frac`` of
    the height is left alone).

    ``stick_frac`` closes the second half of the defect, measured on PO-006 the
    same day: that product is a **rotated** box, so its first rows are the top
    corner — 6 px wide, then 11, 16 … climbing through the thin threshold. The
    run cleared ``run_frac`` and 36 rows (588 px) of the box's own corner were
    erased. A stick is not merely under the thin threshold; it is a small
    fraction of the body (PO-001's 20 px stick is 3 % of 650). A perspective
    corner climbs to the threshold itself, so its widest row is ~12 %. The run is
    erased only when its own **widest** row is under ``stick_frac`` too. This is
    strictly more conservative: it can keep product pixels, never erase more.
    """
    import numpy as np

    from PIL import Image

    alpha_img = im.getchannel("A")
    alpha = np.asarray(alpha_img)
    ys, _ = np.nonzero(alpha > 8)
    if ys.size == 0:
        return im, 0
    y0, y1 = int(ys.min()), int(ys.max())
    widths = np.zeros(y1 - y0 + 1, dtype=np.int32)
    for offset, row in enumerate(range(y0, y1 + 1)):
        hits = np.nonzero(alpha[row] > 8)[0]
        if hits.size:
            widths[offset] = int(hits[-1]) + 1 - int(hits[0])
    body = widths[widths > 0]
    if body.size < 8:
        return im, 0
    median = float(np.median(body))
    thin_limit = max(8.0, floor_frac * median)
    stick_limit = max(8.0, stick_frac * median)
    thin = widths < thin_limit
    min_run = max(4, int((y1 - y0) * run_frac))
    runs = []
    start = None
    for index, flag in enumerate(thin):
        if flag and start is None:
            start = index
        elif not flag and start is not None:
            runs.append((start, index - 1))
            start = None
    if start is not None:
        runs.append((start, len(thin) - 1))
    erased = 0
    out = im.copy()
    cleaned = alpha.copy()
    for first, last in runs:
        if last - first + 1 < min_run:
            continue
        leading = first == 0
        trailing = last == len(thin) - 1
        if not (leading or trailing):
            continue                  # an interior narrow band is part of the object
        if int(widths[first:last + 1].max()) > stick_limit:
            continue                  # a corner that widens to the body, not a stick
        cleaned[y0 + first:y0 + last + 1, :] = 0
        erased += last - first + 1
    if not erased:
        return im, 0
    out.putalpha(Image.fromarray(cleaned, "L"))
    out = trim_to_alpha(out)
    return out, erased


def drop_detached_specks(im, *, threshold: int = 8, area_frac: float = 0.05,
                         gap_frac: float = 0.02) -> Tuple[Any, int]:
    """Erase small alpha components that float away from the product.

    Measured 2026-11-11 on the prompt-only contact sheet: a cutout carried a
    vertical stick above the pouch, a white ring beside it and a ghosted second
    tube — detached pieces of the plate that the matte kept. A speck is dropped
    only when it is both **small** (under ``area_frac`` of the largest component)
    and **detached** (no pixel of it lies within ``gap_frac`` of the product's
    height of the main body), so a three-unit bundle (three similar components)
    and a mug's handle (attached) both survive.

    "Detached" is measured on **pixels**, not on bounding boxes. The box test was
    a hole: PO-006's dashed drop-shadow rule lies inside the box's own bounding
    box, so every dash was classified as "touching the body" (dx = dy = 0) while
    the nearest product pixel was 38 px away. Six dashes survived into the
    composite and the strict stray pass measured 4 marks / 2169 px on the page
    (2026-11-11). The tolerance is unchanged — ``gap`` is still 2 % of the body's
    height — it is only applied to the distance that actually means "attached".
    """
    import numpy as np

    from PIL import Image

    alpha_img = im.getchannel("A")
    alpha = np.asarray(alpha_img)
    binary = (alpha > threshold).astype(np.uint8)
    if binary.sum() == 0:
        return im, 0
    try:
        import cv2
    except Exception:  # noqa: BLE001 - without cv2 there is no component pass
        return im, 0
    count, labels, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)
    if count <= 2:
        return im, 0
    order = sorted(range(1, count), key=lambda i: int(stats[i, cv2.CC_STAT_AREA]),
                   reverse=True)
    main = order[0]
    mh = int(stats[main, cv2.CC_STAT_HEIGHT])
    main_area = float(stats[main, cv2.CC_STAT_AREA])
    gap = max(2, int(mh * float(gap_frac)))
    # Everything within `gap` pixels of the main body, measured on pixels.
    main_mask = (labels == main).astype(np.uint8)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * gap + 1, 2 * gap + 1))
    attached = cv2.dilate(main_mask, kernel)
    dropped = 0
    keep = np.ones(int(count), dtype=bool)
    for index in order[1:]:
        area = float(stats[index, cv2.CC_STAT_AREA])
        if area >= area_frac * main_area:
            continue
        own = labels == index
        if int((attached[own] > 0).sum()) > 0:
            continue                     # a pixel of it touches the body: part of the product
        keep[index] = False
        dropped += 1
    if not dropped:
        return im, 0
    out = im.copy()
    alive = keep[labels]
    cleaned = np.where(alive, alpha, 0).astype(np.uint8)
    out.putalpha(Image.fromarray(cleaned, "L"))
    return out, dropped



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
    product, specks = drop_detached_specks(product)
    product, thin_rows = drop_thin_runs(product)
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

    # The placed silhouette, on the canvas: the label is conformed to the pack
    # face and clipped to this, so no label pixel can land on the scene beside
    # the product (measured 2026-11-11: 7 of 12 prompt-only artefacts had a white
    # card floating beyond the pouch).
    silhouette = Image.new("L", scene.size, 0)
    silhouette.paste(product.getchannel("A"), (left, top))
    mask_buf = io.BytesIO()
    silhouette.save(mask_buf, format=PNG)

    buf = io.BytesIO()
    out.convert("RGB").save(buf, format=PNG)
    return {
        "bytes": buf.getvalue(),
        "width": sw, "height": sh,
        "product_box": [left, top, left + target_w, top + target_h],
        "product_mask": mask_buf.getvalue(),
        "dropped_specks": specks,
        "dropped_thin_rows": thin_rows,
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
