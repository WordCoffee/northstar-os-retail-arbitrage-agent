"""Assemble the ten Galactic variants into one review sheet.

Reads the screenshots the Playwright spec wrote (reports/theme_review) and
pastes them into a labelled 2-column grid. No re-render, no re-capture: this
only lays out what the browser actually produced.

    C:\\Users\\T2Hol\\ComfyUI\\venv\\Scripts\\python.exe tools/galactic_contact_sheet.py
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
SHOTS = ROOT / "reports" / "theme_review"
VARIANTS_JS = ROOT / "northstar-os-ui" / "src" / "shell" / "galacticVariants.js"

ORDER = [
    "event-horizon", "gargantua", "sagittarius", "andromeda", "photon-ring",
    "nebula-bloom", "quasar", "void-architecture", "solar-ash", "observatory",
]

CELL_W = 720
LABEL_H = 62
GAP = 20
COLS = 2


def font(size: int, bold: bool = False):
    for name in (("Inter-Bold.ttf", "Inter-SemiBold.ttf") if bold else ("Inter-Regular.ttf", "Inter-Medium.ttf")):
        for base in (ROOT / "assets" / "fonts", ROOT / "northstar-os-ui" / "src" / "assets" / "fonts"):
            p = base / name
            if p.exists():
                try:
                    return ImageFont.truetype(str(p), size)
                except OSError:
                    pass
    return ImageFont.load_default()


def read_meta() -> dict:
    """Names and intents come from the variant file so the sheet cannot drift."""
    text = VARIANTS_JS.read_text(encoding="utf-8")
    out = {}
    for block in re.finditer(
        r"id: '([^']+)',\s*\n\s*name: '([^']+)',\s*\n\s*intent: '([^']+)'", text
    ):
        out[block.group(1)] = (block.group(2), block.group(3))
    return out


def latest_shot(variant: str) -> Path | None:
    matches = sorted(SHOTS.glob(f"*-{variant}.png"))
    return matches[-1] if matches else None


def main() -> int:
    meta = read_meta()
    cells = []
    for vid in ORDER:
        shot = latest_shot(vid)
        if not shot:
            raise SystemExit(f"missing screenshot for {vid}")
        img = Image.open(shot).convert("RGB")
        ratio = CELL_W / img.width
        img = img.resize((CELL_W, int(img.height * ratio)), Image.LANCZOS)
        cells.append((vid, img))

    cell_h = cells[0][1].height + LABEL_H
    rows = (len(cells) + COLS - 1) // COLS
    sheet_w = COLS * CELL_W + (COLS + 1) * GAP
    sheet_h = rows * cell_h + (rows + 1) * GAP

    sheet = Image.new("RGB", (sheet_w, sheet_h), (6, 8, 14))
    draw = ImageDraw.Draw(sheet)
    f_name = font(21, bold=True)
    f_intent = font(14)

    for i, (vid, img) in enumerate(cells):
        col, row = i % COLS, i // COLS
        x = GAP + col * (CELL_W + GAP)
        y = GAP + row * (cell_h + GAP)
        sheet.paste(img, (x, y))
        name, intent = meta.get(vid, (vid, ""))
        ty = y + img.height + 8
        draw.text((x + 4, ty), f"{i + 1}. {name}", font=f_name, fill=(240, 236, 228))
        short = intent if len(intent) < 74 else intent[:71].rstrip() + "..."
        draw.text((x + 4, ty + 27), short, font=f_intent, fill=(148, 156, 172))

    out = SHOTS / "CONTACT_SHEET.png"
    sheet.save(out, "PNG", optimize=True)
    print(json.dumps({
        "out": str(out),
        "size": f"{sheet.width}x{sheet.height}",
        "variants": [v for v, _ in cells],
        "bytes": out.stat().st_size,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
