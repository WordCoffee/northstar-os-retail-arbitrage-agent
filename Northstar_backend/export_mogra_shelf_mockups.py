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
               "04_kilim_arch", "05_split_duo"]
CAN_DESIGNS = ["06_wall_of_type", "07_dome_gold", "08_stamp_roll",
               "09_edge_stripe", "10_concentric"]

PLATES = {"bag": ("plate2_pouch_front", "plate2_pouch_back"),
          "canister": ("plate2_tube_front", "plate2_tube_back")}


def main() -> None:
    PACK.mkdir(parents=True, exist_ok=True)
    cfg = me.load_plate_config()
    registry = []
    rows_front, rows_back, labels = [], [], []

    for key in BAG_DESIGNS + CAN_DESIGNS:
        kind = "bag" if key in BAG_DESIGNS else "canister"
        pf_name, pb_name = PLATES[kind]
        d_folder = DESIGNS / key
        front_art = Image.open(d_folder / "front.png").convert("RGB")
        back_art = Image.open(d_folder / "back.png").convert("RGB")
        out = PACK / key
        out.mkdir(parents=True, exist_ok=True)

        plate_f = Image.open(STUDIO / f"{pf_name}.png").convert("RGB")
        plate_b = Image.open(STUDIO / f"{pb_name}.png").convert("RGB")
        mf = me.print_package(plate_f, front_art, cfg[pf_name]["kind"], cfg[pf_name])
        mb = me.print_package(plate_b, back_art, cfg[pb_name]["kind"], cfg[pb_name])

        mf.save(out / "front_shelf.png")
        mb.save(out / "back_shelf.png")
        rows_front.append(mf)
        rows_back.append(mb)
        labels.append(key)
        registry.append({"design": key, "front": f"{key}/front_shelf.png",
                         "back": f"{key}/back_shelf.png"})
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
    d.text((margin, 26), "MOGRA ORGANICS — shelf mockups · 10 designs × front + back",
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
    sheet.save(PACK / "contact_sheet.png")

    readme = [
        "# MOGRA ORGANICS — shelf mockups v2 (10 designs, front + back)",
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
    (PACK / "README.md").write_text("\n".join(readme), encoding="utf-8")
    print("PACK:", PACK, "| designs:", len(registry))


if __name__ == "__main__":
    main()
