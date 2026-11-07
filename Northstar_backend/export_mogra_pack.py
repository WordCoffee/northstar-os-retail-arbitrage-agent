"""MOGRA IN A BOX — export the complete print pack from the creative system.

Reproducible end-to-end run of the 2026-10-17 brief:
  rich render (raw, preserved)  ->  motif extraction (engraved line art)
  ->  true-scale doypack art sheets (real logo + real fonts + drawn icons)
  ->  layered dieline vectors, presentation sheet, front-view mockup
  ->  exports/<pack>/ with a README manifest.

Everything deterministic except the motif source (model art extracted from the
raw render). Text is composited with licensed fonts (OFL) - never generated.

Run (from Northstar_backend):  python export_mogra_pack.py
"""

from __future__ import annotations

import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import design_studio_print as dp  # noqa: E402
import dieline_art as da  # noqa: E402
from mockup_compositor import prepare_logo  # noqa: E402
from PIL import Image, ImageDraw, ImageFont  # noqa: E402

STUDIO = ROOT / "data" / "studio_generated"
EXPORTS = ROOT.parent / "exports"
PACK = EXPORTS / "mogra-print-pack-20261017"

LOGO_PATH = Path(r"C:\Users\T2Hol\Downloads\png")
RAW_CANDIDATES = ["8070727f49a5401eae13a7f6a373ee5b_raw.png"]
MOCKUP_CANDIDATES = ["mogra_composed_service_v3.png", "mogra_forest_dusk_composed.png"]

CREAM = (245, 238, 226)
KRAFT = (213, 167, 122)
FOREST = (37, 54, 40)
INK = (23, 23, 23)

BRIEF_PALETTE = {
    "black #171717": (23, 23, 23),
    "kraft #D5A77A": (213, 167, 122),
    "olive #9DBA8B": (157, 186, 139),
    "ivory #F5EEE2": (245, 238, 226),
    "sage #9FA9A4": (159, 169, 164),
    "forest green #253628": (37, 54, 40),
    "cream #D0C5AC": (208, 197, 172),
}
NEAREST_PANTONE = {
    "black #171717": "Black 6 C*",
    "kraft #D5A77A": "728 C*",
    "olive #9DBA8B": "7494 C*",
    "ivory #F5EEE2": "9224 C*",
    "sage #9FA9A4": "7538 C*",
    "forest green #253628": "560 C*",
    "cream #D0C5AC": "7535 C*",
}
SKUS = [
    {"code": "SKU1", "stem": "SKU1_lionsmane_130x210_g40", "width": 130.0,
     "title": "ORGANIC LION'S MANE", "weight": "6 oz (170 g)",
     "ground_name": "kraft #D5A77A", "ground": KRAFT,
     "title_color": CREAM, "subtitle_color": CREAM,
     "back_title": "ORGANIC LION'S MANE",
     "description_lines": [
         "Lion's mane mushroom powder - 100% fruiting body,",
         "gently dried and milled for a smooth, earthy cup."],
     "motif_box": [198, 400, 438, 668], "motif_width_frac": 0.44,
     "gusset_text": "MOGRA ORGANICS - HEALTHY & ORGANIC"},
    {"code": "SKU2", "stem": "SKU2_shiitake_150x210_g40", "width": 150.0,
     "title": "ORGANIC SHIITAKE", "weight": "8 oz (227 g)",
     "ground_name": "ivory #F5EEE2", "ground": CREAM,
     "title_color": FOREST, "subtitle_color": FOREST,
     "back_title": "ORGANIC SHIITAKE",
     "description_lines": [
         "Shiitake mushroom powder - 100% fruiting body,",
         "rich umami depth for broths, sauces and blends."],
     "motif_box": [768, 432, 1008, 758], "motif_width_frac": 0.40,
     "gusset_text": "MOGRA ORGANICS - HEALTHY & ORGANIC"},
]


def _find(candidates, what: str) -> Path:
    for name in candidates:
        p = STUDIO / name
        if p.is_file():
            return p
    raise SystemExit(f"missing {what}: looked for {candidates} in {STUDIO}")


def rgb_to_cmyk_naive(rgb):
    r, g, b = [v / 255.0 for v in rgb]
    k = 1 - max(r, g, b)
    if k >= 1:
        return (0, 0, 0, 100)
    c = (1 - r - k) / (1 - k)
    m = (1 - g - k) / (1 - k)
    y = (1 - b - k) / (1 - k)
    return tuple(round(v * 100) for v in (c, m, y, k))


def main() -> None:
    PACK.mkdir(parents=True, exist_ok=True)
    (PACK / "dielines").mkdir(exist_ok=True)
    (PACK / "motifs").mkdir(exist_ok=True)
    (PACK / "mockups").mkdir(exist_ok=True)

    raw = _find(RAW_CANDIDATES, "raw render midway")
    logo, field = prepare_logo(LOGO_PATH, frame_crop=52)
    logo.save(PACK / "logo_used.png")

    manifest = {
        "pack": "MOGRA ORGANICS - print pack",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "brief": "Stand-up zipper pouch, 2 SKUs, production-ready print files (2026-10-17 brief)",
        "files": [],
    }

    sheets = []
    for sku in SKUS:
        motif = da.extract_ink_motif(raw, sku["motif_box"])
        motif.save(PACK / "motifs" / f"{sku['code']}_motif.png")
        build = dp.build_from_template("doypack", {
            "width_mm": sku["width"], "height_mm": 210, "gusset_mm": 40,
            "weld_mm": 6, "top_weld_mm": 8, "zip_offset_mm": 25, "bleed_mm": 3})
        ops = da.build_ops(build, {**sku, "ground": sku["ground"], "motif": motif,
                                   "back_ink": INK, "gold": da.GOLD_A if sku["code"] == "SKU1" else da.GOLD_B},
                           logo, field)
        png = da.render_png(build, ops, logo, field, dpi=300)
        pdf = da.render_pdf(build, ops, logo, None, field)
        png_path = PACK / f"{sku['stem']}_sheet_300dpi.png"
        pdf_path = PACK / f"{sku['stem']}_sheet.pdf"
        png.save(png_path)
        pdf_path.write_bytes(pdf)
        svg = dp.render_svg(build)
        (PACK / "dielines" / f"{sku['stem']}_dieline_layered.svg").write_text(svg, encoding="utf-8")
        (PACK / "dielines" / f"{sku['stem']}_dieline.pdf").write_bytes(dp.render_pdf(build))
        sheets.append(png)
        manifest["files"] += [
            {"file": png_path.name, "what": f"{sku['title']} art sheet, {sku['width']:.0f}x210mm + 40mm gusset, 3mm bleed, 300dpi (5669px tall), true scale"},
            {"file": pdf_path.name, "what": "same sheet as PDF (Playfair/Inter embedded, not outlined)"},
            {"file": f"dielines/{sku['stem']}_dieline_layered.svg", "what": "layered dieline vector (bleed/trim/fold/safe groups, mm)"},
            {"file": f"motifs/{sku['code']}_motif.png", "what": "engraved mushroom motif, RGBA (extracted from the model's raw render)"},
        ]

    # presentation sheet (deliverable 4)
    gap, margin, caption_h = 120, 140, 220
    total_w = sum(s.width for s in sheets) + gap * (len(sheets) - 1) + margin * 2
    total_h = max(s.height for s in sheets) + margin * 2 + caption_h
    pres = Image.new("RGB", (total_w, total_h), (250, 248, 242))
    d = ImageDraw.Draw(pres)
    x = margin
    for s in sheets:
        pres.paste(s, (x, margin + caption_h))
        x += s.width + gap
    try:
        f_cap = ImageFont.truetype(str(ROOT / "assets" / "fonts" / "PlayfairDisplay.ttf"), 72)
        f_sub = ImageFont.truetype(str(ROOT / "assets" / "fonts" / "Inter.ttf"), 34)
    except Exception:
        f_cap = f_sub = None
    d.text((margin, 90), "MOGRA ORGANICS — master layout · 2 SKUs", fill=(30, 30, 30), font=f_cap)
    d.text((margin, 175), "Flat dieline artwork at 100% scale (front / gusset / back), 3 mm bleed, "
                          "real logo, licensed type, drawn cert icons — cohesive kraft × ivory pair",
           fill=(70, 70, 70), font=f_sub)
    pres_small = pres.resize((pres.width // 3, pres.height // 3), Image.LANCZOS)
    pres_small.save(PACK / "presentation_sheet_both_SKUs.png")
    manifest["files"].append(
        {"file": "presentation_sheet_both_SKUs.png",
         "what": "both SKUs side-by-side at true scale (scaled to 1/3 for viewing)"})

    # front-view mockup (deliverable 3, front only - no 3D side/back yet)
    try:
        mockup = _find(MOCKUP_CANDIDATES, "composed mockup")
        Image.open(mockup).save(PACK / "mockups" / "SKU_pair_front_view_mockup.png")
        manifest["files"].append(
            {"file": "mockups/SKU_pair_front_view_mockup.png",
             "what": "photoreal front-view mockup (real logo/type composited on a model-rendered plate)"})
    except SystemExit:
        manifest["notes"] = ["front-view mockup file not found at export time"]

    # palette + printer notes
    manifest["palette"] = {
        name: {"hex": name.split()[-1], "naive_cmyk": list(rgb_to_cmyk_naive(rgb)),
               "nearest_pantone": NEAREST_PANTONE[name] + " (approximate - confirm with printer)"}
        for name, rgb in BRIEF_PALETTE.items()}
    manifest["honest_limits"] = [
        "Type is embedded, NOT outlined (brief asks outlined or licensed fonts - ours are OFL-licensed; outlining is a one-step follow-up).",
        "CMYK/Pantone values are naive conversions / nearest matches - real conversion requires a colour-managed profile profile at the printer.",
        "Mockups: front view only; back/side-profile 3D renders are not built yet (deferred to the 3D lane).",
        "Weld widths, gusset folds and zipper placement are draft marks - confirm with the co-packer.",
        "Motif = model art extracted from the raw render; verify print resolution before plate production (source ~240px wide at sheet scale).",
    ]
    (PACK / "README.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    # human-readable README
    lines = [
        "# MOGRA ORGANICS - print pack",
        "",
        f"Generated {manifest['generated_at']} by the Northstar creative system",
        "(render -> motif extraction -> true-scale art sheets; text composited, never generated).",
        "",
        "## Files",
    ]
    for f in manifest["files"]:
        lines.append(f"- `{f['file']}` - {f['what']}")
    lines += ["", "## Palette (naive CMYK / nearest Pantone - confirm with printer)"]
    for name, info in manifest["palette"].items():
        lines.append(f"- {name}: CMYK {info['naive_cmyk']} ~ {info['nearest_pantone']}")
    lines += ["", "## Honest limits"]
    lines += [f"- {x}" for x in manifest["honest_limits"]]
    (PACK / "README.md").write_text("\n".join(lines), encoding="utf-8")

    print("PACK:", PACK)
    for f in PACK.rglob("*"):
        if f.is_file():
            print(f"  {f.relative_to(PACK)}  {f.stat().st_size:,} bytes")


if __name__ == "__main__":
    main()
