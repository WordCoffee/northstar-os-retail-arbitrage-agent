"""Listing images: a text-safe render, then the marketplace gate.

The listing prompt pack (`social_frames.LISTING_STYLES`) was only a pack. This
module renders it on the local FLUX 3 lane through `text_fidelity`'s text-safe
guard, then applies the matching gate:

  * a main image (`white-bg`) must be lettering-free AND pass the white
    background / 80-92% fill rubric;
  * a secondary style (lifestyle, flat-lay, macro, scale) is graded on the hook
    rubric instead - but diffusion lettering is still a defect on every listing.

A refused candidate is returned with the measured reasons, not written as a
deliverable. No network, no provider call.
"""
from __future__ import annotations

import io
from typing import Any, Callable, Dict, Optional

import numpy as np
from PIL import Image

import social_frames as sf
import text_fidelity as tf


class ListingImageError(RuntimeError):
    """A listing image that could not be produced or passed its gate."""


def _subject_bbox(img: Image.Image, threshold: int = 18) -> Optional[tuple]:
    """Bounding box of the non-background subject, using the corners as paper."""
    arr = np.asarray(img.convert("RGB")).astype(np.int16)
    h, w = arr.shape[:2]
    band = max(4, int(min(h, w) * 0.03))
    corners = np.concatenate([
        arr[:band, :band].reshape(-1, 3), arr[:band, -band:].reshape(-1, 3),
        arr[-band:, :band].reshape(-1, 3), arr[-band:, -band:].reshape(-1, 3)])
    bg = np.median(corners, axis=0)
    dist = np.max(np.abs(arr - bg), axis=2)
    mask = dist > threshold
    mask[:2, :] = mask[-2:, :] = False
    mask[:, :2] = mask[:, -2:] = False
    ys, xs = np.where(mask)
    if xs.size < 64:
        return None
    return int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1


def subject_bbox(img: Image.Image, threshold: int = 18) -> Optional[tuple]:
    """Public name for the subject box.

    A product photographed in a lifestyle scene is still the same product; the
    only way to compare it with a packshot is to compare the subject, not the
    frame. This is the same detector fit_main_image uses, exposed so the review
    and scorecard paths do not import a private symbol.
    """
    return _subject_bbox(img, threshold=threshold)


def fit_main_image(payload: bytes, *, target_fill: float = 0.86,
                   size: tuple = (1024, 1024)) -> bytes:
    """Crop the rendered subject and place it at the marketplace fill target.

    Diffusion does not hit an 80-92% fill band from a prompt: the two live
    attempts measured 93% ('touching frame') and 78% ('too small'). This pass
    crops the subject's own pixels and rescales them on pure white, so the
    measured fill is deterministic. It is a crop/resize of the model's render,
    not a second invention.
    """
    img = Image.open(io.BytesIO(payload)).convert("RGB")
    bbox = _subject_bbox(img)
    if bbox is None:
        return payload
    crop = img.crop(bbox)
    canvas_w, canvas_h = int(size[0]), int(size[1])
    target = max(1.0, float(target_fill) * min(canvas_w, canvas_h))
    scale = target / max(1, crop.width, crop.height)
    nw = max(1, int(round(crop.width * scale)))
    nh = max(1, int(round(crop.height * scale)))
    crop = crop.resize((nw, nh), Image.LANCZOS)
    canvas = Image.new("RGB", (canvas_w, canvas_h), (255, 255, 255))
    canvas.paste(crop, ((canvas_w - nw) // 2, (canvas_h - nh) // 2))
    buf = io.BytesIO()
    canvas.save(buf, format="PNG")
    return buf.getvalue()


def _flux(prompt: str, *, width: int, height: int, tier: str) -> Dict[str, Any]:
    import studio_generation as sg
    return sg.generate_image(prompt, width=width, height=height, tier=tier)


def generate(style: str, brief: str = "", *, render: Optional[Callable[..., Any]] = None,
             width: int = 1024, height: int = 1024, tier: str = "final"
             ) -> Dict[str, Any]:
    """Render one listing style and gate it. Never raises for a failed gate."""
    if style not in sf.LISTING_STYLES:
        raise ValueError(f"listing_style_unknown: {style!r}; "
                         f"known: {sorted(sf.LISTING_STYLES)}")
    row = sf.LISTING_STYLES[style]
    prompt = row["prompt"]
    if str(brief or "").strip():
        prompt = f"{prompt}. {str(brief).strip()}"

    def _render(text: str) -> Dict[str, Any]:
        if render is not None:
            payload = render(text, width=width, height=height, tier=tier)
        else:
            payload = _flux(text, width=width, height=height, tier=tier)
        if isinstance(payload, (bytes, bytearray)):
            return {"bytes": bytes(payload)}
        return payload

    guarded = tf.render_with_text_guard(render_fn=_render, brief=prompt, text_safe=True)
    image_bytes = guarded["out"]["bytes"]
    main_image = style == "white-bg"
    if main_image:
        image_bytes = fit_main_image(image_bytes, size=(width, height))
    gate = sf.listing_gate(image_bytes, main_image=main_image)
    return {
        "ok": bool(gate["ok"]),
        "style": style,
        "main_image": main_image,
        "prompt": prompt,
        "used_brief": guarded.get("used_brief"),
        "text_fidelity": guarded.get("text_fidelity"),
        "bytes": image_bytes,
        "gate": gate,
        "reason": "" if gate["ok"] else gate["reason"],
    }


__all__ = ["generate", "ListingImageError"]
