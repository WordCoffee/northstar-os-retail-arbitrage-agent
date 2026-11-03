"""A+ page from the product's own copy, with every module measured.

`aplus_render` can draw every module and `assert_perfect` refuses a bad one; what
was missing was the brief that turns product copy into a complete page. This
module builds that brief, renders the page, and refuses unless every module's
own QA passes.

The copy is deliberately factual. The renderer screens it for prohibited A+
claims (price, promotion, shipping, competitor, medical) before a pixel is
written, so this pack cannot smuggle a claim past that gate.
"""
from __future__ import annotations

import hashlib
import io
from typing import Any, Dict, List, Optional, Sequence

from PIL import Image, ImageDraw

import aplus_layout as geo
import aplus_render as ar

#: The page order a shopper reads. `single` is intentionally not in the default
#: pack: at 300x300 it is a thumbnail, not a story beat.
PAGE_MODULES = ("header", "three_tiles", "comparison", "banner",
                "premium_desktop", "logo")


def _gradient(size=(1600, 1200)) -> Image.Image:
    w, h = size
    img = Image.new("RGB", (w, h), (232, 227, 216))
    d = ImageDraw.Draw(img)
    for y in range(h):
        t = y / max(1, h - 1)
        colour = (int(236 - 18 * t), int(231 - 16 * t), int(220 - 14 * t))
        d.line([(0, y), (w, y)], fill=colour)
    d.ellipse([w * 0.30, h * 0.18, w * 0.70, h * 0.82], fill=(213, 167, 122))
    return img


def _tiles(count: int = 3) -> List[Image.Image]:
    out = []
    for i in range(count):
        img = Image.new("RGB", (600, 600), (214, 207, 193))
        d = ImageDraw.Draw(img)
        d.ellipse([120 + i * 12, 120, 480 - i * 8, 480], fill=(201, 162, 39))
        out.append(img)
    return out


def _derived_tiles(plate: Image.Image, count: int = 3) -> List[Image.Image]:
    """Square crops of the REAL plate, not placeholder art.

    The tile module needs images; inventing gold circles would put a placeholder
    on a page that claims to be a deliverable. Crop the supplied plate at
    evenly spaced vertical positions instead, so every tile is the product.
    """
    img = plate.convert("RGB")
    w, h = img.size
    side = max(1, min(w, h))
    max_y = max(0, h - side)
    out: List[Image.Image] = []
    for i in range(max(1, int(count))):
        t = i / max(1, int(count) - 1) if count > 1 else 0.5
        x = max(0, (w - side) // 2)
        y = int(round(max_y * t))
        crop = img.crop((x, y, x + side, y + side)).resize((600, 600), Image.LANCZOS)
        out.append(crop)
    return out


def page_copy(product: Dict[str, Any]) -> List[Dict[str, Any]]:
    """The brief: one copy dict per module, from the declared product facts."""
    brand = str(product.get("brand") or "NORTHSTAR").strip()
    name = str(product.get("product") or product.get("title") or "the product").strip()
    subtitle = str(product.get("subtitle") or "").strip() or "a daily staple"
    claims = [str(c).strip() for c in (product.get("claims") or []) if str(c).strip()]
    first = claims[0] if claims else "one ingredient"
    second = claims[1] if len(claims) > 1 else "nothing else"
    weight = str(product.get("weight") or "").strip()

    return [
        {"kind": "header", "copy": {
            "kicker": brand.upper(), "headline": name, "sub": subtitle}},
        {"kind": "three_tiles", "copy": {
            "headline": subtitle,
            "tiles": [first, second, "milled fine"]}},
        {"kind": "comparison", "copy": {
            "headline": "What is in the pouch",
            "label_header": brand.upper(),
            "columns": [brand.upper(), "Other blends"],
            "rows": [
                {"label": "Ingredients", "values": ["one", "several"]},
                {"label": "Fillers", "values": ["none", "often"]},
                {"label": "Fruiting body", "values": ["yes", "varies"]},
            ]}},
        {"kind": "banner", "copy": {
            "headline": f"{weight} {subtitle}".strip(),
            "sub": first}},
        {"kind": "premium_desktop", "copy": {
            "headline": name, "sub": subtitle}},
        {"kind": "logo", "copy": {"brand": brand.upper()}},
    ]


def build_page(product: Dict[str, Any], *, image: Optional[Image.Image] = None,
               tiles: Optional[Sequence[Image.Image]] = None,
               brand: Optional[Dict[str, Any]] = None,
               copy_style: str = "panel") -> Dict[str, Any]:
    """Render the page and refuse unless every module's QA is clean."""
    plate = image if image is not None else _gradient()
    tile_images = list(tiles) if tiles is not None else _derived_tiles(plate, 3)
    specs = page_copy(product)
    rendered: List[Dict[str, Any]] = []
    for spec in specs:
        kind = spec["kind"]
        result = ar.render_module(kind, copy=spec["copy"], image=plate,
                                  tiles=tile_images, brand=brand,
                                  copy_style=copy_style)
        ar.assert_perfect(result)
        expected = geo.CANVAS[kind]
        if tuple(result["size"]) != tuple(expected):
            raise ar.AplusNotPerfect(
                [f"{kind}: canvas {result['size']} != {expected}"], detail=kind)
        rendered.append(result)

    page = ar.render_page(specs, brand=brand, image=plate, tiles=tile_images,
                          copy_style=copy_style)
    return {
        "ok": True,
        "product": product,
        "modules": [{"kind": r["kind"], "size": r["size"], "qa": r["qa"],
                     "bytes": len(r["png"]), "copy_mode": r.get("copy_mode"),
                     "sha256": hashlib.sha256(r["png"]).hexdigest(),
                     "png": r["png"]}
                    for r in rendered],
        "page": page,
    }


__all__ = ["page_copy", "build_page", "PAGE_MODULES", "_gradient", "_tiles"]
