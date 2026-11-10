"""Build an A+ page from ONE design, with every module showing a different view.

The defect this fixes (measured 2026-11-06, renders/aplus_live_20261031):
the tile rows repeated the same photograph three and four times with different
captions, which is what made the page read cheap.

A page must be built from a *design* (design_registry), and every module must be
a different crop of that same design - the top/seal, the label, the net weight,
the silhouette - rather than the same file pasted again. Nothing here invents a
new product: the crops come from the design's own plate, so the label and the
product stay consistent across the page by construction.

    # new product -> NEW design (never silently reuses the last plate)
    python tools/aplus_from_design.py --plate renders/.../plate.png \
        --brand "Mogra Organics" --product "Lion's Mane 6 oz"

    # "keep designing the same one" -> SAME design, new version
    python tools/aplus_from_design.py --same --brand "Mogra Organics" \
        --product "Lion's Mane 6 oz" --note "autumn scene"
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "Northstar_backend"))

PALETTE = {"field": "#F4F0E6", "ink": "#1E3A2F", "accent": "#A8894F"}


def _on_field(plate: Path, size: Tuple[int, int], *, pad: float = 0.10) -> Path:
    """Put the product on a brand field at a wide aspect, with its backdrop removed.

    Two defects this fixes, both measured on the 2026-11-06 preview:
    a 1024x1536 portrait poured into 970x600 with `cover` sliced the label; and a
    plain paste carried the studio backdrop with it, so the product sat inside a
    visible grey rectangle on the cream field.
    """
    import numpy as np
    from PIL import Image, ImageFilter

    import listing_render as lr

    w, h = size
    canvas = Image.new("RGB", (w, h), (244, 240, 230))
    with Image.open(plate) as im:
        rgb = im.convert("RGB")
        box = lr.subject_bbox(rgb) or (0, 0, rgb.width, rgb.height)
        product = rgb.crop(box)

    # Background removal by border-colour similarity: the plate's backdrop is
    # near-uniform, so a pixel close to the border median is background. This is
    # deterministic, needs no model, and the result is a soft-edged alpha.
    arr = np.asarray(product).astype(np.int16)
    bh, bw = arr.shape[:2]
    band = max(2, int(min(bh, bw) * 0.03))
    border = np.concatenate([arr[:band, :].reshape(-1, 3), arr[-band:, :].reshape(-1, 3),
                             arr[:, :band].reshape(-1, 3), arr[:, -band:].reshape(-1, 3)])
    bg = np.median(border, axis=0)
    dist = np.max(np.abs(arr - bg), axis=2)
    alpha = np.clip((dist - 8) / 18.0, 0.0, 1.0)
    mask = Image.fromarray((alpha * 255).astype(np.uint8), mode="L")
    mask = mask.filter(ImageFilter.GaussianBlur(1.2))
    product = product.convert("RGBA")
    product.putalpha(mask)

    inner_h = int(h * (1 - 2 * pad))
    inner_w = int(w * (1 - 2 * pad))
    scale = min(inner_h / product.height, inner_w / product.width)
    product = product.resize((max(1, int(product.width * scale)),
                              max(1, int(product.height * scale))), Image.LANCZOS)
    canvas.paste(product, ((w - product.width) // 2, (h - product.height) // 2), product)
    out = plate.parent / f"hero_{w}x{h}.png"
    canvas.save(out)
    return out


def _crops(plate: Path, *, count: int = 4) -> List[Tuple[str, Path]]:
    """Distinct, meaningful views of the same product from one plate.

    Uses the subject box so a crop never lands on empty background: full product,
    the top third (seal, brand mark), the lower third (label, net weight), and a
    centred detail. Deterministic - same plate, same crops - because a design
    must not change shape between runs.
    """
    from PIL import Image

    import listing_render as lr

    with Image.open(plate) as im:
        rgb = im.convert("RGB")
        box = lr.subject_bbox(rgb) or (0, 0, rgb.width, rgb.height)
        x0, y0, x1, y1 = box
        w, h = x1 - x0, y1 - y0
        pad = int(min(w, h) * 0.06)
        out_dir = plate.parent / f"{plate.stem}_views"
        out_dir.mkdir(parents=True, exist_ok=True)

        specs = {
            "full": (x0, y0, x1, y1),
            "top": (x0 - pad, y0 - pad, x1 + pad, y0 + int(h * 0.52)),
            "label": (x0 - pad, y0 + int(h * 0.30), x1 + pad, y0 + int(h * 0.86)),
            "base": (x0 - pad, y0 + int(h * 0.55), x1 + pad, y1 + pad),
            "upper_detail": (x0 + int(w * 0.10), y0 + int(h * 0.06),
                             x0 + int(w * 0.90), y0 + int(h * 0.50)),
            "lower_detail": (x0 + int(w * 0.10), y0 + int(h * 0.50),
                             x0 + int(w * 0.90), y1),
            "zoom": (x0 + int(w * 0.18), y0 + int(h * 0.18),
                     x0 + int(w * 0.82), y0 + int(h * 0.62)),
        }
        made: List[Tuple[str, Path]] = []
        for name, rect in list(specs.items())[:max(1, count)]:
            cx0 = max(0, int(rect[0]))
            cy0 = max(0, int(rect[1]))
            cx1 = min(rgb.width, int(rect[2]))
            cy1 = min(rgb.height, int(rect[3]))
            if cx1 - cx0 < 32 or cy1 - cy0 < 32:
                continue
            target = out_dir / f"{name}.png"
            rgb.crop((cx0, cy0, cx1, cy1)).save(target)
            made.append((name, target))
        return made


def build(*, brand: str, product: str, plate: Optional[Path], same: bool,
          note: str, out_dir: Path) -> Dict[str, Any]:
    import aplus_render as ar
    import design_registry as drg

    reg = drg.DesignRegistry()
    if same:
        design = reg.find_same(brand=brand, product=product)
        if design is None:
            return {"ok": False, "error": "same_design_not_found",
                    "detail": f"no stored design for {brand!r} / {product!r}; "
                              "run once without --same to create it"}
        if plate is not None:
            design = reg.add_version(design["id"], asset=plate, note=note or "new plate")
        plate_path = reg.resolve_asset(design["id"], "plate")
    else:
        design = reg.create(brand=brand, product=product, plate=plate,
                            palette=PALETTE, prompt=product,
                            source="plate" if plate else "prompt")
        plate_path = reg.resolve_asset(design["id"], "plate")

    if not plate_path or not plate_path.is_file():
        return {"ok": False, "error": "design_has_no_plate", "design": design}

    views = _crops(plate_path, count=7)
    if len(views) < 7:
        return {"ok": False, "error": "not_enough_views", "views": [v[0] for v in views]}

    # The header (970x600) and banner (970x300) get a contained composition at
    # their own aspect, so the product is never sliced by a cover-crop.
    hero = _on_field(plate_path, (970, 600))
    banner = _on_field(plate_path, (970, 300))

    modules = [
        {"kind": "header", "image": str(hero),
         "copy": {"headline": product, "sub": brand,
                  "kicker": "Mogra Organics"}},
        {"kind": "three_tiles", "copy": {"tiles": ["Whole fruiting body",
                                                   "Cold-milled, never heated",
                                                   "Third-party tested"]}},
        {"kind": "banner", "image": str(banner),
         "copy": {"headline": "One ingredient. Nothing else.",
                  "sub": "No fillers, no carriers, no sweeteners",
                  "kicker": "The label, read closely"}},
        {"kind": "four_tiles", "copy": {"tiles": ["Vegan", "6 oz",
                                                  "Resealable", "Batch dated"]}},
        {"kind": "comparison", "copy": {
            "headline": "Compare the range",
            "columns": ["This product", "Other"],
            "rows": [{"label": "Organic", "values": ["yes", "yes"]},
                     {"label": "Fruiting body only", "values": ["yes", "no"]},
                     {"label": "Net weight", "values": ["6 oz", "4 oz"]}]}},
        {"kind": "logo", "copy": {"brand": brand}},
    ]
    page = ar.render_page(modules, brand=PALETTE, image=plate_path,
                          tiles=[p for _n, p in views],
                          logo=reg.resolve_asset(design["id"], "logo"),
                          out_dir=out_dir)
    page["design_id"] = design["id"]
    page["design_version"] = design.get("version")
    page["views"] = [name for name, _p in views]
    (out_dir / "design.json").write_text(json.dumps({"design": design, "views": page["views"]},
                                                    indent=2), encoding="utf-8")
    return page


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="A+ page from one stored design.")
    parser.add_argument("--brand", default="Mogra Organics")
    parser.add_argument("--product", default="Lion's Mane 6 oz")
    parser.add_argument("--plate", default="")
    parser.add_argument("--same", action="store_true",
                        help="reuse the stored design instead of minting a new one")
    parser.add_argument("--note", default="")
    parser.add_argument("--out", default="")
    ns = parser.parse_args(argv)

    plate = (ROOT / ns.plate) if ns.plate else None
    if plate is not None and not plate.is_file():
        print(json.dumps({"ok": False, "error": f"plate not found: {ns.plate}"}))
        return 2
    out_dir = Path(ns.out) if ns.out else ROOT / "renders" / "aplus_design"
    out_dir.mkdir(parents=True, exist_ok=True)

    page = build(brand=ns.brand, product=ns.product, plate=plate,
                 same=ns.same, note=ns.note, out_dir=out_dir)
    print(json.dumps({k: page.get(k) for k in
                      ("ok", "design_id", "design_version", "views", "bytes_total",
                       "preview", "error", "problems")}, indent=2))
    return 0 if page.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
