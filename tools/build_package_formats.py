"""Build complete package sets (mockup + panels + dieline) for all four formats.

Usage (from the repository root):

    python tools/build_package_formats.py \
        --plate-root exports/flow_formats_live_verified_20261031 \
        --out exports/packages_20261031

The default demo uses the verified Mogra plates already in the repository. A
JSON spec can replace the copy and dimensions:

    {"brand": "...", "theme": "forest", "title": "...", "dims": {...}}
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "Northstar_backend"))

import package_pipeline as pp  # noqa: E402

FORMATS = ("pouch", "box", "bottle", "tube")
DIMS = {
    "pouch": {"width_mm": 100, "height_mm": 200, "gusset_mm": 40},
    "box": {"width_mm": 80, "depth_mm": 40, "height_mm": 180},
    "bottle": {"diameter": 60, "height": 200, "label_height": 80,
               "label_top_offset": 30},
    "tube": {"diameter": 40, "height": 160},
}
DEMO = {
    "brand": "MOGRA ORGANICS",
    "theme": "forest",
    "title": "Mogra Forest Dusk",
    "subtitle": "Organic Mushroom Powder",
    "weight": "NET WT 6 OZ (170 g)",
    "servings": "34",
    "claims": ["Fruiting body", "Dual extracted", "Lab verified"],
    "icons": ["organic_sprout", "non_gmo", "gluten_free"],
    "ingredients": ["Organic reishi mushroom powder."],
    "suggested_use": "Mix one teaspoon into warm water daily.",
    "warnings": ["Consult a physician if pregnant or nursing."],
    "company": "Northstar OS LLC",
    "address": "123 Forest Lane, Portland, OR 97205",
    "country_of_origin": "USA",
    "lot_code": "LOT 2026-10",
}


def _contact_sheet(paths, out_path):
    """A four-up review sheet; the mockups are already the measured renders."""
    images = []
    for kind, path in paths:
        img = Image.open(path).convert("RGB")
        images.append((kind, img))
    if not images:
        return
    thumb = 520
    margin, gap, caption = 36, 24, 52
    row_w = 2 * thumb + gap + 2 * margin
    row_h = 2 * thumb + gap + 2 * (caption + margin)
    sheet = Image.new("RGB", (row_w, row_h), (245, 242, 235))
    d = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype(str(ROOT / "Northstar_backend" / "assets" / "fonts" / "Inter.ttf"), 28)
    except Exception:
        font = ImageFont.load_default()
    for i, (kind, img) in enumerate(images):
        img = img.copy()
        img.thumbnail((thumb, thumb), Image.LANCZOS)
        x = margin + (i % 2) * (thumb + gap)
        y = margin + (i // 2) * (thumb + gap + caption)
        sheet.paste(img, (x + (thumb - img.width) // 2, y))
        d.text((x, y + thumb + 10), kind.upper(), fill=(28, 46, 38), font=font)
    sheet.save(out_path, format="PNG")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--plate-root", default=str(ROOT / "exports" / "flow_formats_live_verified_20261031"))
    ap.add_argument("--out", default=str(ROOT / "exports" / "packages_20261031"))
    ap.add_argument("--formats", nargs="+", choices=FORMATS, default=list(FORMATS))
    ap.add_argument("--spec", help="optional JSON spec merged over the demo")
    args = ap.parse_args(argv)

    spec_path = Path(args.spec) if args.spec else None
    overrides = json.loads(spec_path.read_text(encoding="utf-8")) if spec_path else {}
    plate_root = Path(args.plate_root)
    out_root = Path(args.out)
    out_root.mkdir(parents=True, exist_ok=True)
    built = []
    failures = []
    for kind in args.formats:
        plate = plate_root / kind / "01_plate.png"
        spec = {**DEMO, **overrides, "format": kind}
        spec["dims"] = {**DIMS[kind], **(overrides.get("dims") or {})}
        out_dir = out_root / kind
        try:
            result = pp.build_package(spec, format=kind, plate_path=plate,
                                      out_dir=out_dir)
            if not result.get("ok"):
                failures.append({"format": kind, "questions": result.get("questions")})
                print(f"{kind}: needs input: {result.get('questions')}")
                continue
            files = pp.save_package(result, out_dir)
            built.append((kind, out_dir / files["mockup"]))
            print(json.dumps({
                "format": kind,
                "ok": True,
                "files": files,
                "mockup_method": result.get("mockup_method"),
                "geom_residual_px": result.get("geom_residual_px"),
                "print_ready": result.get("print_ready"),
                "artwork_dpi": (result.get("artwork") or {}).get("dpi"),
                "mockup_dpi": result.get("mockup_dpi"),
                "quality": (result.get("quality") or {}).get("verdict"),
            }))
        except Exception as exc:  # noqa: BLE001 - report every format, do not hide
            failures.append({"format": kind, "error": f"{type(exc).__name__}: {exc}"})
            print(f"{kind}: FAILED {type(exc).__name__}: {exc}")
    if built:
        _contact_sheet(built, out_root / "contact_sheet.png")
        print(f"contact sheet: {out_root / 'contact_sheet.png'}")
    if failures:
        print("failures:", json.dumps(failures, indent=2))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
