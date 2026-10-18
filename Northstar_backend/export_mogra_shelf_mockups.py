"""MOGRA shelf mockups — wrap all 10 designs onto the photoreal plates.

Output: exports/mogra-shelf-mockups-20261018/<design>/{front_shelf.png,back_shelf.png}
plus a contact sheet and README. Bags: exact 4-point homography onto the pouch
silhouette (shading-blended). Canisters: cylindrical wrap (foreshortening +
cylindrical luminance falloff) onto the tube body.

Run (from Northstar_backend):  python export_mogra_shelf_mockups.py
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from mockup_compositor import warp_cylinder, warp_panel  # noqa: E402

STUDIO = ROOT / "data" / "studio_generated"
DESIGNS = ROOT.parent / "exports" / "mogra-designs-20261017" / "designs"
PACK = ROOT.parent / "exports" / "mogra-shelf-mockups-20261018"

# geometry picked from grid overlays (1024x1024 plates)
QUAD_POUCH_FRONT = [(270, 88), (763, 88), (738, 842), (300, 846)]     # TL TR BR BL
QUAD_POUCH_BACK = [(265, 90), (768, 88), (740, 842), (300, 848)]
RECT_TUBE_FRONT = (317, 268, 700, 848)                                 # x0 y0 x1 y1
RECT_TUBE_BACK = (308, 272, 705, 855)

BAG_DESIGNS = ["01_kraft_classic", "02_ivory_minimal", "03_forest_apothecary",
               "04_split_band", "05_arch_crest"]
CAN_DESIGNS = ["06_kraft_catalogue", "07_roundel_band", "08_vertical_spine",
               "09_bottom_band", "10_ivory_patch"]


def main() -> None:
    PACK.mkdir(parents=True, exist_ok=True)
    plate_pf = Image.open(STUDIO / "plate_pouch_front.png").convert("RGB")
    plate_pb = Image.open(STUDIO / "plate_pouch_back.png").convert("RGB")
    plate_tf = Image.open(STUDIO / "plate_tube_front.png").convert("RGB")
    plate_tb = Image.open(STUDIO / "plate_tube_back.png").convert("RGB")

    registry = []
    rows_front, rows_back, labels = [], [], []

    for key in BAG_DESIGNS + CAN_DESIGNS:
        d_folder = DESIGNS / key
        front_art = Image.open(d_folder / "front.png").convert("RGBA")
        back_art = Image.open(d_folder / "back.png").convert("RGBA")
        out = PACK / key
        out.mkdir(parents=True, exist_ok=True)

        if key in BAG_DESIGNS:
            mf = warp_panel(plate_pf.copy(), front_art, QUAD_POUCH_FRONT, shading=0.45)
            mb = warp_panel(plate_pb.copy(), back_art, QUAD_POUCH_BACK, shading=0.45)
        else:
            mf = warp_cylinder(plate_tf.copy(), front_art, RECT_TUBE_FRONT, shading=0.5)
            mb = warp_cylinder(plate_tb.copy(), back_art, RECT_TUBE_BACK, shading=0.5)

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
    d.text((margin, 26), "MOGRA ORGANICS — shelf mockups · 10 designs × front + back", fill=(28, 28, 28), font=f_cap)
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
        "# MOGRA ORGANICS — shelf mockups (10 designs, front + back)",
        "",
        f"Generated {datetime.now(timezone.utc).isoformat()} by the Northstar creative system.",
        "",
        "Each folder = one design wrapped onto a photoreal product plate:",
        "- Bags (01–05): 130×210 mm art homography-warped onto a kraft doypack on the oak shelf.",
        "- Canisters (06–10): half-wrap art cylindrical-warped onto a Ø73×120 mm kraft tube.",
        "",
        "Backs are COMPLETE labels (Supplement Facts with values, real UPC-A + QR,",
        "lot/best-by, full fine print). Placeholder values to certify before print are",
        "listed in ../mogra-designs-20261017/BACK_LABEL_REQUIREMENTS.md.",
        "",
        "## Files",
    ]
    for r in registry:
        readme.append(f"- {r['design']}: `{r['front']}` · `{r['back']}`")
    (PACK / "README.md").write_text("\n".join(readme), encoding="utf-8")
    print("PACK:", PACK, "| designs:", len(registry))


if __name__ == "__main__":
    main()
