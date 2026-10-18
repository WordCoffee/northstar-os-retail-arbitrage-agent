"""Export the MOGRA design set: 10 concepts x (front + back) at 300 dpi.

Run (from Northstar_backend):  python export_mogra_designs.py
Output:  exports/mogra-designs-20261017/
  logo/  mogra_logo_master.png (refined 4x, alpha)  [+ _traced.svg if vtracer present]
  designs/<NN>_<name>/front.png  back.png  [wrap_full.png for canisters]
  contact_sheet.png        all 20 panels at a glance
  BACK_LABEL_REQUIREMENTS.md   what the back label needs + what we await from you
  README.md                design index + palette + limits
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import design_studio_print as dp  # noqa: E402
import dieline_art as da  # noqa: E402
import package_designs as pd  # noqa: E402
from mockup_compositor import prepare_logo  # noqa: E402

STUDIO = ROOT / "data" / "studio_generated"
EXPORTS = ROOT.parent / "exports"
PACK = EXPORTS / "mogra-designs-20261017"
LOGO_PATH = Path(r"C:\Users\T2Hol\Downloads\png")
RAW_CANDIDATES = ["8070727f49a5401eae13a7f6a373ee5b_raw.png"]
MOTIF_BOX = [198, 400, 438, 668]  # lion's mane cluster in the raw render


def refine_logo() -> tuple[Image.Image, tuple]:
    logo, field = prepare_logo(LOGO_PATH, frame_crop=52)
    a = np.array(logo)
    ink = a[..., 3] > 10
    ys, xs = np.where(ink)
    pad = 6
    logo = logo.crop((max(0, int(xs.min()) - pad), max(0, int(ys.min()) - pad),
                      min(logo.width, int(xs.max()) + pad), min(logo.height, int(ys.max()) + pad)))
    big = logo.resize((logo.width * 4, logo.height * 4), Image.LANCZOS)
    rgb = big.convert("RGB").filter(ImageFilter.UnsharpMask(radius=3, percent=90, threshold=2))
    out = Image.merge("RGBA", (*rgb.split(), big.split()[3]))
    return out, field


BACK_REQUIREMENTS = """# MOGRA back-label — regulatory requirements & data we need from you

Our back panels currently carry labelled PLACEHOLDER zones for everything that
must be filled with certified data. To finish the labels for print we need the
following from you (each maps to a visible zone on the sheet):

## Must be provided (legal requirements, US supplements)
1. **Supplement Facts panel** (the white 65x110mm block) — complete values:
   serving size, servings per container, amounts per serving + %DV for every
   Dietary Ingredient (Lion's Mane extract/powder mg, etc.), "Other Ingredients".
2. **Statement of identity** — confirm "Dietary Supplement" vs "Mushroom Powder"
   (affects whether Supplement Facts or Nutrition Facts is required).
3. **Net quantity** — confirm 6 oz (170 g) exact weight on the printed label.
4. **Ingredient list** with allergen statement (e.g. "Produced in a facility that
   also processes tree nuts") if applicable.
5. **Manufacturer / distributor name + street address** (we have
   "T2 Holdings LLC" — need full city/state/zip).
6. **Country of origin** statement ("Product of ___", "Packed in the USA").
7. **FDA disclaimer** (already typeset): "*These statements have not been
   evaluated by the FDA. This product is not intended to diagnose, treat, cure
   or prevent any disease."
8. **Lot number + BEST BY** — printed at fill time; placeholder print zone is on
   the sheet (no data needed now, just confirm your co-packer stamps it).
9. **UPC / GS1 barcode** — your GTIN numbers per SKU (reserved box on sheet).
10. **QR code target** — URL for the QR (reserved box; we generate the code when
    the URL is confirmed).

## Required only if you make the claim
- **USDA Organic** — certifier name + certificate number must appear when the
  organic seal/claims are used (icon row currently shows generic marks).
- **Non-GMO / Gluten-Free / Fruiting Body** — claim substantiation notes.
- **California Prop 65** warning if applicable.
- **Canada / EU / UK** market variants have additional bilingual requirements —
  tell us the target markets.
- Powder safety line ("keep out of reach of children") if required by your
  co-packer / insurer.

## What is already real on the sheets
- Statement block, storage line, suggested use, distributed-by line, reseal
  note, FDA disclaimer, reserved Supplement Facts / QR / UPC / LOT zones,
  3mm bleed + weld/fold/zipper marks (bags) / seam + glue tab (canisters).
"""


def main() -> None:
    PACK.mkdir(parents=True, exist_ok=True)
    (PACK / "logo").mkdir(exist_ok=True)
    (PACK / "designs").mkdir(exist_ok=True)

    logo, field = refine_logo()
    logo.save(PACK / "logo" / "mogra_logo_master.png")
    notes = []
    try:  # optional true vector master (auto-trace; stylised, verify before print)
        import vtracer  # type: ignore
        rgb = Image.new("RGB", logo.size, (255, 255, 255))
        rgb.paste(logo, (0, 0), logo)
        svg = vtracer.convert_pixels_to_svg(
            np.array(rgb), colormode="color", hierarchical="stacked",
            mode="spline", filter_speckle=6)
        (PACK / "logo" / "mogra_logo_master_traced.svg").write_text(svg, encoding="utf-8")
        notes.append("vector auto-trace included (stylised; verify before production)")
    except Exception:
        notes.append("vector auto-trace unavailable (vtracer not installed) - raster master is 4x refined")

    raw = None
    for name in RAW_CANDIDATES:
        p = STUDIO / name
        if p.is_file():
            raw = p
            break
    assert raw, "raw render missing"
    motif = da.extract_ink_motif(raw, MOTIF_BOX)
    (PACK / "logo" / "motif_lionsmane.png")
    motif.save(PACK / "logo" / "motif_lionsmane.png")

    specs = {s["key"]: s for s in pd.design_specs()}
    registry = []
    thumbs_front, thumbs_back = [], []

    for key, spec in specs.items():
        folder = PACK / "designs" / key
        folder.mkdir(parents=True, exist_ok=True)
        if spec["kind"] == "bag":
            front = pd.BAG_FRONTS[key](logo, motif)
            back = pd.render_back(spec, pd.BAG_W, pd.BAG_H)
        else:
            front = pd.CAN_FRONTS[key](logo, motif)
            back = pd.render_back(spec, pd.CAN_HALF, pd.CAN_H)
            wrap = Image.new("RGB", (pd.P(pd.CAN_C + pd.CAN_GLUE), pd.P(pd.CAN_H)), spec["ground"])
            wrap.paste(front, (0, 0))
            wrap.paste(back, (pd.P(pd.CAN_HALF), 0))
            d = ImageDraw.Draw(wrap)
            for x_mm in (pd.CAN_HALF, pd.CAN_C):
                d.line([(pd.P(x_mm), 0), (pd.P(x_mm), pd.P(pd.CAN_H))],
                       fill=(90, 90, 90), width=2)
            wrap.save(folder / "wrap_full.png")
        front.save(folder / "front.png")
        back.save(folder / "back.png")
        thumbs_front.append(front)
        thumbs_back.append(back)
        registry.append({"key": key, "kind": spec["kind"],
                         "front": f"designs/{key}/front.png", "back": f"designs/{key}/back.png",
                         "wrap": f"designs/{key}/wrap_full.png" if spec["kind"] == "canister" else None,
                         "front_mm": [pd.BAG_W, pd.BAG_H] if spec["kind"] == "bag" else [pd.CAN_HALF, pd.CAN_H],
                         })
        print("built", key)

    # contact sheet — all 20 panels
    TH = 760
    def thumb(im):
        r = TH / im.height
        return im.resize((int(im.width * r), TH), Image.LANCZOS)
    tf = [thumb(t) for t in thumbs_front]
    tb = [thumb(t) for t in thumbs_back]
    gap, margin, cap = 40, 60, 120
    row_w = sum(t.width for t in tf) + gap * (len(tf) - 1) + margin * 2
    total_h = TH * 2 + gap + margin * 2 + cap * 2
    sheet = Image.new("RGB", (row_w, total_h), (250, 248, 242))
    d = ImageDraw.Draw(sheet)
    f_cap = ImageFont.truetype(str(ROOT / "assets" / "fonts" / "PlayfairDisplay.ttf"), 52)
    f_sub = ImageFont.truetype(str(ROOT / "assets" / "fonts" / "Inter.ttf"), 30)
    d.text((margin, 30), "MOGRA ORGANICS - Organic Lion's Mane - 10 concepts / 20 views", fill=(28, 28, 28), font=f_cap)
    x = margin
    for t in tf:
        sheet.paste(t, (x, margin + cap))
        x += t.width + gap
    x = margin
    y2 = margin + cap + TH + cap
    d.text((margin, y2 - 60), "BACK PANELS (regulatory layout - placeholder zones labelled)", fill=(70, 70, 70), font=f_sub)
    for t in tb:
        sheet.paste(t, (x, y2))
        x += t.width + gap
    sheet = sheet.resize((sheet.width // 2, sheet.height // 2), Image.LANCZOS)
    sheet.save(PACK / "contact_sheet.png")

    (PACK / "BACK_LABEL_REQUIREMENTS.md").write_text(BACK_REQUIREMENTS, encoding="utf-8")
    manifest = {
        "pack": "MOGRA ORGANICS - 10 package concepts (5 bags + 5 canisters), front + back each",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "logo": "logo/mogra_logo_master.png (refined 4x from supplied artwork)",
        "notes": notes,
        "designs": registry,
        "regulatory": "BACK_LABEL_REQUIREMENTS.md - placeholder zones await certified data",
    }
    (PACK / "README.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    md = ["# MOGRA ORGANICS - 10 design concepts (front + back each)", "",
          f"Generated {manifest['generated_at']} by the Northstar creative system.", ""]
    if notes:
        md += [f"- {n}" for n in notes] + [""]
    md += ["## Designs", ""]
    for r in registry:
        md.append(f"- **{r['key']}** ({r['kind']}): `{r['front']}` + `{r['back']}`"
                  + (f" + `{r['wrap']}`" if r.get("wrap") else ""))
    md += ["", "## Palette", "- kraft #D5A77A - ivory #F5EEE2 - forest #253628 - cream #D0C5AC - olive #9DBA8B - sage #9FA9A4 - black #171717",
           "", "See BACK_LABEL_REQUIREMENTS.md for what we need from you to finish the labels."]
    (PACK / "README.md").write_text("\n".join(md), encoding="utf-8")

    print("PACK:", PACK)
    print("designs:", len(registry), "| files:", sum(1 for f in PACK.rglob('*') if f.is_file()))


if __name__ == "__main__":
    main()
