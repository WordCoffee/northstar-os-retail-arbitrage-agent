"""MOGRA shelf mockups — print-integration engine v2 (studio plates).

The design is PRINTED onto the package photo, not pasted on it:
- silhouette-following mapping (per-row true package width; arcsin wrap on tubes),
- the photo's own lighting baked into the print (shading + folds),
- wrinkle emboss, edge feather, calibrated per-plate silhouette anchors
  (data/mockup_plates.json).

Output: exports/mogra-shelf-mockups-20261018-v3-studio/<design>/{front_shelf.png,back_shelf.png}
Run (from Northstar_backend):  python export_mogra_shelf_mockups.py
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import mockup_engine as me  # noqa: E402

STUDIO = ROOT / "data" / "studio_generated"
DESIGNS = ROOT.parent / "exports" / "mogra-designs-20261018-bold" / "designs"
PACK = ROOT.parent / "exports" / "mogra-shelf-mockups-20261018-v3-studio"

BAG_DESIGNS = ["01_forest_bold", "02_sticker_fun", "03_midnight_luxe",
               "04_kilim_arch", "05_split_duo", "b06_etched_heritage",
               "b07_etched_noir", "b08_foil_monogram", "b09_kraft_plate",
               "b10_botanical_spine", "e01_stone_heritage", "e02_moss_arc",
               "e03_clay_bands", "e04_sand_hero", "e05_bark_editorial",
               "e06_olive_badge", "e07_oat_split", "e08_slate_formal",
               "e09_taupe_watermark", "e10_kelp_luxe", "f01_porcelain_type",
               "f02_cedar_seal", "f03_linen_ledger", "f04_wheat_minimal",
               "f05_pistachio_contour", "f06_porcelain_tile", "f07_rose_wreath",
               "f08_granite_stack", "f09_plum_prescription", "f10_ice_botanical"]
CAN_DESIGNS = ["06_wall_of_type", "07_dome_gold", "08_stamp_roll",
               "09_edge_stripe", "10_concentric"]

PLATES = {"bag": ("plate2_pouch_front", "plate2_pouch_back"),
          "canister": ("plate2_tube_front", "plate2_tube_back")}


def _cli() -> tuple:
    """Optional --only k1,k2  --pack <folder>  --designs <folder>  --scale <n>
    --flat (one folder, no per-design subfolders)."""
    argv = sys.argv[1:]
    only = None
    pack_name = None
    designs_dir = None
    scale = 2.0
    flat = "--flat" in argv
    if "--only" in argv:
        only = {k for k in argv[argv.index("--only") + 1].split(",") if k}
    if "--pack" in argv:
        pack_name = argv[argv.index("--pack") + 1]
    if "--designs" in argv:
        designs_dir = Path(argv[argv.index("--designs") + 1])
    if "--scale" in argv:
        scale = float(argv[argv.index("--scale") + 1])
    return only, pack_name, designs_dir, scale, flat


def main() -> None:
    only, pack_name, designs_dir, scale, flat = _cli()
    pack = (PACK.parent / pack_name) if pack_name else PACK
    pack.mkdir(parents=True, exist_ok=True)
    designs = designs_dir or DESIGNS
    cfg = me.load_plate_config()
    registry = []
    rows_front, rows_back, labels = [], [], []

    keys = [k for k in BAG_DESIGNS + CAN_DESIGNS if (not only or k in only)]
    for key in keys:
        kind = "bag" if key in BAG_DESIGNS else "canister"
        pf_name, pb_name = PLATES[kind]
        d_folder = designs / key
        f_flat, b_flat = designs / f"{key}_front.png", designs / f"{key}_back.png"
        if f_flat.is_file():
            front_art = Image.open(f_flat).convert("RGB")
            back_art = Image.open(b_flat).convert("RGB")
        else:
            front_art = Image.open(d_folder / "front.png").convert("RGB")
            back_art = Image.open(d_folder / "back.png").convert("RGB")
        out = pack / key
        if not flat:
            out.mkdir(parents=True, exist_ok=True)

        plate_f, cfg_f = me.load_plate(STUDIO / f"{pf_name}.png", cfg[pf_name], scale=scale)
        plate_b, cfg_b = me.load_plate(STUDIO / f"{pb_name}.png", cfg[pb_name], scale=scale)
        mf = me.print_package(plate_f, front_art, cfg_f["kind"], cfg_f)
        mb = me.print_package(plate_b, back_art, cfg_b["kind"], cfg_b)

        mf_name = f"{key}_shelf_front.png" if flat else "front_shelf.png"
        mb_name = f"{key}_shelf_back.png" if flat else "back_shelf.png"
        mf.save((pack if flat else out) / mf_name)
        mb.save((pack if flat else out) / mb_name)
        rows_front.append(mf)
        rows_back.append(mb)
        labels.append(key)
        registry.append({"design": key,
                         "front": mf_name if flat else f"{key}/{mf_name}",
                         "back": mb_name if flat else f"{key}/{mb_name}"})
        print("mockup", key, flush=True)

    # contact sheet — 10 fronts, then 10 backs
    TH = 780

    def thumb(im):
        r = TH / im.height
        return im.resize((int(im.width * r), TH), Image.LANCZOS)

    tf = [thumb(i) for i in rows_front]
    tb = [thumb(i) for i in rows_back]
    gap, margin, cap = 36, 60, 150
    row_w = sum(t.width for t in tf) + gap * (len(tf) - 1) + margin * 2
    total_h = TH * 2 + cap * 2 + gap + margin * 2
    sheet = Image.new("RGB", (row_w, total_h), (250, 248, 242))
    d = ImageDraw.Draw(sheet)
    f_cap = ImageFont.truetype(str(ROOT / "assets" / "fonts" / "PlayfairDisplay.ttf"), 54)
    f_lab = ImageFont.truetype(str(ROOT / "assets" / "fonts" / "Inter.ttf"), 26)
    d.text((margin, 26), f"MOGRA ORGANICS — shelf mockups · {len(labels)} designs × front + back",
           fill=(28, 28, 28), font=f_cap)
    x = margin
    for t, lab in zip(tf, labels):
        sheet.paste(t, (x, cap))
        d.text((x + 6, cap - 30), lab, fill=(90, 90, 90), font=f_lab)
        x += t.width + gap
    y2 = cap + TH + cap + gap
    d.text((margin, y2 - 60), "BACK VIEWS (complete regulated labels)", fill=(70, 70, 70), font=f_lab)
    x = margin
    for t in tb:
        sheet.paste(t, (x, y2))
        x += t.width + gap
    sheet = sheet.resize((sheet.width // 2, sheet.height // 2), Image.LANCZOS)
    sheet.save(pack / ("contact_sheet_mockups.png" if flat else "contact_sheet.png"))

    readme = [
        f"# MOGRA ORGANICS — shelf mockups v2 ({len(registry)} designs, front + back)",
        "",
        f"Generated {datetime.now(timezone.utc).isoformat()} by the Northstar creative system.",
        "",
        "Each image = the design PRINTED onto a photoreal studio packshot:",
        "- silhouette-following mapping (per-row true package width; cylindrical",
        "  arcsin wrap on the tubes so the print reaches the visible edges),",
        "- the photo's own lighting baked into the print (cylindrical shading,",
        "  lid shadow, fabric wrinkles), plus wrinkle emboss and edge feathering,",
        "- calibrated per-plate silhouette anchors (data/mockup_plates.json).",
        "",
        "Bags (01–05) on a matte-white doypack plate; canisters (06–10) on a",
        "matte-white paper tube plate with kraft lid.",
        "",
        "Backs are COMPLETE labels (Supplement Facts with values, real UPC-A + QR,",
        "lot/best-by, full fine print). Placeholder values to certify before print",
        "are listed in ../mogra-designs-20261018-bold/BACK_LABEL_REQUIREMENTS.md.",
        "",
        "## Files",
    ]
    for r in registry:
        readme.append(f"- {r['design']}: `{r['front']}` · `{r['back']}`")
    (pack / ("README_mockups.md" if flat else "README.md")).write_text("\n".join(readme), encoding="utf-8")
    print("PACK:", pack, "| designs:", len(registry))


if __name__ == "__main__":
    main()
